"""Index builders using LangChain's built-in retrievers.

Uses LangChain's BM25Retriever, FAISS vectorstore, and EnsembleRetriever
for hybrid search with Reciprocal Rank Fusion.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_openai import OpenAIEmbeddings

from coach.retrieval import Chunk, load_lesson

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Convert Chunks → LangChain Documents
# ---------------------------------------------------------------------------

def _chunks_to_documents(chunks: tuple[Chunk, ...]) -> list[Document]:
    """Convert internal Chunk objects to LangChain Documents."""
    return [
        Document(
            page_content=chunk.text,
            metadata={"chunk_id": chunk.chunk_id, "lesson_id": chunk.lesson_id},
        )
        for chunk in chunks
    ]


def _documents_to_chunks(docs: list[Document]) -> list[Chunk]:
    """Convert LangChain Documents back to internal Chunk objects."""
    return [
        Chunk(
            chunk_id=doc.metadata["chunk_id"],
            text=doc.page_content,
            lesson_id=doc.metadata["lesson_id"],
        )
        for doc in docs
    ]


# ---------------------------------------------------------------------------
# BM25 Retriever (cached per lesson)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=12)
def get_bm25_retriever(lesson_id: str, k: int = 5) -> BM25Retriever:
    """Build and cache a LangChain BM25Retriever for the given lesson."""
    chunks = load_lesson(lesson_id)
    docs = _chunks_to_documents(chunks)
    retriever = BM25Retriever.from_documents(docs, k=k)
    return retriever


# ---------------------------------------------------------------------------
# FAISS Vector Retriever (cached per lesson)
# ---------------------------------------------------------------------------

# Module-level cache (cannot use @lru_cache because FAISS object is not hashable)
_faiss_stores: dict[str, object] = {}


def get_vector_retriever(lesson_id: str, k: int = 5):
    """Build and cache a LangChain FAISS retriever for the given lesson.

    Returns a retriever interface. Requires OPENAI_API_KEY.
    """
    from langchain_community.vectorstores import FAISS
    from coach.config import get_settings

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for vector search")

    if lesson_id not in _faiss_stores:
        chunks = load_lesson(lesson_id)
        docs = _chunks_to_documents(chunks)
        embedding_model = OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
        )
        _faiss_stores[lesson_id] = FAISS.from_documents(docs, embedding_model)

    return _faiss_stores[lesson_id].as_retriever(search_kwargs={"k": k})


# ---------------------------------------------------------------------------
# Hybrid (Ensemble) Retriever
# ---------------------------------------------------------------------------

class CustomEnsembleRetriever:
    """Combines BM25 and Vector retrievers using Reciprocal Rank Fusion (RRF)."""
    def __init__(self, retrievers: list[object], weights: list[float] | None = None, rrf_k: int = 60):
        self.retrievers = retrievers
        self.weights = weights or [0.5] * len(retrievers)
        self.rrf_k = rrf_k

    def invoke(self, query: str) -> list[Document]:
        rrf_scores: dict[str, float] = {}
        doc_map: dict[str, Document] = {}

        for retriever, weight in zip(self.retrievers, self.weights):
            try:
                docs = retriever.invoke(query)
                for rank, doc in enumerate(docs):
                    chunk_id = doc.metadata.get("chunk_id", str(hash(doc.page_content)))
                    score = weight * (1.0 / (self.rrf_k + rank + 1))
                    rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + score
                    doc_map[chunk_id] = doc
            except Exception as exc:
                logger.warning(f"Retriever {retriever} failed: {exc}")

        sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
        return [doc_map[cid] for cid in sorted_ids]


def get_ensemble_retriever(lesson_id: str, k: int = 5, weights: list[float] | None = None):
    """Build a CustomEnsembleRetriever combining BM25 + FAISS with RRF.

    Args:
        lesson_id: Which transcript to search.
        k: Number of results per retriever.
        weights: [bm25_weight, vector_weight]. Default [0.3, 0.7].
    """
    from coach.config import get_settings

    if weights is None:
        weights = [0.3, 0.7]

    bm25 = get_bm25_retriever(lesson_id, k=k)

    settings = get_settings()
    if settings.openai_api_key:
        vector = get_vector_retriever(lesson_id, k=k)
        return CustomEnsembleRetriever(
            retrievers=[bm25, vector],
            weights=weights,
        )
    else:
        # No API key → BM25 only
        logger.warning("No OPENAI_API_KEY; CustomEnsembleRetriever falls back to BM25 only")
        return bm25


def clear_caches() -> None:
    """Clear all cached retrievers and stores (useful for testing)."""
    get_bm25_retriever.cache_clear()
    _faiss_stores.clear()
