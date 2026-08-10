#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-5000}"
PYTHON_BIN="${PYTHON_BIN:-}"
BACKEND_LOG="${BACKEND_LOG:-server.log}"
BRIDGE_LOG="${BRIDGE_LOG:-bridge.log}"
WHATSAPP_BRIDGE_ENABLED="${WHATSAPP_BRIDGE_ENABLED:-false}"
BRIDGE_SCRIPT="${BRIDGE_SCRIPT:-local_whatsapp_bridge.js}"

# Generate one internal per-process bridge credential. It is shared only by the
# backend and bridge processes and is never an owner/customer login credential.
if [ -z "${MS20_BRIDGE_INTERNAL_TOKEN:-}" ]; then
  MS20_BRIDGE_INTERNAL_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
  export MS20_BRIDGE_INTERNAL_TOKEN
fi

if ! command -v tesseract >/dev/null 2>&1 && [ "${MS20_NIX_OCR_READY:-false}" != "true" ]; then
  if command -v nix-shell >/dev/null 2>&1; then
    echo "Loading the local invoice reader..."
    exec nix-shell -p tesseract --run "MS20_NIX_OCR_READY=true WHATSAPP_BRIDGE_ENABLED=$WHATSAPP_BRIDGE_ENABLED bash start.sh"
  fi
  echo "Local invoice reader is unavailable: tesseract was not found."
fi

if [ -z "$PYTHON_BIN" ] && python -c "import uvicorn, PIL, pytesseract" >/dev/null 2>&1; then
  # Replit Publishing installs requirements during its build. Reuse that
  # environment so the required port opens within the health-check window.
  PYTHON_BIN="python"
fi

if [ -z "$PYTHON_BIN" ] || ! "$PYTHON_BIN" -c "import sys" >/dev/null 2>&1; then
  echo "Creating the project Python environment..."
  python -m venv .ms20-venv
  PYTHON_BIN="./.ms20-venv/bin/python"
fi

if ! "$PYTHON_BIN" -c "import uvicorn, PIL, pytesseract" >/dev/null 2>&1; then
  echo "Installing Python requirements from requirements.txt..."
  export PIP_USER=false
  "$PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1 || true
  "$PYTHON_BIN" -m pip install --no-user -r requirements.txt
fi

mkdir -p data

# Replace an older MS2.0 backend before starting the updated code. Without this,
# port 5000 can keep serving an old Python environment after a successful pull.
if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "Stopping the previous MS2.0 backend..."
  pkill -f "uvicorn app.main:app" >/dev/null 2>&1 || true
  for _ in $(seq 1 20); do
    if ! curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then break; fi
    sleep 0.25
  done
fi

echo "Starting MS2.0 backend on port $PORT..."
"$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > server.pid
echo "Backend logs: $BACKEND_LOG"

sleep 0.5
if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
  echo "Backend did not start. Check $BACKEND_LOG."
  exit 1
fi

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

# Warmup runs inside the backend and writes its truthful result to server.log.
# Read only the recent log tail: grep -a treats a binary-detected log as text,
# the fixed phrase selects the event, and tail -1 returns its newest occurrence.
# This displays an existing marker; it never initiates or fabricates warmup.
WARMUP_MARKER=""
for _ in $(seq 1 30); do
  WARMUP_MARKER="$(tail -n 200 "$BACKEND_LOG" 2>/dev/null | grep -aF "REPORT_SOURCE_SNAPSHOT_WARMED" | tail -1 || true)"
  if [ -n "$WARMUP_MARKER" ]; then
    echo "$WARMUP_MARKER"
    break
  fi
  sleep 0.5
done
if [ -z "$WARMUP_MARKER" ]; then
  echo "WARNING: report snapshot warmup marker did not appear within 15 seconds; check $BACKEND_LOG for backend diagnostics."
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
