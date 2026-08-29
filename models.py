from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Rail(str, Enum):
    CREDITS = "bazaar.credits"
    X402 = "x402.exact"
    STRIPE_SPT = "stripe.spt"
    ESCROW = "bazaar.escrow"
    STABLE_INVOICE = "stable.invoice"


class MandateStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class PaymentStatus(str, Enum):
    QUOTED = "quoted"
    AUTHORIZED = "authorized"
    HELD = "held"
    SETTLED = "settled"
    RELEASED = "released"
    REFUNDED = "refunded"
    FAILED = "failed"
    REQUIRES_HUMAN = "requires_human"


class AgentCard(BaseModel):
    agent_id: str
    name: str
    operator: str
    public_key: str
    created_at: str
    reputation: float = 0.5
    completed_jobs: int = 0


class Mandate(BaseModel):
    """AP2-style spend authority granted by a human operator to an agent."""

    mandate_id: str
    agent_id: str
    status: MandateStatus = MandateStatus.ACTIVE
    daily_cap_usd: float = 25.0
    per_call_cap_usd: float = 5.0
    auto_approve_under_usd: float = 1.00
    allow_rails: list[Rail] = Field(
        default_factory=lambda: [Rail.CREDITS, Rail.X402, Rail.STRIPE_SPT, Rail.ESCROW, Rail.STABLE_INVOICE]
    )
    seller_allowlist: list[str] = Field(default_factory=list)
    seller_blocklist: list[str] = Field(default_factory=list)
    skill_allowlist: list[str] = Field(default_factory=list)
    spent_today_usd: float = 0.0
    spent_today_date: str = ""


class Skill(BaseModel):
    skill_id: str
    seller_id: str
    name: str
    description: str
    price_usd: float
    sla_seconds: int = 8
    refund_if_fail: bool = True
    tags: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    accepted_rails: list[Rail] = Field(
        default_factory=lambda: [Rail.CREDITS, Rail.X402, Rail.ESCROW, Rail.STABLE_INVOICE]
    )


class Quote(BaseModel):
    quote_id: str
    skill_id: str
    buyer_id: str
    seller_id: str
    amount_usd: float
    amount_atomic: str
    currency: str = "USD"
    expires_at: str
    accepted_rails: list[Rail]
    escrow_required: bool = False


class PaymentIntent(BaseModel):
    intent_id: str
    quote_id: str
    rail: Rail
    status: PaymentStatus
    amount_usd: float
    buyer_id: str
    seller_id: str
    skill_id: str
    requires_human: bool = False
    human_reason: Optional[str] = None
    x402: Optional[dict[str, Any]] = None
    stripe: Optional[dict[str, Any]] = None
    tx_ref: Optional[str] = None
    created_at: str
    settled_at: Optional[str] = None


class Receipt(BaseModel):
    receipt_id: str
    intent_id: str
    quote_id: str
    skill_id: str
    buyer_id: str
    seller_id: str
    rail: Rail
    amount_usd: float
    status: PaymentStatus
    output_hash: Optional[str] = None
    tx_ref: Optional[str] = None
    issued_at: str
    signature: str


class Job(BaseModel):
    job_id: str
    intent_id: str
    skill_id: str
    buyer_id: str
    input: dict[str, Any]
    output: Optional[dict[str, Any]] = None
    status: str = "queued"
    error: Optional[str] = None
    created_at: str
    finished_at: Optional[str] = None
