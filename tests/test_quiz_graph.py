import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from pydantic import ValidationError

from coach.quiz_graph import process_answer, quiz_graph
from coach.schemas_quiz import QuizModel


def quiz_json(correct_index: int = 0) -> str:
    options = [
        {"text": "Attention", "is_correct": correct_index == 0},
        {"text": "Sorting", "is_correct": correct_index == 1},
        {"text": "Hashing", "is_correct": correct_index == 2},
        {"text": "Polling", "is_correct": correct_index == 3},
    ]
    return json.dumps(
        {
            "title": "Quiz",
            "questions": [
                {
                    "question_text": "Transformer dùng cơ chế nào?",
                    "options": options,
                    "explanation": "Transformer dùng attention.",
                }
            ],
        }
    )


class QuizGraphTests(unittest.TestCase):
    def test_schema_rejects_multiple_correct_options(self) -> None:
        invalid = json.loads(quiz_json())
        invalid["questions"][0]["options"][1]["is_correct"] = True
        with self.assertRaises(ValidationError):
            QuizModel.model_validate(invalid)

    def test_generation_stops_after_retry_budget(self) -> None:
        thread_id = uuid4().hex
        with (
            patch("coach.quiz_graph.search_tool._run", return_value="context"),
            patch("coach.quiz_graph.quiz_tool._run", return_value=quiz_json()),
            patch(
                "coach.quiz_graph.eval_tool._run",
                return_value=json.dumps({"overall_passed": False}),
            ) as evaluator,
        ):
            result = quiz_graph.invoke(
                {
                    "operation": "start",
                    "session_id": thread_id,
                    "topic_query": "Transformer",
                    "lesson_id": "transcript-06-clean",
                    "generation_attempts": 0,
                    "max_generation_attempts": 3,
                    "phase": "generating",
                },
                config={"configurable": {"thread_id": thread_id}, "recursion_limit": 20},
            )
        self.assertEqual(result["phase"], "failed")
        self.assertEqual(result["generation_attempts"], 3)
        self.assertEqual(evaluator.call_count, 3)

    def test_generation_stops_when_evaluator_passes(self) -> None:
        thread_id = uuid4().hex
        with (
            patch("coach.quiz_graph.search_tool._run", return_value="context"),
            patch("coach.quiz_graph.quiz_tool._run", return_value=quiz_json()),
            patch(
                "coach.quiz_graph.eval_tool._run",
                return_value=json.dumps({"overall_passed": True}),
            ),
        ):
            result = quiz_graph.invoke(
                {
                    "operation": "start",
                    "session_id": thread_id,
                    "topic_query": "Transformer",
                    "lesson_id": "transcript-06-clean",
                    "generation_attempts": 0,
                    "max_generation_attempts": 3,
                    "phase": "generating",
                },
                config={"configurable": {"thread_id": thread_id}},
            )
        self.assertEqual(result["phase"], "waiting_for_answer")
        self.assertEqual(result["generation_attempts"], 1)

    def test_correct_answer_completes(self) -> None:
        result = process_answer(
            {
                "quiz_json": quiz_json(correct_index=0),
                "user_answer_idx": 0,
            }
        )
        self.assertEqual(result["phase"], "completed")

    def test_wrong_answer_routes_to_remediation_and_resets_budget(self) -> None:
        result = process_answer(
            {
                "quiz_json": quiz_json(correct_index=0),
                "user_answer_idx": 1,
                "generation_attempts": 3,
            }
        )
        self.assertEqual(result["phase"], "remediating")
        self.assertEqual(result["generation_attempts"], 0)


if __name__ == "__main__":
    unittest.main()
