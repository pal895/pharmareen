#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-5000}"
PYTHON_BIN="${PYTHON_BIN:-./.pythonlibs/bin/python}"
BACKEND_LOG="${BACKEND_LOG:-server.log}"
BRIDGE_LOG="${BRIDGE_LOG:-bridge.log}"
WHATSAPP_BRIDGE_ENABLED="${WHATSAPP_BRIDGE_ENABLED:-false}"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python"
fi

if ! "$PYTHON_BIN" -c "import uvicorn" >/dev/null 2>&1; then
  echo "Installing Python requirements from requirements.txt..."
  "$PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1 || true
  "$PYTHON_BIN" -m pip install -r requirements.txt
fi

mkdir -p data

echo "Starting PharMareen backend on port $PORT..."
"$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > server.pid
echo "Backend logs: $BACKEND_LOG"

cleanup() {
  if kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup INT TERM

echo "Waiting for backend health..."
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "Backend health: OK"
    break
  fi
  sleep 1
done

if ! curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "Backend health: NOT READY"
fi

if [ "$WHATSAPP_BRIDGE_ENABLED" = "true" ]; then
  echo "WhatsApp bridge requested."
  if command -v node >/dev/null 2>&1 && [ -f local_whatsapp_bridge.js ]; then
    export PHARMAREEN_BACKEND_URL="${PHARMAREEN_BACKEND_URL:-http://127.0.0.1:${PORT}}"
    echo "Starting WhatsApp bridge. Logs: $BRIDGE_LOG"
    node local_whatsapp_bridge.js > "$BRIDGE_LOG" 2>&1 &
    BRIDGE_PID=$!
    echo "$BRIDGE_PID" > bridge.pid
  else
    echo "WhatsApp bridge not started: Node.js or local_whatsapp_bridge.js is missing."
  fi
else
  echo "WhatsApp bridge disabled. Set WHATSAPP_BRIDGE_ENABLED=true to start it with the backend."
fi

wait "$BACKEND_PID"
