"""Pydantic schemas for Spaced Repetition using FSRS.

Defines the output structure for scheduling the next review date.
"""

from pydantic import BaseModel, Field

class SpacedRepetitionResult(BaseModel):
    """Kết quả tính toán lịch ôn tập ngắt quãng (Spaced Repetition)."""
    
    is_correct: bool = Field(
        description="Người dùng trả lời đúng hay sai trong lần kiểm tra này."
    )
    scheduled_days: float = Field(
        description="Số ngày tính toán tới lần ôn tập tiếp theo. (VD: 0.0 là ôn lại ngay lập tức, 3.5 là ôn lại sau 3.5 ngày)."
    )
    next_review_iso: str = Field(
        description="Thời điểm chính xác theo chuẩn ISO 8601 để nhắc lại câu hỏi này (hoặc khái niệm bị hổng)."
    )
    card_state_json: str = Field(
        description="Dữ liệu state mã hoá của thuật toán FSRS để lưu vào Database. Trong lần tính toán kế tiếp, hãy nạp state này vào thuật toán."
    )
