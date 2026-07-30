/* ============================================================
   VLearn Study Studio — App Logic
   Agent: Summarize → Topic Select → Quiz (20-25 câu) → Gap Summary
   ============================================================ */

// ─── State ───────────────────────────────────────────────────
const state = {
  sessionId: null,
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
  selectedBloom: "analyze",
  selectedTopicQuery: null,
  errorLog: [],         // [{question, correctAnswer, userAnswer, misconception}]
};

// ─── Helpers ─────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

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

// ─── Agent UI Helpers ─────────────────────────────────────────
const AGENT_PANELS = [
  "agent-welcome",
  "agent-thinking",
  "agent-summary",
  "agent-topic-select",
  "agent-quiz-flow",
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
async function showSummary(lessonId) {
  state.agentPhase = "summary";
  setAgentStatus("active", "Tóm tắt xong");
  showAgentPanel("agent-summary");

  const summaryData = getSummaryForLesson(lessonId);
  const body = $("#summary-body");
  body.innerHTML = "";

  const section1 = document.createElement("div");
  section1.className = "summary-section";
  section1.innerHTML = `<h4>📌 Nội dung cốt lõi</h4><p>${summaryData.core}</p>`;
  body.appendChild(section1);

  const section2 = document.createElement("div");
  section2.className = "summary-section";
  const ul = document.createElement("ul");
  ul.className = "summary-key-points";
  summaryData.points.forEach((pt) => {
    const li = document.createElement("li");
    li.textContent = pt;
    ul.appendChild(li);
  });
  section2.innerHTML = `<h4>🔑 Điểm học trọng tâm</h4>`;
  section2.appendChild(ul);
  body.appendChild(section2);

  if (summaryData.note) {
    const section3 = document.createElement("div");
    section3.className = "summary-section";
    section3.innerHTML = `<h4>💡 Ghi nhớ nhanh</h4><p>${summaryData.note}</p>`;
    body.appendChild(section3);
  }
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
        num_questions: 20,
      }),
    });

    setProgressStep({ read: "done", summarize: "done", quiz: "done" });
    state.sessionId = data.session_id;
    state.targetTotal = data.total_questions || 20;

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
      // Track errors for done screen
      const analysis = data.error_analysis;
      state.errorLog.push({
        question: state.question?.question_text || "—",
        explanation: data.explanation || "",
        misconception: analysis?.misconception_topic || analysis?.misconception_explanation || null,
        correctAnswer: null, // not exposed by API publicly
      });
    }

    updateAgentProgress();
    updateQuizFlowHeader(data.current_question_idx ?? state.answered, data.total_questions ?? state.targetTotal);
    renderQuizResult(data);
    setAgentStatus("active", "Đang quiz");
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

  const analysis = data.error_analysis;
  const misconEl = $("#qf-misconception");
  misconEl.classList.toggle("hidden", !analysis);
  if (analysis) {
    $("#qf-misconception-text").textContent =
      analysis.misconception_explanation || analysis.explanation || analysis.feedback || JSON.stringify(analysis);
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
    setTimeout(() => showAgentDone(), 900);
    return;
  }

  nextBtn.onclick = () => {
    if (data.question) {
      renderQuizQuestion(data.question);
    } else {
      fetchNextQuestion(nextIdx, totalQ);
    }
  };
  reinforceBtn.onclick = () => renderQuizQuestion(data.question);
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
  titleEl.innerHTML = `📋 Tổng hợp lỗ hổng kiến thức <span class="gap-count">${state.errorLog.length} điểm cần ôn</span>`;
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
  state.selectedIndex = null;
  state.question = null;
  state.answered = 0;
  state.correct = 0;
  state.gaps = 0;
  state.agentPhase = "idle";
  state.errorLog = [];
  state.selectedTopicQuery = null;
  updateAgentProgress();
  setAgentStatus("idle", "Sẵn sàng");
  showAgentPanel("agent-welcome");
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
  $("#slide-source-label").textContent = deck.label;

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
  $("#slide-total").textContent = state.slideTotalCount;
  goToSlide(0);
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

    if (id) {
      $("#lesson-id").value = id;
    }

    renderSlideDeck(key);

    if (state.agentPhase !== "idle") {
      resetAgent();
      showToast("Nguồn học đã thay đổi. Bắt đầu lại nhé.");
    }
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
$("#agent-start-btn").addEventListener("click", agentStart);

// "Bắt đầu Quiz ngay" → show topic select
$("#agent-quiz-start").addEventListener("click", showTopicSelect);

// Topic confirm → start quiz with chosen topic & bloom
$("#topic-confirm-btn")?.addEventListener("click", startQuizWithTopic);

$("#qf-submit").addEventListener("click", submitQuizAnswer);
$("#qf-restart").addEventListener("click", resetAgent);
$("#done-restart").addEventListener("click", resetAgent);
$("#done-retry-topic")?.addEventListener("click", showTopicSelect);
$("#agent-retry").addEventListener("click", agentStart);
$("#summary-refresh").addEventListener("click", () => {
  resetAgent();
  setTimeout(agentStart, 100);
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
