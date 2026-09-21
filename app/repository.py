from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ticket, TicketFeedback, TimelineEvent
from app.schemas import (
    IntentType,
    Priority,
    TicketCreate,
    TicketFeedbackCreate,
    TicketOut,
    TicketStatus,
    TicketStatusUpdate,
    TimelineEventOut,
)


ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.NEW: {TicketStatus.NEED_INFO, TicketStatus.AI_PROCESSING, TicketStatus.HUMAN_PROCESSING},
    TicketStatus.NEED_INFO: {TicketStatus.AI_PROCESSING, TicketStatus.HUMAN_PROCESSING},
    TicketStatus.AI_PROCESSING: {TicketStatus.NEED_INFO, TicketStatus.HUMAN_PROCESSING, TicketStatus.RESOLVED},
    TicketStatus.HUMAN_PROCESSING: {TicketStatus.NEED_INFO, TicketStatus.RESOLVED},
    TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.HUMAN_PROCESSING},
    TicketStatus.CLOSED: set(),
}


class TicketNotFoundError(LookupError):
    pass


class InvalidTransitionError(ValueError):
    pass


def _to_out(ticket: Ticket) -> TicketOut:
    return TicketOut(
        ticket_id=ticket.ticket_id,
        title=ticket.title,
        description=ticket.description,
        problem_type=IntentType(ticket.problem_type),
        priority=Priority(ticket.priority),
        status=TicketStatus(ticket.status),
        error_code=ticket.error_code,
        request_id=ticket.request_id,
        impact_scope=ticket.impact_scope,
        attempted_actions=ticket.attempted_actions,
        recommended_next_step=ticket.recommended_next_step,
        assignee=ticket.assignee,
        solution=ticket.solution,
        session_id=ticket.session_id,
        source=ticket.source,
        failed_attempts=ticket.failed_attempts,
        knowledge_candidate=ticket.knowledge_candidate,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def create_ticket(db: Session, payload: TicketCreate, actor: str = "system") -> TicketOut:
    ticket = Ticket(
        ticket_id=f"TKT-{uuid4().hex[:10].upper()}",
        title=payload.title,
        description=payload.description,
        problem_type=payload.problem_type.value,
        priority=payload.priority.value,
        status=TicketStatus.NEW.value,
        error_code=payload.error_code,
        request_id=payload.request_id,
        impact_scope=payload.impact_scope,
        recommended_next_step=payload.recommended_next_step,
        session_id=payload.session_id,
        source=payload.source,
    )
    ticket.attempted_actions = payload.attempted_actions
    db.add(ticket)
    db.flush()
    db.add(
        TimelineEvent(
            ticket_pk=ticket.id,
            event_type="CREATED",
            actor=actor,
            to_status=TicketStatus.NEW.value,
            note="工单已创建",
        )
    )
    db.commit()
    db.refresh(ticket)
    return _to_out(ticket)


def get_ticket_model(db: Session, ticket_id: str) -> Ticket:
    ticket = db.scalar(select(Ticket).where(Ticket.ticket_id == ticket_id))
    if ticket is None:
        raise TicketNotFoundError(ticket_id)
    return ticket


def get_ticket(db: Session, ticket_id: str) -> TicketOut:
    return _to_out(get_ticket_model(db, ticket_id))


def list_tickets(db: Session, limit: int = 100) -> list[TicketOut]:
    rows = db.scalars(select(Ticket).order_by(Ticket.id.desc()).limit(limit)).all()
    return [_to_out(ticket) for ticket in rows]


def update_ticket_status(db: Session, ticket_id: str, payload: TicketStatusUpdate) -> TicketOut:
    ticket = get_ticket_model(db, ticket_id)
    current = TicketStatus(ticket.status)
    if payload.status not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransitionError(f"不允许从 {current.value} 跳转到 {payload.status.value}")
    if payload.status == TicketStatus.RESOLVED and not (payload.solution or ticket.solution):
        raise InvalidTransitionError("标记为 RESOLVED 前必须填写 solution")
    if payload.status == TicketStatus.HUMAN_PROCESSING and not (payload.assignee or ticket.assignee):
        raise InvalidTransitionError("进入 HUMAN_PROCESSING 前必须指定 assignee")

    previous = ticket.status
    ticket.status = payload.status.value
    if payload.assignee:
        ticket.assignee = payload.assignee
    if payload.solution:
        ticket.solution = payload.solution
    if payload.status == TicketStatus.RESOLVED and ticket.solution:
        ticket.knowledge_candidate = True
    db.add(
        TimelineEvent(
            ticket_pk=ticket.id,
            event_type="STATUS_CHANGED",
            actor=payload.actor,
            from_status=previous,
            to_status=payload.status.value,
            note=payload.note,
        )
    )
    db.commit()
    db.refresh(ticket)
    return _to_out(ticket)


def add_feedback(db: Session, ticket_id: str, payload: TicketFeedbackCreate) -> TicketOut:
    ticket = get_ticket_model(db, ticket_id)
    db.add(
        TicketFeedback(
            ticket_pk=ticket.id,
            solved=payload.solved,
            comment=payload.comment,
            actor=payload.actor,
        )
    )
    if not payload.solved:
        ticket.failed_attempts += 1
    db.add(
        TimelineEvent(
            ticket_pk=ticket.id,
            event_type="FEEDBACK",
            actor=payload.actor,
            note=f"用户反馈：{'已解决' if payload.solved else '未解决'}。{payload.comment}",
        )
    )
    db.commit()
    db.refresh(ticket)
    return _to_out(ticket)


def get_timeline(db: Session, ticket_id: str) -> list[TimelineEventOut]:
    ticket = get_ticket_model(db, ticket_id)
    return [
        TimelineEventOut(
            id=event.id,
            event_type=event.event_type,
            actor=event.actor,
            from_status=event.from_status,
            to_status=event.to_status,
            note=event.note,
            created_at=event.created_at,
        )
        for event in ticket.events
    ]

