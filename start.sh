#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-5000}"
PYTHON_BIN="${PYTHON_BIN:-./.pythonlibs/bin/python}"
BACKEND_LOG="${BACKEND_LOG:-server.log}"
BRIDGE_LOG="${BRIDGE_LOG:-bridge.log}"
WHATSAPP_BRIDGE_ENABLED="${WHATSAPP_BRIDGE_ENABLED:-false}"
BRIDGE_SCRIPT="${BRIDGE_SCRIPT:-local_whatsapp_bridge.js}"

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

if [ -n "${REPLIT_DEV_DOMAIN:-}" ]; then
  echo "MS2.0 Main App: https://${REPLIT_DEV_DOMAIN}/main-app/"
else
  echo "MS2.0 Main App: http://127.0.0.1:${PORT}/main-app/"
fi

if [ "$WHATSAPP_BRIDGE_ENABLED" = "true" ]; then
  echo "WhatsApp bridge requested."
  if ! command -v node >/dev/null 2>&1; then
    echo "WhatsApp bridge not started: Node.js is missing."
    echo "Backend stays running. Install/enable Node.js, then restart with WHATSAPP_BRIDGE_ENABLED=true."
  elif [ ! -f "$BRIDGE_SCRIPT" ]; then
    echo "WhatsApp bridge script $BRIDGE_SCRIPT not found."
    if [ -f local_whatsapp_bridge.js ]; then
      BRIDGE_SCRIPT="local_whatsapp_bridge.js"
    elif [ -f baileys-bridge.js ]; then
      BRIDGE_SCRIPT="baileys-bridge.js"
    fi
  fi
  if command -v node >/dev/null 2>&1 && [ -f "$BRIDGE_SCRIPT" ]; then
    if [ -f package.json ] && [ ! -d node_modules ]; then
      if command -v npm >/dev/null 2>&1; then
        echo "Installing WhatsApp bridge dependencies..."
        npm install >> "$BRIDGE_LOG" 2>&1 || echo "npm install failed. Backend stays running; check $BRIDGE_LOG."
      else
        echo "npm is missing, so bridge dependencies could not be installed."
      fi
    fi
    export PHARMAREEN_BACKEND_URL="${PHARMAREEN_BACKEND_URL:-http://127.0.0.1:${PORT}}"
    echo "Starting WhatsApp bridge with $BRIDGE_SCRIPT. Logs: $BRIDGE_LOG"
    node "$BRIDGE_SCRIPT" > "$BRIDGE_LOG" 2>&1 &
    BRIDGE_PID=$!
    echo "$BRIDGE_PID" > bridge.pid
  fi
else
  echo "WhatsApp bridge disabled. Set WHATSAPP_BRIDGE_ENABLED=true to start it with the backend."
fi

wait "$BACKEND_PID"
