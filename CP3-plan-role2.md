# Plan CP-03 — Role 2 (AI & Prompt Engineer) — Active Recall Coach

> Đưa file này cho AI agent (Claude Code) làm theo thứ tự task. Agent chỉ được sửa các
> file trong danh sách "Được đụng" ở mỗi task — **không sửa `codebase/`, `coach/api.py`,
> `coach/observability.py`** trừ khi task nói rõ, vì đó là phần của Role 3.

## 0. Bối cảnh đã audit (để agent không làm lại việc đã có)

Repo hiện đã có sẵn (không cần build lại):
- `coach/prompts.py` — 2 system prompt (question generator + answer evaluator), đã có ràng buộc
  "chỉ dùng CONTEXT", đã có 4 nhãn verdict (`correct/incorrect/ambiguous/unsupported`).
- `coach/schemas.py` — Pydantic schema ép structured output (`RecallQuestion`, `AnswerEvaluation`).
- `coach/graph.py` — LangGraph thật, gọi OpenAI qua `langchain_openai`, có guardrail chặn
  citation không hợp lệ (`validate-question-citations`, `validate-evaluation-citations`),
  có `mock` fallback khi thiếu API key (gắn nhãn `mode: mock`, README đã ghi rõ mock không
  tính là AI call thật cho CP3).
- `eval/golden-set.json` — **20 case, nhưng toàn bộ là case tự viết tay** (`normal:8,
  ambiguous:4, domain:4, out-of-scope:2, source-truth:2`). Chưa có case nào gắn nguồn
  chatlog thật.
- `spec.md` §5-§7 — đã có khung 4 lớp chỗ khó, 4 đường đi, quality bar dự kiến (≥85% case
  đạt, 100% không bịa citation).

**2 gap chặn CP3:**
1. Rubric R4 đòi `≥10 case từ chatlog thật` trong golden set — hiện tại là 0.
2. Không có script nào chạy golden set qua AI thật và xuất bảng kết quả có % — checklist
   CP3 đòi "bảng kết quả lượt 1 có %", hiện chưa tồn tại (`eval/` chỉ có `golden-set.json` +
   `README.md`).

Đã xác nhận trong `data/vlearn-pack/chatlog/...csv`: có **66 lượt hỏi của học viên** chứa
từ khoá liên quan bài `transcript-06-clean.md` (transformer, attention, token,
discriminative/generative AI) — đủ nguyên liệu để mining ≥10 case thật.

---

## Task 1 — Mining ≥10 case thật từ chatlog, phủ nhiều bài (không chỉ transcript-06)

> **Quyết định phạm vi (đã chốt với team):** prototype sẽ mở rộng cho học viên chọn bài học
> bất kỳ trong 6 transcript (Role 3 làm phần chọn lesson trên UI). Vì vậy golden set từ bây
> giờ nên phủ **nhiều lesson_id**, không chỉ `transcript-06-clean`. Backend đã sẵn sàng nhận
> `lesson_id` bất kỳ (`coach/api.py` truyền thẳng `payload.lesson_id` vào graph, không hardcode
> ở tầng backend) — Role 2 **không cần đợi Role 3 xong UI** mới mining/eval đa bài được.

**Mục tiêu:** có ≥10 case trong golden set gắn được `turn_id` thật, kiểm lại được, và trải
ra ≥2-3 lesson khác nhau trong 6 transcript (không dồn hết vào 06).

**Được đụng:** file mới `eval/mine_chatlog_candidates.py`, output `eval/chatlog-candidates.json`
(file trung gian, không phải golden set cuối).

**Lưu ý quan trọng:** cột `day_code` trong `chat_history_anonymized_for_hackathon.csv`
**không map sạch 1-1 vào 6 file transcript** (đa số là mã slide dạng `Lecture_material_ms...`,
phần lớn còn lại là `New learning material` — chính `DATA_DICTIONARY.md` cũng nghi đây là
placeholder/bug). **Không dùng `day_code` để lọc theo bài.** Phải mining bằng từ khoá chủ đề
của từng transcript.

