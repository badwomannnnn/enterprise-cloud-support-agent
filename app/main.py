from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db, init_db
from app.repository import (
    InvalidTransitionError,
    TicketNotFoundError,
    add_feedback,
    create_ticket,
    get_ticket,
    get_timeline,
    list_tickets,
    update_ticket_status,
)
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    TicketCreate,
    TicketFeedbackCreate,
    TicketOut,
    TicketStatusUpdate,
    TimelineEventOut,
)
from app.services import get_agent, get_agent_graph, get_retriever


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    get_retriever()
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="面向企业云产品咨询、API 故障诊断与人工工单协同的演示系统。所有工具数据均为演示环境。",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        llm_provider=settings.llm_provider,
        knowledge_documents=get_retriever().count(),
    )


@app.post("/api/v1/chat", response_model=ChatResponse, tags=["agent"])
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    try:
        graph = get_agent_graph()
        if graph is not None:
            return graph.invoke({"db": db, "request": payload})["response"]
        return get_agent().handle(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/tickets", response_model=TicketOut, status_code=201, tags=["tickets"])
def create_ticket_endpoint(payload: TicketCreate, db: Session = Depends(get_db)) -> TicketOut:
    return create_ticket(db, payload, actor="api-user")


@app.get("/api/v1/tickets", response_model=list[TicketOut], tags=["tickets"])
def list_tickets_endpoint(
    limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)
) -> list[TicketOut]:
    return list_tickets(db, limit)


@app.get("/api/v1/tickets/{ticket_id}", response_model=TicketOut, tags=["tickets"])
def get_ticket_endpoint(ticket_id: str, db: Session = Depends(get_db)) -> TicketOut:
    try:
        return get_ticket(db, ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="工单不存在") from exc


@app.patch("/api/v1/tickets/{ticket_id}/status", response_model=TicketOut, tags=["tickets"])
def update_ticket_status_endpoint(
    ticket_id: str, payload: TicketStatusUpdate, db: Session = Depends(get_db)
) -> TicketOut:
    try:
        return update_ticket_status(db, ticket_id, payload)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="工单不存在") from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/tickets/{ticket_id}/feedback", response_model=TicketOut, tags=["tickets"])
def add_feedback_endpoint(
    ticket_id: str, payload: TicketFeedbackCreate, db: Session = Depends(get_db)
) -> TicketOut:
    try:
        return add_feedback(db, ticket_id, payload)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="工单不存在") from exc


@app.get(
    "/api/v1/tickets/{ticket_id}/timeline",
    response_model=list[TimelineEventOut],
    tags=["tickets"],
)
def ticket_timeline_endpoint(ticket_id: str, db: Session = Depends(get_db)) -> list[TimelineEventOut]:
    try:
        return get_timeline(db, ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="工单不存在") from exc

