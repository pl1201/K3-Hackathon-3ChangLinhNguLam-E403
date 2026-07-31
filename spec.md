# AI SPEC — Active Recall Coach · VLearn

## §1. User & Job

- **Job executor:** Học viên vừa học xong một bài giảng VLearn và cần kiểm tra xem mình thực sự nhớ, hiểu phần nào.
- **Core JTBD:** Sau khi học xong một nội dung, kiểm tra khả năng tự nhớ lại (active recall) để biết chính xác phần cần ôn tiếp.
- **Problem statement:** Việc đọc lại tài liệu hoặc yêu cầu AI tóm tắt tạo cảm giác "quen thuộc ảo" nhưng không chỉ ra được lỗ hổng kiến thức thực sự.
- **Evidence:** Qua mining hơn 200 lượt chat (`eval/chatlog-candidates.json`), có hơn 40% lượt hỏi mang tính thụ động (chỉ yêu cầu tóm tắt hoặc giải thích lại):
  1. *"(Trang 50) tóm gọn những nội dung quan trọng nhất trong day 04 này"* (T0905)
  2. *"Giải thích đoạn bôi đen ở Trang 15."* (T0020)
  3. *"Giải thích đoạn bôi đen ở Trang 29: Sinh văn bản = đoán → nối vào câu → đoán tiếp"* (T0780)
  4. *"Giải thích đoạn bôi đen ở Trang 9: Nếu bài toán không cần dữ liệu mới... agent thường là overkill."* (T0367)
  5. *"kỹ thuật tối ưu prompt, cơ chế gọi tool và cách xử lý ngữ cảnh"* (T0092 - Học viên chỉ dán từ khóa thụ động)

## §2. Impact & quyết định chọn

Lát cắt ưu tiên là một phiên active recall trên **một bài học đã chọn**. Không build LMS, quản lý khóa học hay hệ thống chấm điểm chính thức.

## §3. Giải pháp tương tự

- **Quizlet AI / Flashcards**: 
  - *Flow*: Học viên lật thẻ nhớ keyword hoặc làm bài trắc nghiệm. 
  - *Đáng học*: Giao diện lặp lại ngắt quãng (Spaced Repetition) hiệu quả. 
  - *Đáng né*: Thường chỉ kiểm tra thuộc lòng (remember) chứ không kiểm tra hiểu (understand). 
  - *Mình khác gì*: Active Recall Coach (ARC) sinh câu hỏi phân tích (Bloom: Analyze/Understand) bám sát transcript khóa học thay vì học vẹt.
- **NotebookLM (Google)**:
  - *Flow*: Tải tài liệu, AI tự sinh FAQ hoặc Audio Overview, học viên chat hỏi đáp.
  - *Đáng học*: Trích dẫn nguồn (citation) cực kỳ chính xác.
  - *Đáng né*: Trải nghiệm hoàn toàn thụ động, AI làm hết phần việc, không thúc ép học viên tự nhớ.
  - *Mình khác gì*: ARC đưa học viên vào thế bị động phải trả lời câu hỏi trước, sai thì mới cung cấp citation để sửa lỗi, đúng bản chất "Active Recall".

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

- **Groundedness**: Mọi `evidence[].chunk_id` trong output phải ∈ tập `chunk_id` đã retrieve cho case đó (đếm được tự động, không cần đọc hiểu).
- **Evaluation consistency**: Case cùng `class` phải ra cùng `verdict` nếu answer giống nhau (hoặc chỉ khác biệt diễn đạt). Kiểm chứng bằng cách chạy lại 2 lần 1 subset và so khớp kết quả.
- **Recovery**: Mọi case có `class=ambiguous` phải trả về `next_action=clarify`; mọi case có `class=out-of-scope` phải trả về `next_action=stop`.
- **UX**: Người học hoàn tất phiên mà không cần người hướng dẫn (kiểm chứng bằng user testing với ≥3 người dùng mới).

**Tóm tắt kết quả đánh giá (Lượt gần nhất: run-02-full)**:
*(Golden Set 30 cases, phủ 4 lớp chỗ khó, >10 case từ chatlog thật)*

| Tính năng | Bộ Test | Tổng case | Pass Rate | Ghi chú |
|---|---|---|---|---|
| Đánh giá Quiz (Tự luận) | `run-02-full.md` | 10 | 100.0% | Xử lý tốt các case hỏi mớm, mơ hồ, ngoài lề. Không bịa nguồn. |
| Sinh Quiz Trắc nghiệm (MCQ) | `run-02-full.md` | 10 | 80.0% | Format chuẩn. 2 case fail do AI sinh quiz tự dùng kiến thức ngoài khi input không đủ context (Unsupported). |
| Tóm tắt Bài học (Summary) | `run-02-full.md` | 10 | 90.0% | 100% không bịa nguồn. 1 case fail do từ chối nhầm yêu cầu nằm trong context. |

**Quality bar ban đầu:** ≥85% case qua toàn bộ tiêu chí (Hiện tại đạt 90%).
Xem chi tiết báo cáo và nguyên nhân fail tại thư mục `eval/results/run-02-full.md`.

## §8. Phân công & kế hoạch

- **Thành viên 1**: Viết Spec & Thu thập Evidence.
- **Thành viên 2**: Kỹ thuật Prompt (LLM-as-a-judge, Sinh Quiz).
- **Thành viên 3**: Lập trình Backend (FastAPI, LangGraph).
- **Thành viên 4**: Code Frontend UI (Streaming SSE).
- **Willing users (CP5 Validation)**: [Blank 1], [Blank 2], [Blank 3] (Kiểm chứng UX xem luồng làm quiz có bị kẹt không, log feedback vào thư mục `validation/`).

## §9. Changelog

| Thời điểm | Thay đổi (Commit) | Lý do / Đóng góp |
|---|---|---|
| 2026-07-30 | **fcb4c3b** feat: optimize latency, streaming, model routing | Giảm độ trễ, tối ưu chi phí bằng LLM nhỏ, sửa lỗi UI reset tab |
| 2026-07-30 | **27fb49c** feat: thêm tính năng tóm tắt và đọc slide PDF | Hỗ trợ lấy nội dung PDF để phục vụ tóm tắt bài giảng |
| 2026-07-30 | **71ff4a1** feat: Active Recall Coach enhancements | Bổ sung bài thi 20-25 câu, Bloom taxonomy, và topic selection |