**Cách làm:**
1. Đọc `data/vlearn-pack/chatlog/chat_history_anonymized_for_hackathon.csv` bằng pandas.
2. Với mỗi transcript trong 6 file, xác định bộ từ khoá chủ đề riêng (đọc tiêu đề H1 +
   lướt nhanh nội dung từng file để rút từ khoá, không đoán):
   - `transcript-01` (Xác định bài toán kinh doanh cho AI) → `bài toán|pain|use case|ROI|...`
   - `transcript-02` (Chỉ số thành công & mức tự động hoá) → `metric|chỉ số|tự động hoá|automation level|...`
   - `transcript-03` (Soi bài toán các nhóm · tự động hoá & ràng buộc) → `ràng buộc|constraint|...`
   - `transcript-04` (Foundation: LLM, transformer, attention, agent) → `transformer|attention|agent|token`
   - `transcript-05` (Bài toán · đánh giá · dữ liệu) → `đánh giá|eval|dữ liệu|data|...`
   - `transcript-06` (Foundation: transformer & attention) → `generative|discriminative|transformer|attention|token|next-token`
   - **transcript-04 và 06 trùng chủ đề transformer/attention** — khi match được 1 dòng chatlog,
     phải xác định nó gần nội dung file nào hơn bằng cách so overlap từ khoá với chunk thật
     trong từng file (không chỉ đoán theo tên bài), rồi gắn đúng `lesson_id` + `chunk_id` tương
     ứng.
3. Lọc `role == "student"`, `content` chứa từ khoá của lesson tương ứng.
4. Với mỗi dòng match, lấy kèm `turn_id`, `content` (student) và câu trả lời `tutor` cùng
   `turn_id` (để đối chiếu bối cảnh — không phải để dùng làm expected answer, vì tutor có
   thể sai).
5. Xuất `eval/chatlog-candidates.json`: list gồm `turn_id`, `lesson_id` (transcript nào gần
   nhất), `student_message` (**chỉ trích ngắn phần thể hiện hiểu biết/nhầm lẫn của học viên,
   không copy nguyên văn dài** — tuân README mục "Bảo mật dữ liệu"), `note` (agent tự phân
   loại sơ bộ: có vẻ đúng / sai / mơ hồ / hỏi ngoài phạm vi).
6. In ra terminal candidate theo từng lesson (mục tiêu ít nhất 3-4 lesson có candidate, không
   chỉ 06) để mình (người, không phải agent) chọn tay 10-12 case tốt nhất, dàn đều — agent
   KHÔNG tự quyết định case nào vào golden set, chỉ chuẩn bị danh sách ứng viên có phân loại
   sơ bộ theo lesson.

**Điều kiện dừng task:** `eval/chatlog-candidates.json` tồn tại, ≥20 candidate trải ra ≥3
lesson_id khác nhau, mỗi candidate có `turn_id` truy được ngược vào file csv gốc và `lesson_id`
truy được ngược vào đúng file transcript (kiểm bằng cách grep `chunk_id` tương ứng có tồn tại
trong đúng file `.md`).

---

## Task 2 — Cập nhật `eval/golden-set.json` lên chuẩn CP3

**Mục tiêu:** golden set ≥20 case, đủ cấu trúc rubric R4 đòi:
- ≥2 case / mỗi lớp trong 4 lớp chỗ khó (nguồn sự thật, mơ hồ, ngoài phạm vi, domain)
- 8-10 case thường (normal)
- 2-4 case hiếm
- **≥10 case trong tổng số bắt nguồn từ chatlog thật** (không phải case riêng — có thể case
  "normal" hay "domain" cũng lấy nguồn chatlog, miễn đủ ≥10 case có `source: "chatlog"`)

**Được đụng:** `eval/golden-set.json`, `eval/README.md`.

**Cách làm:**
1. Mở rộng schema mỗi case, thêm 3 field mới (giữ nguyên field cũ `id/answer/expected_verdict/class`):
   ```json
   {
     "id": "chatlog-01",
     "lesson_id": "transcript-04-clean",
     "answer": "...",
     "expected_verdict": "ambiguous",
     "class": "ambiguous",
     "source": "chatlog",
     "source_ref": "T0984"
   }
   ```
   Case tự viết tay giữ `"source": "synthetic"`, không cần `source_ref`, nhưng **vẫn cần
   `lesson_id`** vì eval script (Task 3) chạy per-lesson. 20 case cũ hiện có mặc định
   `lesson_id: "transcript-06-clean"` khi bổ sung field — không cần viết lại nội dung, chỉ
   thêm field.
