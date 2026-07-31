/* ============================================================
   VLearn Study Studio — App Logic
   Agent: Summarize → Topic Select → Quiz (5-25 câu) → Gap Summary
   ============================================================ */

// ─── State ───────────────────────────────────────────────────
const state = {
  sessionId: null,
  essaySessionId: null,
  essayQuestion: null,
  selectedIndex: null,
  question: null,
  lastAction: "start",
  targetTotal: 20,
  answered: 0,
  correct: 0,
  gaps: 0,
  agentPhase: "idle",   // idle | thinking | summary | topic | quiz | done | error
  slideIndex: 0,
  slideTotalCount: 0,
  activeSourceKey: "transcript-06-clean",
  contentMode: "summary",
  selectedBloom: "analyze",
  selectedQuizCount: 20,
  selectedTopicQuery: null,
  structuredSummary: null,
  summaryLessonId: null,
  errorLog: [],         // [{question, correctAnswer, userAnswer, misconception}]
};

// ─── Helpers ─────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);
const transcriptCache = new Map();

function showToast(message, duration = 2200) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => toast.classList.remove("show"), duration);
}

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || `Lỗi ${res.status}`);
  return payload;
}

async function requestStream(path, options, onChunk) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Lỗi ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onChunk(decoder.decode(value));
  }
}

// ─── Agent UI Helpers ─────────────────────────────────────────
const AGENT_PANELS = [
  "agent-welcome",
  "agent-thinking",
  "agent-summary",
  "agent-summary-chat",
  "agent-topic-select",
  "agent-quiz-flow",
  "agent-essay",
  "agent-done",
  "agent-error",
];

function showAgentPanel(id) {
  AGENT_PANELS.forEach((p) => {
    const el = $(`#${p}`);
    if (el) el.classList.toggle("hidden", p !== id);
  });
}

function setAgentStatus(status /* idle|busy|active */, label) {
  const chip = $("#agent-status-chip");
  const avatar = $(".agent-avatar");
  chip.className = `agent-status-chip ${status === "idle" ? "" : status}`;
  $("#agent-status-label").textContent = label;
  if (status === "busy") {
    avatar.classList.add("active");
  } else {
    avatar.classList.remove("active");
  }
}

function setProgressStep(steps) {
  const map = { "ap-read": steps.read, "ap-summarize": steps.summarize, "ap-quiz": steps.quiz };
  Object.entries(map).forEach(([id, s]) => {
    const el = $(`#${id}`);
    if (!el) return;
    el.className = "ap-step" + (s === "active" ? " active" : s === "done" ? " done" : "");
    const em = el.querySelector("em");
    em.textContent = s === "done" ? "✓ Xong" : s === "active" ? "Đang chạy…" : "Chờ";
  });
}

function updateAgentProgress() {
  const pct = state.targetTotal ? Math.round((state.answered / state.targetTotal) * 100) : 0;
  $("#agent-progress-fill").style.width = `${pct}%`;
  $("#agent-answered").textContent = `${state.answered} đã trả lời`;
  $("#agent-accuracy").textContent = state.answered
    ? `${Math.round((state.correct / state.answered) * 100)}% chính xác`
    : "—";
}

// ─── Health Check ─────────────────────────────────────────────
async function checkHealth() {
  const badge = $("#runtime-badge");
  try {
    const health = await request("/api/health");
    const isLive = health.llm === "configured";
    badge.className = `runtime-badge ${isLive ? "live" : "mock"}`;
    badge.textContent = isLive ? "Hệ thống sẵn sàng" : "Chế độ demo";
  } catch {
    badge.className = "runtime-badge danger";
    badge.textContent = "Backend mất kết nối";
  }
}

// ─── Agent: Start → Summary → Topic Select → Quiz ─────────────
async function agentStart() {
  state.agentPhase = "thinking";
  state.answered = 0;
  state.correct = 0;
  state.gaps = 0;
  state.errorLog = [];
  state.selectedIndex = null;
  updateAgentProgress();

  setAgentStatus("busy", "Đang phân tích…");
  showAgentPanel("agent-thinking");
  $("#agent-thinking-text").textContent = "Đang đọc và phân tích bài học…";
  setProgressStep({ read: "active", summarize: "wait", quiz: "wait" });

  const step2Timer = setTimeout(() => {
    if (state.agentPhase === "thinking") {
      $("#agent-thinking-text").textContent = "Đang tóm tắt nội dung…";
      setProgressStep({ read: "done", summarize: "active", quiz: "wait" });
    }
  }, 800);

  const step3Timer = setTimeout(() => {
    if (state.agentPhase === "thinking") {
      $("#agent-thinking-text").textContent = "Đang chuẩn bị câu hỏi…";
      setProgressStep({ read: "done", summarize: "done", quiz: "active" });
    }
  }, 1600);

  try {
    clearTimeout(step2Timer);
    clearTimeout(step3Timer);
    setProgressStep({ read: "done", summarize: "done", quiz: "done" });

    const lessonId = $("#lesson-id").value;
    await showSummary(lessonId);
  } catch (err) {
    clearTimeout(step2Timer);
    clearTimeout(step3Timer);
    showAgentError(err.message);
  }
}

// ─── Summary ─────────────────────────────────────────────────
function openSummaryWorkspace() {
  state.agentPhase = "summary";
  setAgentStatus("active", "Sẵn sàng tóm tắt");
  showAgentPanel("agent-summary");

  const messages = $("#summary-inline-messages");
  if (!messages.children.length) {
    appendInlineSummaryMessage(
      "assistant",
      "Chào bạn! Hãy nhập bài, chủ đề hoặc khoảng slide cần ôn. Mình sẽ trả về các điểm học cốt lõi kèm đúng nguồn."
    );
  }

  if (state.structuredSummary && state.summaryLessonId === $("#lesson-id").value) {
    renderStructuredSummary(state.structuredSummary, state.summaryLessonId);
  }

  $("#summary-inline-input")?.focus();
}

function goHome() {
  state.agentPhase = "idle";
  setAgentStatus("idle", "Sẵn sàng");
  showAgentPanel("agent-welcome");
}

async function showSummary(lessonId) {
  state.agentPhase = "summary";
  setAgentStatus("busy", "Đang tóm tắt…");
  showAgentPanel("agent-summary");

  const body = $("#summary-body");
  body.innerHTML = `<div class="summary-loading">Đang lọc các điểm học quan trọng…</div>`;

  try {
    const data = await request("/api/structured-summary", {
      method: "POST",
      body: JSON.stringify({ lesson_id: lessonId }),
    });
    state.structuredSummary = data.summary;
    state.summaryLessonId = lessonId;
    renderStructuredSummary(data.summary, lessonId);
    appendInlineSummaryMessage("assistant", "Mình đã lọc các điểm cốt lõi và gắn nguồn để bạn xem lại nhanh.");
    setAgentStatus("active", "Tóm tắt xong");
  } catch (err) {
    const fallback = getSummaryForLesson(lessonId);
    renderLegacySummary(fallback);
    setAgentStatus("active", "Bản tóm tắt dự phòng");
    showToast("Chưa tạo được dẫn nguồn động; đang dùng bản tóm tắt dự phòng.");
  }
}

function appendInlineSummaryMessage(role, text) {
  const message = document.createElement("div");
  message.className = `summary-inline-message ${role}`;
  message.textContent = text;
  $("#summary-inline-messages").appendChild(message);
  message.scrollIntoView({ block: "nearest" });
  return message;
}

async function sendInlineSummaryMessage() {
  const input = $("#summary-inline-input");
  const query = input.value.trim();
  if (!query) return;
  input.value = "";
  appendInlineSummaryMessage("user", query);
  const answer = appendInlineSummaryMessage("assistant loading", "Đang lọc micro-facts từ nguồn…");
  setAgentStatus("busy", "Đang tóm tắt…");
  const lessonId = $("#lesson-id").value;

  try {
    const data = await request("/api/structured-summary", {
      method: "POST",
      body: JSON.stringify({
        lesson_id: lessonId,
        query,
      }),
    });
    answer.classList.remove("loading");
    answer.textContent = "";
    renderStructuredSummaryInto(answer, data.summary, data.lesson_id || lessonId);
    setAgentStatus("active", "Tóm tắt xong");
  } catch (err) {
    answer.classList.remove("loading");
    answer.textContent = `Mình chưa tóm tắt được phần này: ${err.message}`;
    setAgentStatus("idle", "Lỗi");
  }
}

