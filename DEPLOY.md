# Sandbox → live

Do this in order. Do not skip to “accept USDT” while confirm is still mixed.

## What is already live
- TronGrid *read* of `TTamF9HU3cYt2fDaTYB4ZUXfvcogBygC7w`
- USDT-TRC20 invoice confirm refuses fake hashes
- 30% commission on release
- 09:45 Asia/Singapore sweep *instruction*

## What is still sandbox
- Process runs on 127.0.0.1
- Store is a JSON file under `/tmp`
- x402 signatures are facilitator-simulated
- Stripe SPT is shape-only
- Daily sweep declares an amount; it cannot broadcast USDT without a signer

## Cut 1 — public host (no live money)
1. Copy `agentic-bazaar` to a machine you control (laptop, VPS, Cloudflare Worker + container).
2. Persist store off `/tmp` (`DATA_DIR=/var/lib/bazaar` or SQLite).
3. Bind `0.0.0.0:8787` behind HTTPS. Publish:
   - `/discovery.json`
   - `/.well-known/x402` later
   - `/v1/treasury` as the public truth page
4. Env: `BAZAAR_MODE=observe` (read chain, still no live settle).

Done when a phone can open the desk URL and `/v1/treasury` shows the same TronGrid numbers.

## Cut 2 — live USDT invoice (first real rail)
This is the founder’s Bitget rail. Do it before x402.

1. Keep pay-to = `TTamF9HU3cYt2fDaTYB4ZUXfvcogBygC7w`.
2. Keep contract = `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`.
3. Buyer sends exact atomic USDT + memo `BZR-…`.
4. Confirm only via TronGrid (already wired).
5. Escrow → run skill → release → 30% books to creator ledger → 09:45 sweep lists that amount.

Optional later: Merx TRON x402 facilitator (`https://x402.merx.exchange`) so agents need no TRX. Not required for invoice.

Done when one real inbound USDT appears in `incoming_usdt` and a receipt cites that tx hash.

## Cut 3 — live x402 USDC
1. Switch network id from Base Sepolia `eip155:84532` to Base `eip155:8453`.
2. Replace `simulate_x402_signature` with a buyer wallet + facilitator `/verify` + `/settle`.
3. Pay-to for USDC skills is a *treasury* address you control, not the founder Tron wallet.
4. 09:45 job still pays the founder in USDT. Convert USDC → USDT off-platform if needed.

Do not put a private key in env as a CLI flag. Use a facilitator or a signing service.

## Cut 4 — live 09:45 deposit
The automation already fires daily. Live deposit needs one of:
- You send the declared amount from a funded wallet to the Bitget address, or
- A custody partner you approved, with spend limits, no seed in the repo.

If accrued is $0, skip. That rule does not change in production.

## Do not do
- Collect mainnet USDT while `BAZAAR_MODE=observe`
- Point invoices at unofficial USDT contracts
- Call TRC-20 transfers “x402 exact”
- Raise or lower the 30%
- Hand the CEO a seed phrase
