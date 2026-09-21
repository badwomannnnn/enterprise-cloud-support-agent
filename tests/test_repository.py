import pytest

from app.repository import InvalidTransitionError, create_ticket, get_timeline, update_ticket_status
from app.schemas import IntentType, Priority, TicketCreate, TicketStatus, TicketStatusUpdate


def make_ticket(db_session):
    return create_ticket(
        db_session,
        TicketCreate(
            title="生产接口异常",
            description="生产环境所有请求失败",
            problem_type=IntentType.SERVICE_INCIDENT,
            priority=Priority.P1,
        ),
    )


def test_ticket_valid_state_flow(db_session):
    ticket = make_ticket(db_session)
    processing = update_ticket_status(
        db_session,
        ticket.ticket_id,
        TicketStatusUpdate(status=TicketStatus.HUMAN_PROCESSING, assignee="support-l2"),
    )
    resolved = update_ticket_status(
        db_session,
        ticket.ticket_id,
        TicketStatusUpdate(status=TicketStatus.RESOLVED, solution="恢复服务并确认监控正常"),
    )
    closed = update_ticket_status(
        db_session,
        ticket.ticket_id,
        TicketStatusUpdate(status=TicketStatus.CLOSED),
    )
    assert processing.status == TicketStatus.HUMAN_PROCESSING
    assert resolved.knowledge_candidate is True
    assert closed.status == TicketStatus.CLOSED
    assert len(get_timeline(db_session, ticket.ticket_id)) == 4


def test_ticket_rejects_illegal_transition(db_session):
    ticket = make_ticket(db_session)
    with pytest.raises(InvalidTransitionError):
        update_ticket_status(
            db_session,
            ticket.ticket_id,
            TicketStatusUpdate(status=TicketStatus.CLOSED),
        )

