import unittest

from pydantic import ValidationError

from coach.essay import build_essay_evaluation
from coach.schemas_quiz import (
    EssayCriterionAssessment,
    EssayLLMAssessment,
    EssayQuestion,
    EssayReferenceEvidence,
)


def make_question(
    *,
    question_text: str = "Giải thích attention trong Transformer.",
    reference_answer: str = (
        "Attention liên kết các token liên quan. "
        "Cơ chế này giúp mô hình tập trung vào ngữ cảnh quan trọng."
    ),
    rubric_points: list[str] | None = None,
) -> EssayQuestion:
    criteria = rubric_points or ["Nêu quan hệ giữa token", "Nêu vai trò"]
    quotes = [
        "Attention liên kết các token liên quan.",
        "Cơ chế này giúp mô hình tập trung vào ngữ cảnh quan trọng.",
    ]
    return EssayQuestion(
        question_text=question_text,
        reference_answer=reference_answer,
        rubric_points=criteria,
        rubric_evidence=[
            EssayReferenceEvidence(criterion=criterion, answer_quote=quotes[index])
            for index, criterion in enumerate(criteria)
        ],
    )


class EssayEvaluationTests(unittest.TestCase):
    def test_mixed_statuses_return_developing_without_numeric_score(self) -> None:
        question = make_question()
        assessment = EssayLLMAssessment(
            criteria=[
                EssayCriterionAssessment(
                    criterion="Nêu quan hệ giữa token",
                    status="met",
                    reason="Nêu đúng.",
                    evidence_quote="Attention liên kết token.",
                ),
                EssayCriterionAssessment(
                    criterion="Nêu vai trò",
                    status="missing",
                    reason="Chưa nêu.",
                ),
            ],
            feedback="Cần bổ sung vai trò của attention.",
        )

        result = build_essay_evaluation(
            question,
            assessment,
            "Attention liên kết token.",
        )

        self.assertEqual(result.verdict, "developing")
        self.assertFalse(hasattr(result, "score"))
        self.assertEqual(
            [item.status for item in result.rubric_breakdown],
            ["met", "missing"],
        )

    def test_all_met_returns_mastered(self) -> None:
        question = make_question()
        assessment = EssayLLMAssessment(
            criteria=[
                EssayCriterionAssessment(
                    criterion=item,
                    status="met",
                    reason="Đạt.",
                    evidence_quote=question.rubric_evidence[index].answer_quote,
                )
                for index, item in enumerate(question.rubric_points)
            ],
            feedback="Câu trả lời đầy đủ.",
        )

        result = build_essay_evaluation(
            question,
            assessment,
            question.reference_answer,
        )

        self.assertEqual(result.verdict, "mastered")
        self.assertTrue(all(item.status == "met" for item in result.rubric_breakdown))

    def test_rubric_echo_needs_review(self) -> None:
        criterion = "Nêu chính xác bốn nội dung chính của buổi học."
        question = make_question(rubric_points=[criterion, "Nêu vai trò"])
        assessment = EssayLLMAssessment(
            criteria=[
                EssayCriterionAssessment(
                    criterion=criterion,
                    status="met",
                    reason="Đạt.",
                    evidence_quote=criterion,
                ),
                EssayCriterionAssessment(
                    criterion="Nêu vai trò",
                    status="missing",
                    reason="Chưa có.",
                ),
            ],
            feedback="Cần bổ sung.",
        )

        result = build_essay_evaluation(question, assessment, criterion)

        self.assertEqual(result.verdict, "needs_review")
        self.assertTrue(all(item.status == "missing" for item in result.rubric_breakdown))
        self.assertIn("lặp lại", result.feedback)

    def test_claim_without_quote_from_answer_is_missing(self) -> None:
        question = make_question()
        assessment = EssayLLMAssessment(
            criteria=[
                EssayCriterionAssessment(
                    criterion="Nêu quan hệ giữa token",
                    status="met",
                    reason="Đạt.",
                    evidence_quote="liên kết các token",
                ),
                EssayCriterionAssessment(
                    criterion="Nêu vai trò",
                    status="missing",
                    reason="Chưa có.",
                ),
            ],
            feedback="Cần bổ sung.",
        )

        result = build_essay_evaluation(
            question,
            assessment,
            "Attention giúp mô hình xử lý ngữ cảnh.",
        )

        self.assertEqual(result.verdict, "needs_review")
        self.assertIn("bằng chứng nguyên văn", result.rubric_breakdown[0].reason)

    def test_reference_answer_must_cover_every_rubric_with_exact_quote(self) -> None:
        with self.assertRaises(ValidationError):
            EssayQuestion(
                question_text="Phân tích lịch sử và các nhóm AI.",
                reference_answer="AI gồm discriminative, generative và agentic.",
                rubric_points=["Nêu ba nhóm AI", "Nêu lịch sử AI"],
                rubric_evidence=[
                    EssayReferenceEvidence(
                        criterion="Nêu ba nhóm AI",
                        answer_quote="AI gồm discriminative, generative và agentic.",
                    ),
                    EssayReferenceEvidence(
                        criterion="Nêu lịch sử AI",
                        answer_quote="AI phát triển từ năm 1970.",
                    ),
                ],
            )


if __name__ == "__main__":
    unittest.main()
