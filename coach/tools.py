"""LangChain Tools for the Active Recall Coach agent.

Provides two retrieval tools that an LLM agent can call:
  1. SemanticSearchTool  — vector similarity via FAISS + OpenAI Embeddings
  2. KeywordSearchTool   — exact keyword/BM25 scoring

Uses LangChain's built-in BM25Retriever, FAISS, and EnsembleRetriever.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from coach.indexing import (
    _documents_to_chunks,
    get_bm25_retriever,
    get_ensemble_retriever,
    get_vector_retriever,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool Input Schemas
# ---------------------------------------------------------------------------

class SearchInput(BaseModel):
    """Input schema shared by both search tools."""
    query: str = Field(description="Câu truy vấn tìm kiếm bằng ngôn ngữ tự nhiên hoặc từ khóa cụ thể.")
    lesson_id: str = Field(
        default="transcript-06-clean",
        description="Mã bài giảng cần tìm kiếm, ví dụ: 'transcript-06-clean'.",
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Số lượng kết quả trả về (tối đa 20).")


# ---------------------------------------------------------------------------
# Semantic Search Tool (Vector Database / FAISS)
# ---------------------------------------------------------------------------

class SemanticSearchTool(BaseTool):
    """Tìm kiếm ngữ nghĩa trong tài liệu bài giảng bằng vector embedding.

    Sử dụng khi cần tìm đoạn văn bản có **ý nghĩa tương tự** với câu hỏi,
    ngay cả khi không chứa chính xác từ khóa. Phù hợp cho các câu hỏi
    diễn đạt lại, tìm khái niệm liên quan, hoặc so sánh ý tưởng.
    """

    name: str = "semantic_search"
    description: str = (
        "Tìm kiếm ngữ nghĩa (semantic search) trong tài liệu bài giảng dựa vào "
        "vector embedding. Dùng khi cần tìm đoạn có ý nghĩa tương đồng với câu hỏi, "
        "kể cả khi từ ngữ khác nhau. Ví dụ: tìm đoạn giải thích về 'cơ chế tập trung' "
        "sẽ trả về đoạn nói về 'attention mechanism'."
    )
    args_schema: type[BaseModel] = SearchInput

    def _run(self, query: str, lesson_id: str = "transcript-06-clean", top_k: int = 5) -> str:
        try:
            retriever = get_vector_retriever(lesson_id, k=top_k)
            docs = retriever.invoke(query)

            if not docs:
                return f"Không tìm thấy kết quả semantic search cho: '{query}'"

            output_parts = [f"🔍 Semantic Search — {len(docs)} kết quả cho: '{query}'\n"]
            for rank, doc in enumerate(docs, 1):
                text_preview = doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content
                chunk_id = doc.metadata.get("chunk_id", "?")
                output_parts.append(
                    f"[{rank}] **[{chunk_id}]**\n{text_preview}\n"
                )
            return "\n".join(output_parts)

        except RuntimeError as exc:
            return f"[Lỗi] {exc}. Hãy dùng keyword_search thay thế."
        except Exception as exc:
            logger.exception("Semantic search failed")
            return f"[Lỗi] Semantic search thất bại: {exc}"

    async def _arun(self, query: str, lesson_id: str = "transcript-06-clean", top_k: int = 5) -> str:
        return self._run(query, lesson_id, top_k)


# ---------------------------------------------------------------------------
# Keyword Search Tool (BM25)
# ---------------------------------------------------------------------------

class KeywordSearchTool(BaseTool):
    """Tìm kiếm từ khóa chính xác trong tài liệu bài giảng bằng BM25.

    Sử dụng khi cần tìm **chính xác** một từ khóa, mã đoạn (ví dụ T06-051),
    tên riêng, hoặc thuật ngữ cụ thể. Phù hợp khi biết rõ từ cần tìm.
    """

    name: str = "keyword_search"
    description: str = (
        "Tìm kiếm từ khóa chính xác (keyword/BM25 search) trong tài liệu bài giảng. "
        "Dùng khi cần tìm chính xác một từ khóa, mã đoạn như 'T06-051', tên riêng "
        "như 'Google', 'transformer', hoặc thuật ngữ kỹ thuật cụ thể. "
        "Cho kết quả tốt nhất khi query chứa từ khóa xuất hiện trực tiếp trong tài liệu."
    )
    args_schema: type[BaseModel] = SearchInput

    def _run(self, query: str, lesson_id: str = "transcript-06-clean", top_k: int = 5) -> str:
        try:
            retriever = get_bm25_retriever(lesson_id, k=top_k)
            docs = retriever.invoke(query)

            if not docs:
                return f"Không tìm thấy kết quả keyword search cho: '{query}'"

            output_parts = [f"🔑 Keyword Search (BM25) — {len(docs)} kết quả cho: '{query}'\n"]
            for rank, doc in enumerate(docs, 1):
                text_preview = doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content
                chunk_id = doc.metadata.get("chunk_id", "?")
                output_parts.append(
                    f"[{rank}] **[{chunk_id}]**\n{text_preview}\n"
                )
            return "\n".join(output_parts)

        except FileNotFoundError:
            return f"[Lỗi] Không tìm thấy bài giảng: '{lesson_id}'"
        except Exception as exc:
            logger.exception("Keyword search failed")
            return f"[Lỗi] Keyword search thất bại: {exc}"

    async def _arun(self, query: str, lesson_id: str = "transcript-06-clean", top_k: int = 5) -> str:
        return self._run(query, lesson_id, top_k)


# ---------------------------------------------------------------------------
# Convenience: get all tools as a list
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Compressed Search Tool (Context Compression)
# ---------------------------------------------------------------------------

class CompressedSearchInput(BaseModel):
    """Input schema for the compressed search tool."""
    query: str = Field(description="Câu truy vấn tìm kiếm bằng ngôn ngữ tự nhiên.")
    lesson_id: str = Field(
        default="transcript-06-clean",
        description="Mã bài giảng cần tìm kiếm.",
    )
    top_k: int = Field(default=8, ge=1, le=20, description="Số lượng kết quả trước nén (tối đa 20).")
    mode: str = Field(
        default="embeddings",
        description=(
            "Chế độ nén: 'embeddings' (nhanh, rẻ — lọc bằng similarity), "
            "'llm' (chính xác — LLM trích câu liên quan), "
            "'pipeline' (embeddings → llm, chất lượng cao nhất)."
        ),
    )


class CompressedSearchTool(BaseTool):
    """Tìm kiếm kết hợp nén ngữ cảnh để tiết kiệm token.

    Dùng Hybrid Search (BM25 + Vector) rồi nén kết quả:
    chỉ giữ lại những đoạn/câu thực sự liên quan đến câu hỏi.
    Giúp giảm đáng kể số token gửi cho LLM mà vẫn giữ chất lượng.
    """

    name: str = "compressed_search"
    description: str = (
        "Tìm kiếm kết hợp nén ngữ cảnh (context compression). "
        "Trước tiên tìm tài liệu bằng hybrid search (BM25 + Vector), "
        "sau đó nén kết quả để chỉ giữ lại phần liên quan nhất. "
        "Giúp tiết kiệm token khi context dài. "
        "Dùng khi cần context chất lượng cao mà gọn nhất có thể."
    )
    args_schema: type[BaseModel] = CompressedSearchInput

    def _run(
        self,
        query: str,
        lesson_id: str = "transcript-06-clean",
        top_k: int = 8,
        mode: str = "embeddings",
    ) -> str:
        try:
            from coach.compression import (
                compressed_retrieve,
                estimate_token_savings,
            )
            from coach.indexing import get_ensemble_retriever

            # Get uncompressed results for comparison
            base_retriever = get_ensemble_retriever(lesson_id, k=top_k)
            original_docs = base_retriever.invoke(query)

            # Get compressed results
            compressed_docs = compressed_retrieve(
                lesson_id, query, mode=mode, base_k=top_k,
            )

            if not compressed_docs:
                return f"Không tìm thấy kết quả sau nén cho: '{query}'"

            # Estimate savings
            savings = estimate_token_savings(original_docs, compressed_docs)

            # Format output
            output_parts = [
                f"📦 Compressed Search ({mode}) — {savings['compressed_docs']}/{savings['original_docs']} docs giữ lại\n"
                f"💰 Tiết kiệm: ~{savings['savings_percent']}% "
                f"(~{savings['estimated_tokens_saved']} tokens)\n"
            ]
            for rank, doc in enumerate(compressed_docs, 1):
                chunk_id = doc.metadata.get("chunk_id", "?")
                text = doc.page_content
                text_preview = text[:300] + "..." if len(text) > 300 else text
                output_parts.append(
                    f"[{rank}] **[{chunk_id}]**\n{text_preview}\n"
                )
            return "\n".join(output_parts)

        except RuntimeError as exc:
            return f"[Lỗi] {exc}"
        except Exception as exc:
            logger.exception("Compressed search failed")
            return f"[Lỗi] Compressed search thất bại: {exc}"

    async def _arun(
        self,
        query: str,
        lesson_id: str = "transcript-06-clean",
        top_k: int = 8,
        mode: str = "embeddings",
    ) -> str:
        return self._run(query, lesson_id, top_k, mode)



# ---------------------------------------------------------------------------
# Structured Summary Tool (Instructor + Pydantic)
# ---------------------------------------------------------------------------

class StructuredSummaryInput(BaseModel):
    """Input schema for the structured summary tool."""
    query: str = Field(
        description="Chủ đề hoặc từ khóa cần tìm kiếm và tóm tắt thành dạng JSON/Pydantic.",
    )
    lesson_id: str = Field(
        default="transcript-06-clean",
        description="Mã bài giảng.",
    )


class StructuredSummaryTool(BaseTool):
    """Công cụ tóm tắt ép kiểu cấu trúc bằng thư viện Instructor.

    Sử dụng khi bạn cần trích xuất thông tin dưới dạng cấu trúc rành mạch
    (ví dụ: phân rã thành các Chủ đề lớn và Sự thật vi mô - MicroFacts)
    nhằm phục vụ việc tạo câu hỏi Quiz hoặc báo cáo tự động.
    """

    name: str = "structured_summary"
    description: str = (
        "Ép cấu trúc tóm tắt (Structured Summary). Đầu tiên sẽ tìm kiếm "
        "thông tin liên quan đến query, sau đó dùng thư viện Instructor ép LLM "
        "trả về một JSON chuẩn xác chứa các Topics và Micro-facts sẵn sàng cho việc tạo Quiz. "
        "Dùng khi bạn cần tạo dữ liệu có cấu trúc từ văn xuôi."
    )
    args_schema: type[BaseModel] = StructuredSummaryInput

    def _run(self, query: str, lesson_id: str = "transcript-06-clean") -> str:
        try:
            from coach.indexing import get_ensemble_retriever
            from coach.structured_summarizer import summarize_to_facts

            # 1. Gather raw context
            base_retriever = get_ensemble_retriever(lesson_id, k=5)
            docs = base_retriever.invoke(query)
            if not docs:
                return f"Không tìm thấy thông tin nào về: '{query}' để tóm tắt."
            
            raw_text = "\n\n".join([doc.page_content for doc in docs])

            # 2. Force structured output using Instructor
            summary_obj = summarize_to_facts(raw_text)

            # 3. Format as readable JSON string (LLM can parse this back if needed)
            import json
            return f"✅ Đã tạo cấu trúc tóm tắt thành công:\n```json\n{summary_obj.model_dump_json(indent=2)}\n```"

        except RuntimeError as exc:
            return f"[Lỗi] {exc}"
        except Exception as exc:
            logger.exception("Structured summarization failed")
            return f"[Lỗi] Structured summarization thất bại: {exc}"

    async def _arun(self, query: str, lesson_id: str = "transcript-06-clean") -> str:
        return self._run(query, lesson_id)



# ---------------------------------------------------------------------------
# Visual Summarization Tool (LlamaParse)
# ---------------------------------------------------------------------------

class VisualSummarizationInput(BaseModel):
    """Input schema for the visual summarization tool."""
    file_path: str = Field(
        description="Đường dẫn tương đối tới file PDF cần trích xuất (ví dụ: 'data/slides/lecture.pdf').",
    )


class VisualSummarizationTool(BaseTool):
    """Công cụ đọc và trích xuất bảng biểu từ PDF bằng LlamaParse.

    Sử dụng khi bạn được yêu cầu phân tích các slide, bài báo khoa học hoặc
    tài liệu PDF có chứa nhiều bảng số liệu và hình ảnh phức tạp mà
    text extraction thông thường không đọc được. Output là Markdown chuẩn.
    """

    name: str = "visual_summarization"
    description: str = (
        "Đọc file PDF và trích xuất toàn bộ dữ liệu, đặc biệt giữ nguyên "
        "cấu trúc của các bảng biểu (Tables) dưới định dạng Markdown. "
        "Giúp lấy số liệu chính xác để làm Quiz."
    )
    args_schema: type[BaseModel] = VisualSummarizationInput

    def _run(self, file_path: str) -> str:
        try:
            from coach.visual_parser import parse_document_to_markdown

            markdown_content = parse_document_to_markdown(file_path)
            
            # Truncate if too long (LLMs usually have context limits)
            max_len = 15000
            if len(markdown_content) > max_len:
                return (
                    f"✅ Đã trích xuất thành công {file_path}:\n\n"
                    f"{markdown_content[:max_len]}\n\n"
                    "...(Nội dung đã bị cắt bớt do quá dài)..."
                )
            
            return f"✅ Đã trích xuất thành công {file_path}:\n\n{markdown_content}"

        except RuntimeError as exc:
            return f"[Lỗi] {exc}"
        except FileNotFoundError as exc:
            return f"[Lỗi] Không tìm thấy file: {exc}"
        except Exception as exc:
            logger.exception("Visual summarization failed")
            return f"[Lỗi] Visual summarization thất bại: {exc}"

    async def _arun(self, file_path: str) -> str:
        return self._run(file_path)



# ---------------------------------------------------------------------------
# Quiz Generator Tool (Instructor + Pydantic)
# ---------------------------------------------------------------------------

class QuizGeneratorInput(BaseModel):
    """Input schema for the quiz generator tool."""
    context_text: str = Field(
        description="Đoạn văn bản, JSON tóm tắt, hoặc thông tin để dựa vào đó sinh câu hỏi Quiz.",
    )
    num_questions: int = Field(
        default=3,
        description="Số lượng câu hỏi cần sinh ra.",
    )
    bloom_level: str = Field(
        default="remember",
        description="Mức độ Bloom: 'remember' (Nhận biết), 'understand' (Thông hiểu), 'apply' (Vận dụng tình huống).",
    )
    use_yake: bool = Field(
        default=False,
        description="Nếu True, dùng YAKE quét văn bản lấy từ khóa làm đáp án nhiễu (distractors).",
    )


class QuizGeneratorTool(BaseTool):
    """Công cụ sinh cấu trúc Quiz chuẩn xác bằng thư viện Instructor.

    Sử dụng khi bạn cần tạo một bài kiểm tra (Quiz) từ một nội dung có sẵn.
    Công cụ này ép LLM phải trả về định dạng JSON nghiêm ngặt với mỗi câu hỏi
    bắt buộc có 4 đáp án (1 đúng, 3 sai) và 1 lời giải thích chi tiết.
    """

    name: str = "generate_quiz"
    description: str = (
        "Nhận vào nội dung kiến thức và sinh ra JSON bộ câu hỏi Quiz đạt chuẩn. "
        "Bắt buộc ép LLM mỗi câu phải có 4 đáp án (1 đúng, 3 sai) và giải thích rõ ràng. "
        "Hỗ trợ phân bậc Bloom (remember/understand/apply) và trích xuất đáp án nhiễu bằng YAKE."
    )
    args_schema: type[BaseModel] = QuizGeneratorInput

    def _run(self, context_text: str, num_questions: int = 3, bloom_level: str = "remember", use_yake: bool = False) -> str:
        try:
            from coach.quiz_generator import generate_quiz

            quiz_obj = generate_quiz(
                context_text, 
                num_questions=num_questions, 
                bloom_level=bloom_level,
                use_yake_distractors=use_yake
            )

            # Format as readable JSON string
            return f"✅ Đã tạo Quiz ({bloom_level.upper()}) thành công:\n```json\n{quiz_obj.model_dump_json(indent=2)}\n```"

        except RuntimeError as exc:
            return f"[Lỗi] {exc}"
        except Exception as exc:
            logger.exception("Quiz generation failed")
            return f"[Lỗi] Quiz generation thất bại: {exc}"

    async def _arun(self, context_text: str, num_questions: int = 3, bloom_level: str = "remember", use_keybert: bool = False) -> str:
        return self._run(context_text, num_questions, bloom_level, use_keybert)


# ---------------------------------------------------------------------------
# Keyword Extractor Tool (YAKE)
# ---------------------------------------------------------------------------

class KeywordExtractorInput(BaseModel):
    """Input schema for the keyword extractor tool."""
    context_text: str = Field(description="Đoạn văn bản cần trích xuất từ khóa.")
    top_n: int = Field(default=5, description="Số lượng từ khóa cần lấy.")

class KeywordExtractorTool(BaseTool):
    """Công cụ trích xuất từ khóa chuyên ngành bằng YAKE.
    
    Sử dụng khi bạn cần lấy các thuật ngữ chính trong một đoạn văn bản (không cần gọi LLM) 
    để làm đáp án sai (distractors) hoặc gợi ý tags.
    """
    name: str = "extract_keywords"
    description: str = (
        "Trích xuất từ khóa (Keywords) từ văn bản bằng thuật toán NLP siêu nhẹ (YAKE). "
        "Dùng để lấy các thuật ngữ chuyên ngành cùng nhóm làm đáp án nhiễu (distractors) "
        "hoặc gắn tag cho bài học."
    )
    args_schema: type[BaseModel] = KeywordExtractorInput

    def _run(self, context_text: str, top_n: int = 5) -> str:
        try:
            from coach.distractor_generator import extract_distractors
            keywords = extract_distractors(context_text, correct_answer="", top_n=top_n)
            return "✅ Các từ khóa được trích xuất:\n- " + "\n- ".join(keywords)
        except RuntimeError as exc:
            return f"[Lỗi] {exc}"
        except Exception as exc:
            logger.exception("Keyword extraction failed")
            return f"[Lỗi] Trích xuất từ khóa thất bại: {exc}"

    async def _arun(self, context_text: str, top_n: int = 5) -> str:
        return self._run(context_text, top_n)


# ---------------------------------------------------------------------------
# Evaluation Tool (Ragas-style LLM-as-a-judge)
# ---------------------------------------------------------------------------

class QuizEvaluatorInput(BaseModel):
    """Input schema for the quiz evaluator tool."""
    context_text: str = Field(description="Tài liệu gốc (Context) dùng để đối chiếu.")
    question: str = Field(description="Câu hỏi trắc nghiệm cần đánh giá.")
    correct_answer: str = Field(description="Đáp án đúng của câu hỏi đó.")

class QuizEvaluatorTool(BaseTool):
    """Công cụ đánh giá chất lượng Quiz (LLM-as-a-judge).
    
    Mô phỏng thuật toán Ragas để chấm điểm Faithfulness (Tính trung thực) 
    và Answer Relevance (Tính bám sát) của một câu hỏi trắc nghiệm.
    """
    name: str = "evaluate_quiz"
    description: str = (
        "Đánh giá chất lượng của một câu hỏi trắc nghiệm so với tài liệu gốc. "
        "Chấm điểm từ 0-100 cho Faithfulness (tránh bịa đặt) và Answer Relevance (tránh lạc đề). "
        "Dùng để kiểm định lại câu hỏi trước khi lưu vào Database."
    )
    args_schema: type[BaseModel] = QuizEvaluatorInput

    def _run(self, context_text: str, question: str, correct_answer: str) -> str:
        try:
            from coach.evaluator import evaluate_quiz_question
            eval_result = evaluate_quiz_question(
                question=question,
                correct_answer=correct_answer,
                context_text=context_text
            )
            # Format as readable JSON string
            return eval_result.model_dump_json(indent=2)
        except Exception as e:
            return f"Error running QuizEvaluatorTool: {e}"

    async def _arun(self, context_text: str, question: str, correct_answer: str) -> str:
        return self._run(context_text, question, correct_answer)

# ---------------------------------------------------------------------------
# Error Analysis Tool (Misconception Tagging)
# ---------------------------------------------------------------------------

class ErrorAnalysisInput(BaseModel):
    """Input schema for the error analysis tool."""
    question: str = Field(description="Câu hỏi trắc nghiệm.")
    correct_answer: str = Field(description="Đáp án đúng.")
    user_answer: str = Field(description="Đáp án sai mà người dùng đã chọn.")
    context_text: Optional[str] = Field(default=None, description="Tài liệu tham khảo (nếu có).")

class ErrorAnalysisTool(BaseTool):
    """Công cụ phân tích lỗi sai và lỗ hổng kiến thức (Misconception).
    
    Đọc câu hỏi, đáp án đúng và đáp án sai người dùng chọn để chẩn đoán xem 
    người dùng đang bị nhầm lẫn khái niệm gì, từ đó gắn nhãn lỗi sai.
    """
    name: str = "analyze_error"
    description: str = (
        "Phân tích lỗi sai của học viên. Nhận vào Câu hỏi, Đáp án Đúng và Đáp án Sai người dùng chọn. "
        "Trả về một JSON chẩn đoán chi tiết 'lỗ hổng kiến thức' (misconception) của họ để lưu vào CSDL."
    )
    args_schema: type[BaseModel] = ErrorAnalysisInput

    def _run(self, question: str, correct_answer: str, user_answer: str, context_text: Optional[str] = None) -> str:
        try:
            from coach.error_analyzer import analyze_user_error
            eval_result = analyze_user_error(
                question=question,
                correct_answer=correct_answer,
                user_answer=user_answer,
                context_text=context_text
            )
            # Format as readable JSON string
            return eval_result.model_dump_json(indent=2)
        except Exception as e:
            return f"Error running ErrorAnalysisTool: {e}"

    async def _arun(self, question: str, correct_answer: str, user_answer: str, context_text: Optional[str] = None) -> str:
        return self._run(question, correct_answer, user_answer, context_text)

# ---------------------------------------------------------------------------
# Spaced Repetition Tool (FSRS Algorithm)
# ---------------------------------------------------------------------------

class SpacedRepetitionInput(BaseModel):
    """Input schema for spaced repetition."""
    is_correct: bool = Field(description="Học viên đã trả lời đúng (True) hay sai (False)?")
    previous_card_json: Optional[str] = Field(default=None, description="Chuỗi JSON state của lần học trước (nếu có).")

class SpacedRepetitionTool(BaseTool):
    """Công cụ Lập lịch Ôn tập Ngắt quãng (Spaced Repetition).
    
    Áp dụng thuật toán FSRS (của phần mềm Anki) để tính toán số ngày 
    và thời điểm chính xác cần nhắc lại câu hỏi (hoặc lỗ hổng kiến thức) này 
    để chống quên lãng.
    """
    name: str = "schedule_review"
    description: str = (
        "Tính toán lịch hẹn ôn tập lại. Nhận vào kết quả Đúng/Sai của User. "
        "Trả về ngày giờ nhắc lại (next_review_iso) và số ngày giãn cách (scheduled_days)."
    )
    args_schema: type[BaseModel] = SpacedRepetitionInput

    def _run(self, is_correct: bool, previous_card_json: Optional[str] = None) -> str:
        try:
            from coach.spaced_repetition import schedule_next_review
            result = schedule_next_review(
                is_correct=is_correct,
                previous_card_json=previous_card_json
            )
            # Format as readable JSON string
            return result.model_dump_json(indent=2)
        except Exception as e:
            return f"Error running SpacedRepetitionTool: {e}"

    async def _arun(self, is_correct: bool, previous_card_json: Optional[str] = None) -> str:
        return self._run(is_correct, previous_card_json)


# ---------------------------------------------------------------------------
# Convenience: get all tools as a list
# ---------------------------------------------------------------------------

def get_retrieval_tools() -> list[BaseTool]:
    """Return all retrieval tools for use in an agent."""
    return [
        SemanticSearchTool(),
        KeywordSearchTool(),
        CompressedSearchTool(),
        StructuredSummaryTool(),
        VisualSummarizationTool(),
        QuizGeneratorTool(),
        KeywordExtractorTool(),
        QuizEvaluatorTool(),
        ErrorAnalysisTool(),
        SpacedRepetitionTool(),
    ]



