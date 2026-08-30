# Agentic Bazaar — Terms of payment

Effective: 2026-08-30  
Jurisdiction to be set by the legal entity that operates the bazaar. These terms are product rules, not a substitute for licensed counsel.

## 1. What is being paid

Creators receive **30% of net profit**. Net profit is settled sales minus refunds.

The remaining **70% of net profit** is the **platform reserve**. It is not creator commission.

## 2. When money moves

A payment obligation exists only after all of the following:

1. A real buyer payment has settled
2. Any refund window applicable to that sale has closed or the refund has been booked
3. The ledger shows `accrued_commission > 0` for creators and/or `platform_reserve > 0` for the reserve
4. A human operator (or a licensed processor) executes the on-chain or off-chain transfer

Zero sales means zero obligation. The payment system is still **on**. It is idle, not broken.

## 3. What this software may not do

- Hold or request private keys
- Broadcast USDT
- Invent sales, commissions, or transfers
- Collect live USDT against a simulated confirmer
- Spend the platform reserve autonomously
- Promise future AI-era uses of the reserve as a present transfer

## 4. Platform reserve (70%)

The reserve may later be used only for lawful purposes decided by the operating entity: infrastructure, refunds, taxes, creator programs, or other documented costs.

A three-month or later change in the AI market does **not** authorize an agent to move funds. Policy can change by a written charter amendment. Balances cannot be spent by prompt.

## 5. Keepers

Keeper processes are monitors and accountants. They:

- Recalculate splits
- Refuse $0 sweeps
- Read the public deposit address
- Write an operator note

They are not custodians. They cannot sign.

## 6. Buyers and creators

- Prices and refunds must be stated before payment
- Chargebacks and refunds reduce net profit before commission is paid
- No party is owed a payout from an empty ledger

## 7. Not a bank

This project does not take public deposits, pay interest, or provide exchange services. USDT received at the published address, if any, is treated as settlement for recorded sales only.
