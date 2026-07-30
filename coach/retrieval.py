import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT_DIR = ROOT / "data" / "vlearn-pack" / "transcript"
CHUNK_PATTERN = re.compile(
    r"\*\*\[(?P<id>T\d{2}-\d{3})\]\*\*\s*(?P<text>.*?)(?=\n\n\*\*\[T\d{2}-\d{3}\]\*\*|\Z)",
    re.DOTALL,
)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    lesson_id: str


def _tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return {
        token
        for token in re.findall(r"[a-z0-9\u00c0-\u024f]+", normalized)
        if len(token) > 2
    }


@lru_cache(maxsize=12)
def load_lesson(lesson_id: str) -> tuple[Chunk, ...]:
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", lesson_id)
    path = TRANSCRIPT_DIR / f"{safe_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"Unknown lesson: {lesson_id}")
    content = path.read_text(encoding="utf-8")
    return tuple(
        Chunk(
            chunk_id=match.group("id"),
            text=" ".join(match.group("text").split()),
            lesson_id=safe_id,
        )
        for match in CHUNK_PATTERN.finditer(content)
    )


def retrieve(lesson_id: str, query: str, limit: int = 6) -> list[Chunk]:
    chunks = load_lesson(lesson_id)
    query_tokens = _tokens(query)
    scored: list[tuple[float, Chunk]] = []
    for chunk in chunks:
        chunk_tokens = _tokens(chunk.text)
        overlap = len(query_tokens & chunk_tokens)
        score = overlap / max(len(query_tokens), 1)
        if any(term in chunk.text.lower() for term in ("transformer", "attention", "generative ai")):
            score += 0.15
        scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [chunk for score, chunk in scored[:limit] if score > 0]
    return selected or list(chunks[20:26])


def format_context(chunks: list[Chunk], max_chars: int) -> str:
    parts: list[str] = []
    used = 0
    for chunk in chunks:
        block = f"[{chunk.chunk_id}] {chunk.text}"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)


def valid_source_ids(chunks: list[Chunk]) -> set[str]:
    return {chunk.chunk_id for chunk in chunks}


# ---------------------------------------------------------------------------
# Advanced retrieval modes (LangChain BM25, FAISS, EnsembleRetriever)
# ---------------------------------------------------------------------------

def keyword_retrieve(lesson_id: str, query: str, limit: int = 6) -> list[Chunk]:
    """Retrieve chunks using LangChain's BM25Retriever."""
    from coach.indexing import _documents_to_chunks, get_bm25_retriever

    retriever = get_bm25_retriever(lesson_id, k=limit)
    docs = retriever.invoke(query)
    return _documents_to_chunks(docs)


def semantic_retrieve(lesson_id: str, query: str, limit: int = 6) -> list[Chunk]:
    """Retrieve chunks using LangChain's FAISS vectorstore (requires OpenAI API key)."""
    from coach.config import get_settings
    from coach.indexing import _documents_to_chunks, get_vector_retriever

    settings = get_settings()
    if not settings.openai_api_key:
        return keyword_retrieve(lesson_id, query, limit)

    retriever = get_vector_retriever(lesson_id, k=limit)
    docs = retriever.invoke(query)
    return _documents_to_chunks(docs)


def hybrid_retrieve(lesson_id: str, query: str, limit: int = 6) -> list[Chunk]:
    """Retrieve chunks using LangChain's EnsembleRetriever (BM25 + FAISS with RRF).

    Weights: BM25 30%, Vector 70% (configurable via get_ensemble_retriever).
    Falls back to BM25 only if no OpenAI API key.
    """
    from coach.indexing import _documents_to_chunks, get_ensemble_retriever

    retriever = get_ensemble_retriever(lesson_id, k=limit)
    docs = retriever.invoke(query)
    return _documents_to_chunks(docs[:limit])


def smart_retrieve(lesson_id: str, query: str, limit: int = 6) -> list[Chunk]:
    """Dispatch to the correct retrieval strategy based on config.

    Reads ``retrieval_mode`` from settings:
      - ``"hybrid"``   → EnsembleRetriever (BM25 + FAISS)  (default)
      - ``"semantic"``  → FAISS only
      - ``"keyword"``   → BM25 only
      - ``"legacy"``    → original token-overlap method
    """
    from coach.config import get_settings

    mode = get_settings().retrieval_mode

    if mode == "hybrid":
        return hybrid_retrieve(lesson_id, query, limit)
    elif mode == "semantic":
        return semantic_retrieve(lesson_id, query, limit)
    elif mode == "keyword":
        return keyword_retrieve(lesson_id, query, limit)
    else:
        return retrieve(lesson_id, query, limit)

