#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f treasury.json ]]; then
  cp treasury.example.json treasury.json
fi
exec python3 server.py
