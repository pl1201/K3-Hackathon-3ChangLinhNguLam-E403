"""Bounded LangGraph workflow for generating and remediating quizzes."""

from __future__ import annotations

import json
import logging
import re
import secrets
from typing import Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from coach.compression import compressed_retrieve
from coach.content_sources import load_lesson_context
from coach.schemas_quiz import QuizModel
from coach.tools import ErrorAnalysisTool, QuizEvaluatorTool, QuizGeneratorTool, SemanticSearchTool

logger = logging.getLogger(__name__)

search_tool = SemanticSearchTool()
quiz_tool = QuizGeneratorTool()
eval_tool = QuizEvaluatorTool()
error_tool = ErrorAnalysisTool()


class QuizState(TypedDict, total=False):
    operation: Literal["start", "answer"]
    session_id: str
    topic_query: str
    lesson_id: str
    num_questions: int
    bloom_level: Literal["remember", "understand", "apply", "analyze", "evaluate"]
    user_answer_idx: int
    context_text: str
    quiz_json: str
    eval_passed: bool
    error_analysis_json: str
    generation_attempts: int
    max_generation_attempts: int
    current_question_idx: int
    phase: Literal["generating", "waiting_for_answer", "remediating", "completed", "failed"]


def extract_json(text: str) -> dict:
    """Extract and parse the first fenced JSON block, or parse the full string."""
    fenced = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    payload = fenced.group(1) if fenced else text
    return json.loads(payload)


def _validated_quiz(state: QuizState) -> QuizModel:
    return QuizModel.model_validate(extract_json(state["quiz_json"]))


def shuffle_quiz_options(quiz: QuizModel) -> QuizModel:
    """Shuffle options once while preserving each option's correctness flag."""
    rng = secrets.SystemRandom()
    for question in quiz.questions:
        rng.shuffle(question.options)
    return quiz


def retrieve_context(state: QuizState) -> QuizState:
    if state.get("context_text"):
        return {}
    
    lesson_id = state.get("lesson_id", "transcript-06-clean")
    query = state.get("topic_query", "Kiến thức tổng hợp")

    if lesson_id in ("day1", "day2"):
        context = load_lesson_context(lesson_id, query, max_chars=16_000)
        return {"context_text": context, "phase": "generating"}

    try:
        context_docs = compressed_retrieve(
            lesson_id=lesson_id,
            query=query,
            mode="embeddings",
            similarity_threshold=0.3
        )
        context = "\n".join([doc.page_content for doc in context_docs])
    except Exception as exc:
        logger.warning(f"compressed_retrieve failed: {exc}")
        context = ""

    if not context:
        context = search_tool._run(query=query, lesson_id=lesson_id, top_k=6)
        
    return {"context_text": context, "phase": "generating"}


def generate_quiz(state: QuizState) -> QuizState:
    attempts = state.get("generation_attempts", 0) + 1
    num_q = state.get("num_questions", 20)
    raw_quiz = quiz_tool._run(
        context_text=state["context_text"],
        num_questions=num_q,
        bloom_level=state.get("bloom_level", "analyze"),
        use_yake=True,
    )
    quiz = QuizModel.model_validate(extract_json(raw_quiz))
    quiz_json = shuffle_quiz_options(quiz).model_dump_json()
    return {
        "quiz_json": quiz_json,
        "generation_attempts": attempts,
        "current_question_idx": 0,
        "phase": "generating",
    }


def evaluate_quiz(state: QuizState) -> QuizState:
    max_attempts = state.get("max_generation_attempts", 3)
    try:
        quiz = _validated_quiz(state)
        if not quiz.questions:
            raise ValueError("Quiz has no questions")
        # Evaluate the first question as a quality gate
        question = quiz.questions[0]
        correct_answer = next(option.text for option in question.options if option.is_correct)
        evaluation = extract_json(
            eval_tool._run(
                context_text=state["context_text"],
                question=question.question_text,
                correct_answer=correct_answer,
            )
        )
        passed = bool(evaluation.get("overall_passed", False))
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Quiz generation/evaluation output was invalid: %s", exc)
        passed = False

    if passed:
        return {"eval_passed": True, "phase": "waiting_for_answer"}
    if state.get("generation_attempts", 0) >= max_attempts:
        return {"eval_passed": False, "phase": "failed"}
    return {"eval_passed": False, "phase": "generating"}


def process_answer(state: QuizState) -> QuizState:
    quiz = _validated_quiz(state)
    current_idx = state.get("current_question_idx", 0)
    answer_index = state["user_answer_idx"]
    if current_idx >= len(quiz.questions):
        return {"phase": "completed"}
    if answer_index >= len(quiz.questions[current_idx].options):
        raise ValueError("answer index is outside the available options")
    if quiz.questions[current_idx].options[answer_index].is_correct:
        # Move to next question
        next_idx = current_idx + 1
        if next_idx >= len(quiz.questions):
            return {"phase": "completed", "current_question_idx": next_idx}
        return {"phase": "waiting_for_answer", "current_question_idx": next_idx}
    return {"phase": "remediating", "generation_attempts": 0}


def analyze_error(state: QuizState) -> QuizState:
    quiz = _validated_quiz(state)
    current_idx = state.get("current_question_idx", 0)
    question = quiz.questions[min(current_idx, len(quiz.questions) - 1)]
    correct_answer = next(option.text for option in question.options if option.is_correct)
    user_answer = question.options[state["user_answer_idx"]].text
    analysis = error_tool._run(
        question=question.question_text,
        correct_answer=correct_answer,
        user_answer=user_answer,
        context_text=state.get("context_text", ""),
    )
    
    next_idx = current_idx + 1
    if next_idx >= len(quiz.questions):
        phase = "completed"
    else:
        phase = "waiting_for_answer"
        
    return {"error_analysis_json": analysis, "phase": phase, "current_question_idx": next_idx}


def route_start(state: QuizState) -> str:
    return "process_answer" if state["operation"] == "answer" else "retrieve_context"


def route_evaluation(state: QuizState) -> str:
    return "generate_quiz" if state["phase"] == "generating" else END


def route_answer(state: QuizState) -> str:
    if state["phase"] in ["completed", "waiting_for_answer"]:
        return END
    return "analyze_error"


builder = StateGraph(QuizState)
builder.add_node("retrieve_context", retrieve_context)
builder.add_node("generate_quiz", generate_quiz)
builder.add_node("evaluate_quiz", evaluate_quiz)
builder.add_node("process_answer", process_answer)
builder.add_node("analyze_error", analyze_error)
builder.add_conditional_edges(
    START,
    route_start,
    {"retrieve_context": "retrieve_context", "process_answer": "process_answer"},
)
builder.add_edge("retrieve_context", "generate_quiz")
builder.add_edge("generate_quiz", "evaluate_quiz")
builder.add_conditional_edges(
    "evaluate_quiz",
    route_evaluation,
    {"generate_quiz": "generate_quiz", END: END},
)
builder.add_conditional_edges(
    "process_answer",
    route_answer,
    {"analyze_error": "analyze_error", END: END},
)
builder.add_edge("analyze_error", END)

quiz_graph = builder.compile(checkpointer=InMemorySaver())
