#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-5000}"
export PHARMAREEN_BACKEND_URL="${PHARMAREEN_BACKEND_URL:-http://localhost:$PORT}"
export BAILEYS_SESSION_PATH="${BAILEYS_SESSION_PATH:-./.baileys_auth}"
export AUTO_RESET_BAILEYS_ON_LOGOUT="${AUTO_RESET_BAILEYS_ON_LOGOUT:-true}"

echo "Baileys session path: $BAILEYS_SESSION_PATH"
if [ "${RESET_BAILEYS_SESSION:-false}" = "true" ]; then
  echo "RESET_BAILEYS_SESSION=true, clearing $BAILEYS_SESSION_PATH"
  rm -rf "$BAILEYS_SESSION_PATH"
fi
if [ "${RESET_LEGACY_BAILEYS_SESSION:-false}" = "true" ]; then
  echo "RESET_LEGACY_BAILEYS_SESSION=true, clearing legacy ./auth_info_baileys"
  rm -rf ./auth_info_baileys
fi

echo "Starting PharMareen FastAPI backend on port $PORT..."
./start.sh > server.log 2>&1 &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT

echo "Waiting for backend health..."
for i in $(seq 1 45); do
  if curl -fsS "http://localhost:$PORT/health" >/dev/null 2>&1; then
    echo "Backend healthy: http://localhost:$PORT/health"
    break
  fi
  sleep 1
done

if ! curl -fsS "http://localhost:$PORT/health" >/dev/null 2>&1; then
  echo "Backend did not become healthy. Last server log lines:"
  tail -80 server.log || true
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is not available. Replit should show node v20 after replit.nix loads."
  echo "Backend is still running. Press Ctrl+C after checking /health."
  wait "$BACKEND_PID"
  exit 0
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is not available. Replit should show npm after replit.nix loads."
  echo "Backend is still running. Press Ctrl+C after checking /health."
  wait "$BACKEND_PID"
  exit 0
fi

echo "Node: $(node -v)"
echo "npm: $(npm -v)"
echo "Baileys package version: $(node -e \"console.log(require('@whiskeysockets/baileys/package.json').version)\" 2>/dev/null || echo 'not installed yet')"

if [ -z "${ALLOWED_WHATSAPP_NUMBERS:-}" ]; then
  echo "SAFE MODE: no allowed numbers configured"
else
  echo "ALLOWED_WHATSAPP_NUMBERS: configured"
fi
echo "DEMO_MODE: ${DEMO_MODE:-false}"
echo "GROUP REPLIES: DISABLED"
echo "UNKNOWN NUMBER REPLIES: DISABLED"

if [ ! -d node_modules ]; then
  echo "Installing WhatsApp bridge packages..."
  if ! npm install; then
    echo "npm install failed. Backend is still running. Fix the npm error above, then restart."
    wait "$BACKEND_PID"
    exit 0
  fi
fi

echo "Baileys package version: $(node -e \"console.log(require('@whiskeysockets/baileys/package.json').version)\")"
echo "Baileys session path in use: $BAILEYS_SESSION_PATH"

echo "Starting Baileys WhatsApp bridge first."
echo "SCAN THE QR CODE BELOW WITH WHATSAPP: Linked devices > Link a device"
set +e
node baileys-bridge.js
BRIDGE_EXIT=$?
set -e

echo "Baileys bridge exited with code $BRIDGE_EXIT. Backend will stay running for /health."
wait "$BACKEND_PID"
