"""Evaluation tool for Quiz generation using LLM-as-a-judge.

Provides Ragas-style metrics (Faithfulness and Answer Relevance) using 
OpenAI's structured outputs via Instructor.
"""

import logging
import instructor
from pydantic import BaseModel

from coach.config import get_settings
from coach.llm_client import create_openai_compatible_client
from coach.schemas_eval import EvaluationResult

logger = logging.getLogger(__name__)

_EVAL_SYSTEM_PROMPT = """Bạn là một Chuyên gia Đánh giá Giáo dục (Educational Evaluator).
Nhiệm vụ của bạn là chấm điểm chất lượng của một câu hỏi trắc nghiệm được sinh ra từ một tài liệu gốc.

Bạn cần đánh giá 2 tiêu chí (thang điểm 0-100):
1. Faithfulness (Tính trung thực): Đáp án đúng có thực sự được suy ra trực tiếp từ tài liệu gốc không? Nếu câu trả lời bịa đặt (hallucination) hoặc lấy kiến thức bên ngoài mà tài liệu không hề nhắc tới, hãy cho điểm thấp (< 50).
2. Answer Relevance (Tính bám sát): Đáp án đúng có trực tiếp trả lời cho câu hỏi được đặt ra không?

Dữ liệu đầu vào:
- TÀI LIỆU GỐC (Context): {context_text}
- CÂU HỎI (Question): {question}
- ĐÁP ÁN ĐÚNG (Correct Answer): {correct_answer}

Quy định:
- `overall_passed` = True nếu cả hai điểm đều >= 70.
"""

def evaluate_quiz_question(
    question: str, 
    correct_answer: str, 
    context_text: str,
    max_retries: int = 3
) -> EvaluationResult:
    """Evaluate a generated quiz question against its source context.

    Args:
        question: The generated question text.
        correct_answer: The text of the correct option.
        context_text: The source context retrieved from the document.
        max_retries: Auto-retries for JSON/Pydantic validation errors.
                     
    Returns:
        An EvaluationResult object containing scores and reasoning.
    """
    settings = get_settings()
    if not settings.llm_enabled:
        raise RuntimeError(
            f"API key for LLM_PROVIDER={settings.llm_provider} is required for evaluation"
        )

    client = instructor.from_openai(create_openai_compatible_client(settings))

    user_prompt = _EVAL_SYSTEM_PROMPT.format(
        context_text=context_text,
        question=question,
        correct_answer=correct_answer
    )

    try:
        evaluation = client.chat.completions.create(
            model=settings.fast_llm_model,
            response_model=EvaluationResult,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0, # Zero temperature for deterministic evaluation
            max_retries=max_retries,
        )
        return evaluation
    except Exception as e:
        logger.error(f"Failed to evaluate question: {e}")
        raise
