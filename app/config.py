from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseModel):
    app_name: str = "企业云产品智能支持与工单协同 Agent"
    app_env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", f"sqlite:///{(PROJECT_ROOT / 'data' / 'support_agent.db').as_posix()}"
        )
    )
    llm_provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "mock"))
    hunyuan_api_key: str | None = Field(default_factory=lambda: os.getenv("HUNYUAN_API_KEY") or None)
    hunyuan_base_url: str = Field(
        default_factory=lambda: os.getenv(
            "HUNYUAN_BASE_URL", "https://tokenhub.tencentcloudmaas.com/v1"
        )
    )
    hunyuan_model: str = Field(default_factory=lambda: os.getenv("HUNYUAN_MODEL", "hy3"))
    hunyuan_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("HUNYUAN_TIMEOUT_SECONDS", "30"))
    )
    retriever_backend: str = Field(default_factory=lambda: os.getenv("RETRIEVER_BACKEND", "simple"))
    chroma_path: Path = Field(
        default_factory=lambda: Path(os.getenv("CHROMA_PATH", PROJECT_ROOT / "data" / "chroma"))
    )
    knowledge_path: Path = Field(
        default_factory=lambda: Path(
            os.getenv("KNOWLEDGE_PATH", PROJECT_ROOT / "knowledge" / "documents.json")
        )
    )
    max_input_chars: int = 8_000
    retrieval_top_k: int = 3
    min_retrieval_score: float = 0.12


@lru_cache
def get_settings() -> Settings:
    return Settings()

