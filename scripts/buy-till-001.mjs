#!/usr/bin/env node
/**
 * First-sale client for Agent Till listing till-001.
 *
 * Does NOT invent a wallet. Reads EVM_PRIVATE_KEY from the environment.
 * Spends 0.05 USDC on Base if the live till is on eip155:8453.
 *
 *   EVM_PRIVATE_KEY=0x... node scripts/buy-till-001.mjs
 *
 * Optional:
 *   TILL_URL=https://web-production-42edc.up.railway.app
 *   MAX_USD=0.05
 */
import { wrapFetchWithPaymentFromConfig } from "@x402/fetch";
import { ExactEvmScheme } from "@x402/evm";
import { privateKeyToAccount } from "viem/accounts";

const TILL_URL = (process.env.TILL_URL || "https://web-production-42edc.up.railway.app").replace(/\/$/, "");
const key = process.env.EVM_PRIVATE_KEY;

if (!key || !/^0x[0-9a-fA-F]{64}$/.test(key)) {
  console.error("Set EVM_PRIVATE_KEY to a 0x + 64 hex private key. Do not paste it into GitHub or Railway.");
  process.exit(1);
}

const account = privateKeyToAccount(key);
const fetchWithPayment = wrapFetchWithPaymentFromConfig(fetch, {
  schemes: [
    { network: "eip155:8453", client: new ExactEvmScheme(account) },
    { network: "eip155:84532", client: new ExactEvmScheme(account) }
  ]
});

const res = await fetchWithPayment(`${TILL_URL}/a2a`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ listing_id: "till-001" })
});

const text = await res.text();
let body;
try {
  body = JSON.parse(text);
} catch {
  body = text;
}

console.log(JSON.stringify({ status: res.status, payment_response: res.headers.get("payment-response"), body }, null, 2));

if (res.status !== 200 || !body?.extract) {
  process.exit(2);
}
