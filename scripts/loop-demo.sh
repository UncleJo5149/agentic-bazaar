#!/bin/sh
# Proves quote -> pay -> extract -> ledger on a local process. No chain.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
PORT="${PORT:-8099}"
export PORT
export PAY_TO_ADDRESS="${PAY_TO_ADDRESS:-0xF9C7c3022Bd8756E06172B37A6F9448a730638C9}"
export X402_NETWORK="${X402_NETWORK:-eip155:8453}"
export ALLOW_DEMO=true
export LEDGER_PATH="${LEDGER_PATH:-$ROOT/data/ledger-demo.jsonl}"
rm -f "$LEDGER_PATH"
node src/server.js &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
i=0
while [ "$i" -lt 30 ]; do
  if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; then
    break
  fi
  i=$((i + 1))
  sleep 0.1
done
echo "== unpaid =="
curl -sS -D - -o /tmp/till-unpaid.json -X POST "http://127.0.0.1:$PORT/a2a" \
  -H 'content-type: application/json' \
  -d '{"listing_id":"till-001"}' | head -n 12
echo
echo "== demo paid =="
curl -sS -X POST "http://127.0.0.1:$PORT/a2a" \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer till-demo' \
  -d '{"listing_id":"till-001"}'
echo
echo "== ledger =="
curl -sS "http://127.0.0.1:$PORT/ledger.json"
echo
echo "== payments.json =="
curl -sS "http://127.0.0.1:$PORT/payments.json"
echo
