# Qwen2.5-1.5B Chat Console

A small Flask app that wraps `Qwen/Qwen2.5-1.5B-Instruct` behind a web chat UI, ready to deploy on [Render](https://render.com).

## How it's structured

```
app.py              Flask server: loads the model on a background thread,
                     exposes /api/status and /api/chat
templates/index.html  Page shell
static/style.css      Console-style dark UI
static/script.js       Polls /api/status, sends chat turns, renders replies
requirements.txt      Python deps (torch is installed separately, see below)
render.yaml            Render blueprint (build + start commands, env vars)
```

The model loads in a background thread so the server can bind to its port immediately — Render's health check would otherwise time out while the ~3 GB model downloads and loads into memory. The UI polls `/api/status` and unlocks the input box once `status: "ready"` comes back.

## Run locally

```bash
python -m venv venv && source venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU wheel, ~200MB smaller than default
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000. First load will take a minute or two while the model downloads from Hugging Face and loads into memory.

## Deploy to Render

1. Push this folder to a GitHub repo.
2. In Render, choose **New → Blueprint** and point it at the repo — it will read `render.yaml` automatically. Or create a **Web Service** manually with:
   - Build command: `pip install --upgrade pip && pip install torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt`
   - Start command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 300`
3. Deploy. Watch the logs — you'll see "Downloading/loading Qwen/Qwen2.5-1.5B-Instruct..." followed by "Model ready on cpu."

### About plan size — please read before deploying

This is a real 1.5B-parameter model running in float32 on CPU. That means:

- **RAM**: weights alone are ~6 GB in float32; Render's free (512 MB) and starter (512 MB–2 GB) tiers will very likely be killed by an out-of-memory error during load. Use at least a **Standard** instance (4 GB+ RAM), which `render.yaml` requests by default.
- **Cold start**: model download + load typically takes 1–3 minutes on a cold instance. Render's free/starter tiers also spin down on idle, so every wake-up repeats this — a paid always-on plan avoids that.
- **Generation speed**: CPU inference is slow. Expect single-digit tokens/second for a 1.5B model, so a 300-token reply can take 20–60+ seconds. `MAX_NEW_TOKENS` in `render.yaml` controls this — lower it for snappier (but shorter) replies.
- **`workers 1`** in the start command is intentional: each gunicorn worker would load its own full copy of the model into memory, so keep it at 1 unless you deliberately size the instance up.

If you want faster responses, the two levers that actually move the needle are a smaller model (e.g. a 0.5B variant) or a GPU-backed host — Render's CPU instances won't get you fast inference on a model this size.

## Customizing

- `MODEL_NAME`, `MAX_NEW_TOKENS`, `MAX_HISTORY_TURNS`, and `SYSTEM_PROMPT` are all environment variables (set in `render.yaml` or your shell).
- Conversation history is kept in the browser tab (not persisted) and replayed with each request, capped at `MAX_HISTORY_TURNS` turns to bound prompt length.