2. Từ 10-12 case đã chọn tay ở Task 1, viết lại thành entry golden set đúng format trên.
   Với mỗi case: agent viết `expected_verdict` dựa theo đúng taxonomy đã định nghĩa trong
   `coach/prompts.py` (correct/incorrect/ambiguous/unsupported) — **việc gán nhãn này phải
   do người review lại**, agent chỉ đề xuất nhãn kèm lý do 1 câu để dễ review nhanh.
3. Đảm bảo sau khi thêm, tổng vẫn phủ đủ ≥2 case mỗi lớp trong 4 lớp taxonomy (①②③④) —
   nếu case chatlog dồn hết vào 1 lớp, bổ sung thêm case synthetic để bù lớp còn thiếu.
4. Cập nhật `eval/README.md`: ghi rõ tỷ lệ case thật/synthetic, cách kiểm lại từng case
   chatlog (mở csv, tìm theo `turn_id`).

**Điều kiện dừng task:** `eval/golden-set.json` có ≥20 case, đếm bằng script:
`source=="chatlog"` ≥10, mỗi `class` trong {`nguon-su-that`/`mo-ho`/`ngoai-pham-vi`/`domain`
— dùng đúng tên lớp đang có: `source-truth/ambiguous/out-of-scope/domain`} ≥2 case, và
`lesson_id` xuất hiện ≥3 giá trị khác nhau trong toàn bộ golden set (không dồn hết vào
`transcript-06-clean`).

---

## Task 3 — Viết `eval/run_eval.py` (bảng kết quả AI thật, có %)

**Mục tiêu:** script chạy toàn bộ golden set qua **AI thật** (không mock), xuất bảng kết
quả — đây là artifact chính TA xác minh tại CP3 ("lời gọi AI thật, không hardcode").

**Được đụng:** file mới `eval/run_eval.py`, output `eval/results/run-01.md` +
`eval/results/run-01.json`.

**Cách làm (bám đúng graph đã có, không viết lại logic gọi model):**
1. Import trực tiếp `coach_graph` từ `coach.graph` và `get_settings` từ `coach.config`.
2. Ở đầu script, `assert settings.llm_enabled`, nếu False thì `raise SystemExit` với thông
   báo rõ "cần OPENAI_API_KEY thật trong .env, không chạy mock cho CP3" — tránh vô tình nộp
   kết quả mock.
3. Với mỗi case trong golden set:
   - Tạo `thread_id` riêng (uuid) cho mỗi case để không lẫn state giữa các case.
   - Gọi graph 2 bước qua `coach_graph.invoke`:
     a. `operation="start"`, `lesson_id=case["lesson_id"]` (**đọc từ chính case, không
        hardcode `transcript-06-clean`** — mỗi case chạy trên đúng bài nó thuộc về) → lấy
        `question` thật do AI sinh ra (KHÔNG dùng câu hỏi cố định `_mock_question`).
     b. `operation="answer"`, `answer=case["answer"]` → lấy `evaluation` thật.
   - So sánh `evaluation["verdict"]` với `case["expected_verdict"]` → `pass/fail`.
   - Ghi chú kỹ thuật: nhánh mock fallback trong `graph.py` (khi thiếu API key) có 1 đoạn
     hardcode chỉ tìm `chunk_id == "T06-051"` làm anchor. Script `run_eval.py` đã tự chặn
     mock ở bước 2 (`assert settings.llm_enabled`) nên đoạn hardcode này **không ảnh hưởng**
     tới lượt eval thật — chỉ nêu ra để không tưởng nhầm là bug khi đọc code.
   - Kiểm tra thêm điều kiện an toàn riêng (không tính vào pass/fail chính nhưng phải log):
     mọi `evidence[].chunk_id` phải nằm trong `chunks` đã retrieve (đã có guardrail trong
     graph rồi, ở đây chỉ double-check và đếm số case có citation bịa = phải luôn = 0).