function renderStructuredSummary(summary, lessonId) {
  const body = $("#summary-body");
  body.classList.remove("hidden");
  body.innerHTML = "";
  renderStructuredSummaryInto(body, summary, lessonId);
}

function renderStructuredSummaryInto(container, summary, lessonId) {
  (summary.topics || []).forEach((topic) => {
    const section = document.createElement("section");
    section.className = "summary-fact-group";

    const heading = document.createElement("h4");
    heading.textContent = topic.topic_name;
    section.appendChild(heading);

    (topic.micro_facts || []).forEach((fact) => {
      const card = document.createElement("article");
      card.className = `summary-fact${fact.is_core_concept ? " core" : ""}`;

      const text = document.createElement("p");
      text.textContent = fact.fact;
      card.appendChild(text);

      if (fact.page_number || fact.chunk_id) {
        const citation = document.createElement("span");
        citation.className = "source-citation";
        citation.textContent = fact.page_number
          ? `[Page ${fact.page_number}${fact.source_file ? ` / ${fact.source_file}` : ""}]`
          : `[Chunk ID: ${fact.chunk_id}]`;
        card.appendChild(citation);

        const sourceButton = createSourceJumpButton({
          lessonId,
          sourceFile: fact.source_file,
          pageNumber: fact.page_number,
          chunkId: fact.chunk_id,
        });
        card.appendChild(sourceButton);
      }
      section.appendChild(card);
    });
    container.appendChild(section);
  });

  if (summary.summary_notes) {
    const note = document.createElement("div");
    note.className = "summary-quick-note";
    note.textContent = summary.summary_notes;
    container.appendChild(note);
  }
}

function renderLegacySummary(summaryData) {
  const body = $("#summary-body");
  body.innerHTML = "";
  const section = document.createElement("div");
  section.className = "summary-section";
  section.innerHTML = `<h4>📌 Nội dung cốt lõi</h4><p></p>`;
  section.querySelector("p").textContent = summaryData.core;
  body.appendChild(section);

  const list = document.createElement("ul");
  list.className = "summary-key-points";
  summaryData.points.forEach((point) => {
    const item = document.createElement("li");
    item.textContent = point;
    list.appendChild(item);
  });
  body.appendChild(list);
}

async function startEssay() {
  state.agentPhase = "essay";
  setAgentStatus("busy", "Đang tạo tự luận…");
  showAgentPanel("agent-essay");
  $("#essay-question-text").textContent = "Đang tạo câu hỏi tự luận từ nguồn…";
  $("#essay-question-source").innerHTML = "";
  $("#essay-result").classList.add("hidden");
  $("#essay-answer-input").value = "";
  $("#essay-submit").disabled = true;

  try {
    const data = await request("/api/essay/sessions", {
      method: "POST",
      body: JSON.stringify({
        lesson_id: $("#lesson-id").value,
        topic_query: state.selectedTopicQuery || "Nội dung bài học này",
        bloom_level: state.selectedBloom || "analyze",
      }),
    });
    state.essaySessionId = data.session_id;
    state.essayQuestion = data.question;
    $("#essay-question-text").textContent = data.question.question_text;
    renderEssaySource($("#essay-question-source"), data.question);
    $("#essay-submit").disabled = false;
    setAgentStatus("active", "Tự luận");
    $("#essay-answer-input").focus();
  } catch (err) {
    $("#essay-question-text").textContent = `Không tạo được câu hỏi: ${err.message}`;
    setAgentStatus("idle", "Lỗi");
  }
}

async function submitEssayAnswer() {
  const answerText = $("#essay-answer-input").value.trim();
  if (answerText.length < 10) {
    showToast("Câu trả lời cần ít nhất 10 ký tự.");
    return;
  }
  const button = $("#essay-submit");
  button.disabled = true;
  button.textContent = "Đang đánh giá…";
  setAgentStatus("busy", "Đang đánh giá…");

  try {
    const data = await request("/api/essay/answers", {
      method: "POST",
      body: JSON.stringify({
        session_id: state.essaySessionId,
        answer_text: answerText,
      }),
    });
    $("#essay-result").classList.remove("hidden");
    const verdictLabels = {
      mastered: "Đã nắm vững",
      developing: "Đang hoàn thiện",
      needs_review: "Cần ôn lại",
    };
    const outcome = $("#essay-outcome");
    outcome.className = `essay-outcome ${data.evaluation.verdict}`;
    $("#essay-verdict").textContent =
      verdictLabels[data.evaluation.verdict] || "Đã đánh giá";
    $("#essay-feedback").textContent = data.evaluation.feedback;
    $("#essay-suggested-answer").textContent = data.suggested_answer;
    renderEssayRubric(data.evaluation.rubric_breakdown || []);
    renderTextList($("#essay-strengths"), data.evaluation.strengths, "Chưa có");
    renderTextList($("#essay-missing"), data.evaluation.missing_points, "Không có");
    renderEssaySource($("#essay-result-source"), data);
    setAgentStatus("active", "Đã đánh giá");
  } catch (err) {
    showToast(`Chưa đánh giá được: ${err.message}`);
    setAgentStatus("idle", "Lỗi");
  } finally {
    button.disabled = false;
    button.textContent = "Đánh giá lại →";
  }
}

function renderEssayRubric(items) {
  const container = $("#essay-rubric-breakdown");
  container.innerHTML = "";
  const labels = {
    met: "Đạt",
    partial: "Đạt một phần",
    missing: "Chưa đạt",
  };
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = `essay-rubric-row ${item.status}`;

    const main = document.createElement("div");
    main.className = "essay-rubric-main";
    const criterion = document.createElement("span");
    criterion.textContent = item.criterion;
    const status = document.createElement("em");
    status.textContent = labels[item.status] || item.status;
    main.append(criterion, status);

    const reason = document.createElement("p");
    reason.textContent = item.reason;
    row.append(main, reason);
    if (item.evidence_quote) {
      const evidence = document.createElement("blockquote");
      evidence.className = "essay-rubric-evidence";
      evidence.textContent = `“${item.evidence_quote}”`;
      row.appendChild(evidence);
    }
    container.appendChild(row);
  });
}

function renderTextList(container, items, emptyText) {
  container.innerHTML = "";
  const values = items?.length ? items : [emptyText];
  values.forEach((value) => {
    const item = document.createElement("li");
    item.textContent = value;
    container.appendChild(item);
  });
}

function renderEssaySource(container, source) {
  container.innerHTML = "";
  if (!source.page_number && !source.chunk_id) return;
  container.appendChild(createSourceJumpButton({
    lessonId: $("#lesson-id").value,
    sourceFile: source.source_file,
    pageNumber: source.page_number,
    chunkId: source.chunk_id,
  }));
}

function createSourceJumpButton({ lessonId, sourceFile, pageNumber, chunkId }) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "source-jump-btn";
  button.textContent = pageNumber
    ? `↗ Mở Slide trang ${pageNumber}`
    : `↗ Mở đoạn ${chunkId}`;
  button.addEventListener("click", () => {
    jumpToSource({ lessonId, sourceFile, pageNumber, chunkId });
  });
  return button;
}

async function jumpToSource({ lessonId, sourceFile, pageNumber, chunkId }) {
  const pdfKey = sourceFile?.includes("d1-slide") ? "day1"
    : sourceFile?.includes("d2-slide") ? "day2"
      : (lessonId === "day1" || lessonId === "day2" ? lessonId : null);
  const targetKey = pdfKey || lessonId || $("#lesson-id").value;

  $$(".source-item").forEach((item) => {
    const isTarget = item.dataset.slide === targetKey || item.dataset.id === targetKey;
    item.classList.toggle("active", isTarget);
    item.setAttribute("aria-pressed", String(isTarget));
  });

  if (pdfKey && pageNumber) {
    renderSlideDeck(targetKey);
    const deck = SLIDE_DECKS[pdfKey];
    const object = $("#slide-track object");
    if (object) {
      object.setAttribute("data", `${deck.pdfUrl}#page=${pageNumber}&toolbar=1&navpanes=0`);
    }
    showToast(`Đã mở ${deck.filename} — trang ${pageNumber}.`);
    return;
  }

  if (chunkId && targetKey.startsWith("transcript-")) {
    await renderTranscriptDeck(targetKey, chunkId);
    showToast(`Đã mở đoạn ${chunkId}.`);
    return;
  }

  renderSlideDeck(targetKey);
  if (pageNumber && SLIDE_DECKS[targetKey]?.slides) {
    goToSlide(Math.max(0, pageNumber - 1));
  }
  showToast(chunkId ? `Nguồn: ${chunkId}` : "Đã mở nguồn liên quan.");
}

