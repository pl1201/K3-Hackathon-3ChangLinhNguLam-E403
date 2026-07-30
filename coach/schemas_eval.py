"""Pydantic schemas for Ragas-style evaluation using LLM-as-a-judge.

Defines the structure for evaluating generated quiz questions.
"""

from pydantic import BaseModel, Field

class EvaluationResult(BaseModel):
    """Báo cáo đánh giá chất lượng của một câu hỏi trắc nghiệm (Quiz Question)."""
    
    faithfulness_score: int = Field(
        description="Điểm trung thực (0-100). Điểm cao nghĩa là câu trả lời ĐÚNG thực sự được suy ra từ văn bản nguồn, không phải do AI tự bịa ra (hallucination).",
        ge=0,
        le=100
    )
    faithfulness_reasoning: str = Field(
        description="Giải thích ngắn gọn tại sao lại cho điểm faithfulness như vậy.",
    )
    
    relevance_score: int = Field(
        description="Điểm bám sát câu hỏi (0-100). Điểm cao nghĩa là đáp án đúng giải quyết trực tiếp câu hỏi được đặt ra, không trả lời lan man, lạc đề.",
        ge=0,
        le=100
    )
    relevance_reasoning: str = Field(
        description="Giải thích ngắn gọn tại sao lại cho điểm relevance như vậy.",
    )
    
    overall_passed: bool = Field(
        description="Đánh giá tổng quan xem câu hỏi này có đạt chuẩn để hiển thị cho học viên không (VD: cả 2 điểm đều >= 70).",
    )
