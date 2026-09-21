from app.config import Settings, PROJECT_ROOT
from app.llm import MockLLMClient
from app.retrieval import SimpleHybridRetriever
from app.schemas import ChatRequest, IntentType
from app.workflow import SupportAgent


def make_agent():
    settings = Settings(knowledge_path=PROJECT_ROOT / "knowledge" / "documents.json")
    return SupportAgent(settings, SimpleHybridRetriever.from_path(settings.knowledge_path), MockLLMClient())


def test_vague_api_error_requests_information(db_session):
    response = make_agent().handle(db_session, ChatRequest(session_id="abc", message="接口调用失败了"))
    assert response.intent == IntentType.API_ERROR
    assert set(response.missing_fields) == {"error_code", "impact_scope"}
    assert response.ticket_id is None


def test_429_calls_tools_and_returns_citation(db_session):
    response = make_agent().handle(
        db_session,
        ChatRequest(
            session_id="abc",
            message="返回 429，部分请求失败，Request ID: req-429-1",
            account_id="demo-account",
        ),
    )
    names = {call.name for call in response.tool_calls}
    assert {"query_error_code", "query_account_quota"}.issubset(names)
    assert response.citations
    assert response.need_human is False


def test_production_incident_creates_p1_ticket(db_session):
    response = make_agent().handle(
        db_session,
        ChatRequest(session_id="incident", message="生产环境刚刚所有请求都返回 503"),
    )
    assert response.need_human is True
    assert response.ticket_id
    assert "138" not in response.redacted_input


def test_sensitive_data_is_redacted_and_escalated(db_session):
    response = make_agent().handle(
        db_session,
        ChatRequest(session_id="secret", message="key=sk-ABCDEFG123456，返回 401，单个请求失败"),
    )
    assert "ABCDEFG" not in response.redacted_input
    assert response.need_human is True

