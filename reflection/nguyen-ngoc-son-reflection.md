# Reflection Cá Nhân - Nguyễn Ngọc Sơn

## 1. Vai trò trong nhóm
Trong dự án này, tôi đảm nhận vai trò chính là Kỹ sư AI (AI Engineer) kiêm Backend Developer. Tôi chịu trách nhiệm tối ưu hóa luồng tương tác của hệ thống, triển khai các tính năng cốt lõi và xây dựng bộ kiểm thử (Golden Set) tự động.

## 2. Phần công việc đã thực hiện
Dựa trên lịch sử commit, tôi đã trực tiếp đảm nhận các hạng mục sau:
- **Phát triển tính năng lõi:** Tích hợp tính năng đọc slide PDF và xây dựng luồng tóm tắt bài giảng (commit `27fb49c`).
- **Tối ưu hệ thống (Optimization):** Cải thiện độ trễ (latency) bằng cách áp dụng cơ chế Streaming SSE, tối ưu Model Routing để giảm chi phí khi gọi LLM, và sửa một số lỗi về luồng UI/UX (commit `fcb4c3b`).
- **Xây dựng Spec & Kiểm thử (Evaluation):** Viết script tạo Golden Set (30 cases) tự động từ dữ liệu chatlog thực tế, triển khai hệ thống LLM-as-a-judge (`run_eval_full.py`) để đánh giá toàn diện cả 3 tính năng: Tự luận, Trắc nghiệm và Tóm tắt theo đúng Rubric của Ban tổ chức. Đồng thời thiết lập và dọn dẹp cấu trúc repo (`e85c443`, `a154003`).

## 3. Cách thức sử dụng AI hỗ trợ
Trong suốt quá trình code, tôi sử dụng AI như một người lập trình cặp (Pair Programmer) đắc lực. Phương pháp làm việc của tôi là giao cho AI xử lý việc gõ boilerplate code và viết logic thô, tuy nhiên **tuyệt đối không phó mặc hoàn toàn**. 
Mỗi khi AI code xong một cụm tính năng hoặc script, tôi đều đọc và kiểm tra lại toàn bộ mã nguồn. Mục tiêu là để xác định xem AI đang hiểu sai ý đồ (intent) của mình ở điểm nào, từ đó đưa ra lời nhắc (prompt) điều chỉnh chính xác, đảm bảo hệ thống vận hành sát với thiết kế (Spec) nhất thay vì chỉ chạy được bề nổi. Việc soi kỹ code cũng giúp tôi sẵn sàng giải thích cơ chế hoạt động của bất cứ hàm nào khi bị Giám khảo hỏi (Vibe-coding rule).

## 4. Bài học lớn nhất từ thất bại của nhóm
Sai lầm lớn nhất và làm mất thời gian nhất của tôi trong dự án này nằm ở khâu **Kiểm thử (Evaluation)**. 
Vào thời điểm đó, nhóm vẫn chưa phát triển xong luồng công cụ (tool) và logic cho hai tính năng Sinh Trắc nghiệm (MCQ) và Tóm tắt. Tuy nhiên, vì nóng vội, tôi đã yêu cầu AI viết script test (LLM-as-a-judge) cho hai tính năng này ngay lập tức. Hệ quả là AI phải "đoán" hoặc mock các function chưa tồn tại, dẫn đến bộ test sinh ra bị sai lệch hoàn toàn so với thiết kế thực tế sau này. Khi hệ thống Backend thực sự hoàn thiện, toàn bộ bộ test cũ không thể tích hợp được. Cuối cùng, tôi buộc phải rollback, loại bỏ bộ test cũ và làm lại mọi thứ từ đầu (xây dựng lại `run_eval_full.py` và `golden-set-full.json`). 

**Bài học rút ra:** Luôn phải tôn trọng thứ tự của vòng đời phát triển phần mềm (SDLC). Không thể viết Integration Test / E2E Test tự động khi các thành phần chức năng (Core Logic) chưa thực sự định hình rõ ràng. Việc đi tắt không giúp nhanh hơn mà chỉ gây ra nợ kỹ thuật (Technical Debt) và phải đập đi xây lại.
