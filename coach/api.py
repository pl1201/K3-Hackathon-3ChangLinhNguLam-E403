from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from coach.config import get_settings
from coach.graph import CoachState, coach_graph
from coach.observability import invocation_context, score_feedback
from coach.schemas import (
    AnswerRequest,
    FeedbackRequest,
    SessionResponse,
    StartSessionRequest,
)


ROOT = Path(__file__).resolve().parents[1]
CODEBASE = ROOT / "codebase"
SESSIONS: dict[str, CoachState] = {}

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
        "langfuse": "configured" if settings.tracing_enabled else "disabled",
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


@app.get("/")
def index() -> FileResponse:
    return FileResponse(CODEBASE / "index.html")


app.mount("/", StaticFiles(directory=CODEBASE), name="static")
