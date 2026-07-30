"""Instructor wrapper for structured summarization.

Uses the `instructor` library to patch the OpenAI client and enforce
strict JSON schema outputs based on Pydantic models.
"""

import logging
from typing import Optional

import instructor

from coach.config import get_settings
from coach.content_sources import load_lesson_context, pdf_filename
from coach.llm_client import create_openai_compatible_client
from coach.schemas_quiz import StructuredSummary

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Bạn là trợ giảng chuyên tạo bản ôn tập siêu nhanh dựa trên nguồn.

Quy tắc bắt buộc:
1. ĐỘ BAO PHỦ TOÀN DIỆN: Quét toàn bộ nguồn và xác định TẤT CẢ các chủ đề lớn — không được bỏ qua bất kỳ phần nào dù ngắn.
   Mỗi phần/section riêng biệt trong nguồn phải được ánh xạ thành ít nhất 1 topic.
2. Phân rã thành 3-6 chủ đề (không giới hạn dưới nếu nguồn có nhiều phần hơn).
3. Mỗi topic có tối đa 3 micro-facts, ưu tiên ý cốt lõi nhất.
4. Mỗi fact là một câu ngắn, có thể đọc hiểu độc lập.
5. CITATION CHÍNH XÁC:
   - Với PDF: lấy `source_file` và `page_number` từ thẻ [Source: ... | Page: ...].
   - Với transcript: lấy `chunk_id` từ thẻ [Txx-xxx].
   - Tuyệt đối không tự tạo số trang, chunk ID hay kiến thức ngoài nguồn.
