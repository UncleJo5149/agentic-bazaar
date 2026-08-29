"""Official USDC / USDT contracts the bazaar will accept.

Ticker is a label. The contract is the asset. Never credit a lookalike.
"""

from __future__ import annotations

from typing import Any

# Creator desk — Bitget Wallet TRON USDT receive address provided by operator.
CREATOR_AGENT_ID = "creator_desk"
CREATOR_TRON_USDT = "TTamF9HU3cYt2fDaTYB4ZUXfvcogBygC7w"
CREATOR_COMMISSION_RATE = 0.30  # 30% of net settled revenue

# Issuer-published mainnet addresses. Amounts are 6 decimals except BNB USDT (18).
ASSETS: dict[str, dict[str, Any]] = {
    "USDC:eip155:8453": {
        "symbol": "USDC",
        "network": "eip155:8453",
        "chain": "Base",
        "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "decimals": 6,
        "transfer": "eip3009",
        "x402": True,
        "invoice": True,
        "pay_to": "0xBazaarUSDC00000000000000000000000Base",
    },
    "USDC:eip155:1": {
        "symbol": "USDC",
        "network": "eip155:1",
        "chain": "Ethereum",
        "asset": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "decimals": 6,
        "transfer": "eip3009",
        "x402": True,
        "invoice": True,
        "pay_to": "0xBazaarUSDC000000000000000000000000Eth",
    },
    "USDC:solana:mainnet": {
        "symbol": "USDC",
        "network": "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",
        "chain": "Solana",
        "asset": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "decimals": 6,
        "transfer": "spl",
        "x402": True,
        "invoice": True,
        "pay_to": "BazaarUSDCSo1anaTreasury111111111111111",
    },
    "USDT:eip155:1": {
        "symbol": "USDT",
        "network": "eip155:1",
        "chain": "Ethereum",
        "asset": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "decimals": 6,
        "transfer": "permit2",  # USDT has no EIP-3009
        "x402": True,
        "invoice": True,
        "pay_to": "0xBazaarUSDT000000000000000000000000Eth",
    },
    "USDT:eip155:56": {
        "symbol": "USDT",
        "network": "eip155:56",
        "chain": "BNB Chain",
        "asset": "0x55d398326f99059fF775485246999027B3197955",
        "decimals": 18,
        "transfer": "permit2",
        "x402": True,
        "invoice": True,
        "pay_to": "0xBazaarUSDT00000000000000000000000BSC",
    },
    "USDT:tron:mainnet": {
        "symbol": "USDT",
        "network": "tron:mainnet",
        "chain": "Tron",
        "asset": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
        "decimals": 6,
        "transfer": "trc20",
        "x402": False,  # not HTTP-402 native; this is the invoice workaround
        "invoice": True,
        "pay_to": "TTamF9HU3cYt2fDaTYB4ZUXfvcogBygC7w",
    },
    "USDT:solana:mainnet": {
        "symbol": "USDT",
        "network": "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",
        "chain": "Solana",
        "asset": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
        "decimals": 6,
        "transfer": "spl",
        "x402": True,
        "invoice": True,
        "pay_to": "BazaarUSDTSo1anaTreasury111111111111111",
    },
}


def list_assets() -> list[dict[str, Any]]:
    out = []
    for key, row in ASSETS.items():
        item = {"id": key, **row}
        out.append(item)
    return out


def get_asset(asset_id: str) -> dict[str, Any]:
    if asset_id not in ASSETS:
        raise KeyError(asset_id)
    return {"id": asset_id, **ASSETS[asset_id]}


def atomic(usd: float, decimals: int) -> str:
    return str(int(round(usd * (10**decimals))))


def x402_accepts(usd: float, quote_id: str) -> list[dict[str, Any]]:
    rows = []
    for key, spec in ASSETS.items():
        if not spec["x402"]:
            continue
        rows.append(
            {
                "scheme": "exact",
                "network": spec["network"],
                "amount": atomic(usd, spec["decimals"]),
                "asset": spec["asset"],
                "payTo": spec["pay_to"],
                "maxTimeoutSeconds": 120,
                "extra": {
                    "name": spec["symbol"],
                    "transfer": spec["transfer"],
                    "quoteId": quote_id,
                    "chain": spec["chain"],
                    "assetId": key,
                },
            }
        )
    return rows
