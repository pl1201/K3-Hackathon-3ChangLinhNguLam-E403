# Evaluation (Kiểm thử)

Thư mục này chứa các kịch bản kiểm thử (Golden Set), các script chạy tự động (LLM-as-a-judge) và báo cáo kết quả nhằm đáp ứng tiêu chuẩn kiểm thử (Rubric R4) của chương trình VLearn Hackathon.

## 1. Cấu trúc Golden Set Tổng Thể

Hệ thống được đánh giá qua một bộ dữ liệu chuẩn (Golden Set) đại diện cho toàn bộ chức năng của sản phẩm.

- **`golden-set-full.json`**: Tập hợp 30 test cases bao trùm 3 tính năng lõi:
  - **10 case Tự luận (Answer)**: Đánh giá câu trả lời của học viên và đặt câu hỏi bù đắp lỗ hổng.
  - **10 case Trắc nghiệm (MCQ)**: Sinh bài tập trắc nghiệm bám sát nội dung bài giảng.
  - **10 case Tóm tắt (Summary)**: Hỗ trợ tóm tắt nội dung khi học viên yêu cầu.
- **Tiêu chuẩn của bộ Golden Set**:
  - Tuân thủ quy tắc phủ đủ 4 lớp rủi ro (Nguồn sự thật, Mơ hồ, Ngoài phạm vi, Đặc thù Domain).
  - Có >10 cases được khai thác thực tế từ dữ liệu hội thoại thật (khai thác qua script `mine_chatlog_candidates.py`).
  - Mỗi test case đều có phân loại rõ ràng (`normal`, `ambiguous`, `unsupported`, `out-of-scope`) và định nghĩa kết quả kỳ vọng (Expected Verdict).

> _Ghi chú: Bộ `golden-set.json` cũ (32 cases) chỉ dành riêng cho tính năng Tự luận, hiện tại đã được gộp 10 case đại diện vào `golden-set-full.json`._

## 2. Cách chạy đánh giá tự động (LLM-as-a-judge)

Quá trình chấm điểm được tự động hóa bằng cách sử dụng GPT-4o đóng vai trò là giám khảo (LLM-as-a-judge) chấm điểm chéo các kết quả trả ra từ Agent.

Để chạy lại toàn bộ bộ test, hãy đảm bảo rằng file `.env` ở thư mục gốc có `OPENAI_API_KEY` hợp lệ, sau đó chạy lệnh:

```bash
python eval/run_eval_full.py
```

*Lưu ý: Quá trình chạy đánh giá 30 cases sẽ mất khoảng 1-2 phút vì hệ thống cần gọi trực tiếp tới OpenAI.*

## 3. Cấu trúc kết quả (`eval/results/`)

Kết quả sau khi chạy `run_eval_full.py` sẽ tự động được xuất ra dạng báo cáo Markdown:
- **`run-02-full.md`**: Báo cáo tổng hợp tỷ lệ Pass Rate chung của cả 3 tính năng, và chi tiết Pass/Fail kèm phản hồi (Feedback) của giám khảo AI cho từng test case.
- **Quality bar**: Mục tiêu là ≥85% tổng thể toàn bộ case qua tiêu chí. Tuyệt đối 100% không bịa citation. 
- *Kết quả gần nhất (run-02-full)*: Đạt 90.0% Pass Rate chung.

## 4. Các script hỗ trợ khác
- `make_golden_set_full.py`: Dùng để trộn và lấy mẫu tạo ra bộ 30 cases cuối cùng từ kho chatlog.
- `eval_mcq.py` / `eval_summary.py`: Các script đánh giá nháp/đơn lẻ phục vụ quá trình phát triển tính năng.
