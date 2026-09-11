import os
import json
import asyncio
import base64
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
import httpx
from google import genai
from google.genai import types

# ── Environment ──────────────────────────────────────────────────────────
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

PRIVATE_KEY = os.getenv("OPERATOR_PRIVATE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HEDERA_ACCOUNT_ID = os.getenv("HEDERA_ACCOUNT_ID")
PAY_TO_ACCOUNT = os.getenv("PAY_TO_ACCOUNT", HEDERA_ACCOUNT_ID)
HCS_TOPIC_ID = os.getenv("HCS_TOPIC_ID", "")
AGENT_TASK = os.getenv("AGENT_TASK", "Get current weather data for Cape Town, South Africa")
RESOURCE_SERVER_URL = os.getenv("RESOURCE_SERVER_URL", "http://127.0.0.1:8000")
SPENDING_THRESHOLD_USD = float(os.getenv("SPENDING_THRESHOLD_HBAR", "5.0"))
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://api.testnet.blocky402.com")

ENDPOINTS = [
    {"path": "/api/weather",              "name": "Weather API",       "service_type": "weather_query"},
    {"path": "/api/weather-intelligence", "name": "Premium Analytics", "service_type": "analytics_run"},
    {"path": "/api/forecast",             "name": "Forecast API",      "service_type": "forecast_batch"},
]

if not PRIVATE_KEY:
    raise ValueError("OPERATOR_PRIVATE_KEY not set")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set")
if not HEDERA_ACCOUNT_ID:
    raise ValueError("HEDERA_ACCOUNT_ID not set")

clean_key = PRIVATE_KEY if PRIVATE_KEY.startswith("0x") else f"0x{PRIVATE_KEY}"

# ── Gemini ──────────────────────────────────────────────────────────────
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ── HCS audit logging ───────────────────────────────────────────────────
_hedera_client = None

def _get_hedera_client():
    global _hedera_client
    if _hedera_client is None:
        from hiero_sdk_python import Client, AccountId, PrivateKey
        _hedera_client = Client.for_testnet()
        aid = AccountId.from_string(HEDERA_ACCOUNT_ID)
        key = PrivateKey.from_string_ecdsa(clean_key)
        _hedera_client.set_operator(aid, key)
    return _hedera_client

def log_to_hcs(event: dict) -> str:
    if not HCS_TOPIC_ID:
        return ""
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    message = json.dumps(event)
    try:
        from hiero_sdk_python import TopicMessageSubmitTransaction, TopicId
        client = _get_hedera_client()
        if not client:
            return ""
        tid = TopicId.from_string(HCS_TOPIC_ID)
        tx = (
            TopicMessageSubmitTransaction()
            .set_topic_id(tid)
            .set_message(message)
            .freeze_with(client)
            .execute(client)
        )
        return str(tx.transaction_id)
    except Exception as e:
        print(f"  [HCS] Error: {e}")
        return ""

# ── Policy gate (deterministic, never LLM) ─────────────────────────────
PRICING_USD = {
    "weather_query": 0.005,
    "analytics_run": 0.050,
    "forecast_batch": 0.020,
}

def is_payment_allowed(service_type: str) -> bool:
    return PRICING_USD.get(service_type, 999) <= SPENDING_THRESHOLD_USD

# ── Gemini service classifier ──────────────────────────────────────────
def classify_service(endpoint: dict, task: str) -> dict:
    prompt = f"""Analyze this API endpoint and determine relevance.

Endpoint: {json.dumps(endpoint, indent=2)}
Task: {task}

Respond with JSON:
{{
  "relevant": true/false,
  "reason": "one-line explanation",
  "value_assessment": "low/medium/high"
}}"""
    response = gemini_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        return {"relevant": True, "reason": "parse failure, defaulting to relevant", "value_assessment": "medium"}

# ── Hedera x402 signing ────────────────────────────────────────────────
def get_fee_payer() -> str:
    try:
        resp = httpx.get(f"{FACILITATOR_URL}/supported", timeout=10)
        data = resp.json()
        return data.get("signers", {}).get("hedera:*", ["0.0.7162784"])[0]
    except Exception:
        return "0.0.7162784"

def sign_hedera_payment(amount_tinybars: int, pay_to: str, fee_payer: str,
                         asset: str = "0.0.0") -> dict:
    """Sign a Hedera TransferTransaction and return x402 PaymentPayload."""
    from hiero_sdk_python import (
        Client, AccountId, PrivateKey, TransferTransaction, Hbar, TransactionId,
    )

    client = Client.for_testnet()
    payer_id = AccountId.from_string(HEDERA_ACCOUNT_ID)
    payee_id = AccountId.from_string(pay_to)
    fee_payer_id = AccountId.from_string(fee_payer)
    key = PrivateKey.from_string_ecdsa(clean_key)
    client.set_operator(payer_id, key)

    # Generate tx with facilitator as fee payer
    tx_id = TransactionId.generate(fee_payer_id)

    tx = TransferTransaction().set_transaction_id(tx_id)

    if asset == "0.0.0":
        tx.add_hbar_transfer(payer_id, Hbar.from_tinybars(-amount_tinybars))
        tx.add_hbar_transfer(payee_id, Hbar.from_tinybars(amount_tinybars))
    else:
        from hiero_sdk_python import TokenId
        tx.add_token_transfer(TokenId.from_string(asset), payer_id, -amount_tinybars)
        tx.add_token_transfer(TokenId.from_string(asset), payee_id, amount_tinybars)

    frozen = tx.freeze_with(client)
    signed = frozen.sign(key)

    tx_bytes = signed.to_bytes()
    payload_b64 = base64.b64encode(tx_bytes).decode("utf-8")

    return {
        "x402Version": 2,
        "scheme": "exact",
        "network": "hedera:testnet",
        "accepted": {
            "scheme": "exact",
            "network": "hedera:testnet",
            "amount": str(amount_tinybars),
            "payTo": pay_to,
            "maxTimeoutSeconds": 300,
            "asset": asset,
            "extra": {"feePayer": fee_payer},
        },
        "payload": {
            "transaction": payload_b64,
        },
    }

def verify_with_facilitator(payment_payload: dict, payment_requirements: dict) -> dict:
    resp = httpx.post(
        f"{FACILITATOR_URL}/verify",
        json={"x402Version": 2, "paymentPayload": payment_payload, "paymentRequirements": payment_requirements},
        timeout=30,
    )
    return resp.json()

def settle_with_facilitator(payment_payload: dict, payment_requirements: dict) -> dict:
    resp = httpx.post(
        f"{FACILITATOR_URL}/settle",
        json={"x402Version": 2, "paymentPayload": payment_payload, "paymentRequirements": payment_requirements},
        timeout=60,
    )
    return resp.json()

# ── Process endpoint ────────────────────────────────────────────────────
async def process_endpoint(endpoint: dict) -> bool:
    url = f"{RESOURCE_SERVER_URL}{endpoint['path']}"
    name = endpoint["name"]
    service_type = endpoint["service_type"]

    print(f"\n{'='*60}")
    print(f"  {name} — {url}")
    print(f"{'='*60}")

    # Gemini classifies
    print("  [Gemini] Analyzing relevance...")
    analysis = classify_service(endpoint, AGENT_TASK)
    print(f"  [Gemini] {json.dumps(analysis)}")

    if not analysis.get("relevant", True):
        print(f"  [SKIP] Not relevant: {analysis.get('reason')}")
        log_to_hcs({
            "event": "service_skipped",
            "agent": HEDERA_ACCOUNT_ID,
            "service": name,
            "reason": analysis.get("reason"),
        })
        return False

    # Policy gate
    if not is_payment_allowed(service_type):
        print(f"  [BLOCKED] Policy rejects {service_type}")
        log_to_hcs({
            "event": "payment_blocked",
            "agent": HEDERA_ACCOUNT_ID,
            "service": name,
            "service_type": service_type,
            "reason": "exceeds_policy_threshold",
            "gemini_reasoning": analysis.get("reason", ""),
        })
        return False

    # Step 1: Request protected resource
    print(f"  [x402] Requesting {url}...")
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30)

        if response.status_code != 402:
            print(f"  [x402] Unexpected status: {response.status_code}")
            return False

        print("  [x402] Got 402 — building Hedera payment...")

        # Parse payment requirements from response body
        body = response.json()
        amount_tinybars = int(body.get("amount_tinybars", 500000))
        pay_to = body.get("pay_to", PAY_TO_ACCOUNT)
        asset = body.get("asset", "0.0.0")
        fee_payer = body.get("fee_payer", get_fee_payer())

    # Step 2: Sign payment
    print(f"  [x402] Signing {amount_tinybars} tinybars...")
    payment_payload = sign_hedera_payment(amount_tinybars, pay_to, fee_payer, asset)
    payment_reqs = payment_payload["accepted"]

    # Step 3: Verify with facilitator
    print("  [x402] Verifying with Blocky402...")
    verify_result = verify_with_facilitator(payment_payload, payment_reqs)
    print(f"  [x402] Verify: {json.dumps(verify_result)}")

    if not verify_result.get("isValid", False):
        reason = verify_result.get("invalidReason", "unknown")
        print(f"  [x402] Verification failed: {reason}")
        log_to_hcs({
            "event": "payment_blocked",
            "agent": HEDERA_ACCOUNT_ID,
            "service": name,
            "service_type": service_type,
            "reason": f"verification_failed: {reason}",
            "gemini_reasoning": analysis.get("reason", ""),
        })
        return False

    # Step 4: Settle with facilitator
    print("  [x402] Settling on Hedera via Blocky402...")
    settle_result = settle_with_facilitator(payment_payload, payment_reqs)
    print(f"  [x402] Settle: {json.dumps(settle_result)}")

    if not settle_result.get("success", False):
        print(f"  [x402] Settlement failed")
        return False

    tx_hash = settle_result.get("transaction", "")
    print(f"  [x402] Settled: {tx_hash}")

    log_to_hcs({
        "event": "payment_settled",
        "agent": HEDERA_ACCOUNT_ID,
        "service": name,
        "service_type": service_type,
        "amount_tinybars": amount_tinybars,
        "tx": tx_hash,
        "gemini_reasoning": analysis.get("reason", ""),
    })

    # Step 5: Access protected resource with payment proof
    print("  [x402] Accessing protected resource...")
    x_payment_b64 = base64.b64encode(json.dumps(payment_payload).encode()).decode()
    async with httpx.AsyncClient() as client:
        resource_response = await client.get(
            url,
            headers={"X-PAYMENT": x_payment_b64},
            timeout=30,
        )
        print(f"  [x402] Status: {resource_response.status_code}")
        try:
            data = resource_response.json()
            print(f"  [x402] Response: {json.dumps(data, indent=2)}")
        except Exception:
            print(f"  [x402] Response: {resource_response.text[:500]}")

    return True

async def run_agent():
    print("=" * 60)
    print("  BRIDLE AGENT — x402 Hedera Payments (Blocky402)")
    print("=" * 60)
    print(f"  Account: {HEDERA_ACCOUNT_ID}")
    print(f"  Facilitator: {FACILITATOR_URL}")
    print(f"  Task: {AGENT_TASK}")
    print(f"  Threshold: ${SPENDING_THRESHOLD_USD}")
    print(f"  Endpoints: {len(ENDPOINTS)}")
    print("=" * 60)

    settled = 0
    skipped = 0

    for ep in ENDPOINTS:
        success = await process_endpoint(ep)
        if success:
            settled += 1
        else:
            skipped += 1

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    print(f"  Settled: {settled}")
    print(f"  Skipped/Blocked: {skipped}")
    print(f"  HCS Events Logged: {settled + skipped}")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(run_agent())