6. `summary_notes`: Chỉ ghi 1 câu kết nối logic giữa CÁC CHỦ ĐỀ — không tóm tắt lại nội dung đã liệt kê.
"""


_INLINE_SYSTEM_PROMPT = """Bạn là trợ giảng trả lời câu hỏi cụ thể của học viên dựa trên nguồn.
Chỉ tóm tắt phần liên quan trực tiếp đến yêu cầu — không cần liệt kê toàn bộ bài.
Mỗi topic chứa 1-3 micro-facts ngắn gọn, có citation chính xác từ nguồn.
`summary_notes` để trống chuỗi rỗng vì đây là trả lời inline, không phải tổng quan toàn bài.
"""


def summarize_to_facts(
    text: str,
    max_retries: int = 3,
    query: str | None = None,
    is_inline: bool = False,
) -> StructuredSummary:
    """Convert source-tagged lesson text into validated micro-facts.

    Args:
        text: Source-tagged lesson text to summarize.
        max_retries: Number of Instructor retry attempts on schema validation failure.
        query: Optional focused topic; if None, summarizes the full lesson.
        is_inline: When True, uses a compact prompt for inline chat responses
                   and sets summary_notes to empty — callers should hide it in the UI.
    """
    settings = get_settings()
    if not settings.llm_enabled:
        raise RuntimeError("A configured LLM provider is required for dynamic summarization")

    system_prompt = _INLINE_SYSTEM_PROMPT if is_inline else _SYSTEM_PROMPT
    user_content = (
        f"Yêu cầu tóm tắt: {query or 'Toàn bộ nội dung cốt lõi'}\n\n"
        f"Nguồn:\n{text}"
    )

    client = instructor.from_openai(create_openai_compatible_client(settings))
    result: StructuredSummary = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_model=StructuredSummary,
        max_retries=max_retries,
    )
    # Enforce empty summary_notes for inline queries so the UI can
    # reliably decide whether to render the note block.
    if is_inline:
        result.summary_notes = ""
    return result


def summarize_lesson(lesson_id: str, query: str | None = None) -> StructuredSummary:
    """Summarize a lesson into structured micro-facts with chunk citations.

    If LLM is enabled, loads transcript text and runs Instructor summarization.
    - Full-lesson requests (query=None) use a comprehensive coverage prompt.
    - Inline chat queries (query provided) use a focused inline prompt.
    Falls back to curated facts only when LLM is unavailable.
    """
    settings = get_settings()
    is_inline = query is not None
    if settings.llm_enabled:
        try:
            context = load_lesson_context(
                lesson_id,
                query or "Liệt kê TẤT CẢ các chủ đề và điểm học cốt lõi của toàn bài",
                max_chars=16_000 if pdf_filename(lesson_id) else 7_000,
                chunk_limit=16,
            )
            return summarize_to_facts(context, query=query, is_inline=is_inline)
        except Exception as exc:
            logger.warning("Dynamic LLM summarization failed (%s); using fallback", exc)

    return get_fallback_summary(lesson_id)


def get_fallback_summary(lesson_id: str) -> StructuredSummary:
    from coach.schemas_quiz import MicroFact, StructuredSummary, Topic

    if lesson_id == "day1":
        return StructuredSummary(
            topics=[
                Topic(
                    topic_name="AI và LLM",
                    micro_facts=[
                        MicroFact(
                            fact="AI bao gồm Machine Learning, Deep Learning, Generative AI và LLM.",
                            is_core_concept=True,
                            source_file="d1-slide-hackathon.pdf",
                            page_number=3,
                        ),
                        MicroFact(
                            fact="Transformer và attention là nền tảng vận hành của phần lớn LLM hiện đại.",
                            is_core_concept=True,
                            source_file="d1-slide-hackathon.pdf",
                            page_number=15,
                        ),
                        MicroFact(
                            fact="Một AI Agent kết hợp mục tiêu, suy luận, công cụ, hành động và bộ nhớ.",
                            is_core_concept=True,
                            source_file="d1-slide-hackathon.pdf",
                            page_number=24,
                        ),
                    ],
                ),
            ],
            summary_notes="Nắm cơ chế LLM, giới hạn context và cách chuyển từ model sang agent.",
        )
    if lesson_id == "day2":
        return StructuredSummary(
            topics=[
                Topic(
                    topic_name="Xác định bài toán AI",
                    micro_facts=[
                        MicroFact(
                            fact="Double Diamond tách quá trình thành Discover, Define, Develop và Deliver.",
                            is_core_concept=True,
                            source_file="d2-slide-hackathon.pdf",
                            page_number=3,
                        ),
                        MicroFact(
                            fact="Discover mở rộng góc nhìn bằng quan sát, phỏng vấn, khảo sát và dữ liệu.",
                            is_core_concept=True,
                            source_file="d2-slide-hackathon.pdf",
                            page_number=4,
                        ),
                    ],
                ),
            ],
            summary_notes="Bắt đầu từ vấn đề có bằng chứng trước khi chọn giải pháp AI.",
        )
    if lesson_id == "transcript-06-clean":
        return StructuredSummary(
            topics=[
                Topic(
                    topic_name="Cơ chế Self-Attention",
                    micro_facts=[
                        MicroFact(
                            fact="Self-Attention giúp mỗi token tính trọng số liên quan với tất cả token khác trong chuỗi.",
                            is_core_concept=True,
                            chunk_id="T06-051",
                            page_number=3,
                        ),
                        MicroFact(
                            fact="Bộ ba vector Query (Q), Key (K), Value (V) được tính bằng tích ma trận từ Embedding.",
                            is_core_concept=True,
                            chunk_id="T06-052",
                            page_number=3,
                        ),
                    ],
                ),
                Topic(
                    topic_name="Multi-Head Attention & Positional Encoding",
                    micro_facts=[
                        MicroFact(
                            fact="Multi-Head Attention dùng 8+ đầu attention song song để học nhiều loại quan hệ ngữ nghĩa.",
                            is_core_concept=True,
                            chunk_id="T06-053",
                            page_number=4,
                        ),
                        MicroFact(
                            fact="Positional Encoding sử dụng hàm sin/cos để bổ sung thông tin vị trí cho token.",
                            is_core_concept=True,
                            chunk_id="T06-054",
                            page_number=5,
                        ),
                    ],
                ),
            ],
            summary_notes="Transformer loại bỏ hoàn toàn recurrence của RNN và là kiến trúc nền tảng cho LLM hiện đại.",
        )
    elif lesson_id == "transcript-04-clean":
        return StructuredSummary(
            topics=[
                Topic(
                    topic_name="Quá trình Huấn luyện LLM",
                    micro_facts=[
                        MicroFact(
                            fact="Pre-training huấn luyện mô hình dự đoán token tiếp theo trên hàng tỷ văn bản không nhãn.",
                            is_core_concept=True,
                            chunk_id="T04-012",
                            page_number=2,
                        ),
                        MicroFact(
                            fact="RLHF căn chỉnh hành vi mô hình bám sát yêu cầu người dùng.",
                            is_core_concept=True,
                            chunk_id="T04-015",
                            page_number=2,
                        ),
                    ],
                ),
            ],
            summary_notes="LLM là mô hình dự đoán token tiếp theo, tối ưu cho mượt ngôn ngữ hơn là tra cứu sự thật.",
        )
    elif lesson_id == "transcript-01-clean":
        return StructuredSummary(
            topics=[
                Topic(
                    topic_name="Tư duy Problem-First",
                    micro_facts=[
                        MicroFact(
                            fact="Ứng dụng AI thành công phải bắt đầu từ nỗi đau (Pain-point) thực tế của người dùng.",
                            is_core_concept=True,
                            chunk_id="T01-005",
                            page_number=1,
                        ),
                    ],
                ),
            ],
            summary_notes="Đo lường ROI và xác định bài toán rõ ràng trước khi chọn mô hình AI.",
        )

    return StructuredSummary(
        topics=[
            Topic(
                topic_name="Kiến thức Trọng tâm",
                micro_facts=[
                    MicroFact(
                        fact="Hiểu rõ khái niệm cốt lõi và ứng dụng thực tế trong bài học.",
                        is_core_concept=True,
                        chunk_id="T01-001",
                        page_number=1,
                    )
                ],
            )
        ],
        summary_notes="Tóm tắt trọng tâm bài học giúp ôn tập nhanh.",
    )