function getSummaryForLesson(lessonId) {
  const map = {
    "transcript-06-clean": {
      core: "Transformer là kiến trúc cách mạng hóa NLP, loại bỏ hoàn toàn recurrence bằng cơ chế Self-Attention — cho phép mô hình học quan hệ giữa các token bất kể khoảng cách trong chuỗi.",
      points: [
        "Self-Attention: mỗi token tính trọng số tập trung với mọi token khác qua Q, K, V",
        "Multi-Head Attention: 8+ đầu song song để nắm nhiều loại quan hệ ngữ nghĩa",
        "Positional Encoding: bổ sung thông tin vị trí vào embedding bằng sin/cos",
        "Feed Forward + Layer Norm: ổn định gradient và tăng khả năng biểu diễn",
        "Encoder-Decoder: Encoder hiểu ngữ cảnh, Decoder sinh ra chuỗi đích",
      ],
      note: "Transformer là nền tảng của GPT, BERT, T5 và hầu hết LLM hiện đại.",
    },
    "transcript-04-clean": {
      core: "LLM (Large Language Model) là mô hình ngôn ngữ được huấn luyện trên hàng nghìn tỷ token văn bản. Chúng học dự đoán token tiếp theo — từ đó nổi lên khả năng lập luận, dịch thuật, lập trình.",
      points: [
        "Pre-training: học trên dữ liệu văn bản khổng lồ không có nhãn",
        "Fine-tuning: tinh chỉnh cho tác vụ cụ thể với dữ liệu nhỏ hơn",
        "RLHF: huấn luyện từ phản hồi của con người để căn chỉnh hành vi",
        "Emergent abilities: khả năng chưa thấy trong mô hình nhỏ xuất hiện khi scale lên",
        "Hallucination: xu hướng tạo ra thông tin sai mà tự tin — cần kiểm chứng",
      ],
      note: "Quy tắc scaling: tăng dữ liệu + tham số + compute → tăng tỉ lệ khả năng.",
    },
    "transcript-01-clean": {
      core: "AI trong kinh doanh không phải là ứng dụng công nghệ mới — mà là giải quyết bài toán thực tế với giá trị đo được. Xuất phát từ vấn đề của khách hàng, không phải từ công nghệ.",
      points: [
        "Xác định đúng bài toán là 80% thành công của dự án AI",
        "ROI phải đo được: giảm chi phí, tăng doanh thu, hoặc cải thiện trải nghiệm",
        "Data maturity: nhiều dự án thất bại vì dữ liệu không đủ chất lượng",
        "Build vs Buy vs API: lựa chọn chiến lược phù hợp ngân sách và năng lực",
        "Stakeholder alignment: cần đồng thuận từ leadership trước khi triển khai",
      ],
      note: "Bắt đầu nhỏ, chứng minh giá trị, rồi scale — đừng đầu tư lớn ngay từ đầu.",
    },
  };
  return map[lessonId] || {
    core: "Bài học chứa nhiều kiến thức quan trọng về AI và Machine Learning.",
    points: ["Hiểu khái niệm cơ bản", "Áp dụng vào bài toán thực tế", "Kiểm tra và đánh giá kết quả"],
    note: "Hãy làm quiz để củng cố kiến thức.",
  };
}

// ─── Topic Selection ─────────────────────────────────────────
const LESSON_TOPICS = {
  "transcript-06-clean": [
    "Toàn bộ bài (tổng hợp)",
    "Self-Attention & Q, K, V",
    "Multi-Head Attention",
    "Positional Encoding",
    "Kiến trúc Encoder-Decoder",
    "So sánh Transformer vs RNN",
  ],
  "transcript-04-clean": [
    "Toàn bộ bài (tổng hợp)",
    "Pre-training & Fine-tuning",
    "RLHF & Alignment",
    "Hallucination & Grounding",
    "Emergent Abilities",
    "Scaling Laws",
  ],
  "transcript-01-clean": [
    "Toàn bộ bài (tổng hợp)",
    "Xác định bài toán AI",
    "ROI & Impact Metrics",
    "Data Maturity",
    "Build vs Buy vs API",
    "Stakeholder Alignment",
  ],
};

function showTopicSelect() {
  state.agentPhase = "topic";
  setAgentStatus("active", "Chọn chủ đề");
  showAgentPanel("agent-topic-select");

  const lessonId = $("#lesson-id").value;
  const topics = LESSON_TOPICS[lessonId] || ["Toàn bộ bài (tổng hợp)"];
  const chipsEl = $("#topic-chips");
  chipsEl.innerHTML = "";

  topics.forEach((topic, i) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "topic-chip" + (i === 0 ? " active" : "");
    btn.textContent = topic;
    btn.addEventListener("click", () => {
      $$(".topic-chip").forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      $("#topic-custom-input").value = "";
      state.selectedTopicQuery = topic === "Toàn bộ bài (tổng hợp)" ? "Nội dung bài học này" : topic;
    });
    chipsEl.appendChild(btn);
  });

  // Default selection = first chip
  state.selectedTopicQuery = "Nội dung bài học này";
}

// Bloom chip selection
$$(".bloom-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    $$(".bloom-chip").forEach((c) => c.classList.remove("active"));
    chip.classList.add("active");
    state.selectedBloom = chip.dataset.level;
  });
});

// Quiz question count selection
$$(".quiz-count-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    $$(".quiz-count-chip").forEach((item) => {
      item.classList.remove("active");
      item.setAttribute("aria-checked", "false");
    });
    chip.classList.add("active");
    chip.setAttribute("aria-checked", "true");
    state.selectedQuizCount = Number(chip.dataset.count);
    const confirmButton = $("#topic-confirm-btn");
    if (confirmButton) {
      confirmButton.innerHTML = `<span>▶</span> Tạo bộ Quiz ${state.selectedQuizCount} câu`;
    }
  });
});

// Custom input clears chip selection
document.addEventListener("DOMContentLoaded", () => {
  const customInput = $("#topic-custom-input");
  if (customInput) {
    customInput.addEventListener("input", (e) => {
      if (e.target.value.trim()) {
        $$(".topic-chip").forEach((c) => c.classList.remove("active"));
        state.selectedTopicQuery = e.target.value.trim();
      }
    });
  }
});

// ─── Quiz Start (after topic confirm) ─────────────────────────
async function startQuizWithTopic() {
  const customVal = $("#topic-custom-input")?.value.trim();
  if (customVal) state.selectedTopicQuery = customVal;

  state.agentPhase = "thinking";
  setAgentStatus("busy", "Đang tạo quiz…");
  showAgentPanel("agent-thinking");
  $("#agent-thinking-text").textContent = "Đang soạn bộ câu hỏi cho chủ đề đã chọn…";
  setProgressStep({ read: "done", summarize: "done", quiz: "active" });

  try {
    const lessonId = $("#lesson-id").value;
    const data = await request("/api/quiz/sessions", {
      method: "POST",
      body: JSON.stringify({
        topic_query: state.selectedTopicQuery || "Nội dung bài học này",
        lesson_id: lessonId,
        bloom_level: state.selectedBloom || "analyze",
        num_questions: state.selectedQuizCount,
      }),
    });

    setProgressStep({ read: "done", summarize: "done", quiz: "done" });
    state.sessionId = data.session_id;
    state.targetTotal = data.total_questions || state.selectedQuizCount;

    if (data.phase === "failed" || !data.question) {
      throw new Error("Không tạo được câu hỏi. Hãy thử chủ đề khác.");
    }

    state.question = data.question;
    startQuizFlow(data);
  } catch (err) {
    showAgentError(err.message);
  }
}

// ─── Quiz Flow ─────────────────────────────────────────────────
function startQuizFlow(initialData) {
  state.agentPhase = "quiz";
  state.answered = 0;
  state.correct = 0;
  state.gaps = 0;
  state.errorLog = [];
  updateAgentProgress();
  setAgentStatus("active", "Đang quiz");
  showAgentPanel("agent-quiz-flow");
  updateQuizFlowHeader(initialData?.current_question_idx ?? 0, initialData?.total_questions ?? state.targetTotal);
  $("#qf-result").classList.add("hidden");

  if (state.question) {
    renderQuizQuestion(state.question);
  }
}

function updateQuizFlowHeader(currentIdx, total) {
  const questionNum = (currentIdx ?? state.answered) + 1;
  const totalNum = total ?? state.targetTotal;
  $("#qf-label").textContent = `CÂU ${questionNum} / ${totalNum}`;
  $("#qf-correct").textContent = `${state.correct} ✓`;
  $("#qf-gaps").textContent = `${state.gaps} ↗`;
}

