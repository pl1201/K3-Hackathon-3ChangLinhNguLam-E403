"""LangGraph orchestration for the Multiple Choice Quiz Engine.

Creates a cyclic workflow for generating, evaluating, and remediating
multiple choice questions.
"""

from typing import Literal, TypedDict, Optional
import json
import logging

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import InMemorySaver

from coach.tools import (
    SemanticSearchTool,
    QuizGeneratorTool,
    QuizEvaluatorTool,
    ErrorAnalysisTool
)

logger = logging.getLogger(__name__)

# Khởi tạo các công cụ
search_tool = SemanticSearchTool()
quiz_tool = QuizGeneratorTool()
eval_tool = QuizEvaluatorTool()
error_tool = ErrorAnalysisTool()

class QuizState(TypedDict, total=False):
    # Control flags
    operation: Literal["start", "answer"]
    
    # Input data
    topic_query: str
    user_answer_idx: int # Vị trí đáp án người dùng chọn (0-3)
    
    # Internal state
    context_text: str
    quiz_json: str
    eval_passed: bool
    error_analysis_json: str
    
    # Output flags
    phase: Literal["generating", "waiting_for_answer", "remediating", "completed"]


# --- NODES ---

def retrieve_context(state: QuizState) -> QuizState:
    """Tìm kiếm tài liệu liên quan đến chủ đề ôn tập."""
    logger.info(f"Retrieving context for topic: {state.get('topic_query')}")
    # Nếu đã có context thì không cần lấy lại (trường hợp bị hallucination cần gen lại câu khác)
    if state.get("context_text"):
        return state
        
    context = search_tool._run(query=state.get("topic_query", "Kiến thức tổng hợp"), top_k=2)
    return {"context_text": context, "phase": "generating"}


def generate_quiz(state: QuizState) -> QuizState:
    """Sinh câu hỏi trắc nghiệm dựa trên Context."""
    logger.info("Generating Quiz...")
    # Tự động kết hợp Bloom Taxonomy (Apply) và Yake Distractors
    quiz_json = quiz_tool._run(
        context_text=state["context_text"], 
        num_questions=1, 
        bloom_level="apply", 
        use_yake=True
    )
    return {"quiz_json": quiz_json}


def extract_json(text: str) -> dict:
    import re
    match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return json.loads(text)

def evaluate_quiz(state: QuizState) -> QuizState:
    """LLM-as-a-judge kiểm định chất lượng câu hỏi."""
    logger.info("Evaluating Quiz quality...")
    quiz_data = extract_json(state["quiz_json"])
    question_obj = quiz_data["questions"][0]
    
    q_text = question_obj["question_text"]
    
    # Tìm đáp án đúng
    correct_ans = next(opt["text"] for opt in question_obj["options"] if opt["is_correct"])
    
    eval_json = eval_tool._run(
        context_text=state["context_text"],
        question=q_text,
        correct_answer=correct_ans
    )
    
    eval_data = json.loads(eval_json)
    passed = eval_data.get("overall_passed", False)
    
    if passed:
        logger.info("Quiz passed evaluation. Waiting for user answer.")
        return {"eval_passed": True, "phase": "waiting_for_answer"}
    else:
        logger.warning(f"Quiz failed evaluation (Hallucination detected). Regenerating...")
        return {"eval_passed": False, "phase": "generating"}


def process_answer(state: QuizState) -> QuizState:
    """Xử lý câu trả lời của học viên."""
    logger.info("Processing user answer...")
    quiz_data = extract_json(state["quiz_json"])
    question_obj = quiz_data["questions"][0]
    
    user_idx = state["user_answer_idx"]
    chosen_option = question_obj["options"][user_idx]
    
    if chosen_option["is_correct"]:
        logger.info("User answered correctly!")
        return {"phase": "completed"}
    else:
        logger.info("User answered incorrectly. Routing to Error Analysis...")
        return {"phase": "remediating"}


def analyze_error(state: QuizState) -> QuizState:
    """Phân tích nguyên nhân lỗi sai và lỗ hổng kiến thức."""
    logger.info("Analyzing misconception...")
    quiz_data = extract_json(state["quiz_json"])
    question_obj = quiz_data["questions"][0]
    
    q_text = question_obj["question_text"]
    correct_ans = next(opt["text"] for opt in question_obj["options"] if opt["is_correct"])
    
    user_idx = state["user_answer_idx"]
    user_ans = question_obj["options"][user_idx]["text"]
    
    error_analysis = error_tool._run(
        question=q_text,
        correct_answer=correct_ans,
        user_answer=user_ans,
        context_text=state["context_text"]
    )
    
    return {"error_analysis_json": error_analysis, "phase": "generating"}


# --- ROUTING LOGIC ---

def route_start(state: QuizState) -> str:
    if state["operation"] == "start":
        return "retrieve_context"
    elif state["operation"] == "answer":
        return "process_answer"
    return "retrieve_context"

def route_evaluation(state: QuizState) -> str:
    if state["eval_passed"]:
        # Tạm dừng đồ thị, chờ người dùng nhập đáp án
        return END
    else:
        # Nếu chất lượng câu hỏi kém, quay lại vòng lặp sinh câu hỏi mới
        return "generate_quiz"

def route_answer(state: QuizState) -> str:
    if state["phase"] == "completed":
        return END
    else:
        return "analyze_error"


# --- BUILD GRAPH ---

builder = StateGraph(QuizState)

builder.add_node("retrieve_context", retrieve_context)
builder.add_node("generate_quiz", generate_quiz)
builder.add_node("evaluate_quiz", evaluate_quiz)
builder.add_node("process_answer", process_answer)
builder.add_node("analyze_error", analyze_error)

builder.add_conditional_edges(START, route_start)

builder.add_edge("retrieve_context", "generate_quiz")
builder.add_edge("generate_quiz", "evaluate_quiz")

builder.add_conditional_edges(
    "evaluate_quiz", 
    route_evaluation,
    {
        END: END,
        "generate_quiz": "generate_quiz"
    }
)

builder.add_conditional_edges(
    "process_answer",
    route_answer,
    {
        END: END,
        "analyze_error": "analyze_error"
    }
)

# Vòng lặp: Sau khi phân tích lỗi sai, ép hệ thống sinh ra một câu hỏi mới để học viên gỡ điểm
builder.add_edge("analyze_error", "generate_quiz")

quiz_graph = builder.compile(checkpointer=InMemorySaver())
