from __future__ import annotations

from typing import Any


def run_skill(skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if skill_id == "skill_match":
        goal = str(payload.get("goal", "")).strip() or "unspecified goal"
        return {
            "matches": [
                {"skill_id": "landed_cost", "why": f"Price the whole path for '{goal}'.", "price_usd": 0.20},
                {"skill_id": "listing_pack", "why": "Listing an agent can publish without rewrite.", "price_usd": 0.25},
                {"skill_id": "claim_check", "why": "Strip claims that get ads rejected.", "price_usd": 0.15},
            ]
        }

    if skill_id == "agent_brief":
        goal = str(payload.get("goal", "Launch an agent marketplace"))
        return {
            "brief": {
                "goal": goal,
                "thesis": "Expand supply only where buyer agents already spend.",
                "rails": ["bazaar.credits", "x402.exact", "stable.invoice"],
                "first_week": [
                    "Post demand, don't guess catalog",
                    "Stock the top requested skills",
                    "Keep escrow and the 30% creator cut",
                ],
            }
        }

    if skill_id == "listing_pack":
        product = str(payload.get("product", "wireless earbuds"))
        return {
            "title": f"{product.title()} — Agent-Ready, 24h Dispatch",
            "bullets": [
                f"Structured for {product} comparison, not banner copy",
                "Attributes agents can parse without scraping",
                "Refund window encoded in the skill SLA",
            ],
            "tags": [product.lower(), "agent-ready", "bazaar"],
        }

    if skill_id == "price_watch":
        sku = str(payload.get("sku", "SKU-2048"))
        return {
            "sku": sku,
            "competitors": [
                {"merchant": "northwind", "price_usd": 18.90},
                {"merchant": "contoso", "price_usd": 17.40},
                {"merchant": "adventure", "price_usd": 19.10},
            ],
            "suggested_price_usd": 17.25,
            "rule": "undercut median by 3% without breaking MAP",
        }

    if skill_id == "landed_cost":
        price = float(payload.get("price_usd", 20))
        ship = float(payload.get("ship_usd", 4.5))
        duty = float(payload.get("duty_usd", 1.2))
        fee = round((price + ship) * 0.029 + 0.30, 2)
        total = round(price + ship + duty + fee, 2)
        return {
            "unit_price_usd": price,
            "shipping_usd": ship,
            "duty_usd": duty,
            "rail_fee_usd": fee,
            "landed_usd": total,
            "note": "This is the number a buyer agent should compare, not shelf price.",
        }

    if skill_id == "claim_check":
        text = str(payload.get("text", "Best on the market. Cures fatigue. Free forever."))
        flags = []
        low = text.lower()
        for word, reason in [
            ("best", "superlative — needs proof or drop it"),
            ("cure", "medical claim — reject"),
            ("free forever", "price claim — encode the real term"),
            ("guaranteed", "outcome claim — cap or remove"),
        ]:
            if word in low:
                flags.append({"phrase": word, "reason": reason})
        return {"text": text, "flags": flags, "safe": len(flags) == 0}

    if skill_id == "supplier_brief":
        item = str(payload.get("item", "USB-C cable 1m"))
        return {
            "item": item,
            "moq": 200,
            "lead_days": 12,
            "ex_works_usd": 1.15,
            "notes": ["Ask for UL photo on the same SKU", "Reject mixed-lot cartons"],
        }

    if skill_id == "schema_product":
        name = str(payload.get("name", "Agentic listing"))
        price = float(payload.get("price_usd", 19))
        return {
            "@type": "Product",
            "name": name,
            "offers": {"@type": "Offer", "price": price, "priceCurrency": "USD"},
        }

    if skill_id == "mandate_draft":
        cap = float(payload.get("daily_cap_usd", 25))
        return {
            "daily_cap_usd": cap,
            "per_call_cap_usd": min(5, cap),
            "auto_approve_under_usd": 1.0,
            "allow_rails": ["bazaar.credits", "x402.exact", "stable.invoice"],
            "human_gate": "anything above auto-approve",
        }

    if skill_id == "receipt_audit":
        receipt_id = str(payload.get("receipt_id", ""))
        return {
            "receipt_id": receipt_id or "missing",
            "checks": {
                "has_output_hash": bool(payload.get("output_hash")),
                "has_tx_ref": bool(payload.get("tx_ref")),
                "status_ok": payload.get("status") in {"settled", "released"},
            },
        }

    if skill_id == "refund_risk":
        category = str(payload.get("category", "general"))
        score = 0.22 if category != "fashion" else 0.41
        return {"category": category, "refund_risk": score, "hold_days": 3 if score > 0.3 else 1}

    if skill_id == "translate_listing":
        title = str(payload.get("title", "Agent-ready cable"))
        lang = str(payload.get("lang", "zh"))
        mapped = {"zh": f"{title}（代理可购）", "id": f"{title} siap agen", "en": title}
        return {"lang": lang, "title": mapped.get(lang, title)}

    if skill_id == "inventory_flag":
        on_hand = int(payload.get("on_hand", 12))
        velocity = float(payload.get("sold_per_day", 3))
        days = round(on_hand / max(velocity, 0.01), 1)
        return {"on_hand": on_hand, "days_left": days, "reorder": days < 7}

    if skill_id == "cart_compare":
        carts = payload.get("carts") or [
            {"merchant": "A", "total_usd": 22.1},
            {"merchant": "B", "total_usd": 20.4},
        ]
        winner = min(carts, key=lambda c: float(c["total_usd"]))
        return {"carts": carts, "pick": winner}

    raise ValueError(f"unknown skill {skill_id}")
