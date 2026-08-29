"""Live TronGrid reader for USDT TRC-20 deposits."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

USDT_TRC20 = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
TRONGRID = "https://api.trongrid.io"


def _get(url: str, timeout: int = 20) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "agentic-bazaar/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def account(address: str) -> dict[str, Any]:
    data = _get(f"{TRONGRID}/v1/accounts/{urllib.parse.quote(address)}")
    rows = data.get("data") or []
    if not rows:
        return {
            "address": address,
            "activated": False,
            "usdt": 0.0,
            "trx": 0.0,
            "raw": data,
        }
    row = rows[0]
    usdt = 0.0
    for item in row.get("trc20") or []:
        if isinstance(item, dict) and USDT_TRC20 in item:
            usdt = int(item[USDT_TRC20]) / 1_000_000
    return {
        "address": address,
        "activated": True,
        "usdt": usdt,
        "trx": int(row.get("balance") or 0) / 1_000_000,
        "create_time": row.get("create_time"),
    }


def incoming_usdt(address: str, limit: int = 20) -> list[dict[str, Any]]:
    q = urllib.parse.urlencode(
        {
            "limit": str(limit),
            "only_confirmed": "true",
            "only_to": "true",
            "contract_address": USDT_TRC20,
        }
    )
    data = _get(
        f"{TRONGRID}/v1/accounts/{urllib.parse.quote(address)}/transactions/trc20?{q}"
    )
    out = []
    for tx in data.get("data") or []:
        raw = int(tx.get("value") or 0)
        token = tx.get("token_info") or {}
        decimals = int(token.get("decimals") or 6)
        out.append(
            {
                "tx_hash": tx.get("transaction_id"),
                "from": tx.get("from"),
                "to": tx.get("to"),
                "amount_usdt": raw / (10**decimals),
                "amount_atomic": str(raw),
                "contract": token.get("address") or USDT_TRC20,
                "block_ts": tx.get("block_timestamp"),
            }
        )
    return out


def verify_usdt_payment(
    address: str, tx_hash: str, expected_atomic: str | None = None
) -> dict[str, Any]:
    txs = incoming_usdt(address, limit=50)
    hit = next((t for t in txs if t["tx_hash"] == tx_hash), None)
    if not hit:
        return {"ok": False, "reason": "tx not found as incoming USDT to treasury"}
    if hit["contract"] != USDT_TRC20:
        return {"ok": False, "reason": "wrong contract", "got": hit["contract"]}
    if expected_atomic and hit["amount_atomic"] != expected_atomic:
        return {
            "ok": False,
            "reason": "amount mismatch",
            "expected": expected_atomic,
            "got": hit["amount_atomic"],
        }
    return {"ok": True, "transfer": hit}
