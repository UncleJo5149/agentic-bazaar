const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const PORT = Number(process.env.PORT || 8080);
const PUBLIC_DIR = path.join(__dirname, "..", "public");
const LISTINGS_DIR = path.join(__dirname, "..", "listings");
const LEDGER_PATH = process.env.LEDGER_PATH || path.join(__dirname, "..", "data", "ledger.jsonl");

const SELLER = {
  legal_name: "RENMOLT ETHICAL SYSTEMS",
  registration: "202603057004 (TR0338241-U)",
  jurisdiction: "MY",
  form: "Registered business under the Registration of Businesses Act 1956"
};

const PROTOCOL_FEE_BPS = 800;
const AGENT_SHARE = 0.6;
const STEWARD_SHARE = 0.4;

const NETWORKS = {
  "eip155:84532": {
    name: "base-sepolia",
    asset: "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    assetName: "USDC",
    money: false
  },
  "eip155:8453": {
    name: "base",
    asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    assetName: "USDC",
    money: true
  }
};

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".md": "text/markdown; charset=utf-8"
};

const seenPayments = new Set();
const ledgerCache = [];

function ensureLedgerDir() {
  fs.mkdirSync(path.dirname(LEDGER_PATH), { recursive: true });
}

function loadLedger() {
  try {
    if (!fs.existsSync(LEDGER_PATH)) return;
    const lines = fs.readFileSync(LEDGER_PATH, "utf8").split("\n").filter(Boolean);
    for (const line of lines) {
      try {
        const row = JSON.parse(line);
        ledgerCache.push(row);
        if (row.payment_hash) seenPayments.add(row.payment_hash);
      } catch {
        /* skip bad line */
      }
    }
  } catch {
    /* first boot */
  }
}

function appendLedger(row) {
  ledgerCache.push(row);
  if (row.payment_hash) seenPayments.add(row.payment_hash);
  try {
    ensureLedgerDir();
    fs.appendFileSync(LEDGER_PATH, JSON.stringify(row) + "\n");
  } catch (err) {
    console.error("ledger_write_failed", err.message);
  }
}

function hashPayment(raw) {
  return crypto.createHash("sha256").update(String(raw)).digest("hex");
}

function send(res, status, body, headers = {}) {
  const payload = typeof body === "string" ? body : JSON.stringify(body, null, 2);
  res.writeHead(status, {
    "content-type": headers["content-type"] || "application/json; charset=utf-8",
    "access-control-allow-origin": "*",
    "access-control-allow-headers":
      "Content-Type, Authorization, X-Till-Paid, X-Payment-Receipt, X-PAYMENT, PAYMENT-SIGNATURE, PAYMENT-REQUIRED",
    "access-control-allow-methods": "GET, POST, OPTIONS",
    ...headers
  });
  res.end(payload);
}

