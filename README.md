# Agent Till

Paid fetch-and-cite access for AI agents.

Legal seller: **RENMOLT ETHICAL SYSTEMS**  
Registration: **202603057004 (TR0338241-U)**  
Form: registered business under the Registration of Businesses Act 1956 (not a Sdn Bhd).  
Valid on the current Borang D until 25 February 2027.

Humans are not the customer.

## What is live in v0.1

- Public page
- `/.well-known/agent.json`
- `/catalog.json`
- `POST /a2a` skill: `fetch-cite`
- HTTP 402 until a payment header is present
- x402 verify + settle through `https://x402.org/facilitator`
- Receipt split: 8% protocol fee, then 60% agent treasury / 40% steward
- `/payments.json` and `/payments.txt` generated from live env

## First closed loop

```bash
sh scripts/loop-demo.sh
```

Real 5¢ USDC on Base:

```bash
npm install @x402/fetch @x402/evm viem
EVM_PRIVATE_KEY=0x... node scripts/buy-till-001.mjs
```

See `GO_LIVE_PAYMENT.md`.

## GitHub → Railway

1. Push this repo to GitHub.
2. In Railway: New Project → Deploy from GitHub repo.
3. Set `PUBLIC_BASE_URL`, `PAY_TO_ADDRESS`, `X402_NETWORK=eip155:8453`.
4. Leave `ALLOW_DEMO` unset or `false` on mainnet.

## Do not put on the public site

Home address from the SSM certificate. Name + registration number is enough.
