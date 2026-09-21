from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Base


def test_health_chat_and_ticket_api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine)

    def override_db():
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            health = client.get("/health")
            assert health.status_code == 200
            assert health.json()["knowledge_documents"] == 17

            chat = client.post(
                "/api/v1/chat",
                json={
                    "session_id": "api-test-429",
                    "message": "返回 429，部分请求失败，Request ID: req-api-test",
                    "account_id": "demo-account",
                },
            )
            assert chat.status_code == 200
            body = chat.json()
            assert body["intent"] == "QUOTA_BILLING"
            assert {item["name"] for item in body["tool_calls"]} == {
                "query_error_code",
                "query_account_quota",
            }

            created = client.post(
                "/api/v1/tickets",
                json={
                    "title": "API smoke test",
                    "description": "用于验证工单接口和状态机",
                    "problem_type": "API_ERROR",
                    "priority": "P2",
                },
            )
            assert created.status_code == 201
            ticket_id = created.json()["ticket_id"]

            invalid = client.patch(
                f"/api/v1/tickets/{ticket_id}/status",
                json={"status": "CLOSED", "actor": "tester"},
            )
            assert invalid.status_code == 409

            timeline = client.get(f"/api/v1/tickets/{ticket_id}/timeline")
            assert timeline.status_code == 200
            assert timeline.json()[0]["event_type"] == "CREATED"
    finally:
        app.dependency_overrides.clear()
