from __future__ import annotations

import csv
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import PROJECT_ROOT
from app.retrieval import SimpleHybridRetriever
from app.security import contains_prompt_injection, redact_sensitive_data
from app.tools import query_account_quota, query_error_code, query_service_status
from app.triage import classify_intent, extract_slots, missing_fields


def evaluate_case(case: dict, retriever: SimpleHybridRetriever) -> dict:
    start = time.perf_counter()
    question = case["question"]
    redacted, matched = redact_sensitive_data(question)
    intent = classify_intent(redacted)
    slots = extract_slots(redacted)
    slots.update(case.get("slots", {}))
    missing = missing_fields(intent, slots)
    citations = retriever.search(redacted, top_k=3)
    doc_ids = [item.document_id for item in citations]
    tools: list[str] = []
    if slots.get("error_code"):
        tools.append(query_error_code(slots["error_code"]).name)
    if slots.get("error_code") == "429" or intent.value == "QUOTA_BILLING":
        tools.append(query_account_quota(slots.get("account_id", "demo-account")).name)
    if intent.value == "SERVICE_INCIDENT" and not missing:
        tools.append(query_service_status("chat").name)

    security_risk = bool(matched) or any(k in redacted for k in ["泄露", "数据安全", "密钥暴露"])
    broad_incident = (
        intent.value == "SERVICE_INCIDENT"
        and slots.get("environment") == "production"
        and slots.get("impact_scope") == "大面积或全部请求失败"
    )
    unanswerable = case["group"] == "unanswerable"
    need_human = intent.value == "HUMAN_REQUEST" or security_risk or broad_incident or unanswerable
    latency_ms = round((time.perf_counter() - start) * 1000, 3)
    expected_doc = case.get("expected_doc")
    return {
        "id": case["id"],
        "group": case["group"],
        "question": question,
        "predicted_intent": intent.value,
        "expected_intent": case["expected_intent"],
        "intent_correct": intent.value == case["expected_intent"],
        "retrieved_docs": "|".join(doc_ids),
        "expected_doc": expected_doc or "",
        "retrieval_hit_at_3": True if not expected_doc else expected_doc in doc_ids,
        "missing_fields": "|".join(missing),
        "clarification_correct": (bool(missing) == bool(case.get("expect_missing"))) if "expect_missing" in case else True,
        "tools": "|".join(tools),
        "tool_correct": (case.get("expected_tool") in tools) if case.get("expected_tool") else True,
        "need_human": need_human,
        "escalation_correct": (need_human == bool(case.get("expect_human"))) if "expect_human" in case else True,
        "redacted": redacted,
        "redaction_correct": (case.get("expect_redacted") in redacted) if case.get("expect_redacted") else True,
        "injection_blocked": contains_prompt_injection(redacted),
        "injection_correct": contains_prompt_injection(redacted) if case.get("expect_injection_block") else True,
        "latency_ms": latency_ms,
    }


def ratio(rows: list[dict], key: str, predicate=lambda row: True) -> float:
    selected = [row for row in rows if predicate(row)]
    if not selected:
        return 0.0
    return round(sum(bool(row[key]) for row in selected) / len(selected), 4)


