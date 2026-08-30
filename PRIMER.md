# Operator primer

## What this repo is

A small HTTP service that:

1. Stores settled sales and refunds
2. Computes 30% creator commission
3. Declares or skips a sweep
4. Reads incoming USDT on the deposit address (TronGrid, read-only)

## What this repo is not

- Not a marketplace storefront
- Not a TRON wallet
- Not a USDT sender
- Not a substitute for the original product repo if you have one

## Daily sweep

1. Confirm the API is up: `GET /health`
2. Read ledger: `GET /v1/treasury`
3. Run `POST /v1/payouts/sweep`
4. If status is `skipped_no_sales`, stop
5. If status is `declared`, a human wallet operator may send USDT to the charter address **only** after verifying the ledger against real settled sales
6. Never paste a private key into the API, GitHub, or chat

## Improve later

- Replace JSON file with a real database
- Ingest orders from the actual store
- Add auth in front of `/v1/ledger` and `/v1/payouts/sweep`
- Keep broadcast out of this process
