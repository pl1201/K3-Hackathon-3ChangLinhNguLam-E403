import sys
import json
from pathlib import Path
from pydantic import BaseModel, Field
import instructor

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from coach.config import get_settings
from coach.llm_client import create_openai_compatible_client
from coach.tools import SemanticSearchTool

class SummaryEvalResult(BaseModel):
    faithfulness_score: int = Field(description="Điểm trung thực từ 0 đến 100. 100 nếu toàn bộ thông tin trong tóm tắt đều dựa trên context.")
    comprehensiveness_score: int = Field(description="Điểm bao quát từ 0 đến 100. 100 nếu tóm tắt đủ các ý chính của context.")
    feedback: str = Field(description="Giải thích chi tiết về điểm số.")
    passed: bool = Field(description="True nếu faithfulness_score >= 90 và comprehensiveness_score >= 70.")

def evaluate_summary():
    settings = get_settings()
    if not settings.llm_enabled:
        print("LLM must be enabled with API key to run evaluation.")
        return
        
    client = instructor.from_openai(create_openai_compatible_client(settings))
    search = SemanticSearchTool()
    
    # Test cases
    test_cases = [
        {"lesson_id": "transcript-06-clean", "query": "Tóm tắt về Generative AI"},
        {"lesson_id": "transcript-06-clean", "query": "Tóm tắt về RLHF trong bài học"}
    ]
    
    results = []
    
    for idx, case in enumerate(test_cases):
        print(f"Running test case {idx+1}: {case['query']}")
        # Get context
        try:
            context = search._run(query=case['query'], top_k=5, lesson_id=case['lesson_id'])
        except Exception as e:
            print(f"Error fetching context: {e}")
            continue
            
        # Generate summary
        system_prompt = (
            "Bạn là một Trợ giảng AI thông minh. "
            "Nhiệm vụ của bạn là tóm tắt nội dung bài giảng một cách ngắn gọn, rõ ràng, dễ hiểu. "
            "Trả lời bằng tiếng Việt, dùng markdown formatting (bold, bullets). "
            "Chỉ dựa trên nội dung được cung cấp, không bịa thêm thông tin."
        )
        user_msg = f"Dựa trên nội dung bài giảng sau:\n\n{context}\n\nYêu cầu: {case['query']}"
        
        raw_client = create_openai_compatible_client(settings)
        try:
            resp = raw_client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.3,
            )
            summary = resp.choices[0].message.content
        except Exception as e:
            print(f"Error generating summary: {e}")
            continue
        
        # Evaluate
        eval_prompt = f"""Bạn là một chuyên gia đánh giá văn bản (AI Prompt Evaluator).
Hãy đánh giá bản tóm tắt sau dựa trên Context được cung cấp.

CONTEXT (Nguồn sự thật):
{context}

TÓM TẮT ĐƯỢC SINH RA:
{summary}

Tiêu chí chấm điểm:
1. Faithfulness (Trung thực): Bản tóm tắt có đưa thông tin bịa đặt (hallucination) nào không nằm trong context không? 
2. Comprehensiveness (Bao quát): Tóm tắt có nắm bắt đủ các ý chính của context để đáp ứng yêu cầu '{case['query']}' không?
"""
        try:
            evaluation = client.chat.completions.create(
                model=settings.llm_model,
                response_model=SummaryEvalResult,
                messages=[{"role": "user", "content": eval_prompt}],
                temperature=0.0
            )
            
            results.append({
                "id": f"summary-{idx+1}",
                "query": case['query'],
                "faithfulness": evaluation.faithfulness_score,
                "comprehensiveness": evaluation.comprehensiveness_score,
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
        "# Kết quả chạy Eval Tóm tắt (Summarization)",
        "",
        f"**Tổng số case**: {total}",
        f"**Pass Rate**: {pass_rate:.1f}%",
        "",
        "## Chi tiết Case",
        "| ID | Query | Faithfulness | Comp. | Pass | Feedback |",
        "|---|---|---|---|---|---|"
    ]
    for r in results:
        is_pass = "✅" if r['passed'] else "❌"
        md.append(f"| {r['id']} | {r['query']} | {r['faithfulness']} | {r['comprehensiveness']} | {is_pass} | {r['feedback']} |")
        
    with open(results_dir / "summary_eval.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))
        
    print(f"Done Summary Eval. Pass rate: {pass_rate}%")

if __name__ == "__main__":
    evaluate_summary()
