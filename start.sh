#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-5000}"
PYTHON_BIN="./.pythonlibs/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python"
fi

echo "Starting PharMareen backend on port $PORT..."
exec "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
