# Agentic Bazaar Charter

Status: operator control plane. Not a wallet.

## Purpose
Record settled sales, refunds, net profit, creator commission (30%), and platform reserve (70%). The payment system is live when idle. Sweep creator commission only when accrued amount is greater than $0.00.

## Immutable payout rules
- Creator commission is 30% of net profits (settled sales after refunds).
- Platform reserve is 70% of net profits. Keepers may account for it. They may not spend it.
- Deposit destination: USDT TRC-20 `TTamF9HU3cYt2fDaTYB4ZUXfvcogBygC7w`
- USDT contract: `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`
- If accrued commission is $0.00, skip. Do not invent a transfer.
- Do not request or use private keys in this stack.
- Do not collect live USDT against a simulated confirmer.
- On-chain queries are read-only (TronGrid).

## Formula
```
net_profit = settled_sales - refunds
accrued_commission = round(max(net_profit, 0) * 0.30, 2)
platform_reserve   = round(max(net_profit, 0) * 0.70, 2)
if accrued_commission <= 0: sweep_status = skipped_no_sales
payment_state = ready_idle when there are no payable profits
```

## Local API
- Base: `http://127.0.0.1:8787`
- `GET /health`
- `GET /v1/payments`
- `GET /v1/keepers`
- `GET /v1/treasury`
- `POST /v1/ledger` (set real `settled_sales` and `refunds` only)
- `POST /v1/payouts/sweep`
- `GET /v1/onchain`
- `GET /v1/primer`

This process is the live local control plane. It is not a wallet. It cannot broadcast TRON transactions.
