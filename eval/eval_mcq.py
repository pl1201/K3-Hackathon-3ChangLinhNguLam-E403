import sys
import json
from pathlib import Path
from pydantic import BaseModel, Field
import instructor

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from coach.config import get_settings
from coach.llm_client import create_openai_compatible_client
from coach.quiz_generator import generate_quiz

class MCQEvalResult(BaseModel):
    is_valid_format: bool = Field(description="True nếu mỗi câu hỏi có đúng 4 đáp án (1 đúng, 3 sai) và có giải thích.")
    faithfulness_score: int = Field(description="Điểm trung thực từ 0-100. Nội dung câu hỏi và đáp án đều phải nằm trong context.")
    distractor_quality: int = Field(description="Điểm chất lượng của đáp án sai từ 0-100. Không được quá hiển nhiên.")
    feedback: str = Field(description="Giải thích về điểm số.")
    passed: bool = Field(description="True nếu is_valid_format=True, faithfulness_score >= 90, distractor_quality >= 70.")

def evaluate_mcq():
    settings = get_settings()
    if not settings.llm_enabled:
        print("LLM must be enabled with API key to run evaluation.")
        return
        
    client = instructor.from_openai(create_openai_compatible_client(settings))
    
    # Test cases
    test_contexts = [
        "Generative AI (Trí tuệ nhân tạo tạo sinh) là một loại AI có khả năng tạo ra nội dung mới như văn bản, hình ảnh, âm thanh từ dữ liệu đầu vào. Khác với AI phân loại (Discriminative AI) chỉ làm nhiệm vụ dự đoán hoặc phân nhóm dữ liệu đã có. Mô hình ngôn ngữ lớn (LLM) là một ví dụ của Generative AI.",
        "Reinforcement Learning from Human Feedback (RLHF) là phương pháp huấn luyện AI sử dụng phản hồi của con người để tối ưu hóa mô hình. Quá trình này bao gồm ba bước: thu thập dữ liệu demonstration, huấn luyện mô hình phần thưởng (Reward Model), và tối ưu hóa chính sách bằng PPO (Proximal Policy Optimization)."
    ]
    
    results = []
    
    for idx, context in enumerate(test_contexts):
        print(f"Running test case {idx+1}")
        try:
            # Generate 2 questions per context
            quiz = generate_quiz(context_text=context, num_questions=2, bloom_level="understand")
            quiz_json = quiz.model_dump_json(indent=2)
        except Exception as e:
            print(f"Error generating quiz: {e}")
            continue
            
        # Evaluate
        eval_prompt = f"""Bạn là một chuyên gia khảo thí và đánh giá đề thi (Quiz Evaluator).
Hãy đánh giá bộ câu hỏi trắc nghiệm sau dựa trên Nguồn kiến thức (Context).

CONTEXT (Nguồn sự thật):
{context}

QUIZ ĐƯỢC SINH RA:
{quiz_json}

Tiêu chí chấm điểm:
1. Format: Mỗi câu hỏi phải có đúng 4 đáp án, trong đó có đúng 1 đáp án đúng và 3 đáp án sai. Phải có lời giải thích.
2. Faithfulness (Trung thực): Câu hỏi và đáp án không được chứa kiến thức bên ngoài Context.
3. Distractor Quality (Chất lượng đáp án nhiễu): Đáp án sai phải hợp lý, liên quan đến ngữ cảnh, không được quá ngớ ngẩn hoặc dễ dàng đoán được mà không cần đọc bài.
"""
        try:
            evaluation = client.chat.completions.create(
                model=settings.llm_model,
                response_model=MCQEvalResult,
                messages=[{"role": "user", "content": eval_prompt}],
                temperature=0.0
            )
            
            results.append({
                "id": f"mcq-{idx+1}",
                "format": evaluation.is_valid_format,
                "faithfulness": evaluation.faithfulness_score,
                "distractor": evaluation.distractor_quality,
                "passed": evaluation.passed,
                "feedback": evaluation.feedback.replace('\n', ' ')
            })
        except Exception as e:
            print(f"Error evaluating: {e}")
        
    # Write report
    results_dir = ROOT_DIR / "eval" / "results"
    results_dir.mkdir(exist_ok=True, parents=True)
    
    total = len(results)
    passed = sum(1 for r in results if r['passed'])
    pass_rate = passed / total * 100 if total > 0 else 0
    
    md = [
        "# Kết quả chạy Eval Sinh Quiz (MCQ Generation)",
        "",
        f"**Tổng số case**: {total}",
        f"**Pass Rate**: {pass_rate:.1f}%",
        "",
        "## Chi tiết Case",
        "| ID | Format OK | Faithfulness | Distractor | Pass | Feedback |",
        "|---|---|---|---|---|---|"
    ]
    for r in results:
        is_pass = "✅" if r['passed'] else "❌"
        fmt = "✅" if r['format'] else "❌"
        md.append(f"| {r['id']} | {fmt} | {r['faithfulness']} | {r['distractor']} | {is_pass} | {r['feedback']} |")
        
    with open(results_dir / "mcq_eval.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))
        
    print(f"Done MCQ Eval. Pass rate: {pass_rate}%")

if __name__ == "__main__":
    evaluate_mcq()
