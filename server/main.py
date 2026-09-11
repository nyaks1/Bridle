import os
import sys
import json
import base64
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import httpx

# ── Environment ──────────────────────────────────────────────────────────
env_path = Path(__file__).resolve().parent.parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

HEDERA_ACCOUNT_ID = os.getenv("HEDERA_ACCOUNT_ID")
PAY_TO_ACCOUNT = os.getenv("PAY_TO_ACCOUNT") or os.getenv("HEDERA_ACCOUNT_ID")
if not PAY_TO_ACCOUNT:
    print("WARNING: PAY_TO_ACCOUNT not set, using HEDERA_ACCOUNT_ID")
    PAY_TO_ACCOUNT = HEDERA_ACCOUNT_ID
print(f"[Config] PAY_TO_ACCOUNT={PAY_TO_ACCOUNT}")
HEDERA_PRIVATE_KEY = os.getenv("OPERATOR_PRIVATE_KEY")
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://api.testnet.blocky402.com")
HCS_TOPIC_ID = os.getenv("HCS_TOPIC_ID", "")

if not HEDERA_ACCOUNT_ID:
    print("ERROR: HEDERA_ACCOUNT_ID not set")
    sys.exit(1)

HEDERA_NETWORK = "hedera:testnet"

# ── Metered pricing (tinybars) ──────────────────────────────────────────
PRICING = {
    "weather_query":  {"tinybars": 500_000,   "usd": "$0.005", "description": "Single weather data query"},
    "analytics_run":  {"tinybars": 5_000_000,  "usd": "$0.050", "description": "Enterprise weather analytics"},
    "forecast_batch": {"tinybars": 2_000_000,  "usd": "$0.020", "description": "Batch forecast retrieval"},
}

SERVICE_TYPES = {
    "/api/weather":              "weather_query",
    "/api/weather-intelligence": "analytics_run",
    "/api/forecast":             "forecast_batch",
}

# ── HCS audit logging ───────────────────────────────────────────────────
_hedera_client = None

def _get_hedera_client():
    global _hedera_client
    if _hedera_client is None and HEDERA_ACCOUNT_ID and HEDERA_PRIVATE_KEY:
        from hiero_sdk_python import Client, AccountId, PrivateKey
        _hedera_client = Client.for_testnet()
        aid = AccountId.from_string(HEDERA_ACCOUNT_ID)
        clean_key = HEDERA_PRIVATE_KEY if HEDERA_PRIVATE_KEY.startswith("0x") else f"0x{HEDERA_PRIVATE_KEY}"
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
        print(f"[HCS] Error: {e}")
        return ""

# ── Facilitator helpers ─────────────────────────────────────────────────
def _get_fee_payer() -> str:
    try:
        resp = httpx.get(f"{FACILITATOR_URL}/supported", timeout=10)
        data = resp.json()
        return data.get("signers", {}).get("hedera:*", ["0.0.7162784"])[0]
    except Exception:
        return "0.0.7162784"

FEE_PAYER = _get_fee_payer()

def verify_payment(payload_dict: dict) -> dict:
    """Verify a payment via Blocky402 facilitator."""
    resp = httpx.post(
        f"{FACILITATOR_URL}/verify",
        json={"x402Version": 2, "paymentPayload": payload_dict, "paymentRequirements": payload_dict.get("accepted", {})},
        timeout=30,
    )
    return resp.json()

def settle_payment(payload_dict: dict) -> dict:
    """Settle a payment via Blocky402 facilitator."""
    resp = httpx.post(
        f"{FACILITATOR_URL}/settle",
        json={"x402Version": 2, "paymentPayload": payload_dict, "paymentRequirements": payload_dict.get("accepted", {})},
        timeout=60,
    )
    return resp.json()

# ── FastAPI ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Bridle x402 Gateway",
    description="Pay-per-call API gateway with Blocky402 facilitator on Hedera",
    version="2.0.0",
)

