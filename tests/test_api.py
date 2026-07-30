import os
import unittest

# Unit tests are deterministic and must never spend tokens or emit traces.
os.environ["ENABLE_LLM"] = "false"
os.environ["ENABLE_TRACING"] = "false"

from fastapi.testclient import TestClient

from coach.api import SESSIONS, app


class CoachApiTests(unittest.TestCase):
    def setUp(self) -> None:
        SESSIONS.clear()
        self.client = TestClient(app)

    def test_health_and_static_app(self) -> None:
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_correct_answer_completes_session(self) -> None:
        started = self.client.post(
            "/api/sessions",
            json={"lesson_id": "transcript-06-clean", "user_id": "test-user"},
        )
        self.assertEqual(started.status_code, 200)
        session = started.json()
        answered = self.client.post(
            "/api/answers",
            json={
                "session_id": session["session_id"],
                "answer": (
                    "Discriminative AI phân loại và dự đoán, còn Generative AI "
                    "nhận prompt để tạo nội dung."
                ),
            },
        )
        result = answered.json()
        self.assertEqual(answered.status_code, 200)
        self.assertEqual(result["phase"], "complete")
        self.assertEqual(result["evaluation"]["verdict"], "correct")
        self.assertTrue(result["evaluation"]["evidence"])

    def test_short_answer_routes_to_clarification(self) -> None:
        session = self.client.post("/api/sessions", json={}).json()
        result = self.client.post(
            "/api/answers",
            json={"session_id": session["session_id"], "answer": "Em chưa rõ"},
        ).json()
        self.assertEqual(result["phase"], "clarify")
        self.assertEqual(result["evaluation"]["next_action"], "clarify")

    def test_unknown_session_is_not_found(self) -> None:
        response = self.client.post(
            "/api/answers",
            json={"session_id": "missing", "answer": "Một câu trả lời"},
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
