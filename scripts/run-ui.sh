#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY_BIN="${PY_BIN:-python3}"

echo "Spúšťam UI cez: $PY_BIN"
exec "$PY_BIN" transcript.py
