#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Updating PharMareen..."
git pull origin main

echo "Installing Python dependencies..."
PYTHON_BIN="${PYTHON_BIN:-./.pythonlibs/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python"
fi
"$PYTHON_BIN" -m pip install -r requirements.txt

if command -v npm >/dev/null 2>&1 && [ -f package.json ]; then
  echo "Installing WhatsApp bridge dependencies..."
  npm install
else
  echo "Node.js/npm missing. Backend will still run; bridge status will show missing."
fi

echo "Stopping old servers..."
pkill -f "uvicorn app.main:app" >/dev/null 2>&1 || true
pkill -f "local_whatsapp_bridge.js" >/dev/null 2>&1 || true
pkill -f "baileys-bridge.js" >/dev/null 2>&1 || true

export WHATSAPP_BRIDGE_ENABLED="${WHATSAPP_BRIDGE_ENABLED:-true}"

echo "Starting PharMareen..."
bash start.sh &
START_PID=$!

echo "Waiting for health..."
for _ in $(seq 1 45); do
  if curl -fsS "http://127.0.0.1:5000/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "Local checks:"
curl -fsS "http://127.0.0.1:5000/health"
echo
curl -fsS "http://127.0.0.1:5000/debug/offline-app" >/dev/null && echo "offline app: ok"
curl -fsS "http://127.0.0.1:5000/offline_app/index.html" | grep -E "Tap & Talk|Save Voice|Save Photo|Scan Barcode|Manual Entry" >/dev/null && echo "frontend: ok"

PUBLIC_URL="${PUBLIC_BASE_URL:-https://pharmareen-1--pal895.replit.app}"
echo
echo "Public links:"
echo "$PUBLIC_URL/health"
echo "$PUBLIC_URL/offline_app/index.html"
echo "$PUBLIC_URL/debug/offline-app"
echo "$PUBLIC_URL/debug/system-status"
echo
echo "If bridge is configured, QR/session logs are in bridge.log."

wait "$START_PID"
