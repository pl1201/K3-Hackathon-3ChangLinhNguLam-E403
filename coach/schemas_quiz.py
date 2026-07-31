"""Pydantic schemas for structured summarization using Instructor.

Defines the rigid JSON structure the LLM must return when summarizing content
for Quiz generation.
"""

from typing import List, Literal, Optional, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

class MicroFact(BaseModel):
    """Một thông tin hoặc định nghĩa cụ thể, ngắn gọn, có tính đúng/sai rõ ràng."""
    fact: str = Field(
        description="Nội dung sự thật (ví dụ: 'Transformer được Google giới thiệu năm 2017').",
        max_length=180,
    )
    is_core_concept: bool = Field(
        description="Đánh dấu True nếu đây là khái niệm lõi bắt buộc phải nhớ, False nếu là thông tin phụ trợ.",
    )
    chunk_id: Optional[str] = Field(
        default=None,
        description="Mã đoạn văn bản trích dẫn trong transcript (vd: 'T06-051').",
    )
    page_number: Optional[int] = Field(
        default=None,
        description="Số trang slide hoặc vị trí trang tài liệu (nếu có).",
    )
    source_file: Optional[str] = Field(
        default=None,
        description="Tên file nguồn để mở lại đúng tài liệu.",
    )
    evidence_quote: Optional[str] = Field(
        default=None,
        max_length=320,
        description=(
            "Trích dẫn ngắn, nguyên văn từ đúng page/chunk, trực tiếp chứng minh cho fact. "
            "Không diễn giải lại nội dung nguồn."
        ),
    )

    @model_validator(mode="after")
    def transcript_fact_does_not_invent_page(self) -> Self:
        if self.chunk_id and not self.source_file:
            self.page_number = None
        return self

class Topic(BaseModel):
    """Một chủ đề lớn trong bài giảng, chứa nhiều sự thật vi mô (micro-facts)."""
    topic_name: str = Field(
        description="Tên chủ đề ngắn gọn (ví dụ: 'Kiến trúc Transformer').",
        max_length=100,
    )
    micro_facts: List[MicroFact] = Field(
        description="Danh sách các sự thật vi mô thuộc chủ đề này.",
        min_length=1,
    )

class StructuredSummary(BaseModel):
    """Bản tóm tắt toàn bộ nội dung dưới dạng cấu trúc phân cấp."""
    topics: List[Topic] = Field(
        description="Danh sách các chủ đề chính có trong văn bản.",
        min_length=1,
    )
    summary_notes: str = Field(
        description="Ghi chú thêm hoặc tóm tắt cực ngắn (1-2 câu) về toàn bộ nội dung.",
    )


class SummaryRequest(BaseModel):
    lesson_id: str = Field(default="transcript-06-clean", pattern=r"^[a-zA-Z0-9_-]+$")
    query: str | None = Field(default=None, min_length=3, max_length=300)


class SummaryResponse(BaseModel):
    lesson_id: str
    summary: StructuredSummary


# ---------------------------------------------------------------------------
# Quiz Generation Schemas
# ---------------------------------------------------------------------------

class QuizOption(BaseModel):
    """Một đáp án (lựa chọn) cho câu hỏi trắc nghiệm."""
    text: str = Field(description="Nội dung của đáp án (ngắn gọn, rõ ràng).")
    is_correct: bool = Field(description="Đánh dấu True nếu đây là đáp án đúng, False nếu là đáp án sai (nhiễu).")

class QuizQuestion(BaseModel):
    """Một câu hỏi trắc nghiệm hoàn chỉnh."""
    question_text: str = Field(
        description="Nội dung câu hỏi.",
    )
    options: List[QuizOption] = Field(
        description="Bắt buộc phải có đúng 4 đáp án (1 đúng, 3 sai).",
        min_length=4,
        max_length=4,
    )
    explanation: str = Field(
        description="Giải thích ngắn gọn 1-2 câu: nêu đáp án đúng và ý cốt lõi.",
        max_length=320,
    )
    source_file: Optional[str] = Field(
        default=None,
        description="Tên file hoặc nguồn tài liệu gốc của kiến thức (nếu có trong Text đầu vào).",
    )
    page_number: Optional[int] = Field(
        default=None,
        description="Số trang, vị trí dòng, hoặc ID đoạn văn để tham chiếu (nếu có trong Text đầu vào).",
    )

    @model_validator(mode="after")
    def has_exactly_one_correct_option(self) -> Self:
        if sum(option.is_correct for option in self.options) != 1:
            raise ValueError("quiz question must have exactly one correct option")
        return self


class QuizModel(BaseModel):
    """Một bộ câu hỏi trắc nghiệm (Quiz) hoàn chỉnh."""
    title: str = Field(
        description="Tiêu đề của bộ Quiz (ví dụ: 'Quiz: Kiến trúc Transformer').",
    )
    questions: List[QuizQuestion] = Field(
        description="Danh sách các câu hỏi trong bộ Quiz.",
        min_length=1,
    )


