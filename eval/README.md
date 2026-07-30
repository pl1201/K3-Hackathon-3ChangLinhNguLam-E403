# Evaluation

# Evaluation

- `golden-set.json`: Hiện có 32 case, bao gồm 20 case synthetic và 12 case thật (mining từ chatlog). Phân bố đầy đủ các lớp: normal, ambiguous, domain, out-of-scope và source-truth.
  - Các case lấy từ chatlog thật có nhãn `source: "chatlog"` và có thể kiểm chứng lại bằng cách tìm `source_ref` (chính là `turn_id`) trong file csv chatlog.
- Quality bar dự kiến: ≥85% toàn bộ case và 100% không bịa citation.

### Cách chạy đánh giá

Để chạy lại toàn bộ bộ test, hãy đảm bảo rằng file `.env` ở thư mục gốc có `OPENAI_API_KEY` hợp lệ, sau đó chạy lệnh sau từ thư mục gốc của dự án:
```bash
python eval/run_eval.py
```
> **Lưu ý**: Script `run_eval.py` sẽ kiểm tra API key thật và chỉ chạy khi có API key. Mock fallback chỉ dùng để kiểm tra flow kỹ thuật, không dùng để chấm CP3.

### Cấu trúc kết quả (`eval/results/`)
- `run-0N.json`: Kết quả chi tiết dạng JSON lưu trữ toàn bộ dữ liệu (pass/fail, citation, model used, thời gian, etc).
- `run-0N.md`: Báo cáo dạng Markdown, tổng hợp tỷ lệ pass rate tổng quan và phân bổ theo class/lesson. Các case thất bại sẽ được ghi nhận nguyên vẹn, không ghi đè hoặc xóa bỏ case fail.
