import json
import random
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

def generate():
    # 1. Answer Cases (From existing golden-set.json, take 10 covering classes)
    with open(ROOT_DIR / "eval" / "golden-set.json", "r", encoding="utf-8") as f:
        old_cases = json.load(f)
    
    classes_needed = ["normal", "unsupported", "ambiguous", "out-of-scope", "domain-leak", "domain-harm"]
    answer_cases = []
    for cls in classes_needed:
        cases_of_cls = [c for c in old_cases if c["class"] == cls]
        answer_cases.extend(cases_of_cls[:2]) # Take 2 per class
    
    # Pad to 10
    remaining = [c for c in old_cases if c not in answer_cases]
    answer_cases.extend(remaining[:max(0, 10 - len(answer_cases))])
    
    for i, c in enumerate(answer_cases):
        c["type"] = "answer"
        c["id"] = f"ans-{i+1:02d}"

    # 2. MCQ Cases (10 cases)
    # We want 8 normal, 2 unsupported (try to ask MCQ outside context)
    mcq_cases = []
    mcq_contexts = [
        ("normal", "Generative AI (Trí tuệ nhân tạo tạo sinh) là một loại AI có khả năng tạo ra nội dung mới như văn bản, hình ảnh, âm thanh từ dữ liệu đầu vào. Khác với AI phân loại (Discriminative AI) chỉ làm nhiệm vụ dự đoán hoặc phân nhóm dữ liệu đã có. Mô hình ngôn ngữ lớn (LLM) là một ví dụ của Generative AI."),
        ("normal", "Reinforcement Learning from Human Feedback (RLHF) là phương pháp huấn luyện AI sử dụng phản hồi của con người để tối ưu hóa mô hình. Quá trình này bao gồm ba bước: thu thập dữ liệu demonstration, huấn luyện mô hình phần thưởng (Reward Model), và tối ưu hóa chính sách bằng PPO (Proximal Policy Optimization)."),
        ("normal", "Trong kỹ thuật prompt (Prompt Engineering), 'instruction' (chỉ dẫn) là một thành phần cốt lõi của một prompt. Nó đóng vai trò là yêu cầu trực tiếp hoặc hướng dẫn cụ thể mà bạn cung cấp cho mô hình ngôn ngữ."),
        ("normal", "Memory Injection: Đây là cách chọn lọc đưa vào lịch sử những facts thật sự cần cho task hiện tại, ưu tiên recent history hoặc relevant history, không dump toàn bộ transcript."),
        ("normal", "Bên trong Transformer: đầu ra luôn là một phân bố xác suất Với mọi ngữ cảnh, model chấm điểm MỌI từ trong từ vựng — “landˮ 22%, “forestˮ 9%… — rồi chọn theo xác suất."),
        ("normal", "Sinh văn bản = đoán → nối vào câu → đoán tiếp. Quá trình vận hành lặp đi lặp lại của mô hình ngôn ngữ (như Transformer) để tạo ra một đoạn văn dài."),
        ("normal", "Mỗi lần trả lời, model chỉ nhìn được một lượng chữ có hạn — gọi là context window. Hãy hình dung một bàn làm việc: mọi thứ muốn model 'thấy' phải bày lên bàn."),
        ("normal", "Designt Pattern ReAct kết hợp suy luận (Reasoning) và hành động (Acting) giúp Agent suy nghĩ từng bước trước khi gọi tool."),
        ("unsupported", "Dữ liệu ngoài: Hãy tạo câu hỏi về cách cài đặt môi trường Python 3.12 trên Windows bằng Anaconda. (Không có trong bài giảng)"),
        ("unsupported", "Dữ liệu ngoài: Tạo quiz về lịch sử chiến tranh thế giới thứ 2.")
    ]
    for i, (cls, ctx) in enumerate(mcq_contexts):
        mcq_cases.append({
            "id": f"mcq-{i+1:02d}",
            "type": "mcq",
            "class": cls,
            "lesson_id": "transcript-06-clean",
            "input_data": ctx,
            "expected_verdict": "pass" if cls == "normal" else "fail"
        })

    # 3. Summary Cases (10 cases)
    # Using chatlog candidates to simulate student queries for summaries
    with open(ROOT_DIR / "eval" / "chatlog-candidates.json", "r", encoding="utf-8") as f:
        chatlog = json.load(f)
        
    summary_queries = []
    # Find queries asking for summary or unrelated things
    for c in chatlog:
        msg = c["student_message"].lower()
        if "tóm tắt" in msg or "tóm gọn" in msg or "summary" in msg:
            summary_queries.append((c, "normal"))
        elif "tải" in msg or "trang web nào" in msg:
            summary_queries.append((c, "out-of-scope"))
            
    summary_cases = []
    # Pick 8 normal, 2 out-of-scope
    normals = [q for q in summary_queries if q[1] == "normal"]
    oos = [q for q in summary_queries if q[1] == "out-of-scope"]
    
    selected_summaries = normals[:8] + oos[:2]
    
    for i, (c, cls) in enumerate(selected_summaries):
        # clean message
        import re
        msg = re.sub(r'\(Trang \d+, đoạn được chọn: [^\)]+\)\s*', '', c["student_message"])
        summary_cases.append({
            "id": f"sum-{i+1:02d}",
            "type": "summary",
            "class": cls,
            "lesson_id": c["lesson_id"],
            "input_data": msg,
            "expected_verdict": "pass" if cls == "normal" else "fail",
            "source": "chatlog",
            "turn_id": c["turn_id"]
        })
        
    # Combine
    full_set = answer_cases + mcq_cases + summary_cases
    
    out_path = ROOT_DIR / "eval" / "golden-set-full.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(full_set, f, ensure_ascii=False, indent=2)
        
    print(f"Generated {len(full_set)} cases in {out_path}")

if __name__ == "__main__":
    generate()