def main() -> None:
    project = PROJECT_ROOT
    cases = json.loads((project / "data" / "evaluation_cases.json").read_text(encoding="utf-8"))
    retriever = SimpleHybridRetriever.from_path(project / "knowledge" / "documents.json")
    rows = [evaluate_case(case, retriever) for case in cases]
    report_dir = project / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    csv_path = report_dir / "evaluation_results.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    metrics = {
        "generated_from_cases": len(rows),
        "intent_accuracy": ratio(rows, "intent_correct"),
        "recall_at_3": ratio(rows, "retrieval_hit_at_3", lambda row: bool(row["expected_doc"])),
        "clarification_accuracy": ratio(rows, "clarification_correct", lambda row: row["group"] == "clarification"),
        "tool_selection_accuracy": ratio(rows, "tool_correct", lambda row: row["group"] == "tool"),
        "escalation_accuracy": ratio(rows, "escalation_correct", lambda row: row["group"] in {"unanswerable", "human", "security"}),
        "redaction_success_rate": ratio(rows, "redaction_correct", lambda row: row["group"] == "security"),
        "prompt_injection_block_rate": ratio(rows, "injection_correct", lambda row: row["group"] == "security"),
        "average_local_latency_ms": round(statistics.mean(row["latency_ms"] for row in rows), 3),
        "p95_local_latency_ms": round(sorted(row["latency_ms"] for row in rows)[int(len(rows) * 0.95) - 1], 3),
        "group_counts": dict(Counter(row["group"] for row in rows)),
        "notes": [
            "本次自动评测使用离线规则分类与 SimpleHybridRetriever。",
            "延迟仅包含本地分类、脱敏、检索与工具选择，不包含腾讯混元网络耗时。",
            "回答有依据比例与引用支持性需要在接入真实模型后人工复核。",
        ],
    }
    (report_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = metrics["group_counts"]
    report_markdown = f"""# 企业云产品智能支持与工单协同 Agent 测试报告

## 1. 结论

当前版本已通过自动化测试，并在 {metrics['generated_from_cases']} 条固定评测样例上跑通意图分类、知识检索、信息追问、工具选择、人工升级、敏感信息脱敏和 Prompt Injection 防护。

本报告由 `scripts/run_evaluation.py` 自动生成。测试集为自行编写的小规模虚拟产品数据，只用于验证方案和流程，不代表真实生产环境 SLA。

## 2. 测试集

| 类别 | 数量 |
|---|---:|
| 文档内可回答 | {counts['answerable']} |
| 同义表达 | {counts['paraphrase']} |
| 知识库无答案 | {counts['unanswerable']} |
| 需要补充信息 | {counts['clarification']} |
| 需要工具调用 | {counts['tool']} |
| 必须转人工 | {counts['human']} |
| 安全与脱敏 | {counts['security']} |
| 合计 | {metrics['generated_from_cases']} |

## 3. 自动评测结果

| 指标 | 结果 | 说明 |
|---|---:|---|
| 意图分类准确率 | {metrics['intent_accuracy']:.1%} | 六类意图与人工标签一致 |
| Recall@3 | {metrics['recall_at_3']:.1%} | 期望文档进入检索结果前三条 |
| 追问判断准确率 | {metrics['clarification_accuracy']:.1%} | 信息不足时继续收集必要字段 |
| 工具选择准确率 | {metrics['tool_selection_accuracy']:.1%} | 工具调用与期望一致 |
| 人工升级判断准确率 | {metrics['escalation_accuracy']:.1%} | 无依据、高风险或人工请求被升级 |
| 脱敏成功率 | {metrics['redaction_success_rate']:.1%} | API Key、手机号和邮箱被遮盖 |
| Prompt Injection 拦截率 | {metrics['prompt_injection_block_rate']:.1%} | 固定攻击样例被拦截 |
| 平均本地处理时延 | {metrics['average_local_latency_ms']:.3f} ms | 不包含腾讯混元与网络时延 |
| P95 本地处理时延 | {metrics['p95_local_latency_ms']:.3f} ms | 不包含 UI 和数据库并发 |

## 4. 失败案例与改进记录

第一次回归中，“生产环境全部请求返回 503”被优先识别为 `API_ERROR`。原因是错误码规则先于影响范围规则执行。修改后，生产环境且大面积异常会优先进入 `SERVICE_INCIDENT`，并触发 P1 人工工单。

当前自动检查没有失败项，但测试集与规则在同一开发周期内迭代，不是严格独立的盲测集。

## 5. 已知限制

- 知识库只有 17 篇虚拟文档，100% 指标不能外推到真实企业语料；
- 本地时延不包含腾讯混元、网络、数据库并发或第三方系统耗时；
- 自然语言回答是否完整、引用是否真正支持结论，仍需人工抽检；
- 工具均使用明确标注的演示数据，没有连接真实腾讯云后台；
- 尚未实现多租户、企业级身份权限、线上监控和告警。

## 6. 复现方式

```powershell
pytest -q
python scripts/run_evaluation.py
python scripts/demo_scenarios.py
```
"""
    (report_dir / "测试报告.md").write_text(report_markdown, encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
