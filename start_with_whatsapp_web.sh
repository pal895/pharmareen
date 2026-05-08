#!/usr/bin/env bash
set -e
PORT="${PORT:-5000}"
export PHARMAREEN_BACKEND_URL="${PHARMAREEN_BACKEND_URL:-http://localhost:$PORT}"

echo "Starting PharMareen FastAPI backend on port $PORT..."
./start.sh > server.log 2>&1 &
BACKEND_PID=$!

echo "Waiting for backend health..."
for i in {1..30}; do
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

echo "Backend healthy. Starting WhatsApp Web bridge..."
node whatsapp-web-bridge.js
kill "$BACKEND_PID" 2>/dev/null || true