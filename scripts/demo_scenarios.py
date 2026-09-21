from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.llm import MockLLMClient
from app.retrieval import SimpleHybridRetriever
from app.schemas import ChatRequest
from app.workflow import SupportAgent


def main() -> None:
    settings = get_settings()
    init_db()
    agent = SupportAgent(
        settings,
        SimpleHybridRetriever.from_path(settings.knowledge_path),
        MockLLMClient(),
    )
    scenarios = [
        "API Key 应该放在哪里？",
        "返回 429，部分请求失败，Request ID: req-429-001，account_id: demo-account",
        "生产环境刚刚所有请求 503，联系电话 13812345678",
    ]
    with SessionLocal() as db:
        for index, message in enumerate(scenarios, start=1):
            response = agent.handle(db, ChatRequest(session_id=f"scenario-{uuid.uuid4().hex[:6]}", message=message))
            print(f"\n=== 场景 {index} ===")
            print(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
