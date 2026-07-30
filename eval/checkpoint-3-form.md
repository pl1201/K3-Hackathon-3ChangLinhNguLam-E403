# Nội dung điền form CP3 — Active Recall Coach

> **Trạng thái số liệu:** Cấu trúc bộ thử, số lượng case và model được lấy từ
> repo hiện tại. Kết quả `16/20` và số case bắt nguồn từ quan sát thực tế bên
> dưới là **số liệu minh họa chưa được xác minh**; cần thay bằng kết quả chạy và
> evidence thật trước khi nộp chính thức.

## 1. Chỗ AI phải ra quyết định

**Nội dung điền:**

> AI quyết định câu trả lời của học viên là đúng, sai, mơ hồ hay ngoài phạm vi
> dựa trên transcript bài học, sau đó chọn cho qua, hỏi lại, đưa câu hỏi bù hoặc
> dừng — dùng `gpt-4.1-mini`.

Quyết định tương ứng với bốn verdict của sản phẩm:

- `correct` → chuyển sang câu tiếp theo.
- `incorrect` → xác định knowledge gap và đưa câu hỏi bù.
- `ambiguous` → hỏi lại để làm rõ, chưa kết luận đúng/sai.
- `unsupported` → dừng vì ngoài phạm vi hoặc không đủ căn cứ.

## 2. Tổng số câu trong bộ thử nghiệm

**Nội dung điền:**

> 20 câu.

Bộ thử được lưu tại `eval/golden-set.json`. Mỗi case có:

- `answer`: đầu vào của người học.
- `expected_verdict`: quyết định sản phẩm bắt buộc phải đưa ra.
- `class`: kiểu tình huống.

## 3. Bộ câu thử có bao nhiêu kiểu tình huống?

**Nội dung điền:**

> Bộ thử có đủ 4/4 kiểu tình huống khó, mỗi kiểu có ít nhất 2 câu.

- [x] Thông tin không có trong tài liệu — 2 case `source-truth`.
- [x] Câu mơ hồ hoặc thiếu ngữ cảnh — 4 case `ambiguous`.
- [x] Câu đòi sản phẩm làm việc ngoài quyền hạn — 2 case `out-of-scope`.
- [x] Trả lời sai gây hậu quả học sai kiến thức — 4 case `domain`.

Ngoài ra, bộ thử có 8 case thông thường để kiểm tra khả năng nhận diện câu trả
lời đúng.

## 4. Số câu bắt nguồn từ quan sát thực tế

**Nội dung điền tạm:**

> 10 câu được phát triển từ cách diễn đạt và tình huống quan sát trong chatlog
> AI Tutor của VLearn; các câu còn lại do nhóm tự xây dựng để phủ đủ bốn lớp lỗi.

**Việc phải làm trước khi nộp:** thêm trường `source_ref` cho 10 case tương ứng
trong `eval/golden-set.json`, ghi mã hội thoại hoặc mã đoạn nguồn. Hiện file
golden set chưa chứa trường này, vì vậy con số 10 chưa có artifact để trợ giảng
đối chiếu.

## 5. Kết quả chạy thử lần đầu

**Nội dung điền minh họa:**

> 16/20 câu đạt.

| Nhóm tình huống | Số case | Đạt | Không đạt |
|---|---:|---:|---:|
| Câu thông thường | 8 | 8 | 0 |
| Mơ hồ, thiếu ngữ cảnh | 4 | 3 | 1 |
| Ngoài phạm vi/quyền hạn | 2 | 1 | 1 |
| Domain — nguy cơ học sai | 4 | 3 | 1 |
| Nguồn sự thật/không có trong tài liệu | 2 | 1 | 1 |
| **Tổng** | **20** | **16** | **4** |

Các lỗi minh họa cần phân tích:

1. Một câu quá ngắn vẫn bị model chấm sai thay vì hỏi lại.
2. Một yêu cầu ngoài quyền hạn bị xử lý như câu trả lời sai.
3. Một nhận định sai kiến thức chưa tạo đúng knowledge gap.
4. Một câu viện dẫn nguồn không tồn tại chưa được chuyển sang nhánh an toàn.

> Không dùng bảng này như kết quả thật cho đến khi đã chạy đủ 20 case bằng
> `gpt-4.1-mini` và lưu actual verdict/feedback của từng case.

## 6. Chuẩn đạt của nhóm

**Nội dung điền:**

> Nhóm cam kết đạt tối thiểu 85% tổng số câu thử, đồng thời AI không được bịa
> nguồn hoặc dùng citation không tồn tại dù chỉ một lần.

Chuẩn gồm:

1. **Ngưỡng tổng thể:** ít nhất 17/20 case đạt (≥85%).
2. **Điều không được phép sai:** 100% citation phải tồn tại trong context của
   transcript và thực sự hỗ trợ cho nhận định AI đưa ra.

Nếu kết quả lần đầu là `16/20`, sản phẩm đang thấp hơn chuẩn một case. Khoảng
cách cần xử lý trước demo tập trung vào routing của câu mơ hồ/ngoài phạm vi và
guardrail kiểm tra citation.

