from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.schemas import Citation


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    title: str
    content: str
    source: str
    product: str
    category: str
    error_codes: tuple[str, ...] = ()


def load_documents(path: Path) -> list[KnowledgeDocument]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        KnowledgeDocument(
            document_id=item["document_id"],
            title=item["title"],
            content=item["content"],
            source=item["source"],
            product=item.get("product", "CloudPilot AI"),
            category=item.get("category", "general"),
            error_codes=tuple(str(code) for code in item.get("error_codes", [])),
        )
        for item in raw
    ]


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9_./:-]+", lowered)
    chinese = re.findall(r"[\u4e00-\u9fff]", lowered)
    bigrams = ["".join(chinese[index : index + 2]) for index in range(max(0, len(chinese) - 1))]
    return latin + chinese + bigrams


class SimpleHybridRetriever:
    """离线可运行的检索器：字符 n-gram 相似度加错误码精确匹配。"""

    def __init__(self, documents: list[KnowledgeDocument]):
        self.documents = documents
        self.doc_tokens = [Counter(tokenize(f"{d.title} {d.content}")) for d in documents]

    @classmethod
    def from_path(cls, path: Path) -> "SimpleHybridRetriever":
        return cls(load_documents(path))

    def search(self, query: str, top_k: int = 3) -> list[Citation]:
        query_tokens = Counter(tokenize(query))
        codes = set(re.findall(r"(?<!\d)(?:400|401|403|404|408|409|429|500|502|503|504)(?!\d)", query))
        scored: list[tuple[float, KnowledgeDocument]] = []
        for document, doc_tokens in zip(self.documents, self.doc_tokens, strict=True):
            overlap = sum(min(count, doc_tokens.get(token, 0)) for token, count in query_tokens.items())
            denom = math.sqrt(sum(v * v for v in query_tokens.values())) * math.sqrt(
                sum(v * v for v in doc_tokens.values())
            )
            cosine = overlap / denom if denom else 0.0
            exact_bonus = 0.45 if codes.intersection(document.error_codes) else 0.0
            title_bonus = 0.08 if any(token in document.title.lower() for token in query_tokens) else 0.0
            score = min(1.0, cosine * 2.5 + exact_bonus + title_bonus)
            if score > 0:
                scored.append((score, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            Citation(
                document_id=document.document_id,
                title=document.title,
                source=document.source,
                excerpt=document.content[:280],
                score=round(score, 4),
            )
            for score, document in scored[:top_k]
        ]

    def count(self) -> int:
        return len(self.documents)


class HashEmbeddingFunction:
    """供 Chroma 离线演示使用的确定性中文 n-gram 向量，不代表生产语义模型。"""

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def name(self) -> str:
        return "cloudpilot-hash-embedding"

    def __call__(self, input: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in input:
            vector = [0.0] * self.dimensions
            for token in tokenize(text):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimensions
                vector[index] += 1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors

    def embed_query(self, input: list[str]) -> list[list[float]]:
        """Chroma 1.x calls this method for query embeddings."""
        return self(input)

    def get_config(self) -> dict[str, int]:
        return {"dimensions": self.dimensions}

    @staticmethod
    def build_from_config(config: dict[str, int]) -> "HashEmbeddingFunction":
        return HashEmbeddingFunction(dimensions=int(config.get("dimensions", 384)))


class ChromaRetriever:
    def __init__(self, documents: list[KnowledgeDocument], persist_path: Path):
        import chromadb

        persist_path.mkdir(parents=True, exist_ok=True)
        self.documents = documents
        self.client = chromadb.PersistentClient(path=str(persist_path))
        self.collection = self.client.get_or_create_collection(
            name="cloudpilot_knowledge",
            embedding_function=HashEmbeddingFunction(),
            metadata={"description": "CloudPilot AI demo knowledge base"},
        )
        if self.collection.count() != len(documents):
            if self.collection.count():
                existing = self.collection.get().get("ids", [])
                if existing:
                    self.collection.delete(ids=existing)
            self.collection.add(
                ids=[d.document_id for d in documents],
                documents=[f"{d.title}\n{d.content}" for d in documents],
                metadatas=[
                    {"title": d.title, "source": d.source, "category": d.category, "error_codes": ",".join(d.error_codes)}
                    for d in documents
                ],
            )

    @classmethod
    def from_path(cls, knowledge_path: Path, persist_path: Path) -> "ChromaRetriever":
        return cls(load_documents(knowledge_path), persist_path)

    def search(self, query: str, top_k: int = 3) -> list[Citation]:
        result = self.collection.query(query_texts=[query], n_results=top_k)
        citations: list[Citation] = []
        for doc_id, text, metadata, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0], strict=True
        ):
            citations.append(
                Citation(
                    document_id=doc_id,
                    title=metadata["title"],
                    source=metadata["source"],
                    excerpt=text.split("\n", 1)[-1][:280],
                    score=round(max(0.0, min(1.0, 1.0 - float(distance) / 2)), 4),
                )
            )
        return citations

    def count(self) -> int:
        return self.collection.count()


def build_retriever(backend: str, knowledge_path: Path, chroma_path: Path):
    if backend.lower() == "chroma":
        try:
            return ChromaRetriever.from_path(knowledge_path, chroma_path)
        except Exception:
            return SimpleHybridRetriever.from_path(knowledge_path)
    return SimpleHybridRetriever.from_path(knowledge_path)
