"""Daily creator commission sweep — 09:45 Asia/Singapore."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .assets import CREATOR_AGENT_ID, CREATOR_COMMISSION_RATE, CREATOR_TRON_USDT

PAYOUT_TZ = ZoneInfo("Asia/Singapore")
PAYOUT_HOUR = 9
PAYOUT_MINUTE = 45


def singapore_now() -> datetime:
    return datetime.now(PAYOUT_TZ)


def is_payout_window(now: datetime | None = None, slack_minutes: int = 20) -> bool:
    now = now or singapore_now()
    target = now.replace(hour=PAYOUT_HOUR, minute=PAYOUT_MINUTE, second=0, microsecond=0)
    delta = abs((now - target).total_seconds())
    return delta <= slack_minutes * 60


def already_swept_today(store, day: str) -> dict[str, Any] | None:
    for row in store.all("payouts").values():
        if row.get("day") == day and row.get("status") in {"swept", "skipped_no_sales"}:
            return row
    return None


def run_daily_sweep(store, ledger, *, force: bool = False) -> dict[str, Any]:
    now = singapore_now()
    day = now.date().isoformat()
    prior = already_swept_today(store, day)
    if prior and not force:
        return {"ok": True, "idempotent": True, "payout": prior}

    accrued = round(float(ledger.balance(CREATOR_AGENT_ID)), 6)
    payout_id = f"pay_{day.replace('-', '')}"

    if accrued <= 0:
        row = {
            "payout_id": payout_id,
            "day": day,
            "status": "skipped_no_sales",
            "amount_usd": 0.0,
            "wallet": CREATOR_TRON_USDT,
            "network": "tron:mainnet",
            "asset": "USDT",
            "contract": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
            "commission_rate": CREATOR_COMMISSION_RATE,
            "declared_at": now.isoformat(),
            "note": "No accrued creator commission. No deposit.",
        }
        store.put("payouts", payout_id, row)
        return {"ok": True, "payout": row}

    ledger.debit(CREATOR_AGENT_ID, accrued, f"daily_sweep:{day}")
    row = {
        "payout_id": payout_id,
        "day": day,
        "status": "declared",
        "amount_usd": accrued,
        "wallet": CREATOR_TRON_USDT,
        "network": "tron:mainnet",
        "asset": "USDT",
        "contract": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
        "commission_rate": CREATOR_COMMISSION_RATE,
        "declared_at": now.isoformat(),
        "onchain": "pending_real_usdt",
        "note": (
            "30% net booked for deposit to the founder Tron address. "
            "On-chain send requires a funded treasury signer; this record is the instruction."
        ),
    }
    store.put("payouts", payout_id, row)
    return {"ok": True, "payout": row}
