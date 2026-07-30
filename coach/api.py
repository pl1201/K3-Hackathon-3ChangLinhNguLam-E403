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
    PublicQuizOption,
    PublicQuizQuestion,
    QuizAnswerRequest,
    QuizModel,
    QuizSessionResponse,
    QuizStartRequest,
)


ROOT = Path(__file__).resolve().parents[1]
CODEBASE = ROOT / "codebase"
SESSIONS: dict[str, CoachState] = {}
QUIZ_SESSIONS: dict[str, QuizState] = {}

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
        explanation=previous_quiz.questions[q_idx].explanation,
        error_analysis=_error_analysis_from_state(result),
        generation_attempts=result.get("generation_attempts", 0),
        current_question_idx=next_idx,
        total_questions=total_q,
    )


SLIDES_DIR = ROOT / "data" / "vlearn-pack" / "slides"


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
