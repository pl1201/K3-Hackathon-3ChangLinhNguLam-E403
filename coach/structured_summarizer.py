"""Instructor wrapper for structured summarization.

Uses the `instructor` library to patch the OpenAI client and enforce
strict JSON schema outputs based on Pydantic models.
"""

import logging
from typing import Optional

import instructor
from openai import OpenAI

from coach.config import get_settings
from coach.schemas_quiz import StructuredSummary

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """Bạn là một chuyên gia phân tích dữ liệu giáo dục.
Nhiệm vụ của bạn là đọc nội dung bài giảng và phân rã nó thành cấu trúc JSON nghiêm ngặt.
Mỗi chủ đề (Topic) phải chứa các sự thật vi mô (MicroFact) cực kỳ ngắn gọn,
sẵn sàng để hệ thống tự động sinh câu hỏi trắc nghiệm (Quiz).
Không được bịa thêm thông tin ngoài văn bản gốc.
"""


def summarize_to_facts(text: str, max_retries: int = 3) -> StructuredSummary:
    """Summarize raw text into a strict hierarchical Pydantic structure.

    Args:
        text: The source text to summarize.
        max_retries: How many times instructor should auto-retry if the LLM
                     returns invalid JSON or violates the Pydantic constraints.
                     
    Returns:
        A validated StructuredSummary object.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for structured summarization")

    # Patch the standard OpenAI client with instructor
    # instructor adds the `response_model` argument to chat.completions.create
    client = instructor.from_openai(OpenAI(api_key=settings.openai_api_key))

    try:
        summary: StructuredSummary = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Hãy phân rã nội dung sau:\n\n{text}"},
            ],
            # This is the magic of instructor: it handles the JSON schema and validation
            response_model=StructuredSummary,
            max_retries=max_retries,
        )
        return summary
    except Exception as exc:
        logger.error("Structured summarization failed: %s", exc)
        raise
