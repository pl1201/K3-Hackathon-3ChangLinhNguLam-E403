"""Pydantic schemas for Error Analysis using Instructor.

Defines the JSON structure for analyzing why a user chose the wrong answer,
identifying their core misconception to be saved in the database.
"""

from typing import Optional
from pydantic import BaseModel, Field

class ErrorAnalysisResult(BaseModel):
    """Kết quả phân tích lỗi sai và lỗ hổng kiến thức của người dùng."""
    
    misconception_topic: str = Field(
        description="Chủ đề cốt lõi mà người dùng đang hiểu sai (VD: 'Sự khác biệt giữa Sơ đồ lớp và Sơ đồ trạng thái'). Càng ngắn gọn càng tốt.",
        max_length=150
    )
    misconception_explanation: str = Field(
        description="Giải thích chi tiết tại sao người dùng lại chọn đáp án sai đó, họ đang bị nhầm lẫn ở tư duy nào?",
    )
    recommended_reading: Optional[str] = Field(
        default=None,
        description="Từ khóa hoặc khái niệm gợi ý người dùng nên ôn tập lại để vá lỗ hổng này."
    )
