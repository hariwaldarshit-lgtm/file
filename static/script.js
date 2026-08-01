const logEl = document.getElementById("log");
const logEmpty = document.getElementById("log-empty");
const composer = document.getElementById("composer");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send-btn");
const statusDot = document.getElementById("status-dot");
const statusMessage = document.getElementById("status-message");

let history = [];
let modelReady = false;
let statusPoll = null;

function autoGrow() {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + "px";
}
inputEl.addEventListener("input", autoGrow);

function setStatus(status, message) {
  statusDot.className = "dot " + status;
  statusMessage.textContent = message;

  if (status === "ready") {
    modelReady = true;
    inputEl.disabled = false;
    sendBtn.disabled = false;
    inputEl.placeholder = "Type a message…";
    if (statusPoll) {
      clearInterval(statusPoll);
      statusPoll = null;
    }
  } else if (status === "error") {
    modelReady = false;
    inputEl.disabled = true;
    sendBtn.disabled = true;
    if (statusPoll) {
      clearInterval(statusPoll);
      statusPoll = null;
    }
  } else {
    modelReady = false;
    inputEl.disabled = true;
    sendBtn.disabled = true;
    inputEl.placeholder = "Waiting for model…";
  }
}

async function pollStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    setStatus(data.status, data.message);
  } catch (err) {
    setStatus("error", "Could not reach server.");
  }
}

statusPoll = setInterval(pollStatus, 2500);
pollStatus();

function hideEmptyState() {
  if (logEmpty) logEmpty.style.display = "none";
}

function appendMessage(role, content) {
  hideEmptyState();
  const wrap = document.createElement("div");
  wrap.className = "msg " + role;

  const label = document.createElement("div");
  label.className = "msg-role";
  label.textContent = role === "user" ? "you" : role === "assistant" ? "assistant" : "system";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = content;

  wrap.appendChild(label);
  wrap.appendChild(bubble);
  logEl.appendChild(wrap);
  logEl.scrollTop = logEl.scrollHeight;
  return bubble;
}

function appendTyping() {
  hideEmptyState();
  const wrap = document.createElement("div");
  wrap.className = "msg assistant";
  wrap.id = "typing-indicator";

  const label = document.createElement("div");
  label.className = "msg-role";
  label.textContent = "assistant";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';

  wrap.appendChild(label);
  wrap.appendChild(bubble);
  logEl.appendChild(wrap);
  logEl.scrollTop = logEl.scrollHeight;
}

function removeTyping() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!modelReady) return;

  const message = inputEl.value.trim();
  if (!message) return;

  appendMessage("user", message);
  history.push({ role: "user", content: message });

  inputEl.value = "";
  autoGrow();
  inputEl.disabled = true;
  sendBtn.disabled = true;
  appendTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });

    const data = await res.json();
    removeTyping();

    if (!res.ok) {
      appendMessage("system", data.message || "Something went wrong.");
    } else {
      appendMessage("assistant", data.reply);
      history.push({ role: "assistant", content: data.reply });
    }
  } catch (err) {
    removeTyping();
    appendMessage("system", "Network error: could not reach the server.");
  } finally {
    inputEl.disabled = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }
});

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    composer.requestSubmit();
  }
});