function renderQuizQuestion(question) {
  state.question = question;
  state.selectedIndex = null;

  const card = $("#qf-question-card");
  card.style.opacity = "0";
  card.style.transform = "translateY(8px)";
  $("#qf-question-text").textContent = question.question_text;
  requestAnimationFrame(() => {
    card.style.transition = "opacity .3s, transform .3s";
    card.style.opacity = "1";
    card.style.transform = "translateY(0)";
  });

  const optList = $("#qf-options");
  optList.innerHTML = "";
  question.options.forEach((opt) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "qf-option";
    btn.dataset.index = opt.index;

    const key = document.createElement("span");
    key.className = "qf-option-key";
    key.textContent = String.fromCharCode(65 + opt.index);

    const text = document.createElement("span");
    text.textContent = opt.text;

    btn.append(key, text);
    btn.addEventListener("click", () => selectQuizOption(opt.index));
    optList.appendChild(btn);
  });

  $("#qf-submit").disabled = true;
  $("#qf-submit").textContent = "Chọn đáp án →";
  $("#qf-result").classList.add("hidden");
}

function selectQuizOption(index) {
  state.selectedIndex = index;
  $$(".qf-option").forEach((btn) => {
    const selected = Number(btn.dataset.index) === index;
    btn.classList.toggle("selected", selected);
  });
  $("#qf-submit").disabled = false;
  $("#qf-submit").textContent = "Xác nhận đáp án →";
}

async function submitQuizAnswer() {
  if (state.selectedIndex === null) return;
  state.lastAction = "answer";

  const submitBtn = $("#qf-submit");
  submitBtn.disabled = true;
  submitBtn.textContent = "Đang kiểm tra…";
  setAgentStatus("busy", "Chấm bài…");

  try {
    const data = await request("/api/quiz/answers", {
      method: "POST",
      body: JSON.stringify({ session_id: state.sessionId, answer_index: state.selectedIndex }),
    });

    state.answered += 1;
    if (data.is_correct) {
      state.correct += 1;
    } else {
      state.gaps += 1;
    }

    updateAgentProgress();
    updateQuizFlowHeader(data.current_question_idx ?? state.answered, data.total_questions ?? state.targetTotal);
    const quizFinished = renderQuizResult(data);
    setAgentStatus("active", "Đang quiz");

    if (!data.is_correct) {
      const misconEl = $("#qf-misconception");
      misconEl.classList.remove("hidden");
      const misconText = $("#qf-misconception-text");
      misconText.textContent = "Đang phân tích lỗi sai...";
      const gapEntry = {
        question: state.question?.question_text || "—",
        explanation: data.explanation || "",
        misconception: "Chưa có phân tích chi tiết.",
        sourceFile: data.review_source_file,
        pageNumber: data.review_page_number,
        correctAnswer: null,
      };
      state.errorLog.push(gapEntry);

      try {
        let fullText = "";
        let rawText = "";
        await requestStream("/api/quiz/stream_error", {
          method: "POST",
          body: JSON.stringify({ session_id: state.sessionId }),
        }, (chunk) => {
          rawText += chunk;
          fullText = rawText.length > 280
            ? `${rawText.slice(0, 279).trimEnd()}…`
            : rawText;
          misconText.textContent = fullText;
          gapEntry.misconception = fullText;
        });
      } catch (err) {
        const fallback = "Hãy xem lại ý cốt lõi trong lời giải và nguồn được dẫn.";
        gapEntry.misconception = fallback;
        misconText.textContent = fallback;
      }
    }
    if (quizFinished) {
      setTimeout(showAgentDone, 250);
    }
  } catch (err) {
    showAgentError(err.message);
  }
}

function renderQuizResult(data) {
  const isCorrect = data.is_correct;
  const resultEl = $("#qf-result");
  resultEl.classList.remove("hidden");

  resultEl.style.opacity = "0";
  requestAnimationFrame(() => {
    resultEl.style.transition = "opacity .3s";
    resultEl.style.opacity = "1";
  });

  const mark = $("#qf-result-mark");
  mark.textContent = isCorrect ? "✓" : "✕";
  mark.className = `qf-result-mark ${isCorrect ? "correct" : "incorrect"}`;

  $("#qf-result-title").textContent = isCorrect
    ? "Chính xác! Bạn nắm tốt kiến thức này."
    : "Chưa đúng. Xem giải thích bên dưới nhé.";

  $("#qf-explanation").textContent = data.explanation || "Chưa có phần giải thích.";

  const sourceButton = $("#qf-source-jump");
  const hasReviewSource = !isCorrect && (data.review_page_number || data.review_source_file);
  sourceButton.classList.toggle("hidden", !hasReviewSource);
  if (hasReviewSource) {
    sourceButton.textContent = data.review_page_number
      ? `↗ Mở Slide trang ${data.review_page_number}`
      : "↗ Mở Slide nguồn";
    sourceButton.onclick = () => jumpToSource({
      lessonId: $("#lesson-id").value,
      sourceFile: data.review_source_file,
      pageNumber: data.review_page_number,
    });
  }

  const misconEl = $("#qf-misconception");
  if (isCorrect) {
    misconEl.classList.add("hidden");
  }

  // Nav buttons logic
  const followUp = !isCorrect && data.phase === "waiting_for_answer" && data.question;
  const isDone = data.phase === "completed";

  // Determine if there's a next question
  const nextIdx = data.current_question_idx ?? state.answered;
  const totalQ = data.total_questions ?? state.targetTotal;
  const hasNext = !followUp && !isDone && nextIdx < totalQ;

  const nextBtn = $("#qf-next");
  const reinforceBtn = $("#qf-reinforce");

  nextBtn.classList.toggle("hidden", !hasNext && !isDone && !followUp ? false : !hasNext);
  reinforceBtn.classList.toggle("hidden", !followUp);

  // If done phase from server
  if (isDone || (!hasNext && !followUp)) {
    nextBtn.classList.add("hidden");
    reinforceBtn.classList.add("hidden");
    return true;
  }

  nextBtn.onclick = () => {
    if (data.question) {
      renderQuizQuestion(data.question);
    } else {
      fetchNextQuestion(nextIdx, totalQ);
    }
  };
  reinforceBtn.onclick = () => renderQuizQuestion(data.question);
  return false;
}

async function fetchNextQuestion(currentIdx, total) {
  setAgentStatus("busy", "Lấy câu tiếp…");
  const submitBtn = $("#qf-submit");
  submitBtn.disabled = true;
  submitBtn.textContent = "Đang tải…";

  const card = $("#qf-question-card");
  card.style.opacity = "0.4";
  const optList = $("#qf-options");
  optList.innerHTML = `<div style="height:40px;background:var(--surface2);border-radius:8px;opacity:.5;animation:pulse-badge 1s ease infinite"></div>`.repeat(3);

  try {
    const data = await request("/api/quiz/sessions", {
      method: "POST",
      body: JSON.stringify({
        topic_query: state.selectedTopicQuery || "Nội dung bài học này",
        lesson_id: $("#lesson-id").value,
        bloom_level: state.selectedBloom || "analyze",
        num_questions: total ?? state.targetTotal,
      }),
    });
    if (data.question) {
      state.sessionId = data.session_id;
      state.question = data.question;
      card.style.opacity = "1";
      renderQuizQuestion(data.question);
      setAgentStatus("active", "Đang quiz");
    }
  } catch (err) {
    card.style.opacity = "1";
    showAgentError(err.message);
  }
}

