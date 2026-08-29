from __future__ import annotations

from datetime import datetime, timezone

from .models import Mandate, MandateStatus, Quote, Rail


class PolicyDenied(Exception):
    def __init__(self, reason: str, requires_human: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.requires_human = requires_human


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def reset_if_new_day(mandate: Mandate) -> Mandate:
    today = utc_today()
    if mandate.spent_today_date != today:
        mandate.spent_today_date = today
        mandate.spent_today_usd = 0.0
    return mandate


def evaluate(mandate: Mandate, quote: Quote, rail: Rail) -> dict:
    """Return a policy decision. Never silently spends."""
    mandate = reset_if_new_day(mandate)

    if mandate.status != MandateStatus.ACTIVE:
        raise PolicyDenied(f"mandate is {mandate.status.value}")

    if quote.buyer_id != mandate.agent_id:
        raise PolicyDenied("mandate agent does not match buyer")

    if rail not in mandate.allow_rails:
        raise PolicyDenied(f"rail {rail.value} is not allowed by mandate")

    if rail not in quote.accepted_rails:
        raise PolicyDenied(f"seller does not accept rail {rail.value}")

    if mandate.seller_allowlist and quote.seller_id not in mandate.seller_allowlist:
        raise PolicyDenied(f"seller {quote.seller_id} is not on allowlist")

    if quote.seller_id in mandate.seller_blocklist:
        raise PolicyDenied(f"seller {quote.seller_id} is blocked")

    if mandate.skill_allowlist and quote.skill_id not in mandate.skill_allowlist:
        raise PolicyDenied(f"skill {quote.skill_id} is not on allowlist")

    if quote.amount_usd > mandate.per_call_cap_usd:
        raise PolicyDenied(
            f"quote ${quote.amount_usd:.2f} exceeds per-call cap ${mandate.per_call_cap_usd:.2f}",
            requires_human=True,
        )

    remaining = mandate.daily_cap_usd - mandate.spent_today_usd
    if quote.amount_usd > remaining:
        raise PolicyDenied(
            f"quote ${quote.amount_usd:.2f} exceeds remaining daily cap ${remaining:.2f}",
            requires_human=True,
        )

    requires_human = quote.amount_usd > mandate.auto_approve_under_usd
    return {
        "ok": True,
        "requires_human": requires_human,
        "reason": (
            f"${quote.amount_usd:.2f} exceeds auto-approve threshold "
            f"${mandate.auto_approve_under_usd:.2f}"
            if requires_human
            else "within auto-approve threshold"
        ),
        "remaining_daily_usd": round(remaining, 4),
    }
