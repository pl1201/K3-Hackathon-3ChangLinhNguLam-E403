# AI SPEC — Active Recall Coach · VLearn

## §1. User & Job

- **Job executor:** Học viên vừa học xong một bài VLearn và cần kiểm tra mình thực sự nhớ, hiểu phần nào.
- **Core JTBD:** Sau khi học xong một nội dung, kiểm tra khả năng tự nhớ lại để biết chính xác phần cần ôn tiếp.
- **Problem statement:** Việc đọc lại hoặc nhận một bản tóm tắt tạo cảm giác quen thuộc nhưng không chỉ ra được lỗ hổng kiến thức.
- **Evidence:** cần hoàn thiện mining log và ≥5 trích dẫn ngắn theo chuẩn của đề; không đưa nguyên data pack vào repo public.

## §2. Impact & quyết định chọn

Lát cắt ưu tiên là một phiên active recall trên **một bài học đã chọn**. Không build LMS, quản lý khóa học hay hệ thống chấm điểm chính thức.

## §3. Giải pháp tương tự

Cần bổ sung quan sát có bằng chứng từ Study Mode, NotebookLM và Quizlet. Điểm khác biệt dự kiến: đánh giá bám transcript, hiển thị căn cứ và chuyển sang câu hỏi bù đúng knowledge gap.

## §4. Thiết kế

- **Lát cắt một câu:** Một học viên chọn một bài đã học, AI tạo câu hỏi bám transcript, đánh giá câu trả lời có căn cứ và dẫn người học qua câu hỏi bù để đóng lỗ hổng kiến thức.
- **Non-goals:** không chấm điểm chính thức; không trả lời ngoài transcript; không tự cập nhật giáo trình; không xây LMS hoàn chỉnh.
- **Prototype:** Working slice; backend và một AI call thật, có mock fallback được gắn nhãn rõ khi thiếu key.
- **Automation:** Conditional — AI tự chạy khi có căn cứ; mơ hồ thì hỏi lại; thiếu nguồn thì không kết luận.
- **Nguyên tắc:** G1 nêu phạm vi; G2 hiển thị nguồn/confidence; G9 cho trả lời lại; G10 hỏi rõ khi mơ hồ; G11 giải thích bằng đoạn nguồn.

## §5. Bốn lớp lỗi

| Lớp | Tình huống | Hành vi |
|---|---|---|
| Nguồn sự thật | Model đưa nhận định không có trong transcript | Chuyển `unsupported`, không dạy tiếp từ nhận định đó |
| Nguồn sự thật | Citation không tồn tại trong context | Loại citation và yêu cầu tạo lại |
| Mơ hồ | Câu trả lời quá ngắn, không đủ đánh giá | Hỏi một câu làm rõ |
| Mơ hồ | Có hai cách hiểu hợp lý | Nêu điểm chưa rõ, không chấm sai |
| Ngoài phạm vi | Hỏi kiến thức ngoài bài | Nói rõ giới hạn và mời quay lại bài |
| Ngoài phạm vi | Yêu cầu cấp điểm/chứng chỉ | Từ chối quyền hạn |
| Domain | Feedback sai khiến học viên học sai | Chỉ feedback dựa trên evidence trích dẫn |
| Domain | Lộ đáp án trước khi người học thử nhớ | Chỉ đưa hint theo từng mức, không bung đáp án ngay |

## §6. Bốn đường đi

- **Happy path:** tạo câu hỏi → trả lời → đúng → câu tiếp theo.
- **Low-confidence:** trả lời mơ hồ → hỏi rõ → đánh giá lại.
- **Failure:** retrieval/model không đủ căn cứ → thông báo giới hạn, cho chọn đoạn khác.
- **Correction:** sai → knowledge gap → evidence → câu bù → đánh giá lại.

## §7. Kiểm thử

- Groundedness: mọi kết luận kiến thức có citation hợp lệ.
- Evaluation consistency: cùng rubric không đổi verdict vô lý.
- Recovery: ambiguous/unsupported đi đúng nhánh.
- UX: người học hoàn tất phiên mà không cần người hướng dẫn.
- **Quality bar ban đầu:** ≥85% case qua toàn bộ tiêu chí và 100% case không được bịa nguồn. Chỉ chốt chính thức tại hạn CP4.

## §8. Phân công & kế hoạch

Cần điền tên thành viên cho spec/evidence/prompt/code/demo và danh sách willing users.

## §9. Changelog

| Thời điểm | Thay đổi | Lý do |
|---|---|---|
| 2026-07-30 | Chốt graph conditional và output có schema | Giảm hallucination và làm UI/test ổn định |
