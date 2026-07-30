from __future__ import annotations

from typing import Literal, TypedDict
from uuid import uuid4

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from coach.config import Settings, get_settings
from coach.observability import langchain_callbacks, typed_observation
from coach.prompt_registry import compile_prompt
from coach.prompts import EVALUATION_PROMPT, QUESTION_PROMPT
from coach.retrieval import Chunk, format_context, load_lesson, retrieve
from coach.schemas import AnswerEvaluation, RecallQuestion, SourceReference


class CoachState(TypedDict, total=False):
    operation: Literal["start", "answer"]
    session_id: str
    user_id: str
    lesson_id: str
    answer: str
    chunks: list[dict[str, str]]
    context: str
    question: dict
    evaluation: dict
    phase: str
    progress: int
    mode: Literal["live", "mock"]


def _model(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=0.1,
        timeout=settings.llm_timeout_seconds,
        max_retries=2,
        api_key=settings.openai_api_key,
        callbacks=langchain_callbacks(),
    )


def retrieve_context(state: CoachState) -> CoachState:
    question = RecallQuestion.model_validate(state["question"]) if state.get("question") else None
    query = (
        "transformer attention generative AI kiến thức cốt lõi"
        if state["operation"] == "start"
        else f"{question.prompt} {state.get('answer', '')}"
    )
    with typed_observation("retriever", "retrieve-transcript-context") as observation:
        observation.update(
            input={"query": query, "lesson_id": state["lesson_id"], "top_k": 6},
            metadata={"retrieval_method": "lexical-overlap", "source": "vlearn-transcript"},
        )
        chunks = retrieve(state["lesson_id"], query)
        if state["operation"] == "start" and not any(chunk.chunk_id == "T06-051" for chunk in chunks):
            anchor = next(
                (chunk for chunk in load_lesson(state["lesson_id"]) if chunk.chunk_id == "T06-051"),
                None,
            )
            if anchor:
                chunks = [anchor, *chunks[:-1]]
        observation.update(
            output={
                "chunk_ids": [chunk.chunk_id for chunk in chunks],
                "chunk_count": len(chunks),
            }
        )
    return {
        "chunks": [
            {"chunk_id": chunk.chunk_id, "text": chunk.text, "lesson_id": chunk.lesson_id}
            for chunk in chunks
        ],
        "context": format_context(chunks, get_settings().max_context_chars),
    }


def _mock_question(chunks: list[dict[str, str]]) -> RecallQuestion:
    source = next((c for c in chunks if c["chunk_id"] == "T06-051"), chunks[0])
    return RecallQuestion(
        question_id=f"q-{uuid4().hex[:10]}",
        prompt=(
            "Theo bài giảng, Discriminative AI và Generative AI khác nhau ở "
            "chức năng đầu ra như thế nào?"
        ),
        expected_points=[
            "Discriminative AI dùng để phân loại hoặc dự đoán.",
            "Generative AI nhận prompt và tạo nội dung.",
        ],
        source_ids=[source["chunk_id"]],
        difficulty="foundation",
    )


def generate_question(state: CoachState) -> CoachState:
    settings = get_settings()
    if not settings.llm_enabled:
        if not settings.enable_mock_fallback:
            raise RuntimeError("OPENAI_API_KEY is required when mock fallback is disabled")
        return {
            "question": _mock_question(state["chunks"]).model_dump(),
            "phase": "question",
            "progress": 15,
            "mode": "mock",
        }
    prompt = compile_prompt(
        "active-recall/question-generator",
        QUESTION_PROMPT,
        context=state["context"],
    )
    question = _model(settings).with_structured_output(RecallQuestion).invoke(
        prompt,
        config={"run_name": "generate-recall-question"},
    )
    allowed = {chunk["chunk_id"] for chunk in state["chunks"]}
    with typed_observation("guardrail", "validate-question-citations") as observation:
        valid = bool(question.source_ids and set(question.source_ids).issubset(allowed))
        observation.update(
            input={"source_ids": question.source_ids, "allowed_source_ids": sorted(allowed)},
            output={"passed": valid},
        )
        if not valid:
            raise ValueError("Question contains an invalid or missing citation")
    return {"question": question.model_dump(), "phase": "question", "progress": 15, "mode": "live"}