function send402(res, body) {
  const encoded = Buffer.from(JSON.stringify(body)).toString("base64");
  return send(res, 402, body, { "PAYMENT-REQUIRED": encoded });
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function publicBase(req) {
  if (process.env.PUBLIC_BASE_URL) return process.env.PUBLIC_BASE_URL.replace(/\/$/, "");
  const proto = req.headers["x-forwarded-proto"] || "https";
  const host = req.headers["x-forwarded-host"] || req.headers.host;
  return `${proto}://${host}`;
}

function loadCatalog() {
  return readJson(path.join(PUBLIC_DIR, "catalog.json"));
}

function findListing(id) {
  return loadCatalog().listings.find((item) => item.id === id);
}

function payConfig() {
  const network = process.env.X402_NETWORK || "eip155:84532";
  const known = NETWORKS[network] || NETWORKS["eip155:84532"];
  const payTo = String(process.env.PAY_TO_ADDRESS || "").trim();
  const facilitator = process.env.X402_FACILITATOR_URL || "https://x402.org/facilitator";
  const rawDemo = process.env.ALLOW_DEMO;
  const allowDemo = known.money
    ? String(rawDemo || "false").toLowerCase() === "true"
    : String(rawDemo || "true").toLowerCase() !== "false";
  return {
    network,
    ...known,
    payTo,
    facilitator,
    allowDemo,
    ready: /^0x[a-fA-F0-9]{40}$/.test(payTo)
  };
}

function paymentsMachine() {
  const cfg = payConfig();
  const status = !cfg.ready
    ? "x402_waiting_for_address"
    : cfg.money
      ? "x402_live_mainnet"
      : "x402_live_testnet";
  return {
    id: "payments-v0.3",
    seller: SELLER.legal_name,
    effective: "2026-09-01",
    status,
    live_status_url: "/pay/status",
    currency_list: ["USD", "USDC"],
    methods: [
      {
        id: "x402",
        live: cfg.ready,
        money: cfg.ready && cfg.money,
        how: "HTTP 402 then retry with PAYMENT-SIGNATURE or X-PAYMENT",
        network: cfg.network,
        network_name: cfg.name,
        asset: cfg.asset,
        payTo: cfg.ready ? cfg.payTo : null,
        facilitator: cfg.facilitator,
        amount_till_001: "50000",
        note: cfg.ready
          ? "Unpaid POST /a2a returns 402. Paid retry settles via the facilitator, then delivers extract + receipt."
          : "Set Railway PAY_TO_ADDRESS to a 0x wallet before agents can pay."
      },
      {
        id: "demo",
        live: cfg.allowDemo,
        money: false,
        how: "Authorization: Bearer till-demo",
        note: cfg.allowDemo ? "Demo key is on. It does not move USDC." : "Demo key is off."
      }
    ],
    merchant_of_record: `${SELLER.legal_name} ${SELLER.registration}`,
    human_readable: "/payments.txt"
  };
}

function paymentsHuman() {
  const cfg = payConfig();
  return [
    `Payment methods — ${SELLER.legal_name}`,
    "Effective 1 September 2026",
    "",
    `Rail: x402 (HTTP 402 + ${cfg.assetName} on ${cfg.name})`,
    `Status: ${cfg.ready ? (cfg.money ? "live_mainnet" : "live_testnet") : "waiting_for_pay_to_address"}`,
    "",
    cfg.ready ? `Live pay-to: ${cfg.payTo}` : "Pay-to: not set",
    `Network: ${cfg.network}`,
    `Asset: ${cfg.asset}`,
    `Facilitator: ${cfg.facilitator}`,
    "",
    "Unpaid POST /a2a returns 402 + PAYMENT-REQUIRED.",
    "Paid retry uses PAYMENT-SIGNATURE or X-PAYMENT.",
    "Same payment header cannot be reused.",
    "Every delivery is written to /ledger.json.",
    "",
    cfg.allowDemo ? "Demo key is on (Authorization: Bearer till-demo)." : "Demo key is off.",
    "",
    "No cash. No chat checkout. No support queue.",
    ""
  ].join("\n");
}

function demoPaid(req) {
  const cfg = payConfig();
  if (!cfg.allowDemo) return false;
  const auth = String(req.headers.authorization || "");
  const tillPaid = String(req.headers["x-till-paid"] || "");
  const demo = process.env.TILL_DEMO_KEY || "till-demo";
  return tillPaid === "1" || tillPaid.toLowerCase() === "true" || auth === `Bearer ${demo}`;
}

function paymentHeader(req) {
  return (
    String(req.headers["payment-signature"] || "") ||
    String(req.headers["x-payment"] || "") ||
    String(req.headers["x-payment-receipt"] || "")
  );
}

function atomicAmount(price) {
  return String(Math.round(Number(price) * 1_000_000));
}

function requirements(req, listing) {
  const cfg = payConfig();
  return {
    scheme: "exact",
    network: cfg.network,
    amount: atomicAmount(listing.price),
    asset: cfg.asset,
    payTo: cfg.payTo,
    maxTimeoutSeconds: 300,
    extra: {
      name: cfg.assetName,
      version: "2",
      resourceUrl: `${publicBase(req)}/a2a`
    }
  };
}

function challenge(req, listing) {
  const cfg = payConfig();
  const accepts = cfg.ready ? [requirements(req, listing)] : [];
  return {
    x402Version: 2,
    error: "payment_required",
    listing_id: listing.id,
    price: listing.price,
    currency: listing.currency || "USD",
    license: listing.license,
    training: listing.training,
    resource: {
      url: `${publicBase(req)}/a2a`,
      description: `fetch-cite ${listing.id}`,
      mimeType: "application/json"
    },
    accepts,
    pay: {
      x402: cfg.ready,
      network: cfg.network,
      network_name: cfg.name,
      asset: cfg.asset,
      payTo: cfg.ready ? cfg.payTo : null,
      facilitator: cfg.facilitator,
      demo_header: cfg.allowDemo ? "Authorization: Bearer till-demo" : null,
      status: cfg.ready ? (cfg.money ? "live_mainnet" : "live_testnet") : "waiting_for_pay_to_address"
    }
  };
}

async function verifyX402(req, listing) {
  const raw = paymentHeader(req);
  if (!raw) return { ok: false, reason: "missing_payment_header" };
  const cfg = payConfig();
  if (!cfg.ready) return { ok: false, reason: "pay_to_not_configured" };

  let paymentPayload = raw;
  try {
    const decoded = Buffer.from(raw, "base64").toString("utf8");
    if (decoded.startsWith("{")) paymentPayload = JSON.parse(decoded);
    else paymentPayload = JSON.parse(raw);
  } catch {
    try {
      paymentPayload = JSON.parse(raw);
    } catch {
      return { ok: false, reason: "invalid_payment_header" };
    }
  }

  const body = {
    x402Version: 2,
    paymentPayload,
    paymentRequirements: requirements(req, listing)
  };

  try {
    const verifyRes = await fetch(`${cfg.facilitator.replace(/\/$/, "")}/verify`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body)
    });
    const verified = await verifyRes.json().catch(() => ({}));
    if (!verified?.isValid) return { ok: false, reason: "not_valid", detail: verified };

    const settleRes = await fetch(`${cfg.facilitator.replace(/\/$/, "")}/settle`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body)
    });
    const settled = await settleRes.json().catch(() => ({}));
    const tx = txFromSettled(settled);
    const settledOk = settled?.success === true || Boolean(settleRes.ok && tx);
    if (!settledOk) {
      return { ok: false, reason: "settle_failed", detail: settled };
    }
    return { ok: true, payer: verified.payer || settled.payer || null, settled };
  } catch (err) {
    return { ok: false, reason: "facilitator_error", detail: String(err.message || err) };
  }
}

