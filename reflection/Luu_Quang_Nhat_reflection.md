# Reflection cá nhân — Lưu Quang Nhật

## 1. Vai trò & phân công

Trong nhóm, mình đảm nhận vai trò **Thành viên 3 — Lập trình Backend (FastAPI, LangGraph)**, chịu trách nhiệm chính về toàn bộ engine xử lý quiz trắc nghiệm (MCQ) và tính năng tóm tắt bài học (Summary).

## 2. Phần mình đã làm — chi tiết

### 2.1 Xây dựng Quiz Engine trắc nghiệm (MCQ) — commit `0cdf7f7`

Đây là phần chiếm nhiều công sức nhất. Mình thiết kế và code toàn bộ pipeline từ đầu đến cuối:

- **`quiz_graph.py`** — LangGraph workflow cho MCQ gồm 5 node: `retrieve_context` → `generate_quiz` → `evaluate_quiz` → `process_answer` → `analyze_error`. Graph có conditional routing: nếu quiz sinh ra không đạt quality gate thì tự retry (tối đa 3 lần), nếu user trả lời sai thì chạy nhánh `analyze_error` để phân tích misconception.
- **`quiz_generator.py`** — Dùng thư viện `instructor` (structured output) để ép LLM trả JSON đúng schema `QuizModel` của Pydantic. Prompt bắt buộc 4 đáp án/câu, đúng 1 đáp án, có citation nguồn. Tích hợp YAKE keyword extraction để sinh distractor chất lượng hơn.
- **`error_analyzer.py`** — LLM phân tích tâm lý học giáo dục: khi học viên chọn sai, tool này tìm ra misconception (đang nhầm khái niệm gì với khái niệm gì) thay vì chỉ nói "sai rồi". Đây chính là lõi "Active Recall" — giúp học viên biết mình hổng ở đâu.
- **`spaced_repetition.py`** — Tích hợp thuật toán FSRS (Free Spaced Repetition Scheduler) để lên lịch ôn tập: trả lời đúng → đẩy interval xa hơn, sai → lặp lại sớm.
- **Schemas Pydantic** — `schemas_quiz.py`, `schemas_error_analysis.py`, `schemas_spaced_repetition.py`: định nghĩa rõ ràng cấu trúc dữ liệu cho mọi input/output, đảm bảo type safety và validation.
- **`distractor_generator.py`**, **`bloom_prompts.py`**, **`compression.py`**, **`evaluator.py`**, **`tools.py`** — Các module phụ trợ: sinh đáp án nhiễu bằng NLP, prompt theo cấp độ Bloom (remember → analyze), nén context dài, đánh giá chất lượng quiz tự động.

### 2.2 Tính năng Tóm tắt & Đọc slide PDF — commit `27fb49c`, `8e7bfcc`

- **`content_sources.py`** — Module đọc PDF slide (Day 1, Day 2) bằng `pypdf`, trích xuất text kèm metadata `[Source: filename | Page: N]` để LLM có thể cite chính xác trang.
- **API endpoint `/api/summarize`** — Streaming response (SSE) cho tóm tắt bài giảng, hỗ trợ cả transcript lẫn PDF. Prompt system bắt buộc LLM cite nguồn `[Trang X]` hoặc `[Txx-xxx]`, tuyệt đối không bịa.
- **`structured_summarizer.py`** — Dùng `instructor` để sinh `StructuredSummary` (topics → micro-facts → citations). Hai chế độ: full-lesson (quét toàn bộ) và inline (trả lời câu hỏi cụ thể). Có fallback bằng dữ liệu curated khi LLM không khả dụng.
- **Frontend integration** — Cập nhật `app.js`, `index.html`, `style.css` để thêm tab Summary với streaming text và slide viewer.

### 2.3 API endpoints

Mình viết/mở rộng các endpoint trong `api.py`:
- `POST /api/quiz/sessions` — Khởi tạo phiên quiz MCQ
- `POST /api/quiz/answers` — Xử lý câu trả lời, trả kết quả + error analysis
- `POST /api/quiz/stream_error` — Streaming phân tích lỗi sai (giảm latency)
- `POST /api/summarize` — Streaming tóm tắt bài giảng
- `POST /api/structured-summary` — Tóm tắt có cấu trúc (JSON)
- `GET /api/slides/{filename}` — Phục vụ file PDF slide

## 3. AI đã hỗ trợ mình thế nào

Mình sử dụng AI (Claude, Cursor) xuyên suốt quá trình build, nhưng ở mức **augment chứ không phải automate**:

