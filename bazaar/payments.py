"""Multi-rail payment adapters.

Live money never moves in this sandbox. Each adapter implements the *wire
shape* of a real 2026 rail so a production facilitator / Stripe / Link
client can be swapped in without changing the bazaar API.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Any

from .assets import CREATOR_AGENT_ID, CREATOR_COMMISSION_RATE, CREATOR_TRON_USDT, get_asset, x402_accepts
from .tron import verify_usdt_payment
from .models import PaymentIntent, PaymentStatus, Quote, Rail
from .store import JsonStore

USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
BAZAAR_TREASURY = "0xBazaar0000000000000000000000000000000Escrow"
X402_NETWORK = "eip155:84532"  # Base Sepolia — swap to 8453 in production


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def usd_to_atomic(usd: float, decimals: int = 6) -> str:
    return str(int(round(usd * (10**decimals))))


def b64json(obj: dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(obj, separators=(",", ":")).encode()).decode()


def decode_b64json(value: str) -> dict[str, Any]:
    return json.loads(base64.b64decode(value.encode()))


class InsufficientFunds(Exception):
    pass


class RailError(Exception):
    pass


class Ledger:
    """Internal credit ledger used as the demo cash account and as escrow."""

    def __init__(self, store: JsonStore):
        self.store = store

    def balance(self, agent_id: str) -> float:
        raw = self.store.get("balances", agent_id)
        if raw is None:
            return 0.0
        return float(raw.get("usd", 0.0))

    def credit(self, agent_id: str, usd: float, reason: str) -> float:
        def mut(current):
            current = current or {"usd": 0.0, "history": []}
            current["usd"] = round(float(current["usd"]) + usd, 6)
            current["history"].append(
                {"ts": now_iso(), "delta": usd, "reason": reason}
            )
            return current

        updated = self.store.update("balances", agent_id, mut)
        return float(updated["usd"])

    def debit(self, agent_id: str, usd: float, reason: str) -> float:
        def mut(current):
            current = current or {"usd": 0.0, "history": []}
            if float(current["usd"]) + 1e-9 < usd:
                raise InsufficientFunds(
                    f"{agent_id} has ${current['usd']:.4f}, needs ${usd:.4f}"
                )
            current["usd"] = round(float(current["usd"]) - usd, 6)
            current["history"].append(
                {"ts": now_iso(), "delta": -usd, "reason": reason}
            )
            return current

        updated = self.store.update("balances", agent_id, mut)
        return float(updated["usd"])


class PaymentRouter:
    def __init__(self, store: JsonStore, ledger: Ledger):
        self.store = store
        self.ledger = ledger

    def build_x402_required(self, quote: Quote, resource_url: str) -> dict[str, Any]:
        required = {
            "x402Version": 2,
            "error": "PAYMENT-SIGNATURE header is required",
            "resource": {
                "url": resource_url,
                "description": f"Invoke skill {quote.skill_id}",
                "mimeType": "application/json",
                "serviceName": "Agentic Bazaar",
                "tags": ["bazaar", "skill", quote.skill_id],
            },
            "accepts": x402_accepts(quote.amount_usd, quote.quote_id),
            "extensions": {
                "bazaarQuoteId": quote.quote_id,
                "invoiceRail": "stable.invoice",
                "note": "USDT-TRC20 is accepted as an invoice, not as native x402 EIP-3009",
            },
        }
        return {
            "status": 402,
            "headers": {"PAYMENT-REQUIRED": b64json(required)},
            "body": required,
        }

    def simulate_x402_signature(self, quote: Quote, payer: str) -> str:
        """Stand-in for an EIP-712 / facilitator-signed PAYMENT-SIGNATURE.

        Production swap: sign with the agent's wallet via @x402/evm or a
        Coinbase/Stripe facilitator. The header shape stays identical.
        """
        payload = {
            "x402Version": 2,
            "resource": {
                "url": f"/v1/invoke?quote={quote.quote_id}",
                "description": f"Invoke skill {quote.skill_id}",
                "mimeType": "application/json",
            },
            "accepted": {
                "scheme": "exact",
                "network": X402_NETWORK,
                "amount": quote.amount_atomic,
                "asset": USDC_BASE_SEPOLIA,
                "payTo": BAZAAR_TREASURY,
                "maxTimeoutSeconds": 60,
                "extra": {"name": "USDC", "version": "2", "quoteId": quote.quote_id},
            },
            "payload": {
                "payer": payer,
                "nonce": secrets.token_hex(16),
                "issuedAt": now_iso(),
                "mode": "facilitator-simulated",
            },
        }
        return b64json(payload)

    def verify_x402_signature(self, header: str, quote: Quote) -> dict[str, Any]:
        try:
            payload = decode_b64json(header)
        except Exception as exc:
            raise RailError(f"malformed PAYMENT-SIGNATURE: {exc}") from exc
        accepted = payload.get("accepted") or {}
        if accepted.get("amount") != quote.amount_atomic:
            raise RailError("signed amount does not match quote")
        if accepted.get("extra", {}).get("quoteId") != quote.quote_id:
            raise RailError("signature is not bound to this quote")
        return payload

    def authorize(
        self,
        quote: Quote,
        rail: Rail,
        buyer_id: str,
        payment_signature: str | None = None,
        human_approved: bool = False,
        requires_human: bool = False,
        invoice_id: str | None = None,
    ) -> PaymentIntent:
        intent_id = "pi_" + secrets.token_hex(8)
        intent = PaymentIntent(
            intent_id=intent_id,
            quote_id=quote.quote_id,
            rail=rail,
            status=PaymentStatus.AUTHORIZED,
            amount_usd=quote.amount_usd,
            buyer_id=buyer_id,
            seller_id=quote.seller_id,
            skill_id=quote.skill_id,
            requires_human=requires_human and not human_approved,
            created_at=now_iso(),
        )

        if intent.requires_human:
            intent.status = PaymentStatus.REQUIRES_HUMAN
            intent.human_reason = (
                "Amount exceeds auto-approve threshold. Operator must approve."
            )
            if invoice_id:
                intent.x402 = {"pending_invoice_id": invoice_id}
            self.store.put("intents", intent_id, intent.model_dump())
            return intent

        if rail == Rail.CREDITS:
            self.ledger.debit(buyer_id, quote.amount_usd, f"hold:{intent_id}")
            self.ledger.credit("escrow", quote.amount_usd, f"hold:{intent_id}")
            intent.status = PaymentStatus.HELD
            intent.tx_ref = f"credits:{intent_id}"

        elif rail == Rail.X402:
            if not payment_signature:
                raise RailError("PAYMENT-SIGNATURE required for x402.exact")
            verified = self.verify_x402_signature(payment_signature, quote)
            # Simulated facilitator settlement. Production: POST to facilitator /settle.
            self.ledger.debit(buyer_id, quote.amount_usd, f"x402:{intent_id}")
            self.ledger.credit("escrow", quote.amount_usd, f"x402:{intent_id}")
            tx = "0x" + hashlib.sha256(payment_signature.encode()).hexdigest()
            intent.status = PaymentStatus.HELD
            intent.tx_ref = tx
            intent.x402 = {
                "network": X402_NETWORK,
                "asset": USDC_BASE_SEPOLIA,
                "amount_atomic": quote.amount_atomic,
                "payer": verified.get("payload", {}).get("payer", buyer_id),
                "transaction": tx,
                "mode": "facilitator-simulated",
            }

        elif rail == Rail.STRIPE_SPT:
            # Stripe Link / Shared Payment Token shape. Production: create a
            # spend request, wait for biometric approval, receive SPT.
            token = "spt_" + secrets.token_hex(12)
            self.ledger.debit(buyer_id, quote.amount_usd, f"spt:{intent_id}")
            self.ledger.credit("escrow", quote.amount_usd, f"spt:{intent_id}")
            intent.status = PaymentStatus.HELD
            intent.tx_ref = token
            intent.stripe = {
                "shared_payment_token": token,
                "scoped_amount_usd": quote.amount_usd,
                "merchant": "agentic_bazaar",
                "single_use": True,
                "mode": "link-wallet-simulated",
            }

        elif rail == Rail.ESCROW:
            self.ledger.debit(buyer_id, quote.amount_usd, f"escrow:{intent_id}")
            self.ledger.credit("escrow", quote.amount_usd, f"escrow:{intent_id}")
            intent.status = PaymentStatus.HELD
            intent.tx_ref = f"escrow:{intent_id}"

        elif rail == Rail.STABLE_INVOICE:
            if not invoice_id:
                raise RailError("invoice_id required for stable.invoice")
            invoice = self.store.get("invoices", invoice_id)
            if not invoice:
                raise RailError("unknown invoice")
            if invoice["status"] != "confirmed":
                raise RailError("invoice is still awaiting an on-chain transfer")
            if invoice["quote_id"] != quote.quote_id:
                raise RailError("invoice is bound to a different quote")
            # Treasury already received USDC/USDT. Do not debit buyer credits.
            self.ledger.credit("escrow", quote.amount_usd, f"onchain:{invoice_id}")
            intent.status = PaymentStatus.HELD
            intent.tx_ref = invoice["tx_hash"]
            intent.x402 = {
                "mode": "stable-invoice",
                "asset_id": invoice["asset_id"],
                "symbol": invoice["symbol"],
                "network": invoice["network"],
                "contract": invoice["contract"],
                "pay_to": invoice["pay_to"],
                "memo": invoice["memo"],
                "tx_hash": invoice["tx_hash"],
                "amount_atomic": invoice["amount_atomic"],
            }

        else:
            raise RailError(f"unknown rail {rail}")

        self.store.put("intents", intent_id, intent.model_dump())
        return intent

    def release_to_seller(self, intent: PaymentIntent, ok: bool) -> PaymentIntent:
        if intent.status not in {PaymentStatus.HELD, PaymentStatus.AUTHORIZED}:
            raise RailError(f"cannot release intent in status {intent.status}")

        if ok:
            self.ledger.debit("escrow", intent.amount_usd, f"release:{intent.intent_id}")
            commission = round(intent.amount_usd * CREATOR_COMMISSION_RATE, 6)
            seller_net = round(intent.amount_usd - commission, 6)
            self.ledger.credit(
                intent.seller_id, seller_net, f"sale_net:{intent.intent_id}"
            )
            self.ledger.credit(
                CREATOR_AGENT_ID, commission, f"creator_commission:{intent.intent_id}"
            )
            intent.status = PaymentStatus.SETTLED
            extra = intent.x402 or {}
            extra.update(
                {
                    "creator_wallet_tron_usdt": CREATOR_TRON_USDT,
                    "creator_commission_usd": commission,
                    "seller_net_usd": seller_net,
                    "commission_rate": CREATOR_COMMISSION_RATE,
                }
            )
            intent.x402 = extra
        else:
            self.ledger.debit("escrow", intent.amount_usd, f"refund:{intent.intent_id}")
            self.ledger.credit(
                intent.buyer_id, intent.amount_usd, f"refund:{intent.intent_id}"
            )
            intent.status = PaymentStatus.REFUNDED

        intent.settled_at = now_iso()
        self.store.put("intents", intent.intent_id, intent.model_dump())
        return intent

    def settlement_response(self, intent: PaymentIntent) -> dict[str, Any]:
        body = {
            "success": intent.status
            in {PaymentStatus.HELD, PaymentStatus.SETTLED, PaymentStatus.RELEASED},
            "transaction": intent.tx_ref or "",
            "network": X402_NETWORK if intent.rail == Rail.X402 else "bazaar:ledger",
            "payer": intent.buyer_id,
            "requirements": {
                "scheme": intent.rail.value,
                "amount_usd": intent.amount_usd,
                "quoteId": intent.quote_id,
            },
        }
        return {
            "headers": {"PAYMENT-RESPONSE": b64json(body)},
            "body": body,
        }

    def open_invoice(self, quote: Quote, asset_id: str) -> dict:
        spec = get_asset(asset_id)
        if not spec.get("invoice"):
            raise RailError(f"{asset_id} is not accepted as an invoice")
        from .assets import atomic
        invoice_id = "inv_" + secrets.token_hex(6)
        memo = "BZR-" + quote.quote_id[-8:].upper()
        invoice = {
            "invoice_id": invoice_id,
            "quote_id": quote.quote_id,
            "buyer_id": quote.buyer_id,
            "seller_id": quote.seller_id,
            "skill_id": quote.skill_id,
            "amount_usd": quote.amount_usd,
            "amount_atomic": atomic(quote.amount_usd, spec["decimals"]),
            "asset_id": asset_id,
            "symbol": spec["symbol"],
            "network": spec["network"],
            "chain": spec["chain"],
            "contract": spec["asset"],
            "pay_to": spec["pay_to"],
            "memo": memo,
            "transfer": spec["transfer"],
            "status": "awaiting_tx",
            "tx_hash": None,
            "created_at": now_iso(),
        }
        self.store.put("invoices", invoice_id, invoice)
        return invoice

    def confirm_invoice(self, invoice_id: str, tx_hash: str, observed_atomic: str | None = None) -> dict:
        invoice = self.store.get("invoices", invoice_id)
        if not invoice:
            raise RailError("unknown invoice")
        if invoice["status"] == "confirmed":
            return invoice
        if not tx_hash or len(tx_hash) < 8:
            raise RailError("tx_hash looks empty")
        if invoice.get("asset_id") == "USDT:tron:mainnet":
            live = verify_usdt_payment(
                invoice["pay_to"], tx_hash, invoice["amount_atomic"]
            )
            if not live.get("ok"):
                raise RailError(f"tron live verify failed: {live.get('reason')}")
            invoice["mode"] = "trongrid-live"
            invoice["live"] = live["transfer"]
        else:
            if observed_atomic and observed_atomic != invoice["amount_atomic"]:
                raise RailError(
                    f"on-chain amount {observed_atomic} != invoice {invoice['amount_atomic']}"
                )
            invoice["mode"] = "indexer-simulated"
        invoice["status"] = "confirmed"
        invoice["tx_hash"] = tx_hash
        invoice["confirmed_at"] = now_iso()
        self.store.put("invoices", invoice_id, invoice)
        return invoice

