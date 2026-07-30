"""Pydantic schemas for structured summarization using Instructor.

Defines the rigid JSON structure the LLM must return when summarizing content
for Quiz generation.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

class MicroFact(BaseModel):
    """Một thông tin hoặc định nghĩa cụ thể, ngắn gọn, có tính đúng/sai rõ ràng."""
    fact: str = Field(
        description="Nội dung sự thật (ví dụ: 'Transformer được Google giới thiệu năm 2017').",
        max_length=150,
    )
    is_core_concept: bool = Field(
        description="Đánh dấu True nếu đây là khái niệm lõi bắt buộc phải nhớ, False nếu là thông tin phụ trợ.",
    )

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
        description="Giải thích chi tiết tại sao đáp án đúng lại đúng, và tại sao các đáp án sai lại sai.",
    )
    source_file: Optional[str] = Field(
        default=None,
        description="Tên file hoặc nguồn tài liệu gốc của kiến thức (nếu có trong Text đầu vào).",
    )
    page_number: Optional[int] = Field(
        default=None,
        description="Số trang, vị trí dòng, hoặc ID đoạn văn để tham chiếu (nếu có trong Text đầu vào).",
    )

class QuizModel(BaseModel):
    """Một bộ câu hỏi trắc nghiệm (Quiz) hoàn chỉnh."""
    title: str = Field(
        description="Tiêu đề của bộ Quiz (ví dụ: 'Quiz: Kiến trúc Transformer').",
    )
    questions: List[QuizQuestion] = Field(
        description="Danh sách các câu hỏi trong bộ Quiz.",
        min_length=1,
    )