function split(price) {
  const paidAmt = Number(price);
  const fee = Number((paidAmt * (PROTOCOL_FEE_BPS / 10000)).toFixed(6));
  const sellerNet = Number((paidAmt - fee).toFixed(6));
  return {
    paid: paidAmt.toFixed(2),
    currency: "USD",
    protocol_fee: fee.toFixed(4),
    seller_net: sellerNet.toFixed(4),
    agent_treasury: (fee * AGENT_SHARE).toFixed(4),
    steward_treasury: (fee * STEWARD_SHARE).toFixed(4)
  };
}

function parseListingId(text) {
  const match = String(text || "").match(/till-[0-9a-z-]+/i);
  return match ? match[0].toLowerCase() : "till-001";
}

function serveStatic(req, res, urlPath) {
  const safe = path.normalize(urlPath).replace(/^(\.\.[/\\])+/, "");
  const filePath = path.join(PUBLIC_DIR, safe === "/" ? "index.html" : safe);
  if (!filePath.startsWith(PUBLIC_DIR)) return send(res, 403, { error: "forbidden" });
  if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) return false;
  const ext = path.extname(filePath);
  send(res, 200, fs.readFileSync(filePath, "utf8"), { "content-type": MIME[ext] || "application/octet-stream" });
  return true;
}

function txFromSettled(settled) {
  if (!settled || typeof settled !== "object") return null;
  return settled.transaction || settled.txHash || settled.hash || settled.transactionHash || null;
}

function recordAndDeliver(res, listing, extra) {
  const receipt = split(listing.price);
  const row = {
    at: new Date().toISOString(),
    listing_id: listing.id,
    rail: extra.rail,
    price: listing.price,
    currency: listing.currency || "USD",
    payer: extra.payer || null,
    tx: extra.tx || txFromSettled(extra.settled) || null,
    payment_hash: extra.payment_hash || null,
    receipt
  };
  appendLedger(row);

  const extractPath = path.join(LISTINGS_DIR, `${listing.id}.txt`);
  const extract = fs.existsSync(extractPath)
    ? fs.readFileSync(extractPath, "utf8").trim()
    : listing.title;
  const body = {
    listing_id: listing.id,
    license: listing.license,
    training: listing.training,
    extract,
    citation: {
      title: listing.title,
      url: listing.url,
      seller: SELLER.legal_name,
      registration: SELLER.registration
    },
    receipt,
    payment: {
      rail: extra.rail,
      payer: extra.payer || null,
      tx: row.tx,
      payment_hash: extra.payment_hash || null
    }
  };
  const paymentResponse = Buffer.from(
    JSON.stringify({
      success: true,
      x402Version: 2,
      rail: extra.rail,
      payer: extra.payer || null,
      transaction: row.tx,
      network: payConfig().network
    })
  ).toString("base64");
  return send(res, 200, body, { "PAYMENT-RESPONSE": paymentResponse });
}

