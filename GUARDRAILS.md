# Payment guardrails

## Ready while idle

`payment_state = ready_idle` when:

- API is up
- Charter rules are loaded
- `settled_sales = 0` and `accrued_commission = 0`
- Sweep returns `skipped_no_sales`
- On-chain watch is read-only

That is a functioning payment system with no volume.

## Hard stops

| Action | Allowed? |
|---|---|
| Compute 30/70 split on $0 | Yes → both buckets $0.00 |
| POST /v1/payouts/sweep on $0 | Yes → skip, no transfer |
| Declare commission when ledger > $0 | Yes, declare only |
| Broadcast USDT from this process | No |
| Store a private key | No |
| Book fictional sales so a bot can “save” 70% | No |
| Let an agent spend reserve “for good” later | No, needs human + written amendment |

## Split

```
net_profit          = settled_sales - refunds
creator_commission  = net_profit * 0.30
platform_reserve    = net_profit * 0.70
```

Negative net profit is floored at 0 for payouts. Refunds cannot create a fake reserve.

## Keepers (software)

Three keepers, no keys:

1. `ledger_keeper` — accepts only explicit settled sales / refunds
2. `split_keeper` — enforces 30/70 and $0 skip
3. `chain_keeper` — TronGrid read of `TTamF9HU3cYt2fDaTYB4ZUXfvcogBygC7w`

If any keeper would need a key to “make it work,” the design is wrong. Fix the sales ingest or use a licensed processor.

## Legal floor

Do whatever it takes **inside law**:

- Record real sales
- Pay creators only from net settled profit
- Keep a documented reserve
- Do not operate an unlicensed money-transmission bot

Display-only is avoided by making the ledger, skip logic, and terms executable. On-chain send stays outside this repo until a real processor or human wallet exists.
