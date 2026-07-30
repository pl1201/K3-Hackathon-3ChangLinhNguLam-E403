from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from coach.config import get_settings
from coach.graph import CoachState, coach_graph
from coach.observability import invocation_context, score_feedback
from coach.quiz_graph import QuizState, extract_json, quiz_graph
from coach.schemas import (
    AnswerRequest,
    FeedbackRequest,
    SessionResponse,
    StartSessionRequest,
)
from coach.schemas_quiz import (
    EssayAnswerRequest,
    EssayResultResponse,
    EssaySessionResponse,
    EssayStartRequest,
    PublicQuizOption,
    PublicQuizQuestion,
    PublicEssayQuestion,
    QuizAnswerRequest,
    QuizModel,
    QuizSessionResponse,
    QuizStartRequest,
    SummaryRequest,
    SummaryResponse,
)


ROOT = Path(__file__).resolve().parents[1]
CODEBASE = ROOT / "codebase"
SESSIONS: dict[str, CoachState] = {}
QUIZ_SESSIONS: dict[str, QuizState] = {}
ESSAY_SESSIONS: dict[str, dict] = {}

app = FastAPI(title="Active Recall Coach API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _new_trace_id() -> str:
    from langfuse import Langfuse

    return Langfuse.create_trace_id()


def _response(state: CoachState, trace_id: str | None) -> SessionResponse:
    return SessionResponse(
        session_id=state["session_id"],
        lesson_id=state["lesson_id"],
        phase=state["phase"],
        question=state.get("question"),
        evaluation=state.get("evaluation"),
        progress=state["progress"],
        trace_id=trace_id,
        mode=state["mode"],
    )


def _invoke(state: CoachState, trace_id: str, operation: str) -> CoachState:
    context = invocation_context(
        trace_id=trace_id,
        session_id=state["session_id"],
        user_id=state["user_id"],
        operation=operation,
        trace_input=(
            {
                "question_id": state.get("question", {}).get("question_id"),
                "answer": state.get("answer"),
            }
            if operation == "evaluate-answer"
            else {"lesson_id": state["lesson_id"]}
        ),
    )
    config = {
        "configurable": {"thread_id": state["session_id"]},
        "run_name": f"active-recall-{operation}",
    }
    with context as root:
        result = coach_graph.invoke(state, config=config)
        if root is not None and hasattr(root, "update"):
            root.update(
                output=(
                    {
                        "verdict": result.get("evaluation", {}).get("verdict"),
                        "feedback": result.get("evaluation", {}).get("feedback"),
                        "next_action": result.get("evaluation", {}).get("next_action"),
                    }
                    if operation == "evaluate-answer"
                    else {
                        "question_id": result.get("question", {}).get("question_id"),
                        "question": result.get("question", {}).get("prompt"),
                        "phase": result["phase"],
                    }
                )
            )
    return result


@app.get("/api/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "llm": "configured" if settings.llm_enabled else "mock-fallback",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "langfuse": "configured" if settings.tracing_enabled else "disabled",
        "quiz_tools": "available",
    }


@app.post("/api/sessions", response_model=SessionResponse)
def start_session(payload: StartSessionRequest) -> SessionResponse:
    session_id = uuid4().hex
    trace_id = _new_trace_id()
    state: CoachState = {
        "operation": "start",
        "session_id": session_id,
        "user_id": payload.user_id,
        "lesson_id": payload.lesson_id,
        "phase": "starting",
        "progress": 0,
        "mode": "live" if get_settings().llm_enabled else "mock",
    }
    try:
        result = _invoke(state, trace_id, "start")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Coach could not start: {exc}") from exc
    result["trace_id"] = trace_id
    SESSIONS[session_id] = result
    return _response(result, trace_id)


@app.post("/api/answers", response_model=SessionResponse)
def submit_answer(payload: AnswerRequest) -> SessionResponse:
    previous = SESSIONS.get(payload.session_id)
    if not previous:
        raise HTTPException(status_code=404, detail="Session not found")
    trace_id = _new_trace_id()
    state: CoachState = {
        **previous,
        "operation": "answer",
        "answer": payload.answer,
    }
    try:
        result = _invoke(state, trace_id, "evaluate-answer")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Answer evaluation failed: {exc}") from exc
    result["trace_id"] = trace_id
    SESSIONS[payload.session_id] = result
    return _response(result, trace_id)


@app.post("/api/feedback")
def feedback(payload: FeedbackRequest) -> dict:
    accepted = score_feedback(payload.trace_id, payload.value, payload.comment)
    return {"accepted": accepted, "reason": None if accepted else "Langfuse is not configured"}


def _public_quiz_question(quiz: QuizModel) -> PublicQuizQuestion:
    question = quiz.questions[0]
    return PublicQuizQuestion(
        question_text=question.question_text,
        options=[
            PublicQuizOption(index=index, text=option.text)
            for index, option in enumerate(question.options)
        ],
        source_file=question.source_file,
        page_number=question.page_number,
    )


def _public_quiz_question_at(quiz: QuizModel, idx: int) -> PublicQuizQuestion:
    """Return a public question at the given index (clamped to valid range)."""
    q_idx = min(idx, len(quiz.questions) - 1)
    question = quiz.questions[q_idx]
    return PublicQuizQuestion(
        question_text=question.question_text,
        options=[
            PublicQuizOption(index=index, text=option.text)
            for index, option in enumerate(question.options)
        ],
        source_file=question.source_file,
        page_number=question.page_number,
    )




def _quiz_from_state(state: QuizState) -> QuizModel | None:
    if not state.get("quiz_json"):
        return None
    try:
        return QuizModel.model_validate(extract_json(state["quiz_json"]))
    except (TypeError, ValueError):
        return None


def _error_analysis_from_state(state: QuizState) -> dict | None:
    raw = state.get("error_analysis_json")
    if not raw:
        return None
    try:
        return extract_json(raw)
    except (TypeError, ValueError):
        return {"detail": raw}


def _short_explanation(text: str, max_chars: int = 260) -> str:
    """Keep learner-facing feedback concise even if a provider is verbose."""
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rsplit(" ", 1)[0] + "…"


def _short_reference_answer(text: str, max_chars: int = 450) -> str:
    """Return a compact model answer suitable for quick learner review."""
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact

    shortened = compact[: max_chars + 1]
    sentence_end = max(
        shortened.rfind("."),
        shortened.rfind("?"),
        shortened.rfind("!"),
    )
    if sentence_end >= 100:
        return shortened[: sentence_end + 1]
    return shortened[:max_chars].rsplit(" ", 1)[0] + "…"


@app.post("/api/essay/sessions", response_model=EssaySessionResponse)
async def start_essay_session(payload: EssayStartRequest) -> EssaySessionResponse:
    if not get_settings().llm_enabled:
        raise HTTPException(status_code=503, detail="A configured LLM provider is required")

    from coach.content_sources import load_lesson_context
    from coach.essay import generate_essay_question

    try:
        context = await run_in_threadpool(
            lambda: load_lesson_context(
                payload.lesson_id,
                payload.topic_query,
                max_chars=16_000,
                chunk_limit=8,
            )
        )
        question = await run_in_threadpool(
            lambda: generate_essay_question(context, payload.topic_query, payload.bloom_level)
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Essay generation failed: {exc}") from exc

    session_id = uuid4().hex
    ESSAY_SESSIONS[session_id] = {"question": question, "context": context}
    return EssaySessionResponse(
        session_id=session_id,
        question=PublicEssayQuestion(
            question_text=question.question_text,
            source_file=question.source_file,
            page_number=question.page_number,
            chunk_id=question.chunk_id,
        ),
    )


@app.post("/api/essay/answers", response_model=EssayResultResponse)
async def submit_essay_answer(payload: EssayAnswerRequest) -> EssayResultResponse:
    session = ESSAY_SESSIONS.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Essay session not found")

    from coach.essay import evaluate_essay_answer

    try:
        evaluation = await run_in_threadpool(
            lambda: evaluate_essay_answer(
                session["question"],
                payload.answer_text,
                session["context"],
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Essay evaluation failed: {exc}") from exc

    question = session["question"]
    return EssayResultResponse(
        session_id=payload.session_id,
        evaluation=evaluation,
        suggested_answer=_short_reference_answer(question.reference_answer),
        source_file=question.source_file,
        page_number=question.page_number,
        chunk_id=question.chunk_id,
    )


@app.post("/api/quiz/sessions", response_model=QuizSessionResponse)
async def start_quiz_session(payload: QuizStartRequest) -> QuizSessionResponse:
    if not get_settings().llm_enabled:
        raise HTTPException(status_code=503, detail="A configured LLM provider is required for quiz generation")

    session_id = uuid4().hex
    initial_state: QuizState = {
        "operation": "start",
        "session_id": session_id,
        "topic_query": payload.topic_query,
        "lesson_id": payload.lesson_id,
        "bloom_level": payload.bloom_level,
        "num_questions": payload.num_questions,
        "generation_attempts": 0,
        "max_generation_attempts": 3,
        "current_question_idx": 0,
        "phase": "generating",
    }
    config = {"configurable": {"thread_id": session_id}, "recursion_limit": 20}
    try:
        result = await run_in_threadpool(lambda: quiz_graph.invoke(initial_state, config=config))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Quiz generation failed: {exc}") from exc

    result["session_id"] = session_id
    QUIZ_SESSIONS[session_id] = result
    quiz = _quiz_from_state(result)
    total_q = payload.num_questions
    return QuizSessionResponse(
        session_id=session_id,
        phase=result.get("phase", "failed"),
        question=_public_quiz_question(quiz) if quiz and result.get("phase") == "waiting_for_answer" else None,
        generation_attempts=result.get("generation_attempts", 0),
        current_question_idx=result.get("current_question_idx", 0),
        total_questions=total_q,
    )


@app.post("/api/quiz/answers", response_model=QuizSessionResponse)
async def submit_quiz_answer(payload: QuizAnswerRequest) -> QuizSessionResponse:
    previous = QUIZ_SESSIONS.get(payload.session_id)
    if not previous:
        raise HTTPException(status_code=404, detail="Quiz session not found")

    previous_quiz = _quiz_from_state(previous)
    if not previous_quiz:
        raise HTTPException(status_code=409, detail="Quiz session has no valid question")
    current_idx = previous.get("current_question_idx", 0)
    q_idx = min(current_idx, len(previous_quiz.questions) - 1)
    selected = previous_quiz.questions[q_idx].options[payload.answer_index]
    is_correct = selected.is_correct

    answer_state: QuizState = {
        **previous,
        "operation": "answer",
        "user_answer_idx": payload.answer_index,
    }
    config = {"configurable": {"thread_id": payload.session_id}, "recursion_limit": 20}
    try:
        result = await run_in_threadpool(lambda: quiz_graph.invoke(answer_state, config=config))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Quiz answer processing failed: {exc}") from exc

    result["session_id"] = payload.session_id
    QUIZ_SESSIONS[payload.session_id] = result
    next_quiz = _quiz_from_state(result)
    next_idx = result.get("current_question_idx", 0)
    total_q = previous.get("num_questions", 20)
    return QuizSessionResponse(
        session_id=payload.session_id,
        phase=result.get("phase", "failed"),
        question=(
            _public_quiz_question_at(next_quiz, next_idx)
            if next_quiz and result.get("phase") == "waiting_for_answer"
            else None
        ),
        is_correct=is_correct,
        explanation=_short_explanation(previous_quiz.questions[q_idx].explanation),
        error_analysis=_error_analysis_from_state(result),
        review_source_file=previous_quiz.questions[q_idx].source_file,
        review_page_number=previous_quiz.questions[q_idx].page_number,
        generation_attempts=result.get("generation_attempts", 0),
        current_question_idx=next_idx,
        total_questions=total_q,
    )


SLIDES_DIR = ROOT / "data" / "vlearn-pack" / "slides"


# ─── Summarize Chat API ──────────────────────────────────────────
from pydantic import BaseModel as PydanticBaseModel
from typing import Optional
from fastapi.responses import StreamingResponse


@app.post("/api/structured-summary", response_model=SummaryResponse)
async def structured_summary(payload: SummaryRequest) -> SummaryResponse:
    """Return evidence-linked micro-facts for a fast lesson review."""
    from coach.content_sources import resolve_lesson_id
    from coach.structured_summarizer import summarize_lesson as build_summary

    effective_lesson_id = resolve_lesson_id(payload.lesson_id, payload.query)
    summary = await run_in_threadpool(
        lambda: build_summary(effective_lesson_id, payload.query)
    )
    return SummaryResponse(lesson_id=effective_lesson_id, summary=summary)

class SummarizeRequest(PydanticBaseModel):
    lesson_id: str
    user_query: Optional[str] = None

@app.post("/api/summarize")
async def summarize_lesson(payload: SummarizeRequest):
    """Summarize a lesson using AI, optionally focused on a user query."""
    settings = get_settings()
    if not settings.llm_enabled:
        raise HTTPException(status_code=503, detail="LLM not configured")

    from coach.content_sources import load_lesson_context
    from coach.llm_client import create_openai_compatible_client

    query = payload.user_query or "Tóm tắt toàn bộ nội dung chính của bài học này"

    try:
        context = await run_in_threadpool(
            lambda: load_lesson_context(
                payload.lesson_id,
                query,
                max_chars=24_000 if payload.lesson_id in ("day1", "day2") else 9_000,
                chunk_limit=12,
            )
        )
    except Exception:
        context = ""

    if not context or context.startswith("[Lỗi]"):
        async def error_gen():
            yield "Chưa tìm thấy nội dung phù hợp cho bài học này. Vui lòng thử lại hoặc chọn bài khác."
        return StreamingResponse(error_gen(), media_type="text/event-stream")

    client = create_openai_compatible_client(settings)

    system_prompt = (
        "Bạn là một Trợ giảng AI thông minh. "
        "Nhiệm vụ của bạn là tóm tắt nội dung bài giảng một cách ngắn gọn, rõ ràng, dễ hiểu. "
        "Trả lời bằng tiếng Việt, dùng markdown formatting (bold, bullets). "
        "Chỉ dựa trên nội dung được cung cấp, không bịa thêm thông tin. "
        "Mỗi ý kiến thức phải kết thúc bằng citation đúng từ metadata nguồn: "
        "dùng `[Trang X]` cho PDF và `[Txx-xxx]` cho transcript. "
        "Không tự tạo citation và không bỏ citation ở các ý chính."
    )

    user_msg = f"Dựa trên nội dung bài giảng sau:\n\n{context}\n\n"
    if payload.user_query:
        user_msg += f"Yêu cầu của học viên: {payload.user_query}"
    else:
        user_msg += "Hãy tóm tắt toàn bộ nội dung chính của bài giảng này thành các điểm trọng tâm."

    async def stream_generator():
        try:
            stream = await run_in_threadpool(
                lambda: client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.3,
                    stream=True,
                )
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:
            yield f"Đã xảy ra lỗi khi tóm tắt: {exc}"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

class StreamErrorRequest(PydanticBaseModel):
    session_id: str

@app.post("/api/quiz/stream_error")
async def stream_error_analysis(payload: StreamErrorRequest):
    settings = get_settings()
    if not settings.llm_enabled:
        raise HTTPException(status_code=503, detail="LLM not configured")

    state = QUIZ_SESSIONS.get(payload.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Quiz session not found")
        
    quiz = _quiz_from_state(state)
    if not quiz:
        raise HTTPException(status_code=409, detail="Quiz session has no valid question")
        
    current_idx = state.get("current_question_idx", 1) - 1 # because it was incremented
    q_idx = min(max(0, current_idx), len(quiz.questions) - 1)
    question = quiz.questions[q_idx]
    
    try:
        correct_answer = next(option.text for option in question.options if option.is_correct)
    except StopIteration:
        correct_answer = "Không có đáp án đúng"

    user_answer_idx = state.get("user_answer_idx", -1)
    if 0 <= user_answer_idx < len(question.options):
        user_answer = question.options[user_answer_idx].text
    else:
        user_answer = "Không rõ"
        
    context_text = state.get("context_text", "Không có tài liệu tham khảo cụ thể.")
    
    from coach.llm_client import create_openai_compatible_client
    from coach.error_analyzer import _ERROR_ANALYSIS_PROMPT
    
    user_prompt = _ERROR_ANALYSIS_PROMPT.format(
        question=question.question_text,
        correct_answer=correct_answer,
        user_answer=user_answer,
        context_text=context_text
    )

    client = create_openai_compatible_client(settings)

    async def stream_error():
        try:
            stream = await run_in_threadpool(
                lambda: client.chat.completions.create(
                    model=settings.fast_llm_model,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.2,
                    stream=True,
                )
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"Lỗi phân tích: {e}"

    return StreamingResponse(stream_error(), media_type="text/event-stream")


@app.get("/api/slides/{filename}")
def get_pdf_slide(filename: str) -> FileResponse:
    file_path = (SLIDES_DIR / filename).resolve()
    if not str(file_path).startswith(str(SLIDES_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Slide file not found")
    return FileResponse(file_path, media_type="application/pdf")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(CODEBASE / "index.html")


app.mount("/", StaticFiles(directory=CODEBASE), name="static")