function handleA2A(req, res) {
  let raw = "";
  req.on("data", (chunk) => {
    raw += chunk;
    if (raw.length > 1_000_000) req.destroy();
  });
  req.on("end", async () => {
    let body = {};
    try {
      body = raw ? JSON.parse(raw) : {};
    } catch {
      return send(res, 400, { error: "invalid_json" });
    }

    const text = body?.params?.message?.parts?.[0]?.text || body?.text || body?.listing_id || "";
    const listingId = body?.listing_id || parseListingId(text);
    const listing = findListing(listingId);
    if (!listing) return send(res, 404, { error: "listing_not_found", listing_id: listingId });

    if (demoPaid(req)) {
      return recordAndDeliver(res, listing, { rail: "demo", payment_hash: "demo" });
    }

    const header = paymentHeader(req);
    if (header) {
      const paymentHash = hashPayment(header);
      if (seenPayments.has(paymentHash)) {
        const body402 = challenge(req, listing);
        body402.pay.verify_error = "replay";
        return send402(res, body402);
      }
      const checked = await verifyX402(req, listing);
      if (checked.ok) {
        return recordAndDeliver(res, listing, {
          rail: "x402",
          payer: checked.payer,
          settled: checked.settled,
          payment_hash: paymentHash
        });
      }
      const body402 = challenge(req, listing);
      body402.pay.verify_error = checked.reason;
      if (checked.detail) body402.pay.verify_detail = checked.detail;
      return send402(res, body402);
    }

    return send402(res, challenge(req, listing));
  });
}

loadLedger();

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (req.method === "OPTIONS") return send(res, 204, "");

  if (req.method === "GET" && url.pathname === "/health") {
    const cfg = payConfig();
    return send(res, 200, {
      ok: true,
      seller: SELLER.legal_name,
      payment: cfg.ready ? (cfg.money ? "live_mainnet" : "live_testnet") : "waiting_for_pay_to_address",
      allow_demo: cfg.allowDemo,
      ledger_rows: ledgerCache.length
    });
  }

  if (req.method === "GET" && url.pathname === "/who") {
    return send(res, 200, SELLER);
  }

  if (req.method === "GET" && url.pathname === "/pay/status") {
    const cfg = payConfig();
    return send(res, 200, {
      seller: SELLER.legal_name,
      ready: cfg.ready,
      money: cfg.ready && cfg.money,
      network: cfg.network,
      network_name: cfg.name,
      asset: cfg.asset,
      payTo: cfg.ready ? cfg.payTo : null,
      facilitator: cfg.facilitator,
      allow_demo: cfg.allowDemo,
      ledger_rows: ledgerCache.length,
      next_step: cfg.ready
        ? cfg.allowDemo
          ? "Mainnet live but demo is still on. Leave ALLOW_DEMO unset."
          : "Accept PAYMENT-SIGNATURE / X-PAYMENT and settle."
        : "Create a Base wallet. Put the public address in Railway variable PAY_TO_ADDRESS."
    });
  }

  if (req.method === "GET" && (url.pathname === "/ledger.json" || url.pathname === "/ledger")) {
    const x402Rows = ledgerCache.filter((row) => row.rail === "x402");
    const demoRows = ledgerCache.filter((row) => row.rail === "demo");
    return send(res, 200, {
      seller: SELLER.legal_name,
      count: ledgerCache.length,
      x402_count: x402Rows.length,
      demo_count: demoRows.length,
      entries: ledgerCache.slice(-200)
    });
  }

  if (req.method === "POST" && (url.pathname === "/a2a" || url.pathname === "/a2a/")) {
    return handleA2A(req, res);
  }

  if (req.method === "GET" && url.pathname === "/payments.json") {
    return send(res, 200, paymentsMachine());
  }

  if (req.method === "GET" && url.pathname === "/payments.txt") {
    return send(res, 200, paymentsHuman(), { "content-type": "text/plain; charset=utf-8" });
  }

  if (req.method === "GET") {
    if (serveStatic(req, res, url.pathname)) return;
    if (url.pathname === "/.well-known/agent.json" || url.pathname === "/agent.json") {
      const cardPath = fs.existsSync(path.join(PUBLIC_DIR, "agent.json"))
        ? path.join(PUBLIC_DIR, "agent.json")
        : path.join(PUBLIC_DIR, ".well-known", "agent.json");
      if (!fs.existsSync(cardPath)) return send(res, 404, { error: "agent_card_missing" });
      const card = readJson(cardPath);
      const base = publicBase(req);
      card.url = `${base}/a2a`;
      card.provider.url = base;
      card.documentationUrl = `${base}/`;
      card.termsOfService = `${base}/terms.json`;
      card.refundPolicy = `${base}/refund.json`;
      card.paymentMethods = `${base}/payments.json`;
      return send(res, 200, card);
    }
  }

  send(res, 404, { error: "not_found" });
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Agent Till listening on ${PORT}`);
});
