from app.config import PROJECT_ROOT
from app.retrieval import ChromaRetriever, SimpleHybridRetriever


def test_error_code_exact_match_ranks_relevant_document():
    retriever = SimpleHybridRetriever.from_path(PROJECT_ROOT / "knowledge" / "documents.json")
    results = retriever.search("接口返回 429，需要怎么重试", top_k=3)
    assert results
    assert results[0].document_id == "kb-rate-limit-429"


def test_retriever_returns_sources():
    retriever = SimpleHybridRetriever.from_path(PROJECT_ROOT / "knowledge" / "documents.json")
    result = retriever.search("Request ID 有什么作用", top_k=1)[0]
    assert result.source.startswith("docs://")
    assert result.excerpt


def test_chroma_retriever_can_query(tmp_path):
    retriever = ChromaRetriever.from_path(
        PROJECT_ROOT / "knowledge" / "documents.json",
        tmp_path / "chroma",
    )
    results = retriever.search("接口返回 429", top_k=3)
    assert retriever.count() == 17
    assert any(item.document_id == "kb-rate-limit-429" for item in results)
