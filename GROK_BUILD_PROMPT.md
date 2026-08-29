# Paste this into Grok Build (plan mode first)

You are taking over **Agentic Bazaar**, a working agent-to-agent skill marketplace.

## Goal
Do not rewrite from scratch. Do not invent a new payment protocol.
Turn this tree into a repo you can run, test, and then connect to live USDC/USDT.

## Immutable (founder lock)
- Creator commission = 30% of net profits (settled sales after refunds).
- Deposit wallet = USDT TRC-20 TTamF9HU3cYt2fDaTYB4ZUXfvcogBygC7w
- Official USDT contract = TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t
- Daily sweep 09:45 Asia/Singapore. If accrued is $0, skip. Do not invent a transfer.
- No private keys in env, flags, or git.

## Already built
Python FastAPI app:
- Mandate → quote → multi-rail pay → escrow → invoke → signed receipt
- Rails: bazaar.credits, x402.exact, stripe.spt, bazaar.escrow, stable.invoice
- Live TronGrid reader in bazaar/tron.py
- Demand board + commerce skills in bazaar/skills.py
- Daily sweep in bazaar/payout.py
- Desk UI in static/index.html

Read CHARTER.md, AGENTS.md, DEPLOY.md, README.md before editing.

## Do this, in order
1. Plan only. List files you will touch.
2. Add pytest for: mandate denial, quote expiry, x402 header bind-to-quote, USDT invoice amount mismatch, refund on skill failure, credits not debited on stable.invoice, 30% split, skip sweep when $0.
3. Replace JSON store with SQLite. Same table names.
4. Isolate simulated settlement in bazaar/adapters/simulated.py. Stub bazaar/adapters/live.py. Keep existing TronGrid confirm.
5. Persist data off /tmp. Add env DATA_DIR, BAZAAR_MODE=observe|accept.
6. Update README: which rails are live vs simulated.

## Explicitly do not
- Do not add unofficial token contracts.
- Do not let USDT-TRC20 pretend to be EIP-3009 x402.
- Do not change the 30% rate or the Tron pay-to.
- Do not build a consumer storefront.

## Done when
python -m pytest passes, python demo_agent.py http://127.0.0.1:8787 completes credits + x402 + USDT invoice paths, and README states live vs simulated.
