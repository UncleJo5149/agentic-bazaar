#!/usr/bin/env python3
"""Agentic Bazaar local treasury API. Read-only chain. No private keys."""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HOST = os.environ.get("BAZAAR_HOST", "127.0.0.1")
PORT = int(os.environ.get("BAZAAR_PORT", "8787"))
ROOT = Path(__file__).resolve().parent
TREASURY_PATH = Path(os.environ.get("BAZAAR_TREASURY", str(ROOT / "treasury.json")))
SGT = timezone(timedelta(hours=8))

DEPOSIT = "TTamF9HU3cYt2fDaTYB4ZUXfvcogBygC7w"
USDT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
TRONGRID = (
    f"https://api.trongrid.io/v1/accounts/{DEPOSIT}/transactions/trc20"
    f"?limit=5&contract_address={USDT}&only_confirmed=true"
)


def now_sgt() -> str:
    return datetime.now(SGT).isoformat(timespec="seconds")


def load_treasury() -> dict:
    if TREASURY_PATH.exists():
        return json.loads(TREASURY_PATH.read_text())
    return {
        "updated_at": now_sgt(),
        "currency": "USD",
        "settled_sales": 0.0,
        "refunds": 0.0,
        "net_profit": 0.0,
        "commission_rate": 0.30,
        "reserve_rate": 0.70,
        "accrued_commission": 0.0,
        "platform_reserve": 0.0,
        "paid_commission": 0.0,
        "payment_state": "ready_idle",
        "sweep_status": "skipped_no_sales",
        "last_sweep_at": None,
        "deposit_address": DEPOSIT,
        "usdt_contract": USDT,
        "notes": "Empty ledger",
    }


def save_treasury(data: dict) -> None:
    data["updated_at"] = now_sgt()
    TREASURY_PATH.write_text(json.dumps(data, indent=2) + "\n")


def recompute(data: dict) -> dict:
    sales = float(data.get("settled_sales", 0) or 0)
    refunds = float(data.get("refunds", 0) or 0)
    net = round(sales - refunds, 2)
    payable = max(net, 0.0)
    comm = round(payable * 0.30, 2)
    reserve = round(payable * 0.70, 2)
    data["net_profit"] = net
    data["commission_rate"] = 0.30
    data["reserve_rate"] = 0.70
    data["accrued_commission"] = comm
    data["platform_reserve"] = reserve
    data["deposit_address"] = DEPOSIT
    data["usdt_contract"] = USDT
    if payable <= 0:
        data["payment_state"] = "ready_idle"
    elif comm > 0:
        data["payment_state"] = "accrual_pending_human_send"
    else:
        data["payment_state"] = "ready_idle"
    return data


