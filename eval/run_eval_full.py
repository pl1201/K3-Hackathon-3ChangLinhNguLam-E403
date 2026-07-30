import sys
import json
import time
import uuid
from pathlib import Path
from pydantic import BaseModel, Field
import instructor

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from coach.config import get_settings
from coach.llm_client import create_openai_compatible_client
from coach.graph import coach_graph
from coach.quiz_generator import generate_quiz
from coach.tools import SemanticSearchTool

# Pydantic models for evaluation
class SummaryEvalResult(BaseModel):
    faithfulness_score: int
    comprehensiveness_score: int
    feedback: str
    passed: bool

class MCQEvalResult(BaseModel):
    is_valid_format: bool
    faithfulness_score: int
    distractor_quality: int
    feedback: str
    passed: bool

def run_eval_full():
    settings = get_settings()
    if not settings.llm_enabled or not settings.openai_api_key:
        print("Cần OPENAI_API_KEY thật trong .env, không chạy mock cho CP3.")
        raise SystemExit(1)

    golden_path = ROOT_DIR / "eval" / "golden-set-full.json"
    with open(golden_path, 'r', encoding='utf-8') as f:
        cases = json.load(f)

    client = instructor.from_openai(create_openai_compatible_client(settings))
    search = SemanticSearchTool()
    raw_client = create_openai_compatible_client(settings)
    results = []

    print(f"Bắt đầu chấm {len(cases)} cases...")
    for idx, case in enumerate(cases):
        print(f"Đang xử lý [{idx+1}/{len(cases)}]: {case['id']} (Type: {case['type']}, Class: {case['class']})")
        
        start_time = time.time()
        result = {
            "id": case["id"],
            "type": case["type"],
            "class": case["class"],
            "lesson_id": case.get("lesson_id", "transcript-06-clean"),
            "expected": case.get("expected_verdict", case.get("expected", "pass")),
            "actual": "fail",
            "pass": False,
            "feedback": "",
            "time_s": 0
        }

        try:
            if case["type"] == "answer":
                thread_id = str(uuid.uuid4())
                config = {"configurable": {"thread_id": thread_id}}
                start_state = coach_graph.invoke(
                    {"operation": "start", "lesson_id": result["lesson_id"]},
                    config=config
                )
                answer_state = coach_graph.invoke(
                    {"operation": "answer", "answer": case["answer"]},
                    config=config
                )
                evaluation = answer_state.get("evaluation", {})
                actual_verdict = evaluation.get("verdict", "")
                result["actual"] = actual_verdict
                result["pass"] = (actual_verdict == result["expected"])
                result["feedback"] = evaluation.get("feedback", "")
                
                evidence = evaluation.get("evidence", [])
                retrieved_chunks = [c["chunk_id"] if isinstance(c, dict) else getattr(c, "chunk_id", None) for c in answer_state.get("chunks", [])]
                fake_citations = [e.get("chunk_id") for e in evidence if e.get("chunk_id") not in retrieved_chunks]
                if fake_citations:
                    result["pass"] = False
                    result["feedback"] = "Fake citations detected."

            elif case["type"] == "mcq":
                context = case["input_data"]
                # Generate 1 question
                quiz = generate_quiz(context_text=context, num_questions=1, bloom_level="understand")
                quiz_json = quiz.model_dump_json()

                eval_prompt = f"CONTEXT:\n{context}\nQUIZ:\n{quiz_json}\nTiêu chí: 1. Format đủ 4 đáp án. 2. Faithfulness. 3. Distractor Quality."
                ev = client.chat.completions.create(
                    model=settings.llm_model,
                    response_model=MCQEvalResult,
                    messages=[{"role": "user", "content": eval_prompt}],
                    temperature=0.0
                )
                
                if case["class"] == "unsupported":
                    result["pass"] = not ev.passed
                    result["actual"] = "fail" if not ev.passed else "pass"
                    result["feedback"] = ev.feedback
                else:
                    result["pass"] = ev.passed
                    result["actual"] = "pass" if ev.passed else "fail"
                    result["feedback"] = ev.feedback
                    
            elif case["type"] == "summary":
                query = case["input_data"]
                ctx = search._run(query=query, top_k=3, lesson_id=result["lesson_id"])
                
                resp = raw_client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": "Tóm tắt ngắn gọn theo yêu cầu từ Context. Nếu không có context phù hợp, nói 'Không có thông tin'."},
                        {"role": "user", "content": f"Context:\n{ctx}\nYêu cầu: {query}"}
                    ]
                )
                summary = resp.choices[0].message.content
                
                eval_prompt = f"CONTEXT:\n{ctx}\nTÓM TẮT:\n{summary}\nYÊU CẦU: {query}\nTiêu chí: Faithfulness và Comprehensiveness."
                ev = client.chat.completions.create(
                    model=settings.llm_model,
                    response_model=SummaryEvalResult,
                    messages=[{"role": "user", "content": eval_prompt}],
                    temperature=0.0
                )
                
                if case["class"] == "out-of-scope":
                    if "Không có thông tin" in summary or ev.faithfulness_score >= 90:
                        result["pass"] = True
                        result["actual"] = "out-of-scope_handled"
                else:
                    result["pass"] = ev.passed
                    result["actual"] = "pass" if ev.passed else "fail"
                
                result["feedback"] = ev.feedback
                
        except Exception as e:
            result["actual"] = "ERROR"
            result["feedback"] = str(e)
            
        result["time_s"] = round(time.time() - start_time, 2)
        results.append(result)
        
    # Write report
    results_dir = ROOT_DIR / "eval" / "results"
    results_dir.mkdir(exist_ok=True, parents=True)
    
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    md = [
        "# Kết quả chạy Eval Tổng thể (run-02-full)",
        "",
        f"**Tổng số case**: {total}",
        f"**Pass Rate chung**: {pass_rate:.1f}%",
        "",
        "## Phân bổ và kết quả theo Tính năng",
        "| Tính năng | Tổng case | Pass Rate |",
        "|---|---|---|"
    ]
    
    for t in ["answer", "mcq", "summary"]:
        t_results = [r for r in results if r["type"] == t]
        if t_results:
            t_pass = sum(1 for r in t_results if r["pass"])
            md.append(f"| {t.upper()} | {len(t_results)} | {t_pass/len(t_results)*100:.1f}% |")
            
    md.extend([
        "",
        "## Chi tiết Case",
        "| ID | Type | Class | Expected | Actual | Pass | Feedback |",
        "|---|---|---|---|---|---|---|"
    ])
    
    for r in results:
        is_pass = "✅" if r["pass"] else "❌"
        md.append(f"| {r['id']} | {r['type']} | {r['class']} | {r['expected']} | {r['actual']} | {is_pass} | {r['feedback'].replace(chr(10), ' ')} |")
        
    with open(results_dir / "run-02-full.md", 'w', encoding='utf-8') as f:
        f.write("\n".join(md))
        
    print(f"\n=> Đã lưu kết quả tại eval/results/run-02-full.md (Pass rate: {pass_rate:.1f}%)")

if __name__ == "__main__":
    run_eval_full()