4. Xuất `eval/results/run-01.json`: list chi tiết từng case (input, verdict thật, verdict kỳ
   vọng, pass/fail, evidence, thời gian chạy, model dùng).
5. Xuất `eval/results/run-01.md`: bảng markdown gồm toàn bộ case (kể cả case fail — **không
   được lọc bỏ case fail**, đúng nguyên tắc "kết quả đo được ghi nhận trung thực" của rubric),
   cột: `id | lesson_id | class | expected | actual | pass? | ghi chú lỗi (nếu fail)`. Cuối
   bảng: tổng % pass toàn bộ, % pass từng lớp, % pass từng `lesson_id` (để lộ ra sớm nếu AI
   yếu hơn hẳn ở 1-2 bài cụ thể — ví dụ bài có nhiều thuật ngữ hơn), % case có citation hợp lệ
   (phải = 100%), so với quality bar trong `spec.md` §7 (≥85% / 100%).
6. Nếu tổng % pass < 85% hoặc có case bịa citation → script tự in ra danh sách case fail kèm
   lý do (verdict lệch gì) để dễ đưa vào Task 4.

**Điều kiện dừng task:** chạy `python -m eval.run_eval` (hoặc `python eval/run_eval.py`
tuỳ cấu trúc import) với `OPENAI_API_KEY` thật trong `.env` → ra `eval/results/run-01.md`
có đủ 20+ dòng, có dòng tổng %, không có case nào bị bỏ sót.

---

## Task 4 — Vòng tinh chỉnh prompt dựa trên kết quả lượt 1 (nếu cần)

**Chỉ chạy nếu Task 3 cho % pass < 85% hoặc có citation bịa.**

**Được đụng:** `coach/prompts.py` — chỉ 2 prompt string, không đụng logic graph.

**Cách làm:**
1. Đọc danh sách case fail Task 3 in ra.
2. Với mỗi case fail, xác định fail thuộc dạng nào:
   - Model quá dễ dãi cho `correct` dù thiếu ý (`expected=incorrect` nhưng ra `correct`)
     → siết `EVALUATION_PROMPT` mục nhãn `correct` (yêu cầu đủ toàn bộ expected_points).
   - Model không hỏi lại khi câu ngắn/mơ hồ → thêm ví dụ minh hoạ ranh giới "bao nhiêu từ /
     bao nhiêu ý thì coi là ambiguous" vào prompt.
   - Model trả lời câu hỏi ngoài phạm vi (vd đòi cấp chứng chỉ) mà không nhận ra
     `unsupported` → thêm rule tường minh: yêu cầu ngoài nội dung học thuật của CONTEXT
     (hành chính, cấp phát, xác nhận) luôn là `unsupported`.
3. Sửa `coach/prompts.py`, chạy lại Task 3 script (lượt 2), lưu thành `eval/results/run-02.md`
   — **giữ nguyên `run-01.md`, không ghi đè**, đúng rule "không ghi đè hoặc xóa case fail".
4. Lặp tối đa 2-3 lượt trong ngày 1; sau `spec.md` commit 23:59 N1, quality bar bị khoá —
   không được đổi bar để khớp kết quả, chỉ được tiếp tục cải thiện prompt và log thêm lượt mới.

**Điều kiện dừng task:** lượt gần nhất đạt ≥85% và 100% citation hợp lệ, hoặc hết thời gian
CP3 — trong trường hợp thứ hai, giữ nguyên kết quả thật kèm phân tích nguyên nhân fail (rubric
R4 chấp nhận % thấp miễn ghi nhận trung thực và có phân tích).

---

## Task 5 — Cập nhật `spec.md` §7 và `eval/README.md` để chấm được R4

**Được đụng:** `spec.md` (chỉ §7), `eval/README.md`.

