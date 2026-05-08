#!/usr/bin/env bash
set -euo pipefail
PORT="${PORT:-5000}"
export PHARMAREEN_BACKEND_URL="${PHARMAREEN_BACKEND_URL:-http://localhost:$PORT}"
export PUPPETEER_SKIP_DOWNLOAD="${PUPPETEER_SKIP_DOWNLOAD:-true}"
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD="${PUPPETEER_SKIP_CHROMIUM_DOWNLOAD:-true}"

if [ -n "${WHATSAPP_WEB_CHROME_PATH:-}" ]; then
  export PUPPETEER_EXECUTABLE_PATH="$WHATSAPP_WEB_CHROME_PATH"
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is not available yet. Replit must load replit.nix, then restart the repl."
  echo "Expected: node -v and npm -v should work."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is not available yet. Replit must load Node.js from replit.nix."
  exit 1
fi

echo "Node: $(node -v)"
echo "npm: $(npm -v)"

if [ ! -d node_modules ]; then
  echo "Installing WhatsApp bridge packages..."
  npm install
fi

echo "Starting PharMareen FastAPI backend on port $PORT..."
./start.sh > server.log 2>&1 &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT

echo "Waiting for backend health..."
for i in $(seq 1 45); do
  if curl -fsS "http://localhost:$PORT/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "http://localhost:$PORT/health" >/dev/null 2>&1; then
  echo "Backend did not become healthy. See server.log."
  tail -80 server.log || true
  exit 1
fi

echo "Backend healthy."
echo "Starting WhatsApp Web bridge. Scan the QR code when it appears."
set +e
node whatsapp-web-bridge.js
BRIDGE_EXIT=$?
set -e

if [ "$BRIDGE_EXIT" -ne 0 ] && [ "${ENABLE_BAILEYS_FALLBACK:-true}" != "false" ]; then
  echo "whatsapp-web.js exited with code $BRIDGE_EXIT. Starting Baileys fallback..."
  node baileys-bridge.js
else
  exit "$BRIDGE_EXIT"
fi
