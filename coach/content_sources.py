"""Load lesson content with source metadata for summaries and quizzes."""

from __future__ import annotations

from pathlib import Path
import re
import unicodedata

from coach.retrieval import format_context, retrieve


ROOT = Path(__file__).resolve().parents[1]
SLIDES_DIR = ROOT / "data" / "vlearn-pack" / "slides"
PDF_LESSONS = {
    "day1": "d1-slide-hackathon.pdf",
    "day2": "d2-slide-hackathon.pdf",
}


def pdf_filename(lesson_id: str) -> str | None:
    return PDF_LESSONS.get(lesson_id)


def resolve_lesson_id(lesson_id: str, query: str | None = None) -> str:
    """Route an explicit Day 1/Day 2 request to the matching PDF deck."""
    if not query:
        return lesson_id

    normalized = unicodedata.normalize("NFKD", query.lower())
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    normalized = re.sub(r"[_-]+", " ", normalized)

    if re.search(r"\b(?:day|ngay)\s*1\b", normalized):
        return "day1"
    if re.search(r"\b(?:day|ngay)\s*2\b", normalized):
        return "day2"
    return lesson_id


def load_pdf_context(lesson_id: str, max_chars: int = 30_000) -> str:
    """Extract page-tagged PDF text so the LLM can return real citations."""
    filename = pdf_filename(lesson_id)
    if not filename:
        raise FileNotFoundError(f"Unknown PDF lesson: {lesson_id}")

    import pypdf

    path = SLIDES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing slide file: {filename}")

    parts: list[str] = []
    used = 0
    with path.open("rb") as stream:
        reader = pypdf.PdfReader(stream)
        for page_number, page in enumerate(reader.pages, start=1):
            text = " ".join((page.extract_text() or "").split())
            if not text:
                continue
            block = f"[Source: {filename} | Page: {page_number}]\n{text}"
            if used + len(block) > max_chars:
                break
            parts.append(block)
            used += len(block)
    return "\n\n".join(parts)


def load_lesson_context(
    lesson_id: str,
    query: str,
    *,
    max_chars: int = 12_000,
    chunk_limit: int = 10,
) -> str:
    """Return source-aware context for either a PDF deck or transcript."""
    if lesson_id in PDF_LESSONS:
        return load_pdf_context(lesson_id, max_chars=max_chars)

    chunks = retrieve(lesson_id, query, limit=chunk_limit)
    return format_context(list(chunks), max_chars=max_chars)
