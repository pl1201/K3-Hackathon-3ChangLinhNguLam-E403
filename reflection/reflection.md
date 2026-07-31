# Reflection cá nhân — Phùng Văn Linh

- **GitHub:** `pl1201`
- **Vai trò chính:** Product/UI Engineer, phụ trách luồng trải nghiệm học tập và tích hợp frontend với backend AI.
- **Sản phẩm:** Active Recall Coach — VLearn Study Studio.

## 1. Phần tôi phụ trách

Trong dự án, tôi tập trung biến ý tưởng Active Recall thành một luồng học hoàn chỉnh, thay vì chỉ tạo một màn hình chatbot. Người học có thể chọn nguồn, tóm tắt nhanh bài học, làm quiz hoặc tự luận, nhận phản hồi về lỗ hổng kiến thức và mở lại đúng slide/đoạn nguồn cần ôn.

Các phần chính tôi đã thực hiện:

1. **Thiết kế và phát triển giao diện học tập**
   - Xây dựng workspace gồm thư viện nguồn, khu vực đọc slide/transcript và AI Coach.
   - Tổ chức lại trang chính thành ba chế độ rõ ràng: Tóm tắt, Tạo Quiz và Tạo Tự luận.
   - Thiết kế lại giao diện theo nhận diện VLearn với tông trắng–xanh, logo, typography và hệ thống trạng thái nhất quán.
   - Bổ sung responsive, trạng thái loading/error/empty và các nút quay lại giữa các luồng.

2. **Phát triển luồng quiz Active Recall**
   - Cho phép chọn chủ đề, mức độ Bloom và số lượng câu hỏi linh hoạt từ 5 đến 25 câu.
   - Bổ sung câu hỏi ở mức hiểu, phân tích và vận dụng thay vì chỉ kiểm tra ghi nhớ.
   - Điều chỉnh vị trí đáp án đúng để tránh toàn bộ câu hỏi có đáp án A.
   - Tổng hợp các câu trả lời sai thành danh sách lỗ hổng kiến thức sau phiên học.

3. **Smart Fact Summarizer và Gap-to-Source Jump**
   - Chuyển nội dung bài giảng thành các micro-fact ngắn, có `Page X` hoặc `Chunk ID`.
   - Cho phép đặt câu hỏi tóm tắt trực tiếp trong khung chat thay vì chỉ có một bản tóm tắt cố định.
   - Khi người học bấm vào nguồn, giao diện mở đúng trang PDF hoặc đúng chunk transcript.
   - Thêm chế độ xem transcript đầy đủ để một bài có 98 đoạn không bị hiểu nhầm thành chỉ có 5 slide tóm tắt.

4. **Luồng tự luận ngắn**
   - Xây dựng API và UI tạo câu hỏi tự luận dựa trên đúng nguồn bài học.
   - Hiển thị đáp án tham khảo ngắn, rubric, phần đã làm tốt, phần cần bổ sung và bằng chứng trích từ chính câu trả lời.
   - Thay cơ chế điểm số tuyệt đối bằng đánh giá định tính để phản hồi phù hợp hơn với mục tiêu ôn tập.

Các commit thể hiện phần đóng góp chính của tôi:

- `71ff4a1`: mở rộng Active Recall Coach với topic selection, Bloom level, quiz 20–25 câu, gap summary và đọc PDF.
- `023275e`: cập nhật UI và core; bổ sung nguồn có citation, Smart Fact Summarizer và luồng tự luận.
- `12b6678`: hoàn thiện transcript viewer, đánh giá tự luận định tính, bằng chứng rubric và các kiểm thử liên quan.
- `2c504f9`: đồng bộ lại giao diện theo nhận diện trắng–xanh của VLearn.

## 2. AI đã hỗ trợ tôi như thế nào?

Tôi sử dụng AI như một công cụ pair-programming để:

- đọc nhanh cấu trúc FastAPI, schema Pydantic và luồng JavaScript hiện có;
- đề xuất cách chia trạng thái UI và phát hiện các điểm dễ mất logic khi chuyển giữa ba chế độ;
- hỗ trợ viết prompt có structured output cho tóm tắt, quiz và tự luận;
- gợi ý test case cho citation, rubric, đáp án tham khảo và transcript;
- rà soát CSS, responsive và tính nhất quán của design token.

