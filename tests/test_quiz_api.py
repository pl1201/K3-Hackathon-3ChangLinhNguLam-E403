import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from coach.api import QUIZ_SESSIONS, app


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
                }
            ],
        }
    )


class QuizApiTests(unittest.TestCase):
    def setUp(self) -> None:
        QUIZ_SESSIONS.clear()
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


if __name__ == "__main__":
    unittest.main()
