"""Generate and evaluate evidence-grounded short-answer questions."""

from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata

import instructor

from coach.config import get_settings
from coach.llm_client import create_openai_compatible_client
from coach.schemas_quiz import (
    EssayCriterionAssessment,
    EssayEvaluation,
    EssayLLMAssessment,
    EssayQuestion,
    EssayRubricScore,
)


def generate_essay_question(
    context_text: str,
    topic_query: str,
    bloom_level: str,
) -> EssayQuestion:
    settings = get_settings()
    client = instructor.from_openai(create_openai_compatible_client(settings))
    return client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Bạn tạo một câu hỏi tự luận ngắn bằng tiếng Việt dựa hoàn toàn trên nguồn. "
                    "Câu hỏi nên trả lời trong 3-6 câu, có 2-4 ý rubric rõ ràng. "
                    "reference_answer phải là một đáp án mẫu ngắn gọn, dễ hiểu, "
                    "gồm 2-4 câu và không quá 450 ký tự. "
                    "Giữ chính xác source_file/page_number hoặc chunk_id từ metadata; không bịa nguồn."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Chủ đề: {topic_query}\nMức Bloom: {bloom_level}\n\n"
                    f"Nguồn:\n{context_text}"
                ),
            },
        ],
        response_model=EssayQuestion,
        max_retries=3,
    )


def evaluate_essay_answer(
    question: EssayQuestion,
    answer_text: str,
    context_text: str,
) -> EssayEvaluation:
    settings = get_settings()
    client = instructor.from_openai(create_openai_compatible_client(settings))
    assessment: EssayLLMAssessment = client.chat.completions.create(
        model=settings.fast_llm_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Bạn chấm câu trả lời tự luận ngắn theo rubric và nguồn. "
                    "Với TỪNG tiêu chí rubric theo đúng thứ tự, chỉ đánh dấu: "
                    "`met` nếu đáp ứng đầy đủ, `partial` nếu đúng một phần, "
                    "`missing` nếu chưa đáp ứng. Với `met` hoặc `partial`, bắt buộc "
                    "chép một đoạn ngắn nguyên văn từ câu trả lời vào evidence_quote. "
                    "Không được suy diễn nội dung mà học viên không viết. Nếu học viên "
                    "chỉ lặp lại câu hỏi hoặc tiêu chí rubric thì đánh dấu `missing`. "
                    "Không tự cho điểm tổng. Feedback tối đa 2 câu; không thưởng kiến thức ngoài nguồn."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Câu hỏi: {question.question_text}\n"
                    f"Đáp án tham chiếu: {question.reference_answer}\n"
                    f"Rubric: {'; '.join(question.rubric_points)}\n"
                    f"Câu trả lời học viên: {answer_text}\n\nNguồn:\n{context_text}"
                ),
            },
        ],
        response_model=EssayLLMAssessment,
        max_retries=3,
    )
    return score_essay_assessment(question, assessment, answer_text)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    normalized = "".join(
        character for character in normalized
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def _is_rubric_echo(answer_text: str, criteria: list[str]) -> bool:
    answer = _normalize_text(answer_text)
    if not answer:
        return False

    for criterion in criteria:
        normalized_criterion = _normalize_text(criterion)
        if answer == normalized_criterion:
            return True
        if len(answer.split()) >= 4 and answer in normalized_criterion:
            return True
        if SequenceMatcher(None, answer, normalized_criterion).ratio() >= 0.82:
            return True
    return False


def score_essay_assessment(
    question: EssayQuestion,
    assessment: EssayLLMAssessment,
    answer_text: str | None = None,
) -> EssayEvaluation:
    """Calculate the final score deterministically from rubric statuses."""
    criteria = question.rubric_points
    count = len(criteria)
    base_weight = round(10 / count, 2)
    weights = [base_weight] * count
    weights[-1] = round(10 - sum(weights[:-1]), 2)
    multipliers = {"met": 1.0, "partial": 0.5, "missing": 0.0}
    normalized_answer = _normalize_text(answer_text or "")
    has_rubric_echo = bool(answer_text) and _is_rubric_echo(answer_text, criteria)

    results: list[EssayRubricScore] = []
    for index, (criterion, max_points) in enumerate(zip(criteria, weights)):
        item = (
            assessment.criteria[index]
            if index < len(assessment.criteria)
            else EssayCriterionAssessment(
                criterion=criterion,
                status="missing",
                reason="Câu trả lời chưa thể hiện tiêu chí này.",
            )
        )
        status = item.status
        reason = item.reason
        if has_rubric_echo:
            status = "missing"
            reason = "Câu trả lời chỉ lặp lại yêu cầu chấm, chưa cung cấp nội dung trả lời."
        elif answer_text and status in ("met", "partial"):
            evidence = _normalize_text(item.evidence_quote or "")
            if not evidence or evidence not in normalized_answer:
                status = "missing"
                reason = "Không tìm thấy bằng chứng nguyên văn cho tiêu chí này trong câu trả lời."

        points = round(max_points * multipliers[status], 2)
        results.append(
            EssayRubricScore(
                criterion=criterion,
                status=status,
                points=points,
                max_points=max_points,
                reason=reason,
            )
        )

    score = round(sum(item.points for item in results), 2)
    verdict = "strong" if score >= 8 else "partial" if score >= 5 else "needs_review"
    strengths = [item.criterion for item in results if item.status == "met"][:3]
    missing_points = [
        item.criterion for item in results if item.status in ("partial", "missing")
    ][:3]
    return EssayEvaluation(
        score=score,
        verdict=verdict,
        feedback=(
            "Bạn đang lặp lại yêu cầu của đề bài, chưa đưa ra câu trả lời có nội dung."
            if has_rubric_echo
            else assessment.feedback
        ),
        strengths=strengths,
        missing_points=missing_points,
        rubric_breakdown=results,
    )
