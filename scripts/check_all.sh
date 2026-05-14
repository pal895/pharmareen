#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-5000}"
BASE_URL="${PHARMAREEN_BACKEND_URL:-http://127.0.0.1:${PORT}}"

echo "Checking PharMareen backend..."
curl -fsS "${BASE_URL}/health"
echo

echo "Checking system status..."
curl -fsS "${BASE_URL}/debug/system-status"
echo
