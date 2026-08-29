# Agentic Bazaar — conventions for Grok Build

## What this is
An agent-to-agent skill marketplace. Humans issue spend mandates. Agents quote, pay, invoke, and get signed receipts.

## Non-negotiables
- Payments are four layers: mandate → quote → settlement adapter → escrow/receipt.
- Do not collapse the product onto a single protocol.
- Ticker is a label. The official contract is the asset. Reject unknown contracts.
- USDC can settle via x402 EIP-3009. USDT-TRC20 is an invoice (watched transfer), not native x402.
- No rail may skip escrow. Failed skills refund automatically.
- Amounts above `mandate.auto_approve_under_usd` require a human approval record.
- Never log raw payment credentials, private keys, or seed phrases.
- Creator commission is immutable: 30% of net settled revenue after refunds.
- Daily sweep at 09:45 Asia/Singapore to TTamF9HU3cYt2fDaTYB4ZUXfvcogBygC7w. Skip if $0.

## Rails
- `bazaar.credits` — prepaid ledger
- `x402.exact` — HTTP 402 + PAYMENT-SIGNATURE / PAYMENT-RESPONSE
- `stripe.spt` — scoped single-use token / Link spend request
- `bazaar.escrow` — explicit hold
- `stable.invoice` — USDC/USDT deposit to official contract + memo

## Code style
- Python 3.12, FastAPI, Pydantic v2.
- Keep adapters in `bazaar/payments.py`. Keep official contracts in `bazaar/assets.py`.
- New chains/tokens are data in `assets.py`, not scattered if/else.
- Simulated settlement is allowed behind a `mode: "*-simulated"` flag. Live code must sit behind the same interface.
- Add tests before changing settlement or policy.

## First production cut
1. Replace JSON file store with SQLite or Postgres.
2. Replace `confirm_invoice` simulation with a real indexer (TronGrid, Basescan, Solana RPC).
3. Replace `simulate_x402_signature` with a facilitator or `@x402/evm`.
4. Keep the HTTP API shape: `/v1/quotes` → `/v1/pay` → `/v1/invoke`.
