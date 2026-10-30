#!/usr/bin/env bash
# Start Ollama (if needed), backend and frontend. Ctrl+C stops all.
cd "$(dirname "$0")/.."
ROOT=$(pwd)
if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null; then
  (nohup ollama serve >/tmp/ollama.log 2>&1 &); sleep 3
fi
cd "$ROOT/backend" && source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACK=$!
trap "kill $BACK 2>/dev/null" EXIT
cd "$ROOT/frontend" && npm run dev