Tôi không dùng nguyên kết quả AI rồi coi đó là đáp án cuối. Những quyết định quan trọng như bỏ điểm số tự luận, giữ citation ở từng micro-fact, phân biệt slide tóm tắt với transcript đầy đủ và giới hạn câu trả lời ngắn đều xuất phát từ việc quan sát lỗi thật trên sản phẩm và phản hồi người dùng. Sau mỗi thay đổi, tôi đối chiếu lại schema, API, UI và test để bảo đảm đề xuất của AI không làm sai luồng nghiệp vụ.

## 3. Case fail quan trọng nhất

Case fail rõ nhất xảy ra ở phần tự luận. Người học sao chép nguyên **đáp án tham khảo** vào ô trả lời nhưng hệ thống chỉ chấm **6.25/10**. LLM nhận xét rằng câu trả lời thiếu phần lịch sử AI và phần thực hành, trong khi chính đáp án tham khảo do hệ thống sinh ra cũng không chứa đầy đủ các ý đó.

Nguyên nhân không nằm ở người học mà ở thiết kế hệ thống:

- câu hỏi, đáp án tham khảo và rubric được sinh ra nhưng chưa được kiểm tra tính nhất quán với nhau;
- LLM vừa diễn giải rubric vừa quyết định trạng thái đạt/chưa đạt nên kết quả có thể dao động;
- giao diện hiển thị một con số có vẻ chính xác, nhưng con số đó không phản ánh một phép đo đủ tin cậy;
- phần nhận xét không chỉ ra bằng chứng cụ thể nào trong câu trả lời đã được dùng để đánh giá.

Tôi đã thay đổi hướng xử lý:

1. Mỗi tiêu chí rubric phải có một đoạn bằng chứng nằm nguyên văn trong đáp án tham khảo.
2. Khi đánh giá, tiêu chí chỉ được ghi nhận là đạt nếu có bằng chứng trích từ câu trả lời của người học.
3. Nếu câu trả lời khớp đáp án tham khảo thì các tiêu chí tương ứng phải được ghi nhận nhất quán.
4. Bỏ điểm tổng `/10`, chuyển sang ba trạng thái định tính: đáp ứng tốt, đáp ứng một phần hoặc cần bổ sung.
5. Giữ phần “Đã làm tốt”, “Cần bổ sung” và đáp án tham khảo ngắn để người học biết bước ôn tiếp theo.

## 4. Bài học cá nhân

Bài học lớn nhất của tôi là **structured output không đồng nghĩa với kết quả đáng tin cậy**. Pydantic có thể bảo đảm JSON đúng schema, nhưng không bảo đảm câu hỏi, đáp án và rubric nhất quán về mặt nội dung. Một con số do hệ thống tạo ra càng cụ thể thì người dùng càng dễ tin, vì vậy nếu không giải thích được cách hình thành con số đó, tốt hơn hết không nên hiển thị nó.

Tôi cũng nhận ra citation không chỉ là chi tiết trang trí. Nút “Mở Slide trang X” hoặc “Mở đoạn T06-xxx” biến phản hồi AI thành một hành động học tập có thể kiểm chứng. Đây là điểm giúp Active Recall Coach khác với một chatbot trả lời trôi chảy nhưng không dẫn người học trở lại nguồn.

Nếu có thêm thời gian, tôi sẽ ưu tiên:

1. thêm bước kiểm tra tự động tính bao phủ giữa câu hỏi, rubric và đáp án tham khảo trước khi hiển thị;
2. chạy evaluation lặp lại nhiều lần để đo độ ổn định của đánh giá định tính;
3. user test riêng luồng Gap-to-Source Jump để đo thời gian người học tìm lại đúng kiến thức sau khi trả lời sai.

Qua dự án, tôi hiểu rõ hơn rằng xây sản phẩm AI không chỉ là gọi model thành công. Phần khó hơn là thiết kế giới hạn, bằng chứng và cơ chế phục hồi để người dùng hiểu AI dựa vào đâu và biết phải làm gì tiếp theo khi AI hoặc chính họ trả lời chưa tốt.
