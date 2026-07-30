"""Error Analysis Tool using LLM to identify user misconceptions.

Analyzes a user's incorrect answer to deduce their knowledge gap.
"""

import logging
from typing import Optional
import instructor

from coach.config import get_settings
from coach.llm_client import create_openai_compatible_client
from coach.schemas_error_analysis import ErrorAnalysisResult

logger = logging.getLogger(__name__)

_ERROR_ANALYSIS_PROMPT = """Bạn là một Gia sư Tâm lý học Giáo dục (Educational Psychologist & Tutor).
Học viên của bạn vừa làm sai một câu hỏi trắc nghiệm. Nhiệm vụ của bạn không phải là chấm điểm, 
mà là TÌM RA NGUYÊN NHÂN SÂU XA (misconception) tại sao học viên lại chọn đáp án sai đó.

Dữ liệu:
- CÂU HỎI: {question}
- ĐÁP ÁN ĐÚNG: {correct_answer}
- ĐÁP ÁN SAI HỌC VIÊN CHỌN: {user_answer}
- TÀI LIỆU THAM KHẢO (Nếu có): {context_text}

Hãy phân tích tư duy của học viên: Việc họ chọn đáp án sai đó chứng tỏ họ đang bị hổng kiến thức ở điểm nào?
Họ đang nhầm lẫn khái niệm gì với khái niệm gì?
Từ đó, trích xuất ra một chủ đề lỗi sai (misconception_topic) và lời giải thích (misconception_explanation).
"""

def analyze_user_error(
    question: str, 
    correct_answer: str, 
    user_answer: str,
    context_text: Optional[str] = None,
    max_retries: int = 3
) -> ErrorAnalysisResult:
    """Analyze a user's incorrect quiz attempt to find misconceptions.

    Args:
        question: The quiz question.
        correct_answer: The correct option.
        user_answer: The incorrect option chosen by the user.
        context_text: Optional reference text.
        max_retries: Auto-retries for JSON/Pydantic validation errors.
                     
    Returns:
        An ErrorAnalysisResult object.
    """
    settings = get_settings()
    if not settings.llm_enabled:
        raise RuntimeError(
            f"API key for LLM_PROVIDER={settings.llm_provider} is required for error analysis"
        )

    client = instructor.from_openai(create_openai_compatible_client(settings))

    user_prompt = _ERROR_ANALYSIS_PROMPT.format(
        question=question,
        correct_answer=correct_answer,
        user_answer=user_answer,
        context_text=context_text or "Không có tài liệu tham khảo cụ thể."
    )

    try:
        analysis = client.chat.completions.create(
            model=settings.llm_model,
            response_model=ErrorAnalysisResult,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2, # Low temperature for analytical consistency
            max_retries=max_retries,
        )
        return analysis
    except Exception as e:
        logger.error(f"Failed to analyze error: {e}")
        raise
