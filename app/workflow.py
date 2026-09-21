from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.config import Settings
from app.llm import LLMClient
from app.schemas import ChatRequest, ChatResponse, IntentType, TicketCreate, ToolCallRecord
from app.security import contains_prompt_injection, redact_sensitive_data
from app.tools import create_ticket_tool, query_account_quota, query_error_code, query_service_status
from app.triage import (
    clarification_question,
    classify_intent,
    extract_slots,
    missing_fields,
    priority_for,
)


@dataclass
class SessionState:
    messages: list[str] = field(default_factory=list)
    slots: dict[str, str] = field(default_factory=dict)
    failed_solutions: int = 0


class SupportAgent:
    def __init__(self, settings: Settings, retriever, llm: LLMClient):
        self.settings = settings
        self.retriever = retriever
        self.llm = llm
        self.sessions: dict[str, SessionState] = {}

    def _session(self, session_id: str) -> SessionState:
        return self.sessions.setdefault(session_id, SessionState())

    def _build_ticket(
        self,
        db: Session,
        request: ChatRequest,
        redacted: str,
        intent: IntentType,
        slots: dict[str, str],
        attempted_actions: list[str],
        security_risk: bool,
    ) -> tuple[ToolCallRecord, str]:
        payload = TicketCreate(
            title=f"{intent.value}: {redacted[:80]}",
            description=redacted,
            problem_type=intent,
            priority=priority_for(intent, slots, security_risk),
            error_code=slots.get("error_code"),
            request_id=slots.get("request_id"),
            impact_scope=slots.get("impact_scope"),
            attempted_actions=attempted_actions,
            recommended_next_step="由二线支持核对服务日志、Request ID 与账户配置",
            session_id=request.session_id,
            source="agent",
        )
        return create_ticket_tool(db, payload)

    def handle(self, db: Session, request: ChatRequest) -> ChatResponse:
        if len(request.message) > self.settings.max_input_chars:
            raise ValueError(f"输入长度不能超过 {self.settings.max_input_chars} 字符")
        redacted, matched_sensitive = redact_sensitive_data(request.message)
        prompt_injection = contains_prompt_injection(redacted)
        session = self._session(request.session_id)
        session.messages.append(redacted)
        combined = "\n".join(session.messages[-6:])
        intent = classify_intent(combined)
        session.slots.update(extract_slots(redacted))
        if request.account_id:
            session.slots["account_id"] = request.account_id

        security_risk = bool(matched_sensitive) or any(
            keyword in redacted for keyword in ["泄露", "数据安全", "密钥暴露", "脱库"]
        )
        if prompt_injection:
            return ChatResponse(
                session_id=request.session_id,
                intent=intent,
                answer="检测到试图绕过系统规则的内容。系统不会泄露提示词、密钥或内部配置；如需正常支持，请只描述业务问题。",
                evidence=["安全策略命中 Prompt Injection 规则"],
                confidence=1.0,
                need_human=False,
                redacted_input=redacted,
            )

        missing = missing_fields(intent, session.slots)
        if missing and intent != IntentType.HUMAN_REQUEST:
            return ChatResponse(
                session_id=request.session_id,
                intent=intent,
                answer=clarification_question(missing),
                missing_fields=missing,
                confidence=0.55,
                need_human=False,
                redacted_input=redacted,
            )

        citations = self.retriever.search(redacted, top_k=self.settings.retrieval_top_k)
        citations = [item for item in citations if item.score >= self.settings.min_retrieval_score]
        tool_calls: list[ToolCallRecord] = []
        if session.slots.get("error_code"):
            tool_calls.append(query_error_code(session.slots["error_code"]))
        if session.slots.get("error_code") == "429" or intent == IntentType.QUOTA_BILLING:
            tool_calls.append(query_account_quota(session.slots.get("account_id", "demo-account")))
        if intent == IntentType.SERVICE_INCIDENT:
            tool_calls.append(query_service_status("chat"))

        explicit_human = intent == IntentType.HUMAN_REQUEST
        broad_production_incident = (
            intent == IntentType.SERVICE_INCIDENT
            and session.slots.get("environment") == "production"
            and session.slots.get("impact_scope") == "大面积或全部请求失败"
        )
        need_human = explicit_human or security_risk or broad_production_incident or session.failed_solutions >= 2
        if not citations and not tool_calls:
            need_human = True

        ticket_id: str | None = None
        if need_human:
            attempted = [str(call.result.get("action")) for call in tool_calls if call.result.get("action")]
            ticket_record, ticket_id = self._build_ticket(
                db, request, redacted, intent, session.slots, attempted, security_risk
            )
            tool_calls.append(ticket_record)

        result = self.llm.generate_answer(
            question=redacted,
            intent=intent,
            citations=citations,
            tool_calls=tool_calls,
        )
        if need_human and ticket_id:
            result.text += f"\n\n系统已创建演示工单 {ticket_id}，请由人工支持继续处理。"

        evidence = []
        if matched_sensitive:
            evidence.append(f"已脱敏字段：{', '.join(matched_sensitive)}")
        evidence.extend(f"引用：{citation.title}" for citation in citations)
        evidence.extend(
            f"工具：{call.name}（演示环境）" for call in tool_calls if call.name != "create_ticket"
        )
        confidence = 0.35
        if citations:
            confidence += min(0.35, citations[0].score * 0.35)
        if tool_calls:
            confidence += 0.2
        if need_human:
            confidence = min(confidence, 0.7)
        return ChatResponse(
            session_id=request.session_id,
            intent=intent,
            answer=result.text,
            evidence=evidence,
            citations=citations,
            tool_calls=tool_calls,
            confidence=round(min(confidence, 0.95), 2),
            need_human=need_human,
            ticket_id=ticket_id,
            redacted_input=redacted,
            model_provider=result.provider,
            usage=result.usage,
        )


def create_langgraph(agent: SupportAgent):
    """返回与核心工作流一致的 LangGraph 包装；缺少依赖时仍可使用 SupportAgent。"""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return None

    from typing_extensions import TypedDict

    class GraphState(TypedDict, total=False):
        db: Session
        request: ChatRequest
        response: ChatResponse

    graph = StateGraph(GraphState)
    graph.add_node("support_workflow", lambda state: {"response": agent.handle(state["db"], state["request"])})
    graph.add_edge(START, "support_workflow")
    graph.add_edge("support_workflow", END)
    return graph.compile()