// ─── Done Screen with Gap Summary ────────────────────────────
function showAgentDone() {
  state.agentPhase = "done";
  setAgentStatus("active", "Hoàn thành!");
  showAgentPanel("agent-done");

  const accuracy = state.answered ? Math.round((state.correct / state.answered) * 100) : 0;
  const summaryText = state.answered
    ? `Bạn đã trả lời ${state.answered} câu — đúng ${state.correct} câu (${accuracy}%).`
    : "Bạn đã hoàn thành bài quiz!";

  $("#done-summary-text").textContent = summaryText +
    (state.gaps > 0 ? ` Có ${state.gaps} lỗ hổng kiến thức cần ôn thêm.` : " Xuất sắc, không có lỗ hổng!");

  // Build gap summary
  const gapSection = $("#done-gap-section");
  gapSection.innerHTML = "";

  if (state.errorLog.length === 0) {
    const perfectEl = document.createElement("div");
    perfectEl.className = "done-perfect";
    perfectEl.innerHTML = `<span>🏆</span><p>Không có lỗ hổng — bạn đã nắm vững toàn bộ nội dung!</p>`;
    gapSection.appendChild(perfectEl);
    return;
  }

  const titleEl = document.createElement("h4");
  titleEl.className = "done-gap-title";
  titleEl.innerHTML = `📋 Tổng hợp lỗ hổng kiến thức <span class="gap-count">${state.gaps} điểm cần ôn</span>`;
  gapSection.appendChild(titleEl);

  state.errorLog.forEach((err, i) => {
    const item = document.createElement("div");
    item.className = "done-gap-item";

    const qEl = document.createElement("div");
    qEl.className = "done-gap-question";
    qEl.innerHTML = `<span class="gap-num">${i + 1}</span><span>${err.question}</span>`;

    item.appendChild(qEl);

    if (err.misconception) {
      const mEl = document.createElement("div");
      mEl.className = "done-gap-misconception";
      mEl.innerHTML = `<strong>🔍 Điểm nhầm lẫn:</strong> ${err.misconception}`;
      item.appendChild(mEl);
    }

    if (err.explanation) {
      const eEl = document.createElement("div");
      eEl.className = "done-gap-explanation";
      eEl.innerHTML = `<strong>💡 Giải thích:</strong> ${err.explanation}`;
      item.appendChild(eEl);
    }

    if (err.pageNumber || err.sourceFile) {
      item.appendChild(createSourceJumpButton({
        lessonId: $("#lesson-id").value,
        sourceFile: err.sourceFile,
        pageNumber: err.pageNumber,
      }));
    }

    gapSection.appendChild(item);
  });
}

function showAgentError(message) {
  state.agentPhase = "error";
  setAgentStatus("idle", "Lỗi");
  showAgentPanel("agent-error");
  $("#agent-error-text").textContent = message || "Đã xảy ra lỗi không xác định.";
}

function resetAgent() {
  state.sessionId = null;
  state.essaySessionId = null;
  state.essayQuestion = null;
  state.selectedIndex = null;
  state.question = null;
  state.answered = 0;
  state.correct = 0;
  state.gaps = 0;
  state.agentPhase = "idle";
  state.errorLog = [];
  state.selectedTopicQuery = null;
  state.structuredSummary = null;
  state.summaryLessonId = null;
  updateAgentProgress();
  setAgentStatus("idle", "Sẵn sàng");
  showAgentPanel("agent-welcome");
  // Clear chat messages
  const chatMsgs = $("#summary-chat-messages");
  if (chatMsgs) chatMsgs.innerHTML = "";
  const inlineMessages = $("#summary-inline-messages");
  if (inlineMessages) inlineMessages.innerHTML = "";
  const summaryBody = $("#summary-body");
  if (summaryBody) {
    summaryBody.classList.add("hidden");
    summaryBody.innerHTML = `<div class="summary-empty-state">Chọn “Tóm tắt toàn bộ” hoặc nhắn phần bạn muốn ôn nhanh.</div>`;
  }
}

// ─── Summary Chat Mode ─────────────────────────────────────────
async function startSummaryChat() {
  state.agentPhase = "summary-chat";
  setAgentStatus("busy", "Đang tóm tắt…");
  showAgentPanel("agent-summary-chat");

  const chatMsgs = $("#summary-chat-messages");
  chatMsgs.innerHTML = "";

  const loadingBubble = appendChatBubble("assistant", "Đang phân tích bài học…", true);

  const lessonId = $("#lesson-id").value;
  try {
    const bubble = appendChatBubble("assistant", "");
    loadingBubble.remove();
    await requestStream("/api/summarize", {
      method: "POST",
      body: JSON.stringify({ lesson_id: lessonId }),
    }, (chunk) => {
      bubble.dataset.raw = (bubble.dataset.raw || "") + chunk;
      bubble.innerHTML = bubble.dataset.raw
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n- /g, "\n• ")
        .replace(/\n/g, "<br>");
    });
    setAgentStatus("active", "Trợ giảng AI");
  } catch (err) {
    loadingBubble.remove();
    appendChatBubble("assistant", "Lỗi: " + err.message);
    setAgentStatus("idle", "Lỗi");
  }
}

async function sendSummaryMessage() {
  const input = $("#summary-chat-input");
  const msg = input.value.trim();
  if (!msg) return;
  input.value = "";

  appendChatBubble("user", msg);
  const loadingBubble = appendChatBubble("assistant", "Đang suy nghĩ…", true);
  setAgentStatus("busy", "Đang trả lời…");

  const lessonId = $("#lesson-id").value;
  try {
    const bubble = appendChatBubble("assistant", "");
    loadingBubble.remove();
    await requestStream("/api/summarize", {
      method: "POST",
      body: JSON.stringify({ lesson_id: lessonId, user_query: msg }),
    }, (chunk) => {
      bubble.dataset.raw = (bubble.dataset.raw || "") + chunk;
      bubble.innerHTML = bubble.dataset.raw
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n- /g, "\n• ")
        .replace(/\n/g, "<br>");
    });
    setAgentStatus("active", "Trợ giảng AI");
  } catch (err) {
    loadingBubble.remove();
    appendChatBubble("assistant", "Lỗi: " + err.message);
    setAgentStatus("idle", "Lỗi");
  }
}

