# Close the first 5¢ loop

The till already quotes, verifies, settles, and writes a ledger row.
What was missing was a buyer that can sign, and machine docs that match live config.

## Railway variables

```
PAY_TO_ADDRESS=0xYourPublicWalletHere
X402_NETWORK=eip155:8453
X402_FACILITATOR_URL=https://x402.org/facilitator
ALLOW_DEMO=false
PUBLIC_BASE_URL=https://web-production-42edc.up.railway.app
```

`PAY_TO_ADDRESS` is the receive address. Never paste a private key into Railway or GitHub.

## Prove the loop locally (no money)

```bash
sh scripts/loop-demo.sh
```

Unpaid `POST /a2a` must be 402.
Demo-paid `POST /a2a` must return `extract` and a ledger row.

## First real 5¢ (USDC on Base)

Need a Base wallet with at least 0.05 USDC plus a little ETH for the facilitator path.

```bash
cd Agent-Till
npm install @x402/fetch @x402/evm viem
EVM_PRIVATE_KEY=0x... node scripts/buy-till-001.mjs
```

Then check:

```
https://web-production-42edc.up.railway.app/ledger.json
```

Done means `x402_count >= 1` and the body contains the till-001 extract.

## After first real payment

Keep `ALLOW_DEMO=false`.
`/payments.json` is generated from live env, not from the stale static file.
