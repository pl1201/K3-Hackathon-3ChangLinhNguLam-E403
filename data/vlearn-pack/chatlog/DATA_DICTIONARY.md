# Data Dictionary — `chat_history_anonymized_for_hackathon.csv`

Nguồn: DB `VLearn Product Analytics — Production` (Postgres, Superset SQL Lab), join `chat_messages` + `turns` + `conversations` + `llm_calls` (aggregated per turn).
Phạm vi: 2,522 dòng (1,261 message pair student+tutor), 22/07 → 29/07/2026, 369 user, 585 hội thoại.

## Kiểm tra dữ liệu nhạy cảm (đã thực hiện)

Quét toàn bộ 2,522 dòng bằng regex/keyword: số điện thoại VN, email, số CCCD/CMND (9–12 số), câu giới thiệu tên, MSSV, địa chỉ, từ khoá liên hệ (Zalo/Facebook/Telegram...).

- 5 dòng bị flag ban đầu, kiểm tra tay từng dòng → **tất cả đều false positive** (câu hỏi đùa không tiết lộ tên, nội dung học thuật nhắc "số điện thoại" như case study, tutor giải thích khái niệm PII).
- Phát hiện: platform đã có **lớp tự động redact PII sẵn** — 12 dòng chứa placeholder `[REDACTED_NAME]` / `[REDACTED_MSSV]` ngay trong `content` khi học sinh chọn đoạn slide có tên/MSSV giảng viên hoặc file.
- **Kết luận: file sạch, không cần mask/remove thêm.**
- ID nhận diện (`conversation_id`, `user_id`, `turn_id`, `message_id`) đã được thay bằng mã ẩn danh (`U0001`, `C0001`, `T0001`, `M0001`...), không map ngược được ra UUID/người thật.

## Bảng field

| Field | Kiểu | Mô tả | Giá trị quan sát được | Ghi chú |
|---|---|---|---|---|
| `conversation_id` | string | ID hội thoại (đã ẩn danh: `C0001`–`C0585`) | | 1 hội thoại = nhiều turn |
| `user_id` | string | Mã học sinh (đã ẩn danh: `U0001`–`U0369`) | 369 user | Không map ngược được ra người thật |
| `day_code` | text | Mã bài giảng/tài liệu ngữ cảnh của hội thoại | vd. `Lecture_material_ms2044ey_k6uor3`, `New learning material`, `day02-c301` | `New learning material` chiếm nhiều nhất (794 msg) — có thể là placeholder/bug đặt tên, đáng hỏi lại team kỹ thuật |
| `conversation_mode` | text | Chế độ hội thoại | 100% `in_class` trong file này | |
| `turn_id` | string | ID 1 lượt hỏi-đáp (đã ẩn danh: `T0001`–`T1261`) | | 1 turn = đúng 2 message (student + tutor) |
| `turn_status` | text | Trạng thái xử lý turn | 100% `completed` | Không có turn lỗi/dở dang trong file |
| `message_id` | string | ID từng dòng tin nhắn (đã ẩn danh: `M0001`–`M2522`) | | |
| `role` | text | Ai gửi tin nhắn | `student` / `tutor` (mỗi loại 1,261 dòng) | |
| `content` | text | Nội dung tin nhắn nguyên văn | | Đã qua lớp redact PII của platform + đã tự kiểm tra lại |
| `move_used` | text | Nước đi sư phạm tutor áp dụng (null cho message của student) | `review_concept`(1072) `give_direct_answer`(146) `give_example`(21) `motivate`(7) `give_hint`(4) `validate_understanding`(1) | |
| `citations` | text (jsonb) | Danh sách số trang tài liệu tutor trích dẫn khi trả lời | vd. `[45]`, hoặc `[]` | 46.2% rỗng — tutor trả lời không grounding vào tài liệu |
| `misconceptions` | text (jsonb) | Danh sách hiểu lầm được phát hiện trong câu trả lời | luôn `[]` | **Field chưa từng được dùng** (0/1,261) |
| `follow_ups` | text (jsonb) | Câu hỏi gợi ý tiếp theo | luôn `[]` | **Field chưa từng được dùng** (0/1,261) |
| `rating` | text | Đánh giá của học sinh cho câu trả lời tutor | `up`(33) `down`(37), phần lớn null | Chỉ ~2.8% tin nhắn có rating |
| `asked_check_question` | boolean | Tutor có chủ động hỏi lại để kiểm tra hiểu bài không | `True`(3) `False`(2515) | Rất hiếm dùng |
| `message_created_at` | timestamp (UTC) | Thời điểm tạo tin nhắn | 2026-07-22 → 2026-07-29 | |
| `llm_call_count` | integer | Số lần gọi LLM để tạo ra turn này | 2–7 lần | Gồm cả bước tool-use trung gian, không chỉ 1 lần generate cuối |
| `models_used` | text | (Các) model LLM dùng trong turn | `gemini-3.1-flash-lite`(1101) `gemini-3-flash`(160) | |
| `total_input_tokens` | integer | Tổng input token của turn | | |
| `total_output_tokens` | integer | Tổng output token của turn | | |
| `total_cost_usd` | numeric | Chi phí ước tính (USD) | **luôn = 0.000000** | ⚠️ Cost tracking đang broken/chưa tính đúng — đừng dùng cột này để phân tích chi phí |
| `avg_latency_ms` | integer | Độ trễ trung bình các lệnh gọi LLM trong turn | median 1,758ms, p90 3,686ms, max 23,848ms | Có outlier gần 24 giây, đáng để hackathon tìm nguyên nhân |
