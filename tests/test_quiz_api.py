import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from coach.api import ESSAY_SESSIONS, QUIZ_SESSIONS, app
from coach.schemas_quiz import EssayEvaluation, EssayQuestion


def quiz_json() -> str:
    return json.dumps(
        {
            "title": "Quiz",
            "questions": [
                {
                    "question_text": "Transformer dùng cơ chế nào?",
                    "options": [
                        {"text": "Attention", "is_correct": True},
                        {"text": "Sorting", "is_correct": False},
                        {"text": "Hashing", "is_correct": False},
                        {"text": "Polling", "is_correct": False},
                    ],
                    "explanation": "Transformer dùng attention.",
                    "source_file": "d1-slide-hackathon.pdf",
                    "page_number": 15,
                }
            ],
        }
    )


class QuizApiTests(unittest.TestCase):
    def setUp(self) -> None:
        QUIZ_SESSIONS.clear()
        ESSAY_SESSIONS.clear()
        self.client = TestClient(app)

    def test_start_quiz_does_not_expose_answer_key(self) -> None:
        graph_result = {
            "phase": "waiting_for_answer",
            "quiz_json": quiz_json(),
            "generation_attempts": 1,
        }
        with (
            patch("coach.api.get_settings", return_value=SimpleNamespace(llm_enabled=True)),
            patch("coach.api.quiz_graph.invoke", return_value=graph_result),
        ):
            response = self.client.post(
                "/api/quiz/sessions",
                json={"topic_query": "Transformer", "lesson_id": "transcript-06-clean"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["question"]["options"]), 4)
        self.assertNotIn("is_correct", json.dumps(payload["question"]))

    def test_start_quiz_requires_llm(self) -> None:
        with patch("coach.api.get_settings", return_value=SimpleNamespace(llm_enabled=False)):
            response = self.client.post("/api/quiz/sessions", json={})
        self.assertEqual(response.status_code, 503)

    def test_start_quiz_forwards_selected_question_count(self) -> None:
        graph_result = {
            "phase": "waiting_for_answer",
            "quiz_json": quiz_json(),
            "generation_attempts": 1,
        }
        with (
            patch("coach.api.get_settings", return_value=SimpleNamespace(llm_enabled=True)),
            patch("coach.api.quiz_graph.invoke", return_value=graph_result) as invoke,
        ):
            response = self.client.post(
                "/api/quiz/sessions",
                json={
                    "topic_query": "Transformer",
                    "lesson_id": "transcript-06-clean",
                    "num_questions": 10,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_questions"], 10)
        self.assertEqual(invoke.call_args.args[0]["num_questions"], 10)

    def test_start_quiz_rejects_question_count_outside_limits(self) -> None:
        for count in (0, 26):
            with self.subTest(count=count):
                response = self.client.post(
                    "/api/quiz/sessions",
                    json={
                        "topic_query": "Transformer",
                        "lesson_id": "transcript-06-clean",
                        "num_questions": count,
                    },
                )
                self.assertEqual(response.status_code, 422)

    def test_unknown_quiz_session_returns_404(self) -> None:
        response = self.client.post(
            "/api/quiz/answers",
            json={"session_id": "missing-session", "answer_index": 0},
        )
        self.assertEqual(response.status_code, 404)

    def test_correct_quiz_answer_returns_explanation(self) -> None:
        session_id = "session-12345678"
        QUIZ_SESSIONS[session_id] = {
            "session_id": session_id,
            "phase": "waiting_for_answer",
            "quiz_json": quiz_json(),
            "generation_attempts": 1,
        }
        graph_result = {
            **QUIZ_SESSIONS[session_id],
            "phase": "completed",
        }
        with patch("coach.api.quiz_graph.invoke", return_value=graph_result):
            response = self.client.post(
                "/api/quiz/answers",
                json={"session_id": session_id, "answer_index": 0},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["is_correct"])
        self.assertIn("attention", payload["explanation"].lower())
        self.assertEqual(payload["review_source_file"], "d1-slide-hackathon.pdf")
        self.assertEqual(payload["review_page_number"], 15)

    def test_structured_summary_returns_evidence_linked_facts(self) -> None:
        with patch(
            "coach.structured_summarizer.get_settings",
            return_value=SimpleNamespace(llm_enabled=False),
        ):
            response = self.client.post(
                "/api/structured-summary",
                json={"lesson_id": "day1"},
            )
        self.assertEqual(response.status_code, 200)
        facts = response.json()["summary"]["topics"][0]["micro_facts"]
        self.assertTrue(any(fact["page_number"] for fact in facts))
        self.assertTrue(any(fact["source_file"] for fact in facts))

    def test_structured_summary_routes_explicit_day_one_query_to_pdf(self) -> None:
        with patch(
            "coach.structured_summarizer.get_settings",
            return_value=SimpleNamespace(llm_enabled=False),
        ):
            response = self.client.post(
                "/api/structured-summary",
                json={
                    "lesson_id": "transcript-06-clean",
                    "query": "Tóm tắt slide Day 1 hackathon",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["lesson_id"], "day1")
        facts = response.json()["summary"]["topics"][0]["micro_facts"]
        self.assertTrue(all(fact["source_file"] == "d1-slide-hackathon.pdf" for fact in facts))

    def test_essay_session_hides_reference_answer_and_returns_source(self) -> None:
        question = EssayQuestion(
            question_text="Vì sao attention quan trọng với Transformer?",
            reference_answer="Attention giúp mỗi token tập trung vào các token liên quan trong ngữ cảnh.",
            rubric_points=["Nêu quan hệ giữa token", "Nêu vai trò của trọng số"],
            source_file="d1-slide-hackathon.pdf",
            page_number=15,
        )
        with (
            patch("coach.api.get_settings", return_value=SimpleNamespace(llm_enabled=True)),
            patch("coach.content_sources.load_lesson_context", return_value="context"),
            patch("coach.essay.generate_essay_question", return_value=question),
        ):
            response = self.client.post(
                "/api/essay/sessions",
                json={"lesson_id": "day1", "topic_query": "Attention"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn("reference_answer", json.dumps(payload))
        self.assertEqual(payload["question"]["page_number"], 15)

    def test_essay_answer_returns_short_evaluation(self) -> None:
        question = EssayQuestion(
            question_text="Vì sao attention quan trọng với Transformer?",
            reference_answer="Attention giúp token tập trung vào phần liên quan.",
            rubric_points=["Nêu quan hệ token", "Nêu trọng số"],
            source_file="d1-slide-hackathon.pdf",
            page_number=15,
        )
        ESSAY_SESSIONS["essay-session-123"] = {"question": question, "context": "context"}
        evaluation = EssayEvaluation(
            score=7,
            verdict="partial",
            feedback="Bạn nêu đúng vai trò chính nhưng cần nói rõ cách tính mức liên quan.",
            strengths=["Đúng vai trò attention"],
            missing_points=["Chưa nêu trọng số liên quan"],
        )
        with patch("coach.essay.evaluate_essay_answer", return_value=evaluation):
            response = self.client.post(
                "/api/essay/answers",
                json={
                    "session_id": "essay-session-123",
                    "answer_text": "Attention giúp mô hình tập trung vào phần quan trọng.",
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["evaluation"]["score"], 7)
        self.assertEqual(payload["page_number"], 15)
        self.assertEqual(
            payload["suggested_answer"],
            "Attention giúp token tập trung vào phần liên quan.",
        )


if __name__ == "__main__":
    unittest.main()
