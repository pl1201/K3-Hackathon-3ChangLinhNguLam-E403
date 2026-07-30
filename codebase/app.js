const state = {
  sessionId: null,
  traceId: null,
  question: null,
  lastAnswer: "",
};

const $ = (selector) => document.querySelector(selector);
const views = ["empty", "learning", "result", "loading", "error"];

function showView(name) {
  views.forEach((view) => {
    $(`#${view}-state`).classList.toggle("hidden", view !== name);
  });
}

function setProgress(value, label) {
  $("#progress-value").textContent = `${value}%`;
  $("#progress-bar").style.width = `${value}%`;
  $("#phase-label").textContent = label;
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

async function checkHealth() {
  try {
    const health = await request("/api/health");
    const badge = $("#runtime-badge");
    badge.textContent = health.llm === "configured" ? "AI trực tiếp" : "Demo an toàn";
    badge.className = `badge ${health.llm === "configured" ? "live" : "mock"}`;
    badge.title = `Langfuse: ${health.langfuse}`;
  } catch {
    $("#runtime-badge").textContent = "Mất kết nối API";
    $("#runtime-badge").className = "badge danger";
  }
}

async function startSession() {
  showView("loading");
  $("#loading-title").textContent = "Đang chọn điểm nhớ quan trọng…";
  $("#loading-copy").textContent = "Coach đang truy xuất transcript và tạo câu hỏi có căn cứ.";
  $("#coach-status").textContent = "Đang chuẩn bị";
  try {
    const data = await request("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ lesson_id: "transcript-06-clean", user_id: "demo-user" }),
    });
    state.sessionId = data.session_id;
    state.traceId = data.trace_id;
    state.question = data.question;
    renderQuestion(data);
  } catch (error) {
    showError(error);
  }
}

function renderQuestion(data) {
  $("#question-text").textContent = data.question.prompt;
  $("#difficulty-chip").textContent =
    data.question.difficulty === "application" ? "Vận dụng" : "Nền tảng";
  $("#answer-input").value = "";
  $("#char-count").textContent = "0";
  $("#coach-status").textContent = data.mode === "live" ? "AI trực tiếp" : "Demo có kiểm soát";
  setProgress(data.progress, "Đang tự nhớ lại");
  showView("learning");
  $("#answer-input").focus();
}

async function submitAnswer() {
  const answer = $("#answer-input").value.trim();
  if (!answer) {
    $("#answer-input").focus();
    $("#answer-input").classList.add("invalid");
    return;
  }
  $("#answer-input").classList.remove("invalid");
  state.lastAnswer = answer;
  showView("loading");
  $("#loading-title").textContent = "Đang đối chiếu với bài học…";
  $("#loading-copy").textContent = "Coach đang kiểm tra ý chính, độ rõ và căn cứ nguồn.";
  try {
    const data = await request("/api/answers", {
      method: "POST",
      body: JSON.stringify({ session_id: state.sessionId, answer }),
    });
    state.traceId = data.trace_id;
    renderResult(data);
  } catch (error) {
    showError(error);
  }
}

function renderResult(data) {
  const evaluation = data.evaluation;
  const presentation = {
    correct: ["✓", "ĐÃ NẮM ĐƯỢC", "Bạn đã nắm đúng ý chính.", "success"],
    incorrect: ["↗", "CẦN CỦNG CỐ", "Bạn đang thiếu một mắt xích.", "warning"],
    ambiguous: ["?", "CẦN LÀM RÕ", "Mình chưa đủ thông tin để chấm.", "neutral"],
    unsupported: ["!", "THIẾU CĂN CỨ", "Mình không nên kết luận từ nguồn hiện có.", "danger"],
  }[evaluation.verdict];

  $("#result-icon").textContent = presentation[0];
  $("#result-label").textContent = presentation[1];
  $("#result-title").textContent = presentation[2];
  $("#result-state").dataset.tone = presentation[3];
  $("#feedback-text").textContent = evaluation.feedback;
  $("#try-again").textContent =
    evaluation.next_action === "clarify" ? "Bổ sung câu trả lời" :
    evaluation.next_action === "next" ? "Ôn lại câu này" : "Thử lại để đóng lỗ hổng";

  const gaps = $("#gap-list");
  gaps.innerHTML = "";
  gaps.classList.toggle("hidden", evaluation.knowledge_gaps.length === 0);
  evaluation.knowledge_gaps.forEach((gap) => {
    const item = document.createElement("p");
    item.textContent = gap;
    gaps.appendChild(item);
  });

  const evidence = evaluation.evidence[0];
  $("#evidence-card").classList.toggle("hidden", !evidence);
  if (evidence) {
    $("#evidence-id").textContent = evidence.chunk_id;
    $("#evidence-quote").textContent = evidence.quote;
    $("#source-card .source-id").textContent = evidence.chunk_id;
    $("#source-card p").textContent = evidence.quote;
  }
  $("#feedback-sent").textContent = "";
  setProgress(data.progress, phaseLabel(data.phase));
  showView("result");
}

function phaseLabel(phase) {
  return {
    complete: "Đã hoàn tất",
    clarify: "Cần làm rõ",
    remediate: "Đang củng cố",
    unsupported: "Thiếu căn cứ",
  }[phase] || "Đã đánh giá";
}

function showError(error) {
  $("#error-message").textContent = error.message;
  $("#coach-status").textContent = "Cần thử lại";
  showView("error");
}

function resetSession() {
  state.sessionId = null;
  state.traceId = null;
  state.question = null;
  state.lastAnswer = "";
  setProgress(0, "Sẵn sàng bắt đầu");
  $("#coach-status").textContent = "Sẵn sàng";
  showView("empty");
}

async function sendFeedback(value, button) {
  if (!state.traceId) return;
  document.querySelectorAll(".feedback-button").forEach((item) => {
    item.disabled = true;
    item.classList.toggle("selected", item === button);
  });
  try {
    const data = await request("/api/feedback", {
      method: "POST",
      body: JSON.stringify({ trace_id: state.traceId, value }),
    });
    $("#feedback-sent").textContent = data.accepted ? "Đã ghi nhận" : "Sẽ ghi nhận khi bật Langfuse";
  } catch {
    $("#feedback-sent").textContent = "Chưa gửi được";
  }
}

$("#start-session").addEventListener("click", startSession);
$("#submit-answer").addEventListener("click", submitAnswer);
$("#retry").addEventListener("click", () => state.sessionId ? submitAnswer() : startSession());
$("#reset-session").addEventListener("click", resetSession);
$("#restart").addEventListener("click", resetSession);
$("#try-again").addEventListener("click", () => {
  $("#answer-input").value = state.lastAnswer;
  $("#char-count").textContent = state.lastAnswer.length;
  showView("learning");
  $("#answer-input").focus();
});
$("#show-source").addEventListener("click", () => {
  $("#source-card").classList.add("pulse");
  $("#source-card").scrollIntoView({ behavior: "smooth", block: "center" });
  setTimeout(() => $("#source-card").classList.remove("pulse"), 900);
});
$("#answer-input").addEventListener("input", (event) => {
  $("#char-count").textContent = event.target.value.length;
  event.target.classList.remove("invalid");
});
$("#answer-input").addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") submitAnswer();
});
document.querySelectorAll(".feedback-button").forEach((button) => {
  button.addEventListener("click", () => sendFeedback(button.dataset.feedback === "true", button));
});

checkHealth();
