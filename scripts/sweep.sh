#!/usr/bin/env bash
set -euo pipefail
BASE="${BAZAAR_URL:-http://127.0.0.1:8787}"
curl -sS "$BASE/health"
echo
curl -sS "$BASE/v1/treasury"
echo
curl -sS -X POST "$BASE/v1/payouts/sweep"
echo
curl -sS "$BASE/v1/onchain"
echo