**Cách làm:**
1. `spec.md` §7 hiện có 4 chiều chất lượng (Groundedness, Evaluation consistency, Recovery,
   UX) nhưng chưa có **định nghĩa kiểm chứng được** cho từng chiều (rubric R4 đòi "người
   ngoài nhóm chấm ra cùng kết quả"). Viết lại mỗi chiều thành 1 điều kiện đo được, ví dụ:
   - Groundedness: mọi `evidence[].chunk_id` trong output phải ∈ tập `chunk_id` đã retrieve
     cho case đó → đếm được, không cần đọc hiểu.
   - Evaluation consistency: case cùng `class` phải ra cùng `verdict` nếu answer giống nhau
     ±diễn đạt → check bằng cách chạy lại 2 lần 1 subset, so khớp.
   - Recovery: mọi case `class=ambiguous` phải có `next_action=clarify`; mọi case
     `class=out-of-scope` phải có `next_action=stop`.
2. Thêm bảng tóm tắt kết quả lượt chạy gần nhất (link tới `eval/results/run-0N.md`) vào cuối
   §7.
3. `eval/README.md`: liệt kê rõ cách chạy lại toàn bộ (`python eval/run_eval.py`), yêu cầu
   `.env` có `OPENAI_API_KEY` thật, giải thích cấu trúc `eval/results/`.

**Điều kiện dừng task:** `spec.md` §7 mỗi chiều chất lượng đọc xong là biết chấm case cụ thể
ra pass/fail mà không cần hỏi lại nhóm.

---

## Task 6 — Checklist trước khi báo TA tại CP3

Không phải task code — checklist người làm tự tick trước 16:00 N1 (K3) / 10:30 N2 (K4):

- [ ] `.env` có `OPENAI_API_KEY` thật, **không commit** (`.gitignore` đã có `.env` — kiểm tra
      lại bằng `git status` trước khi commit).
- [ ] `eval/golden-set.json` ≥20 case, ≥10 case `source:"chatlog"` kiểm lại được qua `turn_id`.
- [ ] `eval/results/run-0N.md` tồn tại, sinh từ lượt chạy AI thật gần nhất (không phải mock —
      kiểm bằng field `mode` trong log/trace nếu có, hoặc chạy lại trước mặt TA).
- [ ] Bảng kết quả có đủ mọi case kể cả fail, có % tổng và % từng lớp.
- [ ] `spec.md` §7 có quality bar bằng số (đã có: ≥85% / 100% không bịa citation).
- [ ] Không có data pack (`data/vlearn-pack/`) nào bị đổi/xoá — chỉ trích ngắn vào golden set.

---

## Ghi chú phối hợp với Role 3 (đa bài học)

- Backend (`coach/api.py`, `coach/retrieval.py`) đã hỗ trợ `lesson_id` bất kỳ — Role 2 không
  cần đợi Role 3 để mining/eval đa bài.
- 2 chỗ Role 3 cần sửa để UI thực sự cho chọn bài (không thuộc phạm vi Role 2, chỉ ghi chú lại
  để bàn giao đúng chỗ):
  - `codebase/app.js` dòng 56 đang hardcode `lesson_id: "transcript-06-clean"` khi gọi
    `POST /api/sessions`.
  - `coach/graph.py` dòng ~59 (nhánh mock fallback) hardcode `chunk_id == "T06-051"` làm
    anchor — chỉ ảnh hưởng khi chạy mock (thiếu API key), không chặn CP3, nhưng nếu Role 3
    muốn demo mock cho bài khác 06 thì cần sửa chỗ này.
- `coach/schemas.py` — `StartSessionRequest.lesson_id` default vẫn để `"transcript-06-clean"`
  là hợp lý (giữ hành vi cũ khi không truyền gì), không cần đổi.

## Ghi chú phạm vi cho agent

- Không sửa `coach/graph.py`, `coach/schemas.py`, `coach/api.py`, `codebase/*` — đó là phần
  Role 3 đã build, chỉ Role 2 mới đụng `coach/prompts.py` và toàn bộ `eval/`.
- Không tự ý hạ quality bar trong `spec.md` để khớp kết quả thấp — nếu kết quả thấp, ghi nhận
  trung thực + phân tích nguyên nhân, không sửa bar.
- Không paste nguyên văn dài từ csv chatlog vào bất kỳ file nào commit lên repo — chỉ trích
  đoạn ngắn cần thiết, giữ `turn_id` để trace ngược.