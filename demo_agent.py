#!/usr/bin/env python3
"""Buyer-agent walkthrough against a running Agentic Bazaar."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787"


def call(method: str, path: str, body: dict | None = None, headers: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"content-type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode()), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"error": raw}
        return exc.code, parsed, dict(exc.headers)


def show(title: str, payload):
    print(f"\n== {title} ==")
    print(json.dumps(payload, indent=2)[:2000])


def main():
    print(f"Talking to {BASE}")
    st, health, _ = call("GET", "/health")
    show("health", health)

    st, buyer, _ = call(
        "POST",
        "/v1/agents",
        {
            "name": "Buyer-7",
            "operator": "buddy",
            "daily_cap_usd": 10,
            "per_call_cap_usd": 2,
            "auto_approve_under_usd": 1.00,
            "starting_credits_usd": 5,
        },
    )
    show("register buyer", buyer)
    buyer_id = buyer["agent"]["agent_id"]

    st, skills, _ = call("GET", "/v1/skills")
    show("catalog", skills)

    # Cheap skill via credits
    st, quote, _ = call(
        "POST", "/v1/quotes", {"skill_id": "agent_brief", "buyer_id": buyer_id}
    )
    show("quote agent_brief", quote)
    st, paid, _ = call(
        "POST",
        "/v1/pay",
        {
            "quote_id": quote["quote"]["quote_id"],
            "buyer_id": buyer_id,
            "rail": "bazaar.credits",
        },
    )
    show("pay credits", paid)
    st, job, _ = call(
        "POST",
        "/v1/invoke",
        {
            "intent_id": paid["intent"]["intent_id"],
            "input": {"goal": "Launch an agent bazaar with real payment rails"},
        },
    )
    show("invoke agent_brief", job)

    # Same buyer, x402 rail
    st, quote2, _ = call(
        "POST", "/v1/quotes", {"skill_id": "listing_pack", "buyer_id": buyer_id}
    )
    st, signed, _ = call(
        "POST",
        f"/v1/x402/sign?quote_id={quote2['quote']['quote_id']}&buyer_id={buyer_id}",
    )
    show("x402 signature", {"PAYMENT-SIGNATURE": signed["PAYMENT-SIGNATURE"][:80] + "..."})
    st, paid2, hdrs = call(
        "POST",
        "/v1/pay",
        {
            "quote_id": quote2["quote"]["quote_id"],
            "buyer_id": buyer_id,
            "rail": "x402.exact",
            "payment_signature": signed["PAYMENT-SIGNATURE"],
        },
    )
    show("pay x402", paid2)
    print("PAYMENT-RESPONSE present:", "payment-response" in {k.lower() for k in hdrs})
    st, job2, _ = call(
        "POST",
        "/v1/invoke",
        {
            "intent_id": paid2["intent"]["intent_id"],
            "input": {"product": "agent-native payment router"},
        },
    )
    show("invoke listing_pack", job2)

    # Over auto-approve threshold → human gate
    st, quote3, _ = call(
        "POST", "/v1/quotes", {"skill_id": "price_watch", "buyer_id": buyer_id}
    )
    st, gated, _ = call(
        "POST",
        "/v1/pay",
        {
            "quote_id": quote3["quote"]["quote_id"],
            "buyer_id": buyer_id,
            "rail": "stripe.spt",
        },
    )
    show("human gate (price_watch $1.50)", gated)
    if "intent" not in gated:
        raise SystemExit(f"expected gated intent, got {gated}")
    st, approved, _ = call(
        "POST",
        "/v1/approvals",
        {
            "intent_id": gated["intent"]["intent_id"],
            "operator": "buddy",
            "approve": True,
        },
    )
    show("operator approved", approved)
    st, job3, _ = call(
        "POST",
        "/v1/invoke",
        {"intent_id": approved["intent"]["intent_id"], "input": {"sku": "SKU-2048"}},
    )
    show("invoke price_watch", job3)

    # Workaround: pay with USDT-TRC20 invoice (no EIP-3009 on Tether)
    st, quote4, _ = call(
        "POST", "/v1/quotes", {"skill_id": "skill_match", "buyer_id": buyer_id}
    )
    st, opened, _ = call(
        "POST",
        "/v1/invoices",
        {"quote_id": quote4["quote"]["quote_id"], "asset_id": "USDT:tron:mainnet"},
    )
    show("usdt invoice opened", opened)
    st, confirmed, _ = call(
        "POST",
        f"/v1/invoices/{opened['invoice']['invoice_id']}/confirm",
        {
            "tx_hash": "tron_txid_simulated_7c91aa",
            "observed_atomic": opened["invoice"]["amount_atomic"],
        },
    )
    show("usdt invoice confirmed", confirmed)
    st, paid4, _ = call(
        "POST",
        "/v1/pay",
        {
            "quote_id": quote4["quote"]["quote_id"],
            "buyer_id": buyer_id,
            "rail": "stable.invoice",
            "invoice_id": opened["invoice"]["invoice_id"],
        },
    )
    show("pay usdt invoice", paid4)
    st, job4, _ = call(
        "POST",
        "/v1/invoke",
        {
            "intent_id": paid4["intent"]["intent_id"],
            "input": {"goal": "accept USDT without a bank"},
        },
    )
    show("invoke after USDT", job4)

    st, receipts, _ = call("GET", f"/v1/receipts?agent_id={buyer_id}")
    show("receipts", receipts)
    st, me, _ = call("GET", f"/v1/agents/{buyer_id}")
    show("buyer after trading", me)


if __name__ == "__main__":
    main()