@app.middleware("http")
async def x402_payment_middleware(request: Request, call_next) -> Response:
    route_key = f"{request.method} {request.url.path}"

    if request.url.path == "/api/health" or request.url.path not in SERVICE_TYPES:
        return await call_next(request)

    service_type = SERVICE_TYPES[request.url.path]
    pricing = PRICING[service_type]

    print(f"[x402] Request: {route_key} ({service_type})")

    payment_header = (
        request.headers.get("payment-signature")
        or request.headers.get("x-payment")
    )

    if not payment_header:
        print("[x402] No payment — returning 402")

        requirements = {
            "scheme": "exact",
            "network": HEDERA_NETWORK,
            "amount": str(pricing["tinybars"]),
            "payTo": PAY_TO_ACCOUNT,
            "maxTimeoutSeconds": 300,
            "asset": "0.0.0",
            "extra": {"feePayer": FEE_PAYER},
        }

        payment_required = {
            "x402Version": 2,
            "accepts": [requirements],
            "resource": {
                "url": str(request.url),
                "description": pricing["description"],
                "mime_type": "application/json",
            },
        }

        req_header = base64.b64encode(json.dumps(payment_required).encode()).decode()

        return JSONResponse(
            status_code=402,
            content={
                "error": "Payment Required",
                "service_type": service_type,
                "amount_tinybars": str(pricing["tinybars"]),
                "amount_usd": pricing["usd"],
        "pay_to": PAY_TO_ACCOUNT,
                "network": HEDERA_NETWORK,
                "asset": "0.0.0",
                "fee_payer": FEE_PAYER,
            },
            headers={"PAYMENT-REQUIRED": req_header},
        )

    try:
        payment_payload = json.loads(base64.b64decode(payment_header).decode("utf-8"))

        print("[x402] Verifying with Blocky402...")
        verify_result = verify_payment(payment_payload)

        if not verify_result.get("isValid", False):
            reason = verify_result.get("invalidReason", "unknown")
            print(f"[x402] Verification failed: {reason}")
            log_to_hcs({
                "event": "payment_blocked",
                "service": service_type,
                "reason": reason,
                "amount_tinybars": pricing["tinybars"],
            })
            return JSONResponse(
                status_code=402,
                content={"error": "Invalid Payment", "reason": reason},
            )

        print("[x402] Payment verified — executing handler...")
        response = await call_next(request)

        if 200 <= response.status_code < 300:
            print("[x402] Settling via Blocky402...")
            try:
                settle_result = settle_payment(payment_payload)
                tx = settle_result.get("transaction", "")
                success = settle_result.get("success", False)
                print(f"[x402] Settled: success={success}, tx={tx}")

                log_to_hcs({
                    "event": "payment_settled",
                    "service": service_type,
                    "amount_tinybars": pricing["tinybars"],
                    "tx": tx,
                    "payer": verify_result.get("payer", ""),
                })

                body = b""
                async for chunk in response.body_iterator:
                    body += chunk
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers={**dict(response.headers), "PAYMENT-RESPONSE": base64.b64encode(json.dumps(settle_result).encode()).decode()},
                    media_type=response.media_type,
                )
            except Exception as e:
                print(f"[x402] Settlement error: {e}")
                return response

        return response

    except Exception as e:
        print(f"[x402] Processing error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── Routes ──────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "facilitator": FACILITATOR_URL,
        "network": HEDERA_NETWORK,
        "pay_to": PAY_TO_ACCOUNT,
        "fee_payer": FEE_PAYER,
        "version": "2.0.0",
        "pricing": {k: {"tinybars": v["tinybars"], "usd": v["usd"]} for k, v in PRICING.items()},
    }

@app.get("/api/weather")
async def get_weather(city: str = "Cape Town"):
    weather_data = {
        "Cape Town":     {"temp_c": 22, "condition": "Sunny", "humidity": 45, "wind_kph": 18},
        "San Francisco": {"temp_c": 16, "condition": "Foggy", "humidity": 78, "wind_kph": 24},
        "New York":      {"temp_c": 12, "condition": "Cloudy", "humidity": 62, "wind_kph": 30},
        "London":        {"temp_c": 10, "condition": "Rainy", "humidity": 85, "wind_kph": 35},
    }
    data = weather_data.get(city, {"temp_c": 25, "condition": "Clear", "humidity": 40, "wind_kph": 12})
    return {
        "city": city,
        "temperature_c": data["temp_c"],
        "condition": data["condition"],
        "humidity_pct": data["humidity"],
        "wind_kph": data["wind_kph"],
        "source": "Bridle Weather API",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/api/weather-intelligence")
async def get_weather_intelligence(city: str = "Cape Town"):
    return {
        "city": city,
        "current": {"temp_c": 22, "condition": "Sunny", "uv_index": 7},
        "forecast_5day": [
            {"day": "Mon", "high": 24, "low": 16, "condition": "Sunny"},
            {"day": "Tue", "high": 22, "low": 15, "condition": "Partly Cloudy"},
            {"day": "Wed", "high": 19, "low": 13, "condition": "Rainy"},
            {"day": "Thu", "high": 21, "low": 14, "condition": "Cloudy"},
            {"day": "Fri", "high": 23, "low": 15, "condition": "Sunny"},
        ],
        "alerts": [
            {"type": "UV", "severity": "moderate", "message": "UV index above 6 — seek shade midday"}
        ],
        "source": "Bridle Weather Intelligence",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/api/forecast")
async def get_forecast(city: str = "Cape Town", days: int = 3):
    return {
        "city": city,
        "days": min(days, 7),
        "forecasts": [
            {"date": f"2026-09-{11+i}", "high": 22 + i, "low": 15 + i, "precipitation_pct": 10 * i}
            for i in range(min(days, 7))
        ],
        "source": "Bridle Forecast API",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.on_event("startup")
async def startup():
    print(f"[Bridle] Started — pay_to={PAY_TO_ACCOUNT}, facilitator={FACILITATOR_URL}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
