from __future__ import annotations

import re

from app.schemas import IntentType, Priority


def classify_intent(text: str) -> IntentType:
    lowered = text.lower()
    if any(k in lowered for k in ["人工", "客服", "转人", "真人", "human"]):
        return IntentType.HUMAN_REQUEST
    broad_failure = any(k in lowered for k in ["大面积", "全部失败", "所有请求", "全部请求"])
    production_or_outage = any(k in lowered for k in ["生产", "线上", "宕机", "服务不可用", "服务异常"])
    server_error = bool(re.search(r"\b(?:500|502|503|504)\b", lowered))
    environment_mentioned = any(k in lowered for k in ["生产环境", "测试环境", "开发环境"])
    has_request_id = any(k in lowered for k in ["request id", "request_id"])
    if any(k in lowered for k in ["大面积", "全部失败", "生产故障", "宕机", "服务不可用", "服务异常"]) or (
        broad_failure and (production_or_outage or server_error)
    ) or (
        server_error and environment_mentioned and not has_request_id
    ):
        return IntentType.SERVICE_INCIDENT
    if re.search(r"\b429\b", lowered) or any(
        k in lowered for k in ["计费", "账单", "费用", "余额", "额度", "qps", "tpm", "限流", "成本", "涨价"]
    ):
        return IntentType.QUOTA_BILLING
    if re.search(r"\b(?:400|401|403|404|408|409|429|500|502|503|504)\b", lowered) or any(
        k in lowered
        for k in [
            "报错",
            "错误码",
            "sdk",
            "接口失败",
            "调用失败",
            "接口不能用",
            "验证失败",
            "调用太快",
            "密钥泄露",
        ]
    ):
        return IntentType.API_ERROR
    if any(k in lowered for k in ["如何", "怎么", "步骤", "配置", "接入", "开通", "创建"]):
        return IntentType.OPERATION_GUIDE
    return IntentType.PRODUCT_CONSULTATION


def extract_slots(text: str) -> dict[str, str]:
    slots: dict[str, str] = {}
    error = re.search(r"(?<!\d)(400|401|403|404|408|409|429|500|502|503|504)(?!\d)", text)
    if error:
        slots["error_code"] = error.group(1)
    request_id = re.search(r"(?i)(?:request[_ -]?id)\s*[:=：]?\s*([A-Za-z0-9_-]{5,})", text)
    if request_id:
        slots["request_id"] = request_id.group(1)
    account = re.search(r"(?i)(?:account[_ -]?id|账户)\s*[:=：]?\s*([A-Za-z0-9_-]{3,})", text)
    if account:
        slots["account_id"] = account.group(1)
    model = re.search(r"(?i)(?:model|模型)\s*[:=：]?\s*([A-Za-z0-9_.-]{2,})", text)
    if model:
        slots["model"] = model.group(1)
    endpoint = re.search(r"(?i)(https?://[^\s]+|/v\d+/[A-Za-z0-9_./-]+)", text)
    if endpoint:
        slots["endpoint"] = endpoint.group(1)
    if any(k in text for k in ["生产", "线上"]):
        slots["environment"] = "production"
    elif any(k in text for k in ["测试", "开发环境"]):
        slots["environment"] = "test"
    if any(k in text for k in ["全部", "大面积", "所有请求"]):
        slots["impact_scope"] = "大面积或全部请求失败"
    elif any(k in text for k in ["部分", "偶发", "少量"]):
        slots["impact_scope"] = "部分请求失败"
    elif "单个" in text:
        slots["impact_scope"] = "单个请求失败"
    time_match = re.search(r"(?:今天|昨天|刚刚|\d{1,2}[:：]\d{2}|\d{4}[-/]\d{1,2}[-/]\d{1,2})", text)
    if time_match:
        slots["occurred_at"] = time_match.group(0)
    return slots


def missing_fields(intent: IntentType, slots: dict[str, str]) -> list[str]:
    if intent == IntentType.API_ERROR:
        required = ["error_code", "impact_scope"]
    elif intent == IntentType.SERVICE_INCIDENT:
        required = ["environment", "impact_scope", "occurred_at"]
    else:
        required = []
    return [field for field in required if not slots.get(field)]


def clarification_question(fields: list[str]) -> str:
    labels = {
        "error_code": "完整错误码或报错原文",
        "impact_scope": "影响范围（单个、部分还是全部请求）",
        "environment": "发生在测试环境还是生产环境",
        "occurred_at": "首次发生时间",
        "request_id": "Request ID",
        "model": "接口或模型名称",
    }
    details = "、".join(labels.get(field, field) for field in fields)
    return f"为了避免直接猜测原因，请补充：{details}。如果有 Request ID、接口地址和已经尝试的操作，也请一并提供。"


def priority_for(intent: IntentType, slots: dict[str, str], security_risk: bool = False) -> Priority:
    if security_risk or (
        intent == IntentType.SERVICE_INCIDENT
        and slots.get("environment") == "production"
        and slots.get("impact_scope") == "大面积或全部请求失败"
    ):
        return Priority.P1
    if intent in {IntentType.API_ERROR, IntentType.SERVICE_INCIDENT, IntentType.QUOTA_BILLING}:
        return Priority.P2
    return Priority.P3