def fetch_onchain() -> dict:
    result = {
        "address": DEPOSIT,
        "contract": USDT,
        "ok": False,
        "usdt_incoming_count": 0,
        "latest_incoming_tx": None,
        "error": None,
    }
    try:
        req = urllib.request.Request(
            TRONGRID,
            headers={"User-Agent": "agentic-bazaar-operator/1.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode())
        rows = payload.get("data") or []
        incoming = [r for r in rows if r.get("to") == DEPOSIT]
        result["ok"] = True
        result["usdt_incoming_count"] = len(incoming)
        if incoming:
            tx = incoming[0]
            raw = tx.get("value") or "0"
            try:
                amount = int(raw) / 1_000_000
            except (TypeError, ValueError):
                amount = None
            result["latest_incoming_tx"] = {
                "txid": tx.get("transaction_id"),
                "from": tx.get("from"),
                "value_usdt": amount,
                "block_timestamp": tx.get("block_timestamp"),
            }
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    return result


def primer() -> dict:
    return {
        "title": "Agentic Bazaar operator primer",
        "live": f"http://{HOST}:{PORT}",
        "rules": [
            "Commission = 30% of net profit after refunds",
            "Platform reserve = 70% of net profit after refunds",
            "Skip sweep at $0.00; system remains ready_idle",
            "No private keys in this process",
            "No live USDT collection against a simulated confirmer",
            "Keepers account and watch; they do not sign or spend",
        ],
        "endpoints": {
            "GET /health": "liveness",
            "GET /v1/treasury": "ledger",
            "GET /v1/payments": "payment state, including idle-ready",
            "GET /v1/keepers": "monitor roles, no keys",
            "POST /v1/payouts/sweep": "declare or skip payout; does not broadcast",
            "GET /v1/onchain": "read-only TronGrid",
            "GET /v1/primer": "this document",
        },
        "constraints": [
            "This API is a control plane, not a wallet.",
            "Zero transactions is a valid live state.",
            "Reserve funds cannot be spent by an agent prompt.",
        ],
    }


def payments_view(data: dict) -> dict:
    data = recompute(data)
    return {
        "payment_state": data.get("payment_state"),
        "functioning": True,
        "volume": "none" if data["accrued_commission"] == 0 and data["settled_sales"] == 0 else "nonzero",
        "settled_sales": data["settled_sales"],
        "refunds": data["refunds"],
        "net_profit": data["net_profit"],
        "creator_commission_30pct": data["accrued_commission"],
        "platform_reserve_70pct": data["platform_reserve"],
        "sweep_status": data.get("sweep_status"),
        "broadcast": False,
        "next_action": (
            "none_idle"
            if data.get("payment_state") == "ready_idle"
            else "human_or_licensed_processor_may_send_declared_amount"
        ),
        "terms": "/TERMS.md",
        "guardrails": "/GUARDRAILS.md",
    }


def keepers_view() -> dict:
    return {
        "role": "save_keepers",
        "custody": False,
        "keys": False,
        "bots": [
            {
                "id": "ledger_keeper",
                "job": "Accept only explicit settled_sales and refunds",
            },
            {
                "id": "split_keeper",
                "job": "Lock 30% creator / 70% platform reserve; skip $0 sweeps",
            },
            {
                "id": "chain_keeper",
                "job": "Read-only watch of the published USDT address",
            },
        ],
        "platform_reserve_policy": (
            "70% accrues only from real net profit. Future lawful use requires "
            "a written charter amendment and a human or licensed sender. "
            "Keepers do not spend."
        ),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "AgenticBazaar/1.0"

    def _json(self, code: int, body: dict) -> None:
        raw = json.dumps(body, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/health":
            self._json(200, {"ok": True, "service": "agentic-bazaar", "time": now_sgt()})
            return
        if path == "/v1/treasury":
            data = recompute(load_treasury())
            save_treasury(data)
            self._json(200, data)
            return
        if path == "/v1/onchain":
            self._json(200, fetch_onchain())
            return
        if path == "/v1/primer":
            self._json(200, primer())
            return
        if path == "/v1/payments":
            self._json(200, payments_view(load_treasury()))
            return
        if path == "/v1/keepers":
            self._json(200, keepers_view())
            return
        if path == "/":
            self._json(
                200,
                {
                    "service": "agentic-bazaar",
                    "health": "/health",
                    "payments": "/v1/payments",
                    "keepers": "/v1/keepers",
                    "primer": "/v1/primer",
                },
            )
            return
        self._json(404, {"error": "not_found", "path": path})

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode())

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/v1/ledger":
            try:
                body = self._read_json_body()
            except json.JSONDecodeError:
                self._json(400, {"error": "invalid_json"})
                return
            data = load_treasury()
            if "settled_sales" in body:
                data["settled_sales"] = float(body["settled_sales"])
            if "refunds" in body:
                data["refunds"] = float(body["refunds"])
            data = recompute(data)
            data["notes"] = body.get("notes", "Ledger updated. Figures must be real settled sales.")
            save_treasury(data)
            self._json(200, data)
            return
        if path != "/v1/payouts/sweep":
            self._json(404, {"error": "not_found", "path": path})
            return
        data = recompute(load_treasury())
        if data["accrued_commission"] <= 0:
            data["sweep_status"] = "skipped_no_sales"
            data["last_sweep_at"] = now_sgt()
            data["notes"] = "Sweep skipped. Accrued commission is $0.00. No transfer invented."
            save_treasury(data)
            self._json(
                200,
                {
                    "sweep_status": "skipped_no_sales",
                    "accrued_commission": 0.0,
                    "broadcast": False,
                    "reason": "zero_commission",
                    "treasury": data,
                },
            )
            return
        # Positive commission: declare only. Never broadcast. Never hold keys.
        data["sweep_status"] = "declared"
        data["last_sweep_at"] = now_sgt()
        data["notes"] = (
            "Commission declared only. This process cannot sign or broadcast USDT. "
            "A human wallet operator must send if and only if treasury figures are real."
        )
        save_treasury(data)
        self._json(
            200,
            {
                "sweep_status": "declared",
                "accrued_commission": data["accrued_commission"],
                "destination": DEPOSIT,
                "broadcast": False,
                "reason": "no_private_keys_control_plane_only",
                "treasury": data,
            },
        )

    def log_message(self, fmt: str, *args) -> None:
        log = ROOT / "server.log"
        line = "%s - %s\n" % (now_sgt(), fmt % args)
        with log.open("a") as fh:
            fh.write(line)


def main() -> None:
    os.chdir(ROOT)
    if not TREASURY_PATH.exists():
        save_treasury(recompute({}))
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"agentic-bazaar listening on http://{HOST}:{PORT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
