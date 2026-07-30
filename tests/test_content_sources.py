import unittest

from coach.content_sources import resolve_lesson_id


class ContentSourceRoutingTests(unittest.TestCase):
    def test_day_one_query_routes_to_day_one_pdf(self) -> None:
        lesson_id = resolve_lesson_id(
            "transcript-06-clean",
            "Tóm tắt slide Day 1 hackathon",
        )

        self.assertEqual(lesson_id, "day1")

    def test_day_two_query_routes_to_day_two_pdf(self) -> None:
        lesson_id = resolve_lesson_id(
            "transcript-06-clean",
            "Cho mình nội dung ngày 2",
        )

        self.assertEqual(lesson_id, "day2")

    def test_query_without_explicit_day_keeps_selected_source(self) -> None:
        lesson_id = resolve_lesson_id(
            "transcript-06-clean",
            "Tóm tắt phần self-attention",
        )

        self.assertEqual(lesson_id, "transcript-06-clean")


if __name__ == "__main__":
    unittest.main()
