#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f bridge.pid ]; then
  kill "$(cat bridge.pid)" >/dev/null 2>&1 || true
  rm -f bridge.pid
fi

if [ -f server.pid ]; then
  kill "$(cat server.pid)" >/dev/null 2>&1 || true
  rm -f server.pid
fi

pkill -f "uvicorn app.main:app" >/dev/null 2>&1 || true
pkill -f "local_whatsapp_bridge.js" >/dev/null 2>&1 || true
echo "PharMareen processes stopped."
