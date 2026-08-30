#!/usr/bin/env python3
"""Agentic Bazaar API — multi-rail agent-to-agent commerce."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from bazaar.models import (
    AgentCard,
    Mandate,
    PaymentStatus,
    Quote,
    Rail,
    Receipt,
    Skill,
)
from bazaar.payments import (
    InsufficientFunds,
    Ledger,
    PaymentRouter,
    RailError,
    usd_to_atomic,
)
from bazaar.policy import PolicyDenied, evaluate, reset_if_new_day
from bazaar.assets import CREATOR_COMMISSION_RATE, CREATOR_TRON_USDT, list_assets
from bazaar.payout import run_daily_sweep
from bazaar.tron import account as tron_account, incoming_usdt
from bazaar.skills import run_skill
from bazaar.store import JsonStore

ROOT = Path(__file__).resolve().parent
DATA = Path("/data" if Path("/data").exists() else "/tmp/agentic-bazaar-data")
DATA.mkdir(parents=True, exist_ok=True)
store = JsonStore(DATA / "bazaar.json")
ledger = Ledger(store)
router = PaymentRouter(store, ledger)

app = FastAPI(title="Agentic Bazaar", version="0.1.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["PAYMENT-REQUIRED", "PAYMENT-RESPONSE"],
)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).isoformat()


def sign_receipt(payload: dict) -> str:
    blob = repr(sorted(payload.items())).encode()
    return "bazaar:" + hashlib.sha256(blob).hexdigest()[:32]


def catalog_spec() -> list[Skill]:
    extra_rails = [Rail.CREDITS, Rail.X402, Rail.ESCROW, Rail.STABLE_INVOICE]
    return [
        Skill(skill_id="skill_match", seller_id="seller_atlas", name="Skill Match", description="Rank bazaar skills against a buyer's goal.", price_usd=0.05, tags=["discovery"], input_schema={"goal": "string"}),
        Skill(skill_id="agent_brief", seller_id="seller_atlas", name="Agent Brief", description="One-page execution brief.", price_usd=0.10, tags=["strategy"], input_schema={"goal": "string"}),
        Skill(skill_id="listing_pack", seller_id="seller_north", name="Listing Pack", description="Title, bullets, and tags a listing agent can publish.", price_usd=0.25, tags=["ecommerce", "copy"], input_schema={"product": "string"}),
        Skill(skill_id="price_watch", seller_id="seller_north", name="Price Watch", description="Competitor snapshot and a suggested price.", price_usd=1.50, tags=["pricing"], input_schema={"sku": "string"}, accepted_rails=[Rail.CREDITS, Rail.X402, Rail.STRIPE_SPT, Rail.ESCROW, Rail.STABLE_INVOICE]),
        Skill(skill_id="landed_cost", seller_id="seller_atlas", name="Landed Cost", description="Shelf price plus ship, duty, and rail fees.", price_usd=0.20, tags=["pricing", "demand"], input_schema={"price_usd": "number", "ship_usd": "number", "duty_usd": "number"}, accepted_rails=extra_rails),
        Skill(skill_id="claim_check", seller_id="seller_north", name="Claim Check", description="Flag ad-policy and medical claims before publish.", price_usd=0.15, tags=["compliance", "demand"], input_schema={"text": "string"}, accepted_rails=extra_rails),
        Skill(skill_id="supplier_brief", seller_id="seller_atlas", name="Supplier Brief", description="MOQ, lead time, and EXW for a sourced item.", price_usd=0.35, tags=["sourcing", "demand"], input_schema={"item": "string"}, accepted_rails=extra_rails),
        Skill(skill_id="schema_product", seller_id="seller_north", name="Product Schema", description="Machine-readable Product JSON an agent can ingest.", price_usd=0.12, tags=["data", "demand"], input_schema={"name": "string", "price_usd": "number"}, accepted_rails=extra_rails),
        Skill(skill_id="mandate_draft", seller_id="seller_atlas", name="Mandate Draft", description="Spend policy a human can sign for an agent.", price_usd=0.08, tags=["policy", "demand"], input_schema={"daily_cap_usd": "number"}, accepted_rails=extra_rails),
        Skill(skill_id="receipt_audit", seller_id="seller_atlas", name="Receipt Audit", description="Check hash, tx, and status on a receipt.", price_usd=0.08, tags=["trust", "demand"], input_schema={"receipt_id": "string"}, accepted_rails=extra_rails),
        Skill(skill_id="refund_risk", seller_id="seller_north", name="Refund Risk", description="Hold-days and refund probability by category.", price_usd=0.18, tags=["risk", "demand"], input_schema={"category": "string"}, accepted_rails=extra_rails),
        Skill(skill_id="translate_listing", seller_id="seller_north", name="Translate Listing", description="Listing title into zh / id / en for local agents.", price_usd=0.10, tags=["locale", "demand"], input_schema={"title": "string", "lang": "string"}, accepted_rails=extra_rails),
        Skill(skill_id="inventory_flag", seller_id="seller_north", name="Inventory Flag", description="Days of cover and reorder flag.", price_usd=0.09, tags=["ops", "demand"], input_schema={"on_hand": "number", "sold_per_day": "number"}, accepted_rails=extra_rails),
        Skill(skill_id="cart_compare", seller_id="seller_atlas", name="Cart Compare", description="Pick the cheaper landed cart.", price_usd=0.16, tags=["pricing", "demand"], input_schema={"carts": "array"}, accepted_rails=extra_rails),
    ]


def seed() -> None:
    existing = store.all("skills")
    if not store.get("agents", "seller_north"):
        sellers = {
            "seller_north": ("Northwind Skills", "Maya Chen"),
            "seller_atlas": ("Atlas Research", "Omar Diallo"),
        }
        for sid, (name, operator) in sellers.items():
            store.put(
                "agents",
                sid,
                AgentCard(
                    agent_id=sid,
                    name=name,
                    operator=operator,
                    public_key="pk_" + sid,
                    created_at=iso(),
                    reputation=0.82,
                    completed_jobs=14,
                ).model_dump(),
            )
            if ledger.balance(sid) == 0:
                ledger.credit(sid, 10.0, "seller-seed")
    for skill in catalog_spec():
        row = skill.model_dump()
        prev = store.get("skills", skill.skill_id) or {}
        row["demand"] = int(prev.get("demand") or 0)
        store.put("skills", skill.skill_id, row)


seed()


class RegisterBody(BaseModel):
    name: str
    operator: str = "human"
    daily_cap_usd: float = 25.0
    per_call_cap_usd: float = 5.0
    auto_approve_under_usd: float = 1.00
    starting_credits_usd: float = 5.00


class QuoteBody(BaseModel):
    skill_id: str
    buyer_id: str


class PayBody(BaseModel):
    quote_id: str
    buyer_id: str
    rail: Rail = Rail.CREDITS
    payment_signature: str | None = None
    human_approved: bool = False
    invoice_id: str | None = None


class InvoiceBody(BaseModel):
    quote_id: str
    asset_id: str = "USDT:tron:mainnet"


class ConfirmInvoiceBody(BaseModel):
    tx_hash: str
    observed_atomic: str | None = None


class ApproveBody(BaseModel):
    intent_id: str
    operator: str
    approve: bool = True


class InvokeBody(BaseModel):
    intent_id: str
    input: dict = Field(default_factory=dict)


class DemandBody(BaseModel):
    buyer_id: str | None = None
    need: str
    max_usd: float = 1.0
    tags: list[str] = Field(default_factory=list)


@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/health")
def health():
    return {"ok": True, "service": "agentic-bazaar", "time": iso()}


@app.get("/discovery.json")
def discovery():
    return {
        "name": "Agentic Bazaar",
        "version": "0.1.0",
        "protocols": ["bazaar.v1", "x402.v2", "ap2-mandate"],
        "rails": [r.value for r in Rail],
        "endpoints": {
            "skills": "/v1/skills",
            "register": "/v1/agents",
            "quote": "/v1/quotes",
            "pay": "/v1/pay",
            "invoke": "/v1/invoke",
            "receipts": "/v1/receipts",
            "assets": "/v1/assets",
            "invoices": "/v1/invoices",
        },
        "stables": ["USDC", "USDT"],
    }


@app.get("/.well-known/agent.json")
def agent_card():
    return {
        "name": "Agentic Bazaar",
        "description": "Agent-to-agent skill marketplace with multi-rail settlement.",
        "skills": list(store.all("skills").keys()),
    }


@app.post("/v1/agents")
def register(body: RegisterBody):
    agent_id = "agt_" + secrets.token_hex(4)
    card = AgentCard(
        agent_id=agent_id,
        name=body.name,
        operator=body.operator,
        public_key="pk_" + secrets.token_hex(8),
        created_at=iso(),
    )
    mandate = Mandate(
        mandate_id="man_" + secrets.token_hex(4),
        agent_id=agent_id,
        daily_cap_usd=body.daily_cap_usd,
        per_call_cap_usd=body.per_call_cap_usd,
        auto_approve_under_usd=body.auto_approve_under_usd,
        spent_today_date=now().strftime("%Y-%m-%d"),
    )
    store.put("agents", agent_id, card.model_dump())
    store.put("mandates", agent_id, mandate.model_dump())
    ledger.credit(agent_id, body.starting_credits_usd, "welcome-grant")
    return {
        "agent": card.model_dump(),
        "mandate": mandate.model_dump(),
        "balance_usd": ledger.balance(agent_id),
    }


@app.get("/v1/agents")
def list_agents():
    agents = store.all("agents")
    out = []
    for aid, card in agents.items():
        row = dict(card)
        row["balance_usd"] = ledger.balance(aid)
        row["mandate"] = store.get("mandates", aid)
        out.append(row)
    return {"agents": out}


@app.get("/v1/agents/{agent_id}")
def get_agent(agent_id: str):
    card = store.get("agents", agent_id)
    if not card:
        raise HTTPException(404, "unknown agent")
    return {
        "agent": card,
        "mandate": store.get("mandates", agent_id),
        "balance_usd": ledger.balance(agent_id),
        "ledger": store.get("balances", agent_id),
    }


@app.post("/v1/demand")
def post_demand(body: DemandBody):
    demand_id = "dem_" + secrets.token_hex(4)
    row = {
        "demand_id": demand_id,
        "buyer_id": body.buyer_id,
        "need": body.need,
        "max_usd": body.max_usd,
        "tags": body.tags,
        "created_at": iso(),
    }
    store.put("demands", demand_id, row)
    need = body.need.lower()
    bumped = []
    for sid, skill in store.all("skills").items():
        blob = " ".join([sid, skill.get("name",""), skill.get("description",""), " ".join(skill.get("tags") or [])]).lower()
        if any(tok in blob for tok in need.split() if len(tok) > 3) or any(tag in (skill.get("tags") or []) for tag in body.tags):
            skill["demand"] = int(skill.get("demand") or 0) + 1
            store.put("skills", sid, skill)
            bumped.append(sid)
    ranked = sorted(store.all("skills").values(), key=lambda s: int(s.get("demand") or 0), reverse=True)
    return {"demand": row, "bumped": bumped, "now_top": [s["skill_id"] for s in ranked[:5]]}


@app.get("/v1/demand")
def list_demand():
    rows = list(store.all("demands").values())
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"demands": rows}


@app.get("/v1/skills")
def list_skills():
    rows = list(store.all("skills").values())
    rows.sort(key=lambda s: int(s.get("demand") or 0), reverse=True)
    return {"skills": rows, "ranked_by": "agent_demand"}


@app.get("/v1/skills/{skill_id}")
def get_skill(skill_id: str):
    skill = store.get("skills", skill_id)
    if not skill:
        raise HTTPException(404, "unknown skill")
    return skill


@app.post("/v1/quotes")
def create_quote(body: QuoteBody):
    skill = store.get("skills", body.skill_id)
    buyer = store.get("agents", body.buyer_id)
    if not skill:
        raise HTTPException(404, "unknown skill")
    if not buyer:
        raise HTTPException(404, "unknown buyer")
    quote = Quote(
        quote_id="quo_" + secrets.token_hex(6),
        skill_id=skill["skill_id"],
        buyer_id=body.buyer_id,
        seller_id=skill["seller_id"],
        amount_usd=float(skill["price_usd"]),
        amount_atomic=usd_to_atomic(float(skill["price_usd"])),
        expires_at=iso(now() + timedelta(minutes=10)),
        accepted_rails=[Rail(r) for r in skill["accepted_rails"]],
        escrow_required=True,
    )
    store.put("quotes", quote.quote_id, quote.model_dump())
    skill["demand"] = int(skill.get("demand") or 0) + 1
    store.put("skills", skill["skill_id"], skill)
    challenge = router.build_x402_required(
        quote, resource_url=f"/v1/pay?quote={quote.quote_id}"
    )
    return {
        "quote": quote.model_dump(),
        "x402": challenge["body"],
        "PAYMENT-REQUIRED": challenge["headers"]["PAYMENT-REQUIRED"],
    }


@app.post("/v1/pay")
def pay(body: PayBody):
    raw = store.get("quotes", body.quote_id)
    if not raw:
        raise HTTPException(404, "unknown quote")
    quote = Quote.model_validate(raw)
    if datetime.fromisoformat(quote.expires_at) < now():
        raise HTTPException(410, "quote expired")
    if quote.buyer_id != body.buyer_id:
        raise HTTPException(403, "quote belongs to another buyer")

    mandate_raw = store.get("mandates", body.buyer_id)
    if not mandate_raw:
        raise HTTPException(403, "buyer has no mandate")
    mandate = Mandate.model_validate(mandate_raw)
    mandate = reset_if_new_day(mandate)

    try:
        decision = evaluate(mandate, quote, body.rail)
    except PolicyDenied as exc:
        raise HTTPException(
            403,
            {
                "error": "policy_denied",
                "reason": exc.reason,
                "requires_human": exc.requires_human,
            },
        )

    try:
        intent = router.authorize(
            quote=quote,
            rail=body.rail,
            buyer_id=body.buyer_id,
            payment_signature=body.payment_signature,
            human_approved=body.human_approved,
            requires_human=decision["requires_human"],
            invoice_id=body.invoice_id,
        )
    except InsufficientFunds as exc:
        raise HTTPException(402, {"error": "insufficient_funds", "detail": str(exc)})
    except RailError as exc:
        raise HTTPException(400, {"error": "rail_error", "detail": str(exc)})

    if intent.status != PaymentStatus.REQUIRES_HUMAN:
        mandate.spent_today_usd = round(mandate.spent_today_usd + quote.amount_usd, 6)
        mandate.spent_today_date = now().strftime("%Y-%m-%d")
        store.put("mandates", body.buyer_id, mandate.model_dump())

    settle = router.settlement_response(intent)
    return JSONResponse(
        {
            "intent": intent.model_dump(),
            "policy": decision,
            "balance_usd": ledger.balance(body.buyer_id),
            "x402_settlement": settle["body"],
        },
        headers=settle["headers"],
    )



@app.get("/v1/assets")
def assets():
    return {
        "unit_of_account": "USD",
        "accepted": list_assets(),
        "workaround": {
            "why_usdt_is_an_invoice": "USDT has no EIP-3009 transferWithAuthorization, so native x402 gasless pay fails. Accept TRC-20 / ERC-20 USDT as a watched transfer, then book USD into escrow.",
            "why_usdc_can_be_x402": "USDC implements EIP-3009, so the agent can sign and a facilitator can pull funds without a prior approve tx.",
        },
    }


@app.post("/v1/invoices")
def open_invoice(body: InvoiceBody):
    raw = store.get("quotes", body.quote_id)
    if not raw:
        raise HTTPException(404, "unknown quote")
    quote = Quote.model_validate(raw)
    try:
        invoice = router.open_invoice(quote, body.asset_id)
    except KeyError:
        raise HTTPException(400, f"unknown asset {body.asset_id}")
    except RailError as exc:
        raise HTTPException(400, str(exc))
    return {"invoice": invoice, "instructions": (
        f"Send exactly {invoice['amount_atomic']} atomic {invoice['symbol']} "
        f"on {invoice['chain']} to {invoice['pay_to']} with memo {invoice['memo']}. "
        f"Contract must be {invoice['contract']}."
    )}


@app.post("/v1/invoices/{invoice_id}/confirm")
def confirm_invoice(invoice_id: str, body: ConfirmInvoiceBody):
    try:
        invoice = router.confirm_invoice(invoice_id, body.tx_hash, body.observed_atomic)
    except RailError as exc:
        raise HTTPException(400, str(exc))
    return {"invoice": invoice}


@app.get("/v1/invoices")
def list_invoices():
    rows = list(store.all("invoices").values())
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"invoices": rows}

@app.get("/v1/keepers")
def keepers():
    return {
        "role": "save_keepers",
        "custody": False,
        "keys": False,
        "bots": [
            {"id": "ledger_keeper", "job": "Accept only explicit settled sales and refunds"},
            {"id": "split_keeper", "job": "Lock 30% creator / 70% seller+reserve; skip $0 sweeps"},
            {"id": "chain_keeper", "job": "Read-only watch of TTamF9HU3cYt2fDaTYB4ZUXfvcogBygC7w"},
        ],
        "platform_reserve_policy": "Keepers account. They do not spend. No private keys in this process.",
    }


@app.get("/v1/primer")
def primer():
    return {
        "title": "Agentic Bazaar operator primer",
        "live": "https://agentic-bazaar-production.up.railway.app/",
        "rules": [
            "Commission = 30% of net profit after refunds",
            "Skip sweep at $0.00",
            "No private keys in this process",
            "No live USDT collection against a simulated confirmer",
            "Keepers watch; they do not sign or spend",
        ],
        "shop": ["/v1/skills", "/v1/quotes", "/v1/pay", "/v1/invoke", "/docs"],
        "treasury": ["/v1/treasury", "/v1/payments", "/v1/keepers", "/v1/payouts/sweep"],
    }


@app.get("/v1/payments")
def payments_state():
    accrued = ledger.balance("creator_desk")
    return {
        "payment_state": "ready_idle" if accrued <= 0 else "accrued",
        "accrued_commission": accrued,
        "commission_rate": CREATOR_COMMISSION_RATE,
        "deposit_address": CREATOR_TRON_USDT,
        "broadcast": False,
        "note": "Zero volume is a valid live state. Sweep will skip.",
    }


@app.get("/v1/treasury")
def treasury():
    live = tron_account(CREATOR_TRON_USDT)
    incoming = incoming_usdt(CREATOR_TRON_USDT, limit=10)
    return {
        "creator_wallet": CREATOR_TRON_USDT,
        "network": "TRON",
        "asset": "USDT",
        "contract": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
        "commission_rate": 0.30,
        "onchain": live,
        "incoming_usdt": incoming,
        "local_creator_balance_usd": ledger.balance("creator_desk"),
        "payouts": list(store.all("payouts").values()),
        "truth": "Only incoming_usdt rows from TronGrid count as real deposits.",
    }


@app.get("/v1/ceo")
def ceo_desk():
    payouts = list(store.all("payouts").values())
    payouts.sort(key=lambda r: r.get("day", ""), reverse=True)
    return {
        "role": "CEO",
        "charter": "30% of net profits to TTamF9HU3cYt2fDaTYB4ZUXfvcogBygC7w at 09:45 Asia/Singapore",
        "commission_rate": CREATOR_COMMISSION_RATE,
        "wallet": CREATOR_TRON_USDT,
        "accrued_usd": ledger.balance("creator_desk"),
        "payouts": payouts[:14],
        "ethics": [
            "no fake on-chain deposits",
            "no private keys in the bazaar",
            "skip the sweep when accrued is zero",
        ],
    }


@app.post("/v1/payouts/sweep")
def sweep_creator(force: bool = False):
    return run_daily_sweep(store, ledger, force=force)


@app.get("/v1/payouts")
def list_payouts():
    rows = list(store.all("payouts").values())
    rows.sort(key=lambda r: r.get("day", ""), reverse=True)
    return {"payouts": rows}


@app.get("/v1/x402/challenge/{quote_id}")
def x402_challenge(quote_id: str):
    raw = store.get("quotes", quote_id)
    if not raw:
        raise HTTPException(404, "unknown quote")
    quote = Quote.model_validate(raw)
    challenge = router.build_x402_required(quote, f"/v1/pay?quote={quote_id}")
    return JSONResponse(challenge["body"], status_code=402, headers=challenge["headers"])


@app.post("/v1/x402/sign")
def x402_sign(quote_id: str, buyer_id: str):
    """Dev helper: mint a simulated PAYMENT-SIGNATURE bound to a quote.

    Production agents sign with their own wallet. This endpoint exists so the
    sandbox can demonstrate the exact header handshake.
    """
    raw = store.get("quotes", quote_id)
    if not raw:
        raise HTTPException(404, "unknown quote")
    quote = Quote.model_validate(raw)
    sig = router.simulate_x402_signature(quote, payer=buyer_id)
    return {"PAYMENT-SIGNATURE": sig, "rail": Rail.X402.value}


@app.post("/v1/approvals")
def approve(body: ApproveBody):
    raw = store.get("intents", body.intent_id)
    if not raw:
        raise HTTPException(404, "unknown intent")
    if raw["status"] != PaymentStatus.REQUIRES_HUMAN.value:
        raise HTTPException(409, "intent is not waiting for a human")

    quote = Quote.model_validate(store.get("quotes", raw["quote_id"]))
    if not body.approve:
        raw["status"] = PaymentStatus.FAILED.value
        raw["human_reason"] = f"denied by {body.operator}"
        store.put("intents", body.intent_id, raw)
        return {"intent": raw}

    try:
        pending = (raw.get("x402") or {}).get("pending_invoice_id")
        intent = router.authorize(
            quote=quote,
            rail=Rail(raw["rail"]),
            buyer_id=raw["buyer_id"],
            human_approved=True,
            requires_human=False,
            invoice_id=pending,
        )
    except InsufficientFunds as exc:
        raise HTTPException(402, str(exc))

    mandate = Mandate.model_validate(store.get("mandates", raw["buyer_id"]))
    mandate = reset_if_new_day(mandate)
    mandate.spent_today_usd = round(mandate.spent_today_usd + quote.amount_usd, 6)
    store.put("mandates", raw["buyer_id"], mandate.model_dump())
    store.put("approvals", body.intent_id, {"operator": body.operator, "at": iso()})
    return {"intent": intent.model_dump(), "balance_usd": ledger.balance(raw["buyer_id"])}


@app.post("/v1/invoke")
def invoke(body: InvokeBody, payment_signature: str | None = Header(default=None)):
    raw = store.get("intents", body.intent_id)
    if not raw:
        raise HTTPException(404, "unknown intent")
    if raw["status"] not in {PaymentStatus.HELD.value, PaymentStatus.AUTHORIZED.value}:
        raise HTTPException(402, f"intent not paid (status={raw['status']})")

    from bazaar.models import PaymentIntent, Job

    intent = PaymentIntent.model_validate(raw)
    job_id = "job_" + secrets.token_hex(6)
    job = Job(
        job_id=job_id,
        intent_id=intent.intent_id,
        skill_id=intent.skill_id,
        buyer_id=intent.buyer_id,
        input=body.input,
        created_at=iso(),
    )
    try:
        output = run_skill(intent.skill_id, body.input)
        job.output = output
        job.status = "done"
        job.finished_at = iso()
        intent = router.release_to_seller(intent, ok=True)
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.finished_at = iso()
        intent = router.release_to_seller(intent, ok=False)

    store.put("jobs", job_id, job.model_dump())

    output_hash = None
    if job.output:
        output_hash = hashlib.sha256(repr(job.output).encode()).hexdigest()

    receipt = Receipt(
        receipt_id="rcpt_" + secrets.token_hex(6),
        intent_id=intent.intent_id,
        quote_id=intent.quote_id,
        skill_id=intent.skill_id,
        buyer_id=intent.buyer_id,
        seller_id=intent.seller_id,
        rail=intent.rail,
        amount_usd=intent.amount_usd,
        status=intent.status,
        output_hash=output_hash,
        tx_ref=intent.tx_ref,
        issued_at=iso(),
        signature="",
    )
    receipt.signature = sign_receipt(receipt.model_dump())
    store.put("receipts", receipt.receipt_id, receipt.model_dump())

    agent = store.get("agents", intent.seller_id)
    if agent and job.status == "done":
        agent["completed_jobs"] = int(agent.get("completed_jobs", 0)) + 1
        store.put("agents", intent.seller_id, agent)

    return {
        "job": job.model_dump(),
        "intent": intent.model_dump(),
        "receipt": receipt.model_dump(),
        "buyer_balance_usd": ledger.balance(intent.buyer_id),
        "seller_balance_usd": ledger.balance(intent.seller_id),
    }


@app.get("/v1/receipts")
def list_receipts(agent_id: str | None = None):
    rows = list(store.all("receipts").values())
    if agent_id:
        rows = [r for r in rows if r["buyer_id"] == agent_id or r["seller_id"] == agent_id]
    rows.sort(key=lambda r: r["issued_at"], reverse=True)
    return {"receipts": rows}


@app.get("/v1/intents")
def list_intents():
    rows = list(store.all("intents").values())
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return {"intents": rows}


@app.get("/v1/jobs")
def list_jobs():
    rows = list(store.all("jobs").values())
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return {"jobs": rows}


@app.get("/v1/ledger")
def public_ledger():
    return {"accounts": store.all("balances")}


@app.exception_handler(HTTPException)
async def http_exc(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(detail, status_code=exc.status_code)
    return JSONResponse({"error": detail}, status_code=exc.status_code)
