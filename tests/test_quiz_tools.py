import json
import unittest
from unittest.mock import Mock, patch

from langchain_core.documents import Document

from coach.schemas_error_analysis import ErrorAnalysisResult
from coach.schemas_eval import EvaluationResult
from coach.schemas_quiz import (
    MicroFact,
    QuizModel,
    QuizOption,
    QuizQuestion,
    StructuredSummary,
    Topic,
)
from coach.tools import (
    CompressedSearchTool,
    ErrorAnalysisTool,
    KeywordExtractorTool,
    KeywordSearchTool,
    QuizEvaluatorTool,
    QuizGeneratorTool,
    SemanticSearchTool,
    SpacedRepetitionTool,
    StructuredSummaryTool,
    VisualSummarizationTool,
    get_retrieval_tools,
)


def sample_quiz() -> QuizModel:
    return QuizModel(
        title="Transformer quiz",
        questions=[
            QuizQuestion(
                question_text="Transformer dùng cơ chế nào?",
                options=[
                    QuizOption(text="Attention", is_correct=True),
                    QuizOption(text="Sorting", is_correct=False),
                    QuizOption(text="Hashing", is_correct=False),
                    QuizOption(text="Polling", is_correct=False),
                ],
                explanation="Transformer sử dụng attention.",
            )
        ],
    )


class QuizToolsTests(unittest.TestCase):
    def test_registry_contains_ten_unique_tools(self) -> None:
        tools = get_retrieval_tools()
        self.assertEqual(len(tools), 10)
        self.assertEqual(len({tool.name for tool in tools}), 10)

    def test_keyword_search_runs_offline(self) -> None:
        output = KeywordSearchTool()._run("Generative AI", top_k=2)
        self.assertIn("T06-", output)

    def test_semantic_search_formats_mocked_documents(self) -> None:
        retriever = Mock()
        retriever.invoke.return_value = [
            Document(page_content="Attention giúp mô hình tập trung.", metadata={"chunk_id": "T06-001"})
        ]
        with patch("coach.tools.get_vector_retriever", return_value=retriever):
            output = SemanticSearchTool()._run("attention", top_k=1)
        self.assertIn("T06-001", output)

    def test_compressed_search_reports_mocked_savings(self) -> None:
        retriever = Mock()
        retriever.invoke.return_value = [
            Document(page_content="Long context", metadata={"chunk_id": "T06-001"})
        ]
        compressed = [Document(page_content="Short", metadata={"chunk_id": "T06-001"})]
        savings = {
            "compressed_docs": 1,
            "original_docs": 1,
            "savings_percent": 50,
            "estimated_tokens_saved": 10,
        }
        with (
            patch("coach.indexing.get_ensemble_retriever", return_value=retriever),
            patch("coach.compression.compressed_retrieve", return_value=compressed),
            patch("coach.compression.estimate_token_savings", return_value=savings),
        ):
            output = CompressedSearchTool()._run("attention")
        self.assertIn("50%", output)

    def test_structured_summary_serializes_mocked_result(self) -> None:
        retriever = Mock()
        retriever.invoke.return_value = [Document(page_content="Transformer context")]
        summary = StructuredSummary(
            topics=[
                Topic(
                    topic_name="Transformer",
                    micro_facts=[MicroFact(fact="Transformer dùng attention.", is_core_concept=True)],
                )
            ],
            summary_notes="Tóm tắt.",
        )
        with (
            patch("coach.indexing.get_ensemble_retriever", return_value=retriever),
            patch("coach.structured_summarizer.summarize_to_facts", return_value=summary),
        ):
            output = StructuredSummaryTool()._run("transformer")
        self.assertIn('"topics"', output)

    def test_visual_summarization_uses_parser(self) -> None:
        with patch("coach.visual_parser.parse_document_to_markdown", return_value="# Slide"):
            output = VisualSummarizationTool()._run("data/example.pdf")
        self.assertIn("# Slide", output)

    def test_quiz_generator_serializes_valid_quiz(self) -> None:
        with patch("coach.quiz_generator.generate_quiz", return_value=sample_quiz()):
            output = QuizGeneratorTool()._run("context", num_questions=1)
        self.assertIn('"questions"', output)

    def test_keyword_extractor_runs_offline(self) -> None:
        output = KeywordExtractorTool()._run(
            "Transformer sử dụng attention để xử lý ngữ cảnh và tạo biểu diễn.",
            top_n=3,
        )
        self.assertNotIn("thất bại", output.lower())

    def test_quiz_evaluator_serializes_mocked_result(self) -> None:
        evaluation = EvaluationResult(
            faithfulness_score=90,
            faithfulness_reasoning="Bám nguồn.",
            relevance_score=90,
            relevance_reasoning="Đúng trọng tâm.",
            overall_passed=True,
        )
        with patch("coach.evaluator.evaluate_quiz_question", return_value=evaluation):
            output = QuizEvaluatorTool()._run("context", "question", "answer")
        self.assertTrue(json.loads(output)["overall_passed"])

    def test_error_analysis_serializes_mocked_result(self) -> None:
        analysis = ErrorAnalysisResult(
            misconception_topic="Attention",
            misconception_explanation="Nhầm attention với sorting.",
            recommended_reading="Attention mechanism",
        )
        with patch("coach.error_analyzer.analyze_user_error", return_value=analysis):
            output = ErrorAnalysisTool()._run("q", "correct", "wrong")
        self.assertEqual(json.loads(output)["misconception_topic"], "Attention")

    def test_spaced_repetition_runs_offline(self) -> None:
        output = SpacedRepetitionTool()._run(is_correct=True)
        parsed = json.loads(output)
        self.assertTrue(parsed["is_correct"])
        self.assertTrue(parsed["next_review_iso"])


if __name__ == "__main__":
    unittest.main()