class QuizStartRequest(BaseModel):
    topic_query: str = Field(default="Transformer và Generative AI", min_length=3, max_length=300)
    lesson_id: str = Field(default="transcript-06-clean", pattern=r"^[a-zA-Z0-9_-]+$")
    num_questions: int = Field(default=20, ge=1, le=25, description="Số lượng câu hỏi trong bộ quiz (mặc định 20, tối đa 25).")
    bloom_level: Literal["remember", "understand", "apply", "analyze", "evaluate"] = "analyze"


class QuizAnswerRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    answer_index: int = Field(ge=0, le=3)


class PublicQuizOption(BaseModel):
    index: int = Field(ge=0, le=3)
    text: str


class PublicQuizQuestion(BaseModel):
    question_text: str
    options: list[PublicQuizOption] = Field(min_length=4, max_length=4)
    source_file: str | None = None
    page_number: int | None = None


class QuizSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    phase: Literal["waiting_for_answer", "remediating", "completed", "failed"]
    question: PublicQuizQuestion | None = None
    is_correct: bool | None = None
    explanation: str | None = None
    error_analysis: dict | None = None
    review_source_file: str | None = None
    review_page_number: int | None = None
    generation_attempts: int = Field(default=0, ge=0, le=3)
    current_question_idx: int = Field(default=0, ge=0, description="Index câu hiện tại (0-based).")
    total_questions: int = Field(default=20, ge=1, le=25, description="Tổng số câu trong bộ quiz.")


# ---------------------------------------------------------------------------
# Short Essay Schemas
# ---------------------------------------------------------------------------

class EssayReferenceEvidence(BaseModel):
    criterion: str = Field(min_length=3, max_length=180)
    answer_quote: str = Field(
        min_length=3,
        max_length=300,
        description="Trích dẫn nguyên văn từ reference_answer chứng minh tiêu chí đã được trả lời.",
    )


class EssayQuestion(BaseModel):
    question_text: str = Field(min_length=10, max_length=500)
    reference_answer: str = Field(min_length=20, max_length=500)
    rubric_points: list[str] = Field(min_length=2, max_length=5)
    rubric_evidence: list[EssayReferenceEvidence] = Field(min_length=2, max_length=5)
    source_file: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    chunk_id: str | None = Field(default=None, pattern=r"^T\d{2}-\d{3}$")

    @model_validator(mode="after")
    def transcript_question_does_not_invent_page(self) -> Self:
        if self.chunk_id and not self.source_file:
            self.page_number = None
        if len(self.rubric_evidence) != len(self.rubric_points):
            raise ValueError("mỗi tiêu chí rubric phải có đúng một bằng chứng trong đáp án mẫu")

        normalized_answer = " ".join(self.reference_answer.lower().split())
        for index, criterion in enumerate(self.rubric_points):
            evidence = self.rubric_evidence[index]
            if evidence.criterion.strip().lower() != criterion.strip().lower():
                raise ValueError("rubric_evidence phải giữ đúng thứ tự và nội dung rubric_points")
            if " ".join(evidence.answer_quote.lower().split()) not in normalized_answer:
                raise ValueError("answer_quote phải là trích dẫn nguyên văn từ reference_answer")
        return self


class EssayStartRequest(BaseModel):
    topic_query: str = Field(default="Nội dung bài học này", min_length=3, max_length=300)
    lesson_id: str = Field(default="transcript-06-clean", pattern=r"^[a-zA-Z0-9_-]+$")
    bloom_level: Literal["understand", "apply", "analyze", "evaluate"] = "analyze"


class EssayAnswerRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    answer_text: str = Field(min_length=10, max_length=5000)


class EssayCriterionAssessment(BaseModel):
    criterion: str = Field(max_length=180)
    status: Literal["met", "partial", "missing"]
    reason: str = Field(max_length=220)
    evidence_quote: str | None = Field(
        default=None,
        max_length=300,
        description="Trích dẫn nguyên văn ngắn từ câu trả lời học viên; bắt buộc khi met/partial.",
    )


class EssayLLMAssessment(BaseModel):
    criteria: list[EssayCriterionAssessment] = Field(min_length=1, max_length=5)
    feedback: str = Field(max_length=320)


class EssayRubricResult(BaseModel):
    criterion: str
    status: Literal["met", "partial", "missing"]
    reason: str
    evidence_quote: str | None = None


class EssayEvaluation(BaseModel):
    verdict: Literal["mastered", "developing", "needs_review"]
    feedback: str = Field(max_length=320)
    strengths: list[str] = Field(default_factory=list, max_length=3)
    missing_points: list[str] = Field(default_factory=list, max_length=3)
    rubric_breakdown: list[EssayRubricResult] = Field(default_factory=list, max_length=5)


class PublicEssayQuestion(BaseModel):
    question_text: str
    source_file: str | None = None
    page_number: int | None = None
    chunk_id: str | None = None


class EssaySessionResponse(BaseModel):
    session_id: str
    question: PublicEssayQuestion


class EssayResultResponse(BaseModel):
    session_id: str
    evaluation: EssayEvaluation
    suggested_answer: str = Field(
        max_length=500,
        description="Đáp án tham khảo ngắn, chỉ trả về sau khi học viên đã nộp bài.",
    )
    source_file: str | None = None
    page_number: int | None = None
    chunk_id: str | None = None
