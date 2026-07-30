import unittest

from coach.essay import score_essay_assessment
from coach.schemas_quiz import (
    EssayCriterionAssessment,
    EssayLLMAssessment,
    EssayQuestion,
)


class EssayScoringTests(unittest.TestCase):
    def test_score_is_deterministic_sum_of_rubric_rows(self) -> None:
        question = EssayQuestion(
            question_text="Phân tích bốn nội dung chính của buổi học.",
            reference_answer="Đáp án tham chiếu đủ bốn nội dung và ý nghĩa.",
            rubric_points=["Nội dung 1", "Nội dung 2", "Nội dung 3", "Giải thích ý nghĩa"],
        )
        assessment = EssayLLMAssessment(
            criteria=[
                EssayCriterionAssessment(criterion="Nội dung 1", status="met", reason="Nêu đúng."),
                EssayCriterionAssessment(criterion="Nội dung 2", status="partial", reason="Nêu chưa đủ."),
                EssayCriterionAssessment(criterion="Nội dung 3", status="missing", reason="Chưa nêu."),
                EssayCriterionAssessment(
                    criterion="Giải thích ý nghĩa",
                    status="missing",
                    reason="Chưa giải thích.",
                ),
            ],
            feedback="Cần bổ sung các ý còn thiếu.",
        )

        result = score_essay_assessment(question, assessment)

        self.assertEqual(result.score, 3.75)
        self.assertEqual(sum(item.points for item in result.rubric_breakdown), 3.75)
        self.assertEqual(sum(item.max_points for item in result.rubric_breakdown), 10)
        self.assertEqual(result.verdict, "needs_review")

    def test_all_met_scores_ten(self) -> None:
        question = EssayQuestion(
            question_text="Giải thích attention trong Transformer.",
            reference_answer="Attention tính mức liên quan giữa các token.",
            rubric_points=["Nêu token", "Nêu mức liên quan", "Nêu vai trò"],
        )
        assessment = EssayLLMAssessment(
            criteria=[
                EssayCriterionAssessment(criterion=item, status="met", reason="Đạt.")
                for item in question.rubric_points
            ],
            feedback="Câu trả lời đầy đủ.",
        )

        result = score_essay_assessment(question, assessment)

        self.assertEqual(result.score, 10)
        self.assertEqual(result.verdict, "strong")

    def test_rubric_echo_receives_no_credit(self) -> None:
        criterion = "Nêu chính xác bốn nội dung chính của buổi học."
        question = EssayQuestion(
            question_text="Phân tích bốn nội dung chính của buổi học.",
            reference_answer="Đáp án tham chiếu đủ bốn nội dung và ý nghĩa.",
            rubric_points=[criterion, "Phân tích ý nghĩa"],
        )
        assessment = EssayLLMAssessment(
            criteria=[
                EssayCriterionAssessment(
                    criterion=criterion,
                    status="met",
                    reason="Đạt.",
                    evidence_quote=criterion,
                ),
                EssayCriterionAssessment(
                    criterion="Phân tích ý nghĩa",
                    status="missing",
                    reason="Chưa có.",
                ),
            ],
            feedback="Cần bổ sung.",
        )

        result = score_essay_assessment(question, assessment, criterion)

        self.assertEqual(result.score, 0)
        self.assertTrue(all(item.status == "missing" for item in result.rubric_breakdown))
        self.assertIn("lặp lại", result.feedback)

    def test_claim_without_quote_from_answer_receives_no_credit(self) -> None:
        question = EssayQuestion(
            question_text="Giải thích attention.",
            reference_answer="Attention liên kết các token liên quan.",
            rubric_points=["Nêu quan hệ giữa token", "Nêu vai trò"],
        )
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

        result = score_essay_assessment(
            question,
            assessment,
            "Attention giúp mô hình xử lý ngữ cảnh.",
        )

        self.assertEqual(result.score, 0)
        self.assertIn("bằng chứng nguyên văn", result.rubric_breakdown[0].reason)


if __name__ == "__main__":
    unittest.main()