- **Scaffolding ban đầu**: Dùng AI để sinh skeleton cho các module (`quiz_graph.py`, `error_analyzer.py`). Ví dụ: mình mô tả flow LangGraph (5 node, conditional edge khi quiz fail, routing khi user sai) → AI sinh ra bộ khung TypedDict + node functions + routing logic. Nhưng mình phải sửa đáng kể: logic retry, shuffle options bằng `secrets.SystemRandom()`, xử lý edge case khi `current_question_idx` vượt quá số câu hỏi.
- **Prompt engineering**: AI giúp draft prompt tiếng Việt cho quiz generator và error analyzer. Mình iterate nhiều lần: ban đầu prompt sinh quiz không ép được đúng 4 đáp án → thêm luật "PHẢI có CHÍNH XÁC 4 đáp án" vào system prompt. Error analyzer ban đầu trả lời dài dòng → thêm constraint "tối đa 2 câu, khoảng 45 từ".
- **Debug**: Khi `instructor` + `QuizModel` validation fail liên tục, dùng AI phân tích error trace → phát hiện LLM đôi khi trả về 3 hoặc 5 options thay vì 4 → thêm `max_retries=3` và strict Pydantic validation.
- **Tích hợp FSRS**: Mình chưa dùng thư viện `fsrs` bao giờ. Dùng AI để hiểu API (`Card`, `Rating`, `Scheduler.review_card()`) rồi viết wrapper `schedule_next_review()`.

**Phần mình tự quyết định**, AI không làm thay:
- Kiến trúc tổng thể quiz graph (tách 5 node thay vì 1 monolith function)
- Quyết định dùng `instructor` thay vì parse JSON thủ công (giảm hallucinated schema)
- Thiết kế error analysis flow: khi sai → phân tích misconception → cho xem giải thích ngắn → tiếp câu tiếp theo (thay vì dừng lại hoặc bắt làm lại)
- Trade-off chọn `fast_llm_model` cho error analysis (cần nhanh, chấp nhận analysis kém hơn một chút) vs `llm_model` cho quiz generation (cần chính xác)

## 4. Bài học từ case fail của nhóm

### Case fail đáng nhớ nhất: MCQ sinh quiz bằng kiến thức ngoài nguồn (mcq-09, mcq-10 — Unsupported)

Trong kết quả eval run-02-full, hai case `mcq-09` và `mcq-10` bị fail vì LLM **tự dùng kiến thức ngoài để sinh quiz** khi input không đủ context. Case `mcq-09` hỏi về cài Python bằng Anaconda, `mcq-10` hỏi về Chiến tranh Thế giới 2 — cả hai đều hoàn toàn ngoài nội dung bài giảng AI, nhưng LLM vẫn "vui vẻ" sinh ra quiz hoàn chỉnh, format đúng, đáp án hợp lý. Giám khảo AI (LLM-as-a-judge) cũng không phát hiện vì nó chỉ chấm format và logic đáp án, không kiểm tra xem nội dung có nằm trong context không.

**Bài học rút ra:**

1. **Prompt "không bịa" chưa đủ để ngăn LLM bịa.** System prompt mình viết có dòng "Chỉ dựa vào nội dung được cung cấp, tuyệt đối không bịa thêm kiến thức ngoài" — nhưng khi context quá ngắn hoặc không liên quan, LLM vẫn rơi vào parametric knowledge thay vì từ chối. Cần thêm **guardrail ở code level**: kiểm tra context có đủ dài/liên quan không trước khi gọi sinh quiz, và nếu không đủ thì trả về lỗi thay vì để LLM tự xử.

2. **LLM-as-a-judge có blind spot.** Giám khảo AI chấm format + distractor quality tốt, nhưng không cross-check nội dung quiz với context gốc. Nếu làm lại, mình sẽ thêm một chiều đánh giá "faithfulness" riêng: kiểm tra mỗi câu hỏi và đáp án có trace được về đoạn cụ thể trong context không.

3. **"Phủ 4 lớp chỗ khó" không phải checkbox — mà phải thấm vào code.** Nhóm mình đã liệt kê kỹ 4 lớp rủi ro trong spec (Nguồn sự thật, Mơ hồ, Ngoài phạm vi, Domain), và tính năng essay đã xử lý tốt (100% pass). Nhưng ở MCQ pipeline, mình chưa implement đủ guardrail cho lớp ① (Nguồn sự thật) — cụ thể là thiếu bước validation "nội dung quiz có nằm trong context không?" sau khi LLM sinh ra. Đây là lỗ hổng thiết kế, không phải lỗi prompt.

Nếu có thêm thời gian, việc đầu tiên mình sẽ làm là thêm một node `validate_faithfulness` vào quiz graph — sau `generate_quiz` và trước `evaluate_quiz` — để cross-reference từng câu hỏi với context chunks bằng semantic similarity, loại bỏ câu hỏi không có evidence trước khi đưa đến học viên.
