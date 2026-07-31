# Nhật ký Kiểm chứng Người dùng (Validation Log)

## 1. Bảng Feedback nguyên văn
*(Bắt buộc: Tối thiểu 5 người ngoài nhóm, có ít nhất 2 willing users đã khai báo ở CP1)*

| Người thử (Tên/Vai trò) | Task được giao | Quan sát (Họ kẹt ở đâu?) | Quote nguyên văn (Trả lời 3 câu hỏi) | Mức độ nghiêm trọng |
|---|---|---|---|---|
| Trần Doãn Hưng (Học viên - Willing User) | Tự kiểm tra bài học | Đợi lâu khi AI sinh câu hỏi, tưởng máy đơ nên bấm reload. | "Mình hỏi xong đợi một lúc lâu không thấy AI phản hồi, không biết là nó đang nghĩ hay máy lag. Kết quả trả ra tốt nhưng đợi lâu làm tụt mood." | Cao |
| Ngô Khánh Trượng (Học viên - Willing User) | Bắt đầu làm Quiz | Loay hoay ở màn hình đầu, không biết phải gõ câu lệnh gì để bắt đầu. | "Vào app thấy mỗi ô chat, không biết chọn bài nào hay phải gõ gì. Giá mà có menu chọn sẵn bài học thì dễ dùng hơn." | Cao |
| Cao Huy Phúc (Học viên - Willing User) | Muốn xem lại lý thuyết | Làm sai câu hỏi, phải mở tab khác để tìm slide đọc lại. | "Lúc AI chỉ ra lỗ hổng, mình muốn mở slide gốc lên đối chiếu ngay nhưng hệ thống không có, phải chuyển qua hệ thống LMS gốc rất phiền." | Trung bình |
| Kim Mạnh Hưng (HV nhóm khác) | Làm Quiz nâng cao | Trả lời đúng liên tục nhưng cảm giác chán vì câu hỏi dễ. | "Câu hỏi đa số là nhắc lại định nghĩa. Mình muốn có câu hỏi bắt phân tích sâu hơn hoặc làm bài thi dài 20 câu để test tổng lực." | Trung bình |
| Nguyễn Thị Xuân Mai (HV nhóm khác) | Đọc lại slide bài giảng | Tìm kiếm từ khóa trên PDF khó khăn do slide nhiều chữ. | "Slide chữ nhiều quá, mình muốn hệ thống tự động bôi đậm (highlight) những từ khóa quan trọng ngay trên file PDF để dễ nhìn hơn." | Thấp |

## 2. Tổng hợp & Hành động (Action Items)

- **Chủ đề lặp nhiều nhất:** Tình trạng người dùng lúng túng khi bắt đầu (thiếu định hướng), trải nghiệm chờ đợi bị gián đoạn (latency cao), và nhu cầu tương tác với tài liệu gốc (slide PDF).
- **Thay đổi đã làm ngay (Ghi vào Changelog):** 
  - **Tối ưu Streaming SSE (Commit fcb4c3b):** Hiển thị câu trả lời dạng luồng (streaming) ngay lập tức để giảm độ trễ (latency), giúp user không cảm thấy máy bị đơ.
  - **Menu Topic Selection (Commit 71ff4a1):** Thêm hộp thoại chọn Topic để người dùng click bắt đầu ngay thay vì phải tự gõ lệnh.
  - **Tích hợp đọc Slide PDF & Bloom Taxonomy (Commit 27fb49c, 71ff4a1):** Thêm tính năng hiển thị slide PDF trực tiếp trên giao diện để tiện tra cứu. Bổ sung các cấp độ câu hỏi tư duy bậc cao (HOTS) và bài test dài 20-25 câu.
- **Giữ nguyên có lý do (Không đổi):** 
  - **Tính năng tự động bôi đậm (Highlight) từ khóa trên PDF:** Việc can thiệp vẽ (draw/highlight) lên bề mặt PDF đòi hỏi xử lý vector phức tạp trên Frontend, làm tăng đáng kể kích thước gói tin và làm chậm tốc độ render. Thay vì can thiệp trực tiếp vào file PDF, chúng tôi khuyến khích người dùng sử dụng tính năng "Tóm tắt" để AI trích xuất và hiển thị các từ khóa quan trọng ngay tại cửa sổ chat.
- **Đưa vào Backlog (Sẽ làm sau):** Thêm tính năng nhận diện giọng nói (Voice-to-text) để hỗ trợ nhập liệu nhanh hơn cho người lười gõ phím.
