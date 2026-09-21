from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import Settings
from app.schemas import Citation, IntentType, ToolCallRecord


@dataclass
class LLMResult:
    text: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)


class LLMClient(ABC):
    @abstractmethod
    def generate_answer(
        self,
        *,
        question: str,
        intent: IntentType,
        citations: list[Citation],
        tool_calls: list[ToolCallRecord],
    ) -> LLMResult:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    def generate_answer(
        self,
        *,
        question: str,
        intent: IntentType,
        citations: list[Citation],
        tool_calls: list[ToolCallRecord],
    ) -> LLMResult:
        evidence: list[str] = []
        steps: list[str] = []
        for call in tool_calls:
            if call.name == "query_error_code":
                evidence.append(f"错误码说明：{call.result.get('meaning')}")
                steps.append(str(call.result.get("action")))
            elif call.name == "query_account_quota":
                evidence.append(
                    f"演示账户状态：{call.result.get('status')}，QPS {call.result.get('qps_used')}/{call.result.get('qps_limit')}"
                )
                if call.result.get("status") == "rate_limited":
                    steps.append("降低并发并采用指数退避，等待限流窗口恢复")
            elif call.name == "query_service_status":
                evidence.append(f"演示服务状态：{call.result.get('status')}，{call.result.get('message')}")
        if citations:
            evidence.append(f"知识库依据：{citations[0].title}")
            steps.append(citations[0].excerpt)
        if not steps:
            return LLMResult(
                text="当前知识库和演示工具没有足够依据支持确定结论，建议补充完整报错和 Request ID 后转人工处理。",
                provider="mock",
            )
        compact_steps = [step for step in steps if step][:3]
        answer = "诊断依据：" + "；".join(evidence) + "。\n建议步骤：\n" + "\n".join(
            f"{index}. {step}" for index, step in enumerate(compact_steps, start=1)
        )
        answer += "\n以上查询均来自演示环境，请勿视为真实云平台状态。"
        return LLMResult(text=answer, provider="mock")


class HunyuanLLMClient(LLMClient):
    def __init__(self, settings: Settings):
        if not settings.hunyuan_api_key:
            raise ValueError("未配置 HUNYUAN_API_KEY")
        self.api_key = settings.hunyuan_api_key
        self.base_url = settings.hunyuan_base_url.rstrip("/")
        self.model = settings.hunyuan_model
        self.timeout = settings.hunyuan_timeout_seconds

    def generate_answer(
        self,
        *,
        question: str,
        intent: IntentType,
        citations: list[Citation],
        tool_calls: list[ToolCallRecord],
    ) -> LLMResult:
        context = {
            "intent": intent.value,
            "citations": [citation.model_dump() for citation in citations],
            "tool_results": [call.model_dump() for call in tool_calls],
        }
        system = (
            "你是企业云产品技术支持助手。只能依据提供的知识片段和工具结果回答。"
            "若依据不足，明确说无法判断并建议转人工。工具结果全部来自演示环境，必须明确标注。"
            "不要输出或猜测密钥。答案使用中文，先写诊断依据，再写可执行步骤，最后列出引用标题。"
        )
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"用户问题：{question}\n可用依据：{json.dumps(context, ensure_ascii=False)}",
                },
            ],
            "temperature": 0.1,
            "stream": False,
        }
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage") or {}
        return LLMResult(
            text=data["choices"][0]["message"]["content"],
            provider="hunyuan",
            usage={str(key): int(value) for key, value in usage.items() if isinstance(value, int)},
        )


class ResilientLLMClient(LLMClient):
    def __init__(self, primary: LLMClient | None, fallback: LLMClient):
        self.primary = primary
        self.fallback = fallback

    def generate_answer(self, **kwargs: Any) -> LLMResult:
        if self.primary is not None:
            try:
                return self.primary.generate_answer(**kwargs)
            except Exception as exc:
                result = self.fallback.generate_answer(**kwargs)
                result.text += f"\n\n真实模型调用失败，已切换离线模式：{type(exc).__name__}。"
                return result
        return self.fallback.generate_answer(**kwargs)


def build_llm_client(settings: Settings) -> ResilientLLMClient:
    primary: LLMClient | None = None
    if settings.llm_provider.lower() == "hunyuan" and settings.hunyuan_api_key:
        primary = HunyuanLLMClient(settings)
    return ResilientLLMClient(primary=primary, fallback=MockLLMClient())

