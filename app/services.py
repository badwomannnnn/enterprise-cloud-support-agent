from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.llm import build_llm_client
from app.retrieval import build_retriever
from app.workflow import SupportAgent, create_langgraph


@lru_cache
def get_retriever():
    settings = get_settings()
    return build_retriever(settings.retriever_backend, settings.knowledge_path, settings.chroma_path)


@lru_cache
def get_agent() -> SupportAgent:
    settings = get_settings()
    return SupportAgent(settings, get_retriever(), build_llm_client(settings))


@lru_cache
def get_agent_graph():
    return create_langgraph(get_agent())

