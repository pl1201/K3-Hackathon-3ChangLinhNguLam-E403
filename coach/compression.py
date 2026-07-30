"""Context compression utilities for reducing token usage.

Implements compression using OpenAI Embeddings for similarity filtering
and optional LLM extraction. Compatible with LangChain v1.3.x.

Three compression strategies:
  1. EmbeddingsCompressor — fast, cheap: removes docs below similarity threshold
  2. LLMExtractor         — precise, costly: LLM extracts relevant sentences only
  3. CompressionPipeline  — chains both for maximum quality
"""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from coach.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Embeddings-based compressor (fast, cheap)
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a, dtype="float32")
    b_arr = np.array(b, dtype="float32")
    dot = np.dot(a_arr, b_arr)
    norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    return float(dot / norm) if norm > 0 else 0.0


def compress_by_embeddings(
    docs: list[Document],
    query: str,
    similarity_threshold: float = 0.5,
    top_k: int | None = None,
) -> list[Document]:
    """Filter documents by embedding similarity to the query.

    Fast and cheap — only embedding comparison, no LLM call.

    Args:
        docs: Documents to filter.
        query: Query to measure relevance against.
        similarity_threshold: Minimum cosine similarity to keep (0-1).
        top_k: If set, keep only top-k most similar docs.

    Returns:
        Filtered and scored documents.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for embeddings compression")

    embeddings = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
    )

    # Embed query and all documents
    query_embedding = embeddings.embed_query(query)
    doc_texts = [doc.page_content for doc in docs]
    doc_embeddings = embeddings.embed_documents(doc_texts)

    # Score each document
    scored: list[tuple[float, Document]] = []
    for doc, doc_emb in zip(docs, doc_embeddings):
        score = _cosine_similarity(query_embedding, doc_emb)
        if score >= similarity_threshold:
            enriched_doc = Document(
                page_content=doc.page_content,
                metadata={**doc.metadata, "relevance_score": round(score, 4)},
            )
            scored.append((score, enriched_doc))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Apply top_k if set
    if top_k is not None:
        scored = scored[:top_k]

    return [doc for _score, doc in scored]


# ---------------------------------------------------------------------------
# LLM-based extractor (precise, costly)
# ---------------------------------------------------------------------------

_EXTRACT_PROMPT = """Trích xuất chỉ những câu hoặc đoạn văn có liên quan trực tiếp đến câu hỏi.
Giữ nguyên ngôn ngữ gốc, không thêm bớt ý. Nếu không có phần nào liên quan, trả về "KHÔNG LIÊN QUAN".

Câu hỏi: {query}

Nội dung:
{content}

Phần liên quan:"""


def compress_by_llm(
    docs: list[Document],
    query: str,
) -> list[Document]:
    """Extract only relevant sentences using an LLM.

    Precise but costly — makes one LLM call per document.

    Args:
        docs: Documents to extract from.
        query: Query to determine relevance.

    Returns:
        Documents with content reduced to only relevant sentences.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for LLM compression")

    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0,
        api_key=settings.openai_api_key,
        max_tokens=500,
    )

    compressed = []
    for doc in docs:
        prompt = _EXTRACT_PROMPT.format(query=query, content=doc.page_content)
        try:
            response = llm.invoke(prompt)
            extracted = response.content.strip()
            if extracted and extracted != "KHÔNG LIÊN QUAN":
                compressed.append(
                    Document(
                        page_content=extracted,
                        metadata={**doc.metadata, "compressed_by": "llm"},
                    )
                )
        except Exception as exc:
            logger.warning("LLM extraction failed for %s: %s", doc.metadata.get("chunk_id"), exc)
            compressed.append(doc)  # Keep original on failure

    return compressed


# ---------------------------------------------------------------------------
# Compression pipeline (embeddings → LLM)
# ---------------------------------------------------------------------------

def compress_pipeline(
    docs: list[Document],
    query: str,
    similarity_threshold: float = 0.5,
    use_llm: bool = False,
) -> list[Document]:
    """Multi-stage compression: embeddings filter, then optional LLM extraction.

    Stage 1: EmbeddingsFilter — remove docs below similarity threshold (cheap).
    Stage 2: LLMExtractor — extract relevant sentences from survivors (optional, costly).

    Args:
        docs: Documents to compress.
        query: Query for relevance.
        similarity_threshold: For embeddings filter.
        use_llm: Whether to apply LLM extraction after filtering.
    """
    # Stage 1: Embeddings filter
    filtered = compress_by_embeddings(docs, query, similarity_threshold=similarity_threshold)

    if not filtered:
        return filtered

    # Stage 2: LLM extraction (optional)
    if use_llm:
        filtered = compress_by_llm(filtered, query)

    return filtered


# ---------------------------------------------------------------------------
# Compressed retriever (combines retrieval + compression)
# ---------------------------------------------------------------------------

def compressed_retrieve(
    lesson_id: str,
    query: str,
    mode: str = "embeddings",
    base_k: int = 8,
    similarity_threshold: float = 0.5,
) -> list[Document]:
    """Retrieve documents and compress them in one step.

    Args:
        lesson_id: Which transcript to search.
        query: Search query.
        mode: Compression mode:
            - "embeddings" — fast similarity filter only
            - "llm"        — LLM extraction only
            - "pipeline"   — embeddings filter → LLM extraction
        base_k: Number of docs from the base retriever.
        similarity_threshold: For embeddings filter.
    """
    from coach.indexing import get_ensemble_retriever

    # Step 1: Retrieve (hybrid BM25 + Vector)
    base_retriever = get_ensemble_retriever(lesson_id, k=base_k)
    docs = base_retriever.invoke(query)

    if not docs:
        return []

    # Step 2: Compress
    if mode == "llm":
        return compress_by_llm(docs, query)
    elif mode == "pipeline":
        return compress_pipeline(docs, query, similarity_threshold=similarity_threshold, use_llm=True)
    else:  # "embeddings"
        return compress_by_embeddings(docs, query, similarity_threshold=similarity_threshold)


# ---------------------------------------------------------------------------
# Token savings estimator
# ---------------------------------------------------------------------------

def estimate_token_savings(
    original_docs: list[Document],
    compressed_docs: list[Document],
) -> dict:
    """Estimate token savings from compression.

    Returns a dict with original/compressed char counts and savings percentage.
    """
    original_chars = sum(len(doc.page_content) for doc in original_docs)
    compressed_chars = sum(len(doc.page_content) for doc in compressed_docs)
    savings_pct = (
        round((1 - compressed_chars / original_chars) * 100, 1)
        if original_chars > 0
        else 0
    )
    return {
        "original_docs": len(original_docs),
        "compressed_docs": len(compressed_docs),
        "original_chars": original_chars,
        "compressed_chars": compressed_chars,
        "savings_percent": savings_pct,
        "estimated_tokens_saved": (original_chars - compressed_chars) // 4,
    }