def _mock_evaluation(state: CoachState) -> AnswerEvaluation:
    normalized = state["answer"].strip().lower()
    source = next((c for c in state["chunks"] if c["chunk_id"] == "T06-051"), state["chunks"][0])
    if len(normalized.split()) < 4:
        return AnswerEvaluation(
            verdict="ambiguous",
            score=0.25,
            feedback="Câu trả lời còn quá ngắn để mình kết luận. Bạn có thể nói rõ đầu ra của từng nhóm AI không?",
            next_action="clarify",
        )
    has_discriminative = any(term in normalized for term in ("phân loại", "dự đoán", "gán nhãn"))
    has_generative = any(term in normalized for term in ("tạo", "sinh", "content", "nội dung"))
    if has_discriminative and has_generative:
        return AnswerEvaluation(
            verdict="correct",
            score=1,
            evidence=[SourceReference(chunk_id=source["chunk_id"], quote=source["text"][:300])],
            feedback="Đúng trọng tâm: một bên phân loại/dự đoán, một bên sinh nội dung từ prompt.",
            next_action="next",
        )
    return AnswerEvaluation(
        verdict="incorrect",
        score=0.45,
        knowledge_gaps=["Chưa phân biệt rõ loại đầu ra của hai nhóm AI."],
        evidence=[SourceReference(chunk_id=source["chunk_id"], quote=source["text"][:300])],
        feedback="Bạn đã chạm tới chủ đề nhưng còn thiếu sự khác nhau về đầu ra. Hãy đối chiếu đoạn nguồn rồi thử giải thích lại.",
        next_action="remediate",
    )


def evaluate_answer(state: CoachState) -> CoachState:
    settings = get_settings()
    if not settings.llm_enabled:
        if not settings.enable_mock_fallback:
            raise RuntimeError("OPENAI_API_KEY is required when mock fallback is disabled")
        evaluation = _mock_evaluation(state)
        return {"evaluation": evaluation.model_dump(), "mode": "mock"}
    question = RecallQuestion.model_validate(state["question"])
    prompt = compile_prompt(
        "active-recall/answer-evaluator",
        EVALUATION_PROMPT,
        question=question.prompt,
        expected_points="\n".join(f"- {item}" for item in question.expected_points),
        answer=state["answer"],
        context=state["context"],
    )
    evaluation = _model(settings).with_structured_output(AnswerEvaluation).invoke(
        prompt,
        config={"run_name": "evaluate-recall-answer"},
    )
    allowed = {chunk["chunk_id"] for chunk in state["chunks"]}
    with typed_observation("guardrail", "validate-evaluation-citations") as observation:
        evidence = [item for item in evaluation.evidence if item.chunk_id in allowed]
        passed = evaluation.verdict not in {"correct", "incorrect"} or bool(evidence)
        observation.update(
            input={
                "verdict": evaluation.verdict,
                "source_ids": [item.chunk_id for item in evaluation.evidence],
                "allowed_source_ids": sorted(allowed),
            },
            output={"passed": passed, "valid_source_ids": [item.chunk_id for item in evidence]},
        )
        if not passed:
            evaluation = AnswerEvaluation(
                verdict="unsupported",
                score=0,
                feedback="Mình chưa có đủ căn cứ hợp lệ trong bài để đánh giá câu trả lời này.",
                next_action="stop",
            )
        else:
            evaluation.evidence = evidence
    return {"evaluation": evaluation.model_dump(), "mode": "live"}


def route_evaluation(state: CoachState) -> str:
    return state["evaluation"]["next_action"]


def complete_next(state: CoachState) -> CoachState:
    return {"phase": "complete", "progress": 100}


def ask_clarification(state: CoachState) -> CoachState:
    return {"phase": "clarify", "progress": 40}


def remediate(state: CoachState) -> CoachState:
    return {"phase": "remediate", "progress": 55}


def stop_unsupported(state: CoachState) -> CoachState:
    return {"phase": "unsupported", "progress": 30}


def operation_route(state: CoachState) -> str:
    return state["operation"]


builder = StateGraph(CoachState)
builder.add_node("retrieve-context", retrieve_context)
builder.add_node("generate-question", generate_question)
builder.add_node("evaluate-answer", evaluate_answer)
builder.add_node("complete-session", complete_next)
builder.add_node("ask-clarification", ask_clarification)
builder.add_node("remediate-gap", remediate)
builder.add_node("stop-unsupported", stop_unsupported)
builder.add_conditional_edges(START, operation_route, {"start": "retrieve-context", "answer": "retrieve-context"})
builder.add_conditional_edges(
    "retrieve-context",
    operation_route,
    {"start": "generate-question", "answer": "evaluate-answer"},
)
builder.add_edge("generate-question", END)
builder.add_conditional_edges(
    "evaluate-answer",
    route_evaluation,
    {
        "next": "complete-session",
        "clarify": "ask-clarification",
        "remediate": "remediate-gap",
        "stop": "stop-unsupported",
    },
)
builder.add_edge("complete-session", END)
builder.add_edge("ask-clarification", END)
builder.add_edge("remediate-gap", END)
builder.add_edge("stop-unsupported", END)

coach_graph = builder.compile(checkpointer=InMemorySaver())
