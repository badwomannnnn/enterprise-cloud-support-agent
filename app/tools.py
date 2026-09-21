from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.repository import create_ticket as persist_ticket
from app.repository import get_ticket
from app.schemas import TicketCreate, ToolCallRecord


ERROR_CODES = {
    "400": {"meaning": "请求参数格式或字段不合法", "action": "校验 JSON、必填字段和字段类型"},
    "401": {"meaning": "鉴权失败", "action": "检查 API Key、请求头和密钥所属环境"},
    "403": {"meaning": "无访问权限", "action": "检查模型开通状态、账号权限和地域"},
    "404": {"meaning": "接口或资源不存在", "action": "核对 Base URL、模型名称和资源 ID"},
    "408": {"meaning": "请求超时", "action": "缩短输入、提高客户端超时并检查网络"},
    "429": {"meaning": "请求频率、并发或 Token 配额超过限制", "action": "降低并发、指数退避并检查账户额度"},
    "500": {"meaning": "服务端内部错误", "action": "保留 Request ID，有限重试后转人工"},
    "502": {"meaning": "上游网关返回异常", "action": "检查服务状态，有限重试后转人工"},
    "503": {"meaning": "服务暂时不可用", "action": "查询服务状态并采用退避重试"},
    "504": {"meaning": "网关等待上游超时", "action": "查询服务状态并检查请求耗时"},
}

SERVICE_STATUS = {
    "chat": {"status": "operational", "message": "对话推理服务运行正常"},
    "embedding": {"status": "operational", "message": "向量服务运行正常"},
    "batch": {"status": "degraded", "message": "批量任务存在排队，实时对话不受影响"},
}

ACCOUNT_QUOTAS = {
    "demo-account": {"qps_limit": 5, "qps_used": 5, "token_balance": 120_000, "status": "rate_limited"},
    "healthy-account": {"qps_limit": 20, "qps_used": 3, "token_balance": 900_000, "status": "normal"},
}


def _record(name: str, arguments: dict[str, Any], result: dict[str, Any]) -> ToolCallRecord:
    return ToolCallRecord(name=name, arguments=arguments, result={**result, "demo": True})


def query_service_status(service_name: str) -> ToolCallRecord:
    normalized = service_name.lower().strip() or "chat"
    result = SERVICE_STATUS.get(normalized, {"status": "unknown", "message": "演示环境没有该服务记录"})
    return _record("query_service_status", {"service_name": normalized}, result)


def query_account_quota(account_id: str) -> ToolCallRecord:
    normalized = account_id or "demo-account"
    result = ACCOUNT_QUOTAS.get(
        normalized,
        {"qps_limit": None, "qps_used": None, "token_balance": None, "status": "unknown"},
    )
    return _record("query_account_quota", {"account_id": normalized}, result)


def query_error_code(error_code: str) -> ToolCallRecord:
    result = ERROR_CODES.get(
        str(error_code),
        {"meaning": "演示错误码库未收录", "action": "保留完整报错和 Request ID 后转人工"},
    )
    return _record("query_error_code", {"error_code": str(error_code)}, result)


def create_ticket_tool(db: Session, payload: TicketCreate) -> tuple[ToolCallRecord, str]:
    ticket = persist_ticket(db, payload, actor="support-agent")
    record = _record(
        "create_ticket",
        {"problem_type": payload.problem_type.value, "priority": payload.priority.value},
        {"ticket_id": ticket.ticket_id, "status": ticket.status.value},
    )
    return record, ticket.ticket_id


def query_ticket_status(db: Session, ticket_id: str) -> ToolCallRecord:
    ticket = get_ticket(db, ticket_id)
    return _record(
        "query_ticket_status",
        {"ticket_id": ticket_id},
        {"status": ticket.status.value, "priority": ticket.priority.value, "assignee": ticket.assignee},
    )


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    function: Callable[..., ToolCallRecord]


TOOL_REGISTRY = {
    "query_service_status": ToolDefinition("query_service_status", "查询模拟服务状态", query_service_status),
    "query_account_quota": ToolDefinition("query_account_quota", "查询模拟账户额度", query_account_quota),
    "query_error_code": ToolDefinition("query_error_code", "查询错误码说明", query_error_code),
}

