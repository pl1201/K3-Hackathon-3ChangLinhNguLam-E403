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
    EssayRubricResult,
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
                    "Đáp án mẫu phải trả lời ĐỦ mọi rubric. Với từng rubric, điền "
                    "rubric_evidence cùng thứ tự và chép một answer_quote nguyên văn "
                    "từ reference_answer làm bằng chứng. "
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
                    "Bạn đánh giá câu trả lời tự luận ngắn theo rubric và nguồn. "
                    "Với TỪNG tiêu chí rubric theo đúng thứ tự, chỉ đánh dấu: "
                    "`met` nếu đáp ứng đầy đủ, `partial` nếu đúng một phần, "
                    "`missing` nếu chưa đáp ứng. Với `met` hoặc `partial`, bắt buộc "
                    "chép một đoạn ngắn nguyên văn từ câu trả lời vào evidence_quote. "
                    "Không được suy diễn nội dung mà học viên không viết. Nếu học viên "
                    "chỉ lặp lại câu hỏi hoặc tiêu chí rubric thì đánh dấu `missing`. "
                    "Tuyệt đối không tạo điểm số. Feedback tối đa 2 câu; "
                    "không ghi nhận kiến thức ngoài nguồn."
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
    return build_essay_evaluation(question, assessment, answer_text)


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


def build_essay_evaluation(
    question: EssayQuestion,
    assessment: EssayLLMAssessment,
    answer_text: str | None = None,
) -> EssayEvaluation:
    """Build transparent qualitative feedback from rubric statuses."""
    criteria = question.rubric_points
    normalized_answer = _normalize_text(answer_text or "")
    has_rubric_echo = bool(answer_text) and _is_rubric_echo(answer_text, criteria)
    matches_reference = bool(answer_text) and (
        normalized_answer == _normalize_text(question.reference_answer)
    )

    results: list[EssayRubricResult] = []
    for index, criterion in enumerate(criteria):
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
        evidence_quote = item.evidence_quote
        if matches_reference:
            status = "met"
            reason = "Nội dung khớp đáp án tham khảo và thể hiện đầy đủ tiêu chí."
            evidence_quote = question.rubric_evidence[index].answer_quote
        elif has_rubric_echo:
            status = "missing"
            reason = "Câu trả lời chỉ lặp lại yêu cầu chấm, chưa cung cấp nội dung trả lời."
            evidence_quote = None
        elif answer_text and status in ("met", "partial"):
            evidence = _normalize_text(evidence_quote or "")
            if not evidence or evidence not in normalized_answer:
                status = "missing"
                reason = "Không tìm thấy bằng chứng nguyên văn cho tiêu chí này trong câu trả lời."
                evidence_quote = None

        results.append(
            EssayRubricResult(
                criterion=criterion,
                status=status,
                reason=reason,
                evidence_quote=evidence_quote if status in ("met", "partial") else None,
            )
        )

    statuses = [item.status for item in results]
    verdict = (
        "mastered"
        if statuses and all(status == "met" for status in statuses)
        else "developing"
        if any(status in ("met", "partial") for status in statuses)
        else "needs_review"
    )
    strengths = [item.criterion for item in results if item.status == "met"][:3]
    missing_points = [
        item.criterion for item in results if item.status in ("partial", "missing")
    ][:3]
    return EssayEvaluation(
        verdict=verdict,
        feedback=(
            "Bạn đã thể hiện đầy đủ các ý chính trong đáp án tham khảo."
            if matches_reference
            else
            "Bạn đang lặp lại yêu cầu của đề bài, chưa đưa ra câu trả lời có nội dung."
            if has_rubric_echo
            else assessment.feedback
        ),
        strengths=strengths,
        missing_points=missing_points,
        rubric_breakdown=results,
    )
