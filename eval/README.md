# Evaluation

- `golden-set.json`: 20 case ban đầu, phủ normal, ambiguous, domain, out-of-scope và source-truth.
- Quality bar dự kiến: ≥85% toàn bộ case và 100% không bịa citation.
- Khi có API key, chạy toàn bộ bộ test với model thật và lưu output từng lượt; không ghi đè hoặc xóa case fail.

Mock fallback chỉ dùng để kiểm tra flow kỹ thuật. Kết quả mock không được trình bày như kết quả chất lượng model tại CP3.
