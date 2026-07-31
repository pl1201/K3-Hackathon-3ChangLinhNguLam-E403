from typing import Literal

from pydantic import BaseModel, Field


Verdict = Literal["correct", "incorrect", "ambiguous", "unsupported"]
NextAction = Literal["next", "clarify", "remediate", "stop"]


class SourceReference(BaseModel):
    chunk_id: str
    quote: str = Field(min_length=1, max_length=400)


class RecallQuestion(BaseModel):
    question_id: str
    prompt: str = Field(min_length=10)
    expected_points: list[str] = Field(min_length=1, max_length=4)
    source_ids: list[str] = Field(min_length=1)
    difficulty: Literal["foundation", "application"] = "foundation"


class AnswerEvaluation(BaseModel):
    verdict: Verdict
    score: float = Field(ge=0, le=1)
    knowledge_gaps: list[str] = Field(default_factory=list, max_length=4)
    evidence: list[SourceReference] = Field(default_factory=list, max_length=4)
    feedback: str = Field(min_length=1, max_length=1200)
    next_action: NextAction


class StartSessionRequest(BaseModel):
    lesson_id: str = "transcript-06-clean"
    user_id: str = "demo-user"


class AnswerRequest(BaseModel):
    session_id: str
    answer: str = Field(min_length=1, max_length=4000)


class FeedbackRequest(BaseModel):
    trace_id: str
    value: bool
    comment: str | None = Field(default=None, max_length=1000)


class SessionResponse(BaseModel):
    session_id: str
    lesson_id: str
    phase: str
    question: RecallQuestion | None = None
    evaluation: AnswerEvaluation | None = None
    progress: int = Field(ge=0, le=100)
    trace_id: str | None = None
    mode: Literal["live", "mock"]


class TranscriptChunkResponse(BaseModel):
    chunk_id: str = Field(pattern=r"^T\d{2}-\d{3}$")
    text: str = Field(min_length=1)


class TranscriptResponse(BaseModel):
    lesson_id: str
    total_chunks: int = Field(ge=1)
    chunks: list[TranscriptChunkResponse] = Field(min_length=1)
