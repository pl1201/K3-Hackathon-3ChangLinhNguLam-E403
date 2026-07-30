"""Instructor wrapper for Quiz Generation.

Enforces strict JSON schema outputs based on QuizModel to ensure quizzes
always have the correct number of options, correct answers, and explanations.
"""

import logging
from typing import Optional

import instructor

from coach.config import get_settings
from coach.llm_client import create_openai_compatible_client
from coach.schemas_quiz import QuizModel

logger = logging.getLogger(__name__)



_QUIZ_SYSTEM_PROMPT = """Bạn là một chuyên gia thiết kế bài giảng và đề thi trắc nghiệm (Quiz).
Nhiệm vụ của bạn là đọc các kiến thức được cung cấp và tạo ra một bộ câu hỏi trắc nghiệm đúng với yêu cầu.

Luật BẮT BUỘC:
1. Mỗi câu hỏi PHẢI có CHÍNH XÁC 4 đáp án (options).
2. Trong 4 đáp án, PHẢI có CHÍNH XÁC 1 đáp án đúng (is_correct=true) và 3 đáp án sai (is_correct=false).
3. Các đáp án sai (distractors) phải hợp lý, logic, ưu tiên sử dụng các thuật ngữ cùng nhóm/chuyên ngành. Bạn CÓ THỂ sử dụng danh sách Gợi ý Đáp án Nhiễu (nếu có) để chế câu sai, nhưng phải cẩn thận đừng biến chúng thành đáp án đúng.
4. MỖI câu hỏi BẮT BUỘC phải có một lời giải thích (explanation) rõ ràng giải thích tại sao đáp án đó đúng và tại sao các đáp án kia sai.
5. Chỉ dựa vào nội dung được cung cấp, tuyệt đối không bịa thêm kiến thức ngoài.
6. TRÍCH DẪN NGUỒN: Nếu nội dung kiến thức đầu vào có chứa siêu dữ liệu (metadata) như Tên file (Source), Số trang (Page)... bạn BẮT BUỘC phải trích xuất và điền vào trường `source_file` và `page_number` của câu hỏi tương ứng để học viên biết đường tra cứu lại.
"""


def generate_quiz(
    context_text: str, 
    num_questions: int = 5, 
    bloom_level: str = "remember",
    use_yake_distractors: bool = False,
    max_retries: int = 3
) -> QuizModel:
    """Generate a structured Quiz from context text using Instructor.

    Args:
        context_text: The source text or facts to base the questions on.
        num_questions: Number of questions to generate.
        bloom_level: Bloom's taxonomy level (remember, understand, apply).
        use_yake_distractors: If True, uses YAKE to extract terms to feed to the LLM as distractor ideas.
        max_retries: Auto-retries for JSON/Pydantic validation errors.
                     
    Returns:
        A validated QuizModel object.
    """
    settings = get_settings()
    if not settings.llm_enabled:
        raise RuntimeError(
            f"API key for LLM_PROVIDER={settings.llm_provider} is required for quiz generation"
        )

    from coach.bloom_prompts import get_bloom_prompt
    
    bloom_prompt = get_bloom_prompt(bloom_level)
    user_prompt_text = bloom_prompt.format(
        context_text=context_text, 
        num_questions=num_questions
    )

    if use_yake_distractors:
        try:
            from coach.distractor_generator import extract_distractors
            # Extract some general terms from the text to serve as distractor ideas
            # Since we don't have the "correct answer" yet (the LLM makes it), we just extract top keywords
            distractors = extract_distractors(context_text, correct_answer="", top_n=8)
            if distractors:
                user_prompt_text += (
                    "\n\nGỢI Ý TỪ KHÓA LÀM ĐÁP ÁN NHIỄU (Sử dụng các từ này làm đáp án sai "
                    "nếu thấy phù hợp):\n" + ", ".join(distractors)
                )
        except Exception as exc:
            logger.warning("Failed to extract distractors with YAKE: %s", exc)

    client = instructor.from_openai(create_openai_compatible_client(settings))

    try:
        quiz: QuizModel = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _QUIZ_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt_text},
            ],
            response_model=QuizModel,
            max_retries=max_retries,
        )
        return quiz
    except Exception as exc:
        logger.error("Quiz generation failed: %s", exc)
        raise

