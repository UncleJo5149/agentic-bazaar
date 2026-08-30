# Agentic Bazaar

Local treasury and creator-commission control plane.

This is not a wallet. It does not hold private keys and it does not broadcast USDT.

## Rules

- Creator commission = 30% of net profit (`settled_sales - refunds`)
- Deposit: USDT TRC-20 `TTamF9HU3cYt2fDaTYB4ZUXfvcogBygC7w`
- Contract: `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`
- If accrued commission is `$0.00`, sweep is skipped
- No invented transfers
- On-chain reads only (TronGrid)

See `CHARTER.md`, `PRIMER.md`, `TERMS.md`, and `GUARDRAILS.md`.

Payment is designed to function with **zero transactions**: state `ready_idle`, sweep skipped, 30/70 split both at `$0.00`. That is live, not display-only.

Keepers are accounting monitors. They do not hold keys and they do not spend the 70% reserve.

## Run locally

Requires Python 3.10+. No pip packages.

```bash
cp treasury.example.json treasury.json
python3 server.py
```

API: `http://127.0.0.1:8787`

```bash
curl http://127.0.0.1:8787/health
curl http://127.0.0.1:8787/v1/treasury
curl http://127.0.0.1:8787/v1/payments
curl http://127.0.0.1:8787/v1/keepers
curl -X POST http://127.0.0.1:8787/v1/payouts/sweep
curl http://127.0.0.1:8787/v1/onchain
```

## Docker

```bash
docker compose up --build
```

Binds `8787`. Use `BAZAAR_HOST=0.0.0.0` inside the container (already set in compose).

## Record real sales

Edit `treasury.json` (or `POST /v1/ledger`) with **actual** settled sales and refunds. Do not type fictional revenue to force a payout.

## What GitHub Actions does

`.github/workflows/smoke.yml` starts the server and checks `/health`. It does not send USDT.

## Push to GitHub

```bash
git init
git add CHARTER.md PRIMER.md TERMS.md GUARDRAILS.md README.md server.py \
        treasury.example.json .gitignore Dockerfile compose.yaml scripts .github
git commit -m "Add Agentic Bazaar operator stack"
git branch -M main
git remote add origin git@github.com:YOUR_USER/agentic-bazaar.git
git push -u origin main
```

Do not commit wallets, keys, or a live `treasury.json` that contains invented balances.
