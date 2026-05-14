#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export WHATSAPP_BRIDGE_ENABLED="${WHATSAPP_BRIDGE_ENABLED:-true}"
exec bash start.sh
