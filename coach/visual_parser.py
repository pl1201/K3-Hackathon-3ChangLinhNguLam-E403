"""Visual Parsing using LlamaParse for complex documents.

Extracts tables, charts, and structured text from PDFs/PPTX into clean Markdown
format, preserving the structure for LLM understanding.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from coach.config import get_settings

logger = logging.getLogger(__name__)


def parse_document_to_markdown(file_path: str, use_cache: bool = True) -> str:
    """Parse a document into Markdown using LlamaParse.

    Args:
        file_path: Absolute or relative path to the file (e.g., .pdf).
        use_cache: If True, saves and loads the result from a local cache file
                   to avoid repeated API calls.

    Returns:
        The full parsed document content as a Markdown string.
    """
    settings = get_settings()
    if not settings.llama_cloud_api_key:
        raise RuntimeError("LLAMA_CLOUD_API_KEY is required for Visual Summarization")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Check cache first
    cache_dir = Path("data/parsed_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{path.stem}_parsed.md"

    if use_cache and cache_file.exists():
        logger.info("Loading parsed markdown from cache: %s", cache_file)
        return cache_file.read_text(encoding="utf-8")

    from llama_parse import LlamaParse

    logger.info("Calling LlamaParse API for %s", path.name)
    parser = LlamaParse(
        api_key=settings.llama_cloud_api_key,
        result_type="markdown",
        verbose=True,
    )

    try:
        # Load and parse the document
        documents = parser.load_data(str(path))
        
        # Combine all pages into a single markdown string
        full_markdown = "\n\n".join([doc.text for doc in documents])

        # Save to cache
        if use_cache:
            cache_file.write_text(full_markdown, encoding="utf-8")
            logger.info("Saved parsed markdown to cache: %s", cache_file)

        return full_markdown
    except Exception as exc:
        logger.error("LlamaParse failed for %s: %s", path.name, exc)
        raise
