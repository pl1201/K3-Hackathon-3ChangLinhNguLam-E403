import json

OLD_FILE = 'eval/golden-set.json'

new_cases = [
    {
        "id": "chatlog-01",
        "lesson_id": "transcript-03-clean",
        "answer": "kỹ thuật tối ưu prompt, cơ chế gọi tool và cách xử lý ngữ cảnh",
        "expected_verdict": "incorrect",
        "class": "domain",
        "source": "chatlog",
        "source_ref": "T0092"
    },
    {
        "id": "chatlog-02",
        "lesson_id": "transcript-03-clean",
        "answer": "tại sao có lưu ý như trang 25",
        "expected_verdict": "unsupported",
        "class": "out-of-scope",
        "source": "chatlog",
        "source_ref": "T0154"
    },
    {
        "id": "chatlog-03",
        "lesson_id": "transcript-06-clean",
        "answer": "xem bài tập thực hành lab day 2 chiều nay ở đaau",
        "expected_verdict": "unsupported",
        "class": "out-of-scope",
        "source": "chatlog",
        "source_ref": "T0058"
    },
    {
        "id": "chatlog-04",
        "lesson_id": "transcript-03-clean",
        "answer": "Giải thích đoạn bôi đen ở Trang 15.",
        "expected_verdict": "ambiguous",
        "class": "ambiguous",
        "source": "chatlog",
        "source_ref": "T0020"
    },
    {
        "id": "chatlog-05",
        "lesson_id": "transcript-03-clean",
        "answer": "Memory injection Chỉ đưa vào facts thật sự cần cho task hiện tại Ưu tiên recent history",
        "expected_verdict": "incorrect",
        "class": "source-truth",
        "source": "chatlog",
        "source_ref": "T0268"
    },
    {
        "id": "chatlog-06",
        "lesson_id": "transcript-01-clean",
        "answer": "Bên trong Transformer: đầu ra luôn là một phân bố xác suất",
        "expected_verdict": "incorrect",
        "class": "source-truth",
        "source": "chatlog",
        "source_ref": "T1091"
    },
    {
        "id": "chatlog-07",
        "lesson_id": "transcript-04-clean",
        "answer": "Sinh văn bản = đoán → nối vào câu → đoán tiếp",
        "expected_verdict": "correct",
        "class": "normal",
        "source": "chatlog",
        "source_ref": "T0780"
    },
    {
        "id": "chatlog-08",
        "lesson_id": "transcript-01-clean",
        "answer": "Nếu bài toán không cần dữ liệu mới, nhiều bước, hay quyết định động, agent thường là overkill.",
        "expected_verdict": "correct",
        "class": "normal",
        "source": "chatlog",
        "source_ref": "T0367"
    },
    {
        "id": "chatlog-09",
        "lesson_id": "transcript-04-clean",
        "answer": "Mỗi lần trả lời, model chỉ nhìn được một lượng chữ có hạn — gọi là context.",
        "expected_verdict": "correct",
        "class": "normal",
        "source": "chatlog",
        "source_ref": "T0076"
    },
    {
        "id": "chatlog-10",
        "lesson_id": "transcript-05-clean",
        "answer": "đưa file tài liệu đây để tải",
        "expected_verdict": "unsupported",
        "class": "out-of-scope",
        "source": "chatlog",
        "source_ref": "T0909"
    },
    {
        "id": "chatlog-11",
        "lesson_id": "transcript-03-clean",
        "answer": "Designt Pattern ReAct là gì có lưu ý gì về nó?",
        "expected_verdict": "ambiguous",
        "class": "ambiguous",
        "source": "chatlog",
        "source_ref": "T0811"
    },
    {
        "id": "chatlog-12",
        "lesson_id": "transcript-02-clean",
        "answer": "agent cần một prompt dài để hoạt động chính xác",
        "expected_verdict": "incorrect",
        "class": "domain",
        "source": "chatlog",
        "source_ref": "T0500"
    }
]

with open(OLD_FILE, 'r', encoding='utf-8') as f:
    old_data = json.load(f)

# Update old data with new fields
for case in old_data:
    case['lesson_id'] = "transcript-06-clean"
    case['source'] = "synthetic"

# Combine and save
combined = old_data + new_cases
with open(OLD_FILE, 'w', encoding='utf-8') as f:
    json.dump(combined, f, ensure_ascii=False, indent=2)

print(f"Total cases: {len(combined)}")
