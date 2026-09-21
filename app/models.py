from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    problem_type: Mapped[str] = mapped_column(String(40))
    priority: Mapped[str] = mapped_column(String(5), default="P3")
    status: Mapped[str] = mapped_column(String(40), default="NEW")
    error_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    impact_scope: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attempted_actions_json: Mapped[str] = mapped_column(Text, default="[]")
    recommended_next_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    knowledge_candidate: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    events: Mapped[list["TimelineEvent"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", order_by="TimelineEvent.id"
    )
    feedback: Mapped[list["TicketFeedback"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )

    @property
    def attempted_actions(self) -> list[str]:
        try:
            return json.loads(self.attempted_actions_json or "[]")
        except json.JSONDecodeError:
            return []

    @attempted_actions.setter
    def attempted_actions(self, value: list[str]) -> None:
        self.attempted_actions_json = json.dumps(value, ensure_ascii=False)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_pk: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    actor: Mapped[str] = mapped_column(String(100))
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ticket: Mapped[Ticket] = relationship(back_populates="events")


class TicketFeedback(Base):
    __tablename__ = "ticket_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_pk: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    solved: Mapped[bool] = mapped_column(Boolean)
    comment: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(100), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ticket: Mapped[Ticket] = relationship(back_populates="feedback")

