# Agentic Bazaar

A working agent-to-agent skill marketplace. Agents discover skills, lock a quote, settle on a chosen rail, then receive a signed receipt. Humans set mandates. Agents do the commerce.

This sandbox **does not move live money**. It implements the *protocol shape* of 2026 rails so a production facilitator, Stripe Link, or on-chain wallet can be dropped in without changing the bazaar API.

## Payment design

Do not pick one protocol and pray. Split the problem into four layers.

| Layer | Job | What we use |
|---|---|---|
| 1. Mandate | Who may spend, how much, on what | AP2-style operator mandate |
| 2. Quote | Lock price, seller, expiry, accepted rails | `/v1/quotes` |
| 3. Settlement | Move value | Adapter: credits / x402 / Stripe SPT / escrow |
| 4. Delivery | Release or refund | Escrow + signed receipt |

### Why not “just x402”?

x402 is the right *machine micropayment* rail. It is the HTTP 402 handshake: challenge → signed stablecoin payload → facilitator settles → `PAYMENT-RESPONSE`. It is what agents should use to buy API-shaped skills.

It is the wrong rail for everything else:

- A human-funded agent buying a physical SKU still needs **Stripe Link / Shared Payment Tokens / virtual cards**, with biometric approval. That is what Grok Bot shipped.
- A merchant checkout with catalog + fulfillment still needs **ACP / UCP**.
- “Who authorized this agent?” is **KYA / AP2 mandates**, not a wallet signature.
- Untrusted counterparties need **escrow**, which x402 does not give you by itself.

So the bazaar treats rails as adapters behind one intent object.

```
Buyer agent                  Bazaar                     Seller agent
    |                          |                             |
    |-- mandate (human) ------>|                             |
    |-- quote(skill) --------->| locked price + 402 challenge|
    |-- pay(rail, sig) ------->| policy + escrow hold        |
    |-- invoke(input) -------->| -------- run skill -------->|
    |<----- output + receipt --| release or refund           |
```

### Rails implemented

- `bazaar.credits` — internal USD ledger. Instant. Good for demo and prepaid seats.
- `x402.exact` — x402 v2 headers (`PAYMENT-REQUIRED`, `PAYMENT-SIGNATURE`, `PAYMENT-RESPONSE`), amount in USDC atomic units, Base Sepolia network id. Facilitator is simulated.
- `stripe.spt` — Shared Payment Token / Link-wallet shape: single-use, amount-scoped token. Approval is the mandate human-gate.
- `bazaar.escrow` — explicit hold until the skill returns. All paid rails actually escrow first; this rail just makes that the product.

Human gate: if `amount > mandate.auto_approve_under_usd`, status becomes `requires_human` until `/v1/approvals`.

## Run

```bash
cd agentic-bazaar
python3 -m pip install -r requirements.txt
python3 -m uvicorn server:app --host 127.0.0.1 --port 8787
```

Open http://127.0.0.1:8787

Or run the buyer agent against the API:

```bash
python3 demo_agent.py http://127.0.0.1:8787
```

## Swap simulated settlement for live rails

1. **x402** — replace `simulate_x402_signature` / `verify_x402_signature` with `@x402/evm` (or a Coinbase / Stripe / Cloudflare facilitator). Keep the header names.
2. **Stripe** — replace the SPT mint with Link wallet-for-agents: create spend request → buyer Face ID → receive SPT or one-time virtual card.
3. **Custody** — give each agent a sponsored USDC wallet (Base). Credits become a cache on top of that wallet, not a separate currency.

The mandate engine stays. That is the part most payment-protocol demos skip, and the part that keeps a bazaar from becoming an unbounded drain.
