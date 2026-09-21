from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class IntentType(StrEnum):
    PRODUCT_CONSULTATION = "PRODUCT_CONSULTATION"
    OPERATION_GUIDE = "OPERATION_GUIDE"
    API_ERROR = "API_ERROR"
    QUOTA_BILLING = "QUOTA_BILLING"
    SERVICE_INCIDENT = "SERVICE_INCIDENT"
    HUMAN_REQUEST = "HUMAN_REQUEST"


class TicketStatus(StrEnum):
    NEW = "NEW"
    NEED_INFO = "NEED_INFO"
    AI_PROCESSING = "AI_PROCESSING"
    HUMAN_PROCESSING = "HUMAN_PROCESSING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Priority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Citation(BaseModel):
    document_id: str
    title: str
    source: str
    excerpt: str
    score: float = Field(ge=0, le=1)


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    environment: str = "demo"


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=3, max_length=100)
    message: str = Field(min_length=1, max_length=8_000)
    account_id: str | None = Field(default=None, max_length=100)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message 不能为空")
        return value


class ChatResponse(BaseModel):
    session_id: str
    intent: IntentType
    answer: str
    evidence: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    need_human: bool = False
    ticket_id: str | None = None
    redacted_input: str
    model_provider: str = "mock"
    usage: dict[str, int] = Field(default_factory=dict)


class TicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=8_000)
    problem_type: IntentType
    priority: Priority = Priority.P3
    error_code: str | None = None
    request_id: str | None = None
    impact_scope: str | None = None
    attempted_actions: list[str] = Field(default_factory=list)
    recommended_next_step: str | None = None
    session_id: str | None = None
    source: str = "manual"


class TicketStatusUpdate(BaseModel):
    status: TicketStatus
    actor: str = Field(default="support-engineer", min_length=2, max_length=100)
    note: str = Field(default="", max_length=2_000)
    assignee: str | None = Field(default=None, max_length=100)
    solution: str | None = Field(default=None, max_length=8_000)


class TicketFeedbackCreate(BaseModel):
    solved: bool
    comment: str = Field(default="", max_length=2_000)
    actor: str = Field(default="user", max_length=100)


class TimelineEventOut(BaseModel):
    id: int
    event_type: str
    actor: str
    from_status: str | None = None
    to_status: str | None = None
    note: str
    created_at: datetime


class TicketOut(BaseModel):
    ticket_id: str
    title: str
    description: str
    problem_type: IntentType
    priority: Priority
    status: TicketStatus
    error_code: str | None = None
    request_id: str | None = None
    impact_scope: str | None = None
    attempted_actions: list[str] = Field(default_factory=list)
    recommended_next_step: str | None = None
    assignee: str | None = None
    solution: str | None = None
    session_id: str | None = None
    source: str
    failed_attempts: int
    knowledge_candidate: bool
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    app: str
    llm_provider: str
    knowledge_documents: int

