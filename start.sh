#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-5000}"
PYTHON_BIN="./.pythonlibs/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python"
fi

if ! "$PYTHON_BIN" -c "import uvicorn" >/dev/null 2>&1; then
  echo "Installing Python requirements from requirements.txt..."
  "$PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1 || true
  "$PYTHON_BIN" -m pip install -r requirements.txt
fi

echo "Starting PharMareen backend on port $PORT..."
exec "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