function appendChatBubble(role, text, isLoading = false) {
  const chatMsgs = $("#summary-chat-messages");
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble chat-${role}${isLoading ? " loading" : ""}`;

  if (role === "assistant" && !isLoading) {
    bubble.innerHTML = text
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\n- /g, "\n• ")
      .replace(/\n/g, "<br>");
  } else {
    bubble.textContent = text;
  }

  chatMsgs.appendChild(bubble);
  chatMsgs.scrollTop = chatMsgs.scrollHeight;
  return bubble;
}

// ─── Slide Decks Data for All Sources ─────────────────────────
const SLIDE_DECKS = {
  "transcript-06-clean": {
    label: "Transformer & Attention",
    slides: [
      {
        type: "hero",
        badge: "Bài 06",
        title: "Transformer & Attention Mechanism",
        desc: "Kiến trúc nền tảng của các mô hình ngôn ngữ lớn hiện đại",
        tags: ["Self-Attention", "Multi-Head", "Positional Encoding"],
      },
      {
        overline: "PHẦN 1",
        title: "Vấn đề với RNN",
        bullets: [
          "<strong>Vanishing gradient</strong> — gradient biến mất khi chuỗi dài",
          "<strong>Xử lý tuần tự</strong> — không thể song song hóa khi huấn luyện",
          "<strong>Long-range dependency</strong> — khó ghi nhớ ngữ cảnh xa",
        ],
        note: "💡 Transformer giải quyết cả 3 vấn đề này với cơ chế Attention",
      },
      {
        overline: "PHẦN 2",
        title: "Self-Attention là gì?",
        diagram: true,
        caption: "Mỗi token 'nhìn' vào tất cả token khác để tính trọng số tập trung",
      },
      {
        overline: "PHẦN 3",
        title: "Multi-Head Attention",
        heads: [
          { title: "Head 1", sub: "Ngữ pháp" },
          { title: "Head 2", sub: "Ngữ nghĩa" },
          { title: "Head 3", sub: "Tham chiếu" },
          { title: "+5 heads", more: true },
        ],
        caption: "8 đầu attention song song → nắm bắt nhiều loại quan hệ trong văn bản",
      },
      {
        overline: "PHẦN 4",
        title: "Positional Encoding",
        bullets: [
          "Transformer không có thứ tự vốn có — cần thêm thông tin vị trí",
          "Dùng hàm sin/cos tần số khác nhau cho từng chiều vector",
          "Cho phép mô hình suy luận về khoảng cách giữa các từ",
        ],
        note: "🔢 PE(pos, 2i) = sin(pos/10000^(2i/d))",
      },
      {
        type: "summary",
        overline: "TÓM TẮT",
        title: "Kiến trúc Transformer",
        steps: [
          "Input Embedding + Positional Encoding",
          "Multi-Head Self-Attention (×N)",
          "Feed Forward + Layer Norm",
          "Output & Softmax",
        ],
      },
    ],
  },
  "transcript-04-clean": {
    label: "LLM hoạt động thế nào",
    slides: [
      {
        type: "hero",
        badge: "Bài 04",
        title: "LLM & Cơ chế Sinh Ngôn Ngữ",
        desc: "Cách các mô hình ngôn ngữ lớn tiếp nhận prompt và sinh dữ liệu",
        tags: ["Pre-training", "Fine-tuning", "RLHF", "Hallucination"],
      },
      {
        overline: "PHẦN 1",
        title: "Quá trình Huấn luyện LLM",
        bullets: [
          "<strong>Pre-training:</strong> Học trên hàng nghìn tỷ token văn bản không nhãn",
          "<strong>SFT (Supervised Fine-tuning):</strong> Tinh chỉnh theo dạng Cặp Hỏi-Đáp",
          "<strong>RLHF:</strong> Căn chỉnh hành vi mô hình theo phản hồi của con người",
        ],
        note: "🧠 Mô hình học nguyên lý cơ bản: Dự đoán token tiếp theo có xác suất cao nhất",
      },
      {
        overline: "PHẦN 2",
        title: "Cửa sổ Ngữ cảnh (Context Window)",
        bullets: [
          "Xác định lượng thông tin tối đa LLM có thể đọc trong một lần",
          "Ngữ cảnh càng dài → Chi phí tính toán càng tăng theo cấp số nhân",
          "Needle in a Haystack: Thách thức tìm lại thông tin ở giữa văn bản dài",
        ],
        note: "🔍 RAG giúp mở rộng khả năng tri thức mà không cần tăng kích thước mô hình",
      },
      {
        overline: "PHẦN 3",
        title: "Hiện tượng Hallucination",
        bullets: [
          "LLM tự tin tạo ra thông tin bịa đặt không có thật",
          "Nguyên nhân: Mô hình tối ưu cho độ mượt ngôn ngữ thay vì tính đúng đắn",
          "Giải pháp: Sử dụng RAG, Prompt Constraints và Citation Enforcement",
        ],
        note: "⚠️ Luôn kiểm tra căn cứ (Evidence) trước khi tin tưởng kết luận của LLM",
      },
      {
        type: "summary",
        overline: "TÓM TẮT",
        title: "Vòng đời xử lý Prompt",
        steps: [
          "Tokenize User Prompt",
          "Retrieve Relevant Context (RAG)",
          "LLM Autoregressive Generation",
          "Guardrail & Grounding Validation",
        ],
      },
    ],
  },
  "transcript-01-clean": {
    label: "Bài toán kinh doanh AI",
    slides: [
      {
        type: "hero",
        badge: "Bài 01",
        title: "Ứng dụng AI trong Kinh doanh",
        desc: "Xác định bài toán thực tế và đo lường giá trị sản phẩm AI",
        tags: ["Problem-First", "ROI", "Data Maturity", "Build vs Buy"],
      },
      {
        overline: "PHẦN 1",
        title: "Tư duy Problem-First",
        bullets: [
          "<strong>Không bắt đầu từ công nghệ:</strong> Bắt đầu từ vướng mắc của người dùng",
          "<strong>Xác định Pain cụ thể:</strong> Ai vướng? Vướng ở đâu? Hậu quả là gì?",
          "<strong>Tối ưu quy trình:</strong> AI giúp giảm thời gian hay tăng chất lượng?",
        ],
        note: "🎯 80% dự án thất bại vì giải quyết bài toán không ai cần",
      },
      {
        overline: "PHẦN 2",
        title: "Đo lường ROI & Impact",
        bullets: [
          "<strong>Tần suất & Quy mô:</strong> Bao nhiêu người bị ảnh hưởng mỗi ngày?",
          "<strong>Chi phí hiện tại:</strong> Mất bao nhiêu giờ lao động cho tác vụ thủ công?",
          "<strong>Mục tiêu sản phẩm:</strong> Giảm 50% thời gian ôn tập của học viên",
        ],
        note: "📈 Giá trị kinh doanh = (Chi phí tiết kiệm + Doanh thu tăng) - Chi phí AI",
      },
      {
        type: "summary",
        overline: "TÓM TẮT",
        title: "Khung quyết định Dự án AI",
        steps: [
          "Xác định Pain-point có evidence",
          "Đánh giá Data Maturity & Độ khả thi",
          "Lựa chọn Chiến lược Build / Buy / API",
          "Xây dựng Prototype & Đo lường Impact",
        ],
      },
    ],
  },
  "transcript-02-clean": {
    label: "Chỉ số thành công",
    slides: [
      {
        type: "hero",
        badge: "Bài 02",
        title: "Chỉ số Thành công Sản phẩm AI",
        desc: "Thiết lập hệ thống chỉ số đo lường hiệu quả và trải nghiệm người dùng",
        tags: ["Product Metrics", "Accuracy", "Latency", "User Retention"],
      },
      {
        overline: "PHẦN 1",
        title: "Hệ thống Chỉ số 3 Lớp",
        bullets: [
          "<strong>Business Metric:</strong> Retention rate, Time saved, Completion rate",
          "<strong>UX Metric:</strong> User satisfaction score, Correction rate, Drop-off",
          "<strong>AI Technical Metric:</strong> Faithfulness, Precision, Latency, Token cost",
        ],
        note: "📊 Chỉ số AI kỹ thuật phải phục vụ trực tiếp cho chỉ số trải nghiệm người dùng",
      },
      {
        overline: "PHẦN 2",
        title: "Tối ưu Chi phí & Tốc độ",
        bullets: [
          "<strong>Latency Budget:</strong> Phản hồi dưới 2 giây để giữ chân người dùng",
          "<strong>Token Budget:</strong> Nén context (Context Compression) để giảm 40% chi phí API",
          "<strong>Streaming:</strong> Hiển thị câu trả lời ngay khi model đang sinh token",
        ],
        note: "⚡ Trải nghiệm nhanh và chính xác quan trọng hơn một câu trả lời dài",
      },
    ],
  },
  "transcript-03-clean": {
    label: "Tự động hóa & ràng buộc",
    slides: [
      {
        type: "hero",
        badge: "Bài 03",
        title: "Tự động hóa & Ràng buộc Hệ thống",
        desc: "Thiết kế luồng Conditional Agent và kiểm soát rủi ro vận hành",
        tags: ["Conditional Graph", "Guardrails", "Human-in-the-Loop"],
      },
      {
        overline: "PHẦN 1",
        title: "Conditional Agent Design",
        bullets: [
          "<strong>Tự động khi đủ căn cứ:</strong> AI sinh câu hỏi và chấm điểm từ transcript",
          "<strong>Hỏi lại khi mơ hồ:</strong> Nếu câu trả lời quá ngắn → Yêu cầu giải thích thêm",
          "<strong>Từ chối khi thiếu nguồn:</strong> Không tự bịa đáp án nếu tài liệu không nhắc tới",
        ],
        note: "🛡️ An toàn dữ liệu và tính chính xác là ưu tiên hàng đầu",
      },
      {
        overline: "PHẦN 2",
        title: "Kiểm soát 4 Lớp Lỗi",
        bullets: [
          "<strong>Nguồn sự thật:</strong> Bắt buộc citation hợp lệ",
          "<strong>Mơ hồ:</strong> Chuyển trạng thái clarify",
          "<strong>Ngoài phạm vi:</strong> Mời quay lại bài học",
          "<strong>Domain-specific:</strong> Cung cấp hint thay vì lộ đáp án ngay",
        ],
        note: "🔄 Thiết kế 4 đường đi (Happy, Low-conf, Failure, Correction)",
      },
    ],
  },
  "transcript-05-clean": {
    label: "Đánh giá & dữ liệu",
    slides: [
      {
        type: "hero",
        badge: "Bài 05",
        title: "Đánh giá & Quản trị Dữ liệu",
        desc: "Xây dựng Golden Set và quy trình Đánh giá tự động cho Agent",
        tags: ["Golden Set", "Ragas", "LLM-as-a-Judge", "Eval Harness"],
      },
      {
        overline: "PHẦN 1",
        title: "Xây dựng Golden Set",
        bullets: [
          "<strong>Tập dữ liệu chuẩn:</strong> Câu hỏi mẫu + Đáp án đúng + Mã đoạn trích dẫn",
          "<strong>Đa dạng độ khó:</strong> Nhận biết, Thông hiểu, Phân tích, Vận dụng",
          "<strong>Bảo mật:</strong> Ẩn danh hóa dữ liệu trước khi đưa vào pipeline",
        ],
        note: "🧪 Golden set giúp đo lường chính xác regression sau mỗi lần thay đổi prompt",
      },
      {
        overline: "PHẦN 2",
        title: "LLM-as-a-Judge Evaluation",
        bullets: [
          "<strong>Faithfulness:</strong> Đánh giá mức độ trung thực so với context (0-100%)",
          "<strong>Answer Relevance:</strong> Đánh giá câu trả lời có đúng trọng tâm câu hỏi",
          "<strong>Automated Evals:</strong> Chạy script đo lường tự động qua CI/CD",
        ],
        note: "🎯 Đạt pass-rate >= 85% trước khi đưa vào sản phẩm",
      },
    ],
  },
  "day1": {
    label: "Day 1 Hackathon Slide (PDF Gốc)",
    pdfUrl: "/api/slides/d1-slide-hackathon.pdf",
    filename: "d1-slide-hackathon.pdf",
  },
  "day2": {
    label: "Day 2 Hackathon Slide (PDF Gốc)",
    pdfUrl: "/api/slides/d2-slide-hackathon.pdf",
    filename: "d2-slide-hackathon.pdf",
  },
};

// ─── Render Slide Deck Dynamically ─────────────────────────────
function renderSlideDeck(key) {
  const deck = SLIDE_DECKS[key] || SLIDE_DECKS["transcript-06-clean"];
  state.activeSourceKey = key;
  state.contentMode = "summary";
  $("#slide-source-label").textContent = deck.label;
  $("#slide-stage").classList.remove("transcript-mode");
  $("#slide-counter").classList.remove("transcript-counter");
  syncContentModeControls(key, "summary");

  const track = $("#slide-track");
  const dots = $("#slide-dots");

  track.innerHTML = "";
  dots.innerHTML = "";

  // If source is a PDF file, embed native PDF viewer
  if (deck.pdfUrl) {
    track.style.transform = "none";
    track.innerHTML = `
      <div class="pdf-viewer-wrap" style="width:100%; height:100%; display:flex; flex-direction:column; padding:12px; box-sizing:border-box;">
        <div class="pdf-toolbar" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; padding:8px 14px; background:var(--surface); border-radius:10px; border:1.5px solid var(--line); box-shadow:var(--shadow-xs);">
          <span style="font-size:12px; font-weight:800; color:var(--ink);">📄 File PDF gốc: <strong>${deck.filename}</strong></span>
          <a href="${deck.pdfUrl}" target="_blank" rel="noopener" style="font-size:11px; font-weight:800; color:var(--brand); text-decoration:none; display:flex; align-items:center; gap:4px;">
            <span>↗ Mở tab mới</span>
          </a>
        </div>
        <object data="${deck.pdfUrl}#toolbar=1&navpanes=0" type="application/pdf" width="100%" height="100%" style="flex:1; border:1.5px solid var(--line); border-radius:12px; background:#525659; min-height:480px;">
          <iframe src="${deck.pdfUrl}" width="100%" height="100%" style="border:none; border-radius:12px; min-height:480px;">
            <p style="padding:20px; text-align:center;">Trình duyệt không hỗ trợ xem PDF trực tiếp. <a href="${deck.pdfUrl}" target="_blank">Bấm vào đây để tải PDF</a>.</p>
          </iframe>
        </object>
      </div>
    `;
    dots.innerHTML = `<span style="font-size:11px; color:var(--muted); font-weight:700;">📄 Đang hiển thị file PDF gốc</span>`;
    $("#slide-total").textContent = "PDF";
    $("#slide-current").textContent = "1";
    $("#slide-prev").disabled = true;
    $("#slide-next").disabled = true;
    return;
  }

  deck.slides.forEach((slide, idx) => {
    const card = document.createElement("div");
    card.className = "slide-card" + (idx === 0 ? " active" : "");
    card.dataset.slideIndex = idx;

    const inner = document.createElement("div");

    if (slide.type === "hero") {
      inner.className = "slide-inner slide-hero";
      inner.innerHTML = `
        <div class="slide-badge">${slide.badge || "Bài học"}</div>
        <h2>${slide.title}</h2>
        <p>${slide.desc}</p>
        <div class="slide-tags">
          ${(slide.tags || []).map(t => `<span>${t}</span>`).join("")}
        </div>
      `;
    } else if (slide.type === "summary") {
      inner.className = "slide-inner slide-summary-slide";
      const stepsHtml = (slide.steps || []).map((step, sIdx) => `
        <div class="arch-step">${step}</div>
        ${sIdx < slide.steps.length - 1 ? `<div class="arch-arrow">↓</div>` : ""}
      `).join("");

      inner.innerHTML = `
        <p class="slide-overline overline">${slide.overline || "TÓM TẮT"}</p>
        <h3>${slide.title}</h3>
        <div class="arch-steps">${stepsHtml}</div>
      `;
    } else {
      inner.className = "slide-inner";
      let contentHtml = `<p class="slide-overline overline">${slide.overline || ""}</p><h3>${slide.title}</h3>`;

      if (slide.bullets) {
        contentHtml += `<ul class="slide-bullets">${slide.bullets.map(b => `<li>${b}</li>`).join("")}</ul>`;
      }

      if (slide.diagram) {
        contentHtml += `
          <div class="slide-diagram">
            <div class="diag-row">
              <div class="diag-box q">Q<small>Query</small></div>
              <div class="diag-box k">K<small>Key</small></div>
              <div class="diag-box v">V<small>Value</small></div>
            </div>
            <div class="diag-formula">Attention(Q,K,V) = softmax(QK<sup>T</sup>/√d<sub>k</sub>)·V</div>
          </div>
        `;
      }

      if (slide.heads) {
        contentHtml += `
          <div class="slide-heads-grid">
            ${slide.heads.map(h => `
              <div class="head-item ${h.more ? 'head-more' : ''}">
                <span>${h.title}</span>
                ${h.sub ? `<small>${h.sub}</small>` : ''}
              </div>
            `).join("")}
          </div>
        `;
      }

      if (slide.caption) {
        contentHtml += `<p class="slide-caption">${slide.caption}</p>`;
      }

      if (slide.note) {
        contentHtml += `<div class="slide-note">${slide.note}</div>`;
      }

      inner.innerHTML = contentHtml;
    }

    card.appendChild(inner);
    track.appendChild(card);

    // Create dot button
    const dot = document.createElement("button");
    dot.className = "dot" + (idx === 0 ? " active" : "");
    dot.type = "button";
    dot.dataset.idx = idx;
    dot.setAttribute("aria-label", `Slide ${idx + 1}`);
    dot.addEventListener("click", () => goToSlide(idx));
    dots.appendChild(dot);
  });

  state.slideTotalCount = deck.slides.length;
  $("#slide-total").textContent = `${state.slideTotalCount} trang`;
  goToSlide(0);
}

function syncContentModeControls(key, mode) {
  const isTranscript = key.startsWith("transcript-");
  const switcher = $("#content-mode-switch");
  switcher.classList.toggle("hidden", !isTranscript);

  const summaryButton = $("#summary-view-btn");
  const transcriptButton = $("#transcript-view-btn");
  summaryButton.classList.toggle("active", mode === "summary");
  transcriptButton.classList.toggle("active", mode === "transcript");
  summaryButton.setAttribute("aria-selected", String(mode === "summary"));
  transcriptButton.setAttribute("aria-selected", String(mode === "transcript"));
}

async function loadTranscript(lessonId) {
  if (!transcriptCache.has(lessonId)) {
    transcriptCache.set(
      lessonId,
      request(`/api/transcripts/${encodeURIComponent(lessonId)}`)
    );
  }
  try {
    return await transcriptCache.get(lessonId);
  } catch (error) {
    transcriptCache.delete(lessonId);
    throw error;
  }
}

async function renderTranscriptDeck(key, focusChunkId = null) {
  if (!key.startsWith("transcript-")) return;

  const deck = SLIDE_DECKS[key] || SLIDE_DECKS["transcript-06-clean"];
  state.activeSourceKey = key;
  state.contentMode = "transcript";
  $("#slide-source-label").textContent = deck.label;
  $("#slide-stage").classList.add("transcript-mode");
  $("#slide-counter").classList.add("transcript-counter");
  $("#slide-current").textContent = "…";
  $("#slide-total").textContent = "đoạn";
  $("#slide-prev").disabled = true;
  $("#slide-next").disabled = true;
  syncContentModeControls(key, "transcript");

  const track = $("#slide-track");
  const dots = $("#slide-dots");
  track.style.transform = "none";
  track.innerHTML = `<div class="transcript-view"><div class="transcript-loading">Đang tải transcript đầy đủ…</div></div>`;
  dots.innerHTML = `<span class="transcript-footer-status">Đang đọc nguồn transcript</span>`;

  try {
    const data = await loadTranscript(key);
    $("#slide-current").textContent = data.total_chunks;

    const view = document.createElement("div");
    view.className = "transcript-view";

    const header = document.createElement("div");
    header.className = "transcript-view-header";
    const title = document.createElement("div");
    title.className = "transcript-view-title";
    const titleText = document.createElement("strong");
    titleText.textContent = "Transcript đầy đủ";
    const countText = document.createElement("span");
    countText.textContent = `${data.total_chunks} đoạn nguồn · cuộn để đọc`;
    title.append(titleText, countText);

    const search = document.createElement("input");
    search.type = "search";
    search.className = "transcript-search";
    search.placeholder = "Tìm nội dung hoặc mã đoạn…";
    search.setAttribute("aria-label", "Tìm trong transcript");
    header.append(title, search);

    const list = document.createElement("div");
    list.className = "transcript-list";
    const chunkElements = [];
    data.chunks.forEach((chunk) => {
      const article = document.createElement("article");
      article.className = "transcript-chunk";
      article.id = `chunk-${chunk.chunk_id}`;
      article.dataset.search = `${chunk.chunk_id} ${chunk.text}`.toLowerCase();

      const chunkId = document.createElement("span");
      chunkId.className = "transcript-chunk-id";
      chunkId.textContent = chunk.chunk_id;
      const text = document.createElement("p");
      text.textContent = chunk.text;
      article.append(chunkId, text);
      list.appendChild(article);
      chunkElements.push(article);
    });

    const empty = document.createElement("div");
    empty.className = "transcript-empty hidden";
    empty.textContent = "Không tìm thấy đoạn phù hợp.";

    search.addEventListener("input", () => {
      const query = search.value.trim().toLowerCase();
      let visibleCount = 0;
      chunkElements.forEach((element) => {
        const isVisible = !query || element.dataset.search.includes(query);
        element.classList.toggle("hidden", !isVisible);
        if (isVisible) visibleCount += 1;
      });
      empty.classList.toggle("hidden", visibleCount > 0);
      countText.textContent = query
        ? `${visibleCount}/${data.total_chunks} đoạn phù hợp`
        : `${data.total_chunks} đoạn nguồn · cuộn để đọc`;
      $("#slide-current").textContent = visibleCount;
    });

    view.append(header, list, empty);
    track.replaceChildren(view);
    dots.innerHTML = `<span class="transcript-footer-status">Hiển thị đủ ${data.total_chunks} đoạn nguồn</span>`;

    if (focusChunkId) {
      requestAnimationFrame(() => {
        const target = document.getElementById(`chunk-${focusChunkId}`);
        if (!target) return;
        target.classList.add("focused");
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  } catch (error) {
    const view = document.createElement("div");
    view.className = "transcript-view";
    const errorMessage = document.createElement("div");
    errorMessage.className = "transcript-error";
    errorMessage.textContent = `Không tải được transcript: ${error.message}`;
    view.appendChild(errorMessage);
    track.replaceChildren(view);
    $("#slide-current").textContent = "0";
  }
}

// ─── Source Selection ─────────────────────────────────────────
$$(".source-item").forEach((item) => {
  item.addEventListener("click", () => {
    $$(".source-item").forEach((s) => {
      s.classList.remove("active");
      s.setAttribute("aria-pressed", "false");
    });
    item.classList.add("active");
    item.setAttribute("aria-pressed", "true");

    const id = item.dataset.id;
    const slideKey = item.dataset.slide;
    const key = id || slideKey;
    const previousLessonId = $("#lesson-id").value;

    if (key) {
      $("#lesson-id").value = key;
    }

    if (previousLessonId !== key) {
      state.structuredSummary = null;
      state.summaryLessonId = null;
      $("#summary-inline-messages").innerHTML = "";
      $("#summary-body").classList.add("hidden");
      $("#summary-body").innerHTML = `<div class="summary-empty-state">Chọn “Tóm tắt toàn bộ” hoặc nhắn phần bạn muốn ôn nhanh.</div>`;
    }

    renderSlideDeck(key);
  });
  item.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); item.click(); }
  });
});

// Source filter
$("#source-filter").addEventListener("input", (e) => {
  const q = e.target.value.toLowerCase();
  $$("[data-search]").forEach((item) => item.classList.toggle("hidden", !item.dataset.search.includes(q)));
});

// Collapse sources
$("#collapse-sources").addEventListener("click", () => {
  document.body.classList.toggle("sources-collapsed");
});

// ─── Slide Navigation ─────────────────────────────────────────
function initSlides() {
  renderSlideDeck("transcript-06-clean");
}

function goToSlide(idx) {
  if (state.contentMode !== "summary") return;
  const cards = $$(".slide-card");
  if (idx < 0 || idx >= cards.length) return;
  state.slideIndex = idx;

  const track = $("#slide-track");
  track.style.transform = `translateX(-${idx * 100}%)`;

  cards.forEach((c, i) => c.classList.toggle("active", i === idx));
  $$(".dot").forEach((d, i) => d.classList.toggle("active", i === idx));

  $("#slide-current").textContent = idx + 1;
  $("#slide-prev").disabled = idx === 0;
  $("#slide-next").disabled = idx === cards.length - 1;
}

$("#slide-prev").addEventListener("click", () => goToSlide(state.slideIndex - 1));
$("#slide-next").addEventListener("click", () => goToSlide(state.slideIndex + 1));
$("#summary-view-btn").addEventListener("click", () => {
  renderSlideDeck(state.activeSourceKey);
});
$("#transcript-view-btn").addEventListener("click", () => {
  renderTranscriptDeck(state.activeSourceKey);
});

$$(".dot").forEach((dot) => {
  dot.addEventListener("click", () => goToSlide(Number(dot.dataset.idx)));
});

(function initSwipe() {
  const stage = $("#slide-stage");
  let startX = 0, isDragging = false;
  stage.addEventListener("pointerdown", (e) => {
    startX = e.clientX; isDragging = true;
    stage.setPointerCapture(e.pointerId);
  });
  stage.addEventListener("pointermove", (e) => {
    if (!isDragging) return;
  });
  stage.addEventListener("pointerup", (e) => {
    if (!isDragging) return;
    const dx = e.clientX - startX;
    if (Math.abs(dx) > 50) {
      goToSlide(state.slideIndex + (dx < 0 ? 1 : -1));
    }
    isDragging = false;
  });
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    if (e.key === "ArrowRight") goToSlide(state.slideIndex + 1);
    if (e.key === "ArrowLeft") goToSlide(state.slideIndex - 1);
  });
})();

// ─── Agent Button Events ──────────────────────────────────────
// Welcome screen dual buttons
$("#agent-summary-btn").addEventListener("click", openSummaryWorkspace);
$("#agent-quiz-btn").addEventListener("click", showTopicSelect);
$("#agent-essay-btn")?.addEventListener("click", startEssay);
$("#summary-back-home")?.addEventListener("click", goHome);
$("#topic-back-home")?.addEventListener("click", goHome);

$("#summary-all-btn")?.addEventListener("click", () => {
  $("#summary-inline-input").value = "Tóm tắt toàn bộ bài";
  sendInlineSummaryMessage();
});
$("#summary-inline-send")?.addEventListener("click", sendInlineSummaryMessage);
$("#summary-inline-input")?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") sendInlineSummaryMessage();
});

// Summary chat: switch to quiz
$("#summary-chat-switch-quiz")?.addEventListener("click", showTopicSelect);

// Summary chat: send message
$("#summary-chat-send")?.addEventListener("click", sendSummaryMessage);
$("#summary-chat-input")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendSummaryMessage();
});

$("#essay-back-summary")?.addEventListener("click", goHome);
$("#essay-submit")?.addEventListener("click", submitEssayAnswer);

// Topic confirm → start quiz with chosen topic & bloom
$("#topic-confirm-btn")?.addEventListener("click", startQuizWithTopic);

$("#qf-submit").addEventListener("click", submitQuizAnswer);
$("#qf-back-summary")?.addEventListener("click", goHome);
$("#qf-restart").addEventListener("click", resetAgent);
$("#done-restart").addEventListener("click", resetAgent);
$("#done-retry-topic")?.addEventListener("click", showTopicSelect);
$("#agent-retry").addEventListener("click", () => {
  resetAgent();
  openSummaryWorkspace();
});
$("#summary-refresh").addEventListener("click", () => {
  $("#summary-inline-input").value = "Tóm tắt lại toàn bộ bài";
  sendInlineSummaryMessage();
});

// ─── Reset Session ────────────────────────────────────────────
$("#reset-session").addEventListener("click", () => {
  resetAgent();
  showToast("Phiên học mới đã bắt đầu.");
});

// ─── Init ─────────────────────────────────────────────────────
checkHealth();
initSlides();
updateAgentProgress();
