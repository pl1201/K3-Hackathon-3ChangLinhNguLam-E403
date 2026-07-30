import json
import uuid
import os
import time
from pathlib import Path

# Adjust python path if needed to import coach
import sys
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from coach.graph import coach_graph
from coach.config import get_settings

def run_eval():
    settings = get_settings()
    if not settings.llm_enabled or not settings.openai_api_key:
        print("Cần OPENAI_API_KEY thật trong .env, không chạy mock cho CP3.")
        raise SystemExit(1)
        
    golden_path = ROOT_DIR / "eval" / "golden-set.json"
    with open(golden_path, 'r', encoding='utf-8') as f:
        cases = json.load(f)
        
    results = []
    
    for case in cases:
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        
        start_time = time.time()
        
        # Step 1: Start
        try:
            start_state = coach_graph.invoke(
                {
                    "operation": "start",
                    "lesson_id": case.get("lesson_id", "transcript-06-clean")
                },
                config=config
            )
            
            # Step 2: Answer
            answer_state = coach_graph.invoke(
                {
                    "operation": "answer",
                    "answer": case["answer"]
                },
                config=config
            )
            
            evaluation = answer_state.get("evaluation", {})
            actual_verdict = evaluation.get("verdict", "")
            expected_verdict = case["expected_verdict"]
            is_pass = (actual_verdict == expected_verdict)
            
            # Check citations
            evidence = evaluation.get("evidence", [])
            retrieved_chunks = [c["chunk_id"] if isinstance(c, dict) else getattr(c, "chunk_id", None) for c in answer_state.get("chunks", [])]
            fake_citations = [e.get("chunk_id") for e in evidence if e.get("chunk_id") not in retrieved_chunks]
            
            elapsed = time.time() - start_time
            
            result = {
                "id": case["id"],
                "lesson_id": case.get("lesson_id", "transcript-06-clean"),
                "class": case["class"],
                "expected": expected_verdict,
                "actual": actual_verdict,
                "pass": is_pass,
                "fake_citations": len(fake_citations) > 0,
                "time_s": round(elapsed, 2),
                "error": None
            }
            results.append(result)
            print(f"[{result['id']}] Pass: {is_pass} | Expected: {expected_verdict} | Actual: {actual_verdict}")
            
            # In ra nguyên nhân fail để debug
            if not is_pass:
                q_dict = answer_state.get("question", {})
                print(f"   Question: {q_dict.get('prompt')}")
                print(f"   Expected points: {q_dict.get('expected_points')}")
                print(f"   Student Answer: {case['answer']}")
                print(f"   Feedback: {evaluation.get('feedback')}")
            
        except Exception as e:
            results.append({
                "id": case["id"],
                "lesson_id": case.get("lesson_id", "transcript-06-clean"),
                "class": case["class"],
                "expected": case["expected_verdict"],
                "actual": "ERROR",
                "pass": False,
                "fake_citations": False,
                "time_s": round(time.time() - start_time, 2),
                "error": str(e)
            })
            print(f"[{case['id']}] ERROR: {str(e)}")
            
    # Output JSON
    results_dir = ROOT_DIR / "eval" / "results"
    results_dir.mkdir(exist_ok=True, parents=True)
    
    with open(results_dir / "run-01.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    # Stats
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    pass_rate = (passed / total * 100) if total > 0 else 0
    fake_citations = sum(1 for r in results if r.get("fake_citations"))
    
    # Per class
    class_stats = {}
    for r in results:
        cls = r["class"]
        if cls not in class_stats:
            class_stats[cls] = {"total": 0, "pass": 0}
        class_stats[cls]["total"] += 1
        if r["pass"]:
            class_stats[cls]["pass"] += 1
            
    # Per lesson
    lesson_stats = {}
    for r in results:
        lid = r["lesson_id"]
        if lid not in lesson_stats:
            lesson_stats[lid] = {"total": 0, "pass": 0}
        lesson_stats[lid]["total"] += 1
        if r["pass"]:
            lesson_stats[lid]["pass"] += 1
            
    # Markdown
    md = [
        "# Kết quả chạy Eval (run-01)",
        "",
        f"**Tổng số case**: {total}",
        f"**Pass**: {passed}/{total} ({pass_rate:.1f}%)",
        f"**Số case bịa citation**: {fake_citations}",
        "",
        "## Theo Class",
    ]
    for cls, stats in class_stats.items():
        md.append(f"- **{cls}**: {stats['pass']}/{stats['total']} ({stats['pass']/stats['total']*100:.1f}%)")
        
    md.extend(["", "## Theo Lesson"])
    for lid, stats in lesson_stats.items():
        md.append(f"- **{lid}**: {stats['pass']}/{stats['total']} ({stats['pass']/stats['total']*100:.1f}%)")
        
    md.extend([
        "",
        "## Chi tiết Case",
        "| ID | Lesson | Class | Expected | Actual | Pass | Ghi chú |",
        "|---|---|---|---|---|---|---|"
    ])
    
    fails = []
    for r in results:
        is_pass = "✅" if r["pass"] else "❌"
        note = r.get("error", "") or ("Fake Citation" if r.get("fake_citations") else "")
        md.append(f"| {r['id']} | {r['lesson_id']} | {r['class']} | {r['expected']} | {r['actual']} | {is_pass} | {note} |")
        
        if not r["pass"] or r.get("fake_citations"):
            fails.append(r)
            
    with open(results_dir / "run-01.md", 'w', encoding='utf-8') as f:
        f.write("\n".join(md))
        
    print(f"\n=> Đã lưu kết quả tại eval/results/run-01.md (Pass rate: {pass_rate:.1f}%)")
    
    if pass_rate < 85 or fake_citations > 0:
        print("\nDANH SÁCH CASE FAIL HOẶC LỖI:")
        for r in fails:
            print(f"- {r['id']}: Expected {r['expected']}, got {r['actual']} (Fake Citation: {r.get('fake_citations')})")
            if r.get("error"):
                print(f"  Error: {r['error']}")

if __name__ == '__main__':
    run_eval()
