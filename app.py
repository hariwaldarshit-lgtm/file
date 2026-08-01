import os
import threading
import time

import torch
from flask import Flask, request, jsonify, render_template
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct")
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "300"))
MAX_HISTORY_TURNS = int(os.environ.get("MAX_HISTORY_TURNS", "6"))
SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    "You are a professional AI assistant. Give clear, accurate and complete answers.",
)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Model loading (in a background thread so the web server can bind to a port
# immediately -- Render's health check will otherwise time out while the
# ~3GB model is still downloading/loading into memory).
# ---------------------------------------------------------------------------
state = {
    "status": "loading",   # loading | ready | error
    "message": "Starting up...",
    "tokenizer": None,
    "model": None,
    "device": None,
}


def load_model():
    try:
        state["status"] = "loading"
        state["message"] = f"Downloading/loading {MODEL_NAME}..."
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            torch_dtype=torch.bfloat16,
            low_cpu_mem_usage=True,
        )
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        model.eval()

        state["tokenizer"] = tokenizer
        state["model"] = model
        state["device"] = device
        state["status"] = "ready"
        state["message"] = f"Model ready on {device}."
        print(state["message"])
    except Exception as exc:  # noqa: BLE001
        state["status"] = "error"
        state["message"] = f"Failed to load model: {exc}"
        print(state["message"])


threading.Thread(target=load_model, daemon=True).start()


def build_messages(history, user_message):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    trimmed = history[-MAX_HISTORY_TURNS:] if history else []
    for turn in trimmed:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    return messages


def generate_response(history, user_message):
    tokenizer = state["tokenizer"]
    model = state["model"]
    device = state["device"]

    messages = build_messages(history, user_message)
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(text, return_tensors="pt").to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    response = tokenizer.decode(
        outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True
    )
    return response.strip()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", model_name=MODEL_NAME)


@app.route("/api/status")
def status():
    return jsonify({"status": state["status"], "message": state["message"]})


@app.route("/api/chat", methods=["POST"])
def chat():
    if state["status"] != "ready":
        return jsonify({
            "error": "not_ready",
            "message": state["message"],
        }), 503

    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not user_message:
        return jsonify({"error": "empty_message"}), 400

    start = time.time()
    try:
        reply = generate_response(history, user_message)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": "generation_failed", "message": str(exc)}), 500

    return jsonify({
        "reply": reply,
        "elapsed_seconds": round(time.time() - start, 2),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
