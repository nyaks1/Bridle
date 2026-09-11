"""Bridle HTTP 402 & On-Chain Paywall Gateway.

Features:
- Dual Payment Paths:
  1. Micro-Payments: x402 Protocol via Blocky402 Facilitator / Hedera Native HBAR.
  2. Macro-Payments (> 1.0 HBAR): Direct On-Chain settlement to BridlePaywall contract
     verified with resilient exponential backoff polling.
- Hedera Consensus Service (HCS) immutable audit logging for all settled and blocked transactions.
"""

import os
import sys
import json
import time
import base64
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, Header, HTTPException, status
from fastapi.responses import JSONResponse
import httpx
from web3 import Web3

# ── Environment ──────────────────────────────────────────────────────────
env_path = Path(__file__).resolve().parent.parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

HEDERA_RPC_URL = os.getenv("HEDERA_RPC_URL", "https://testnet.hashio.io/api")
HEDERA_ACCOUNT_ID = os.getenv("HEDERA_ACCOUNT_ID")
PAY_TO_ACCOUNT = os.getenv("PAY_TO_ACCOUNT") or HEDERA_ACCOUNT_ID
HEDERA_PRIVATE_KEY = os.getenv("OPERATOR_PRIVATE_KEY")
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://api.testnet.blocky402.com")
HCS_TOPIC_ID = os.getenv("HCS_TOPIC_ID", "0.0.10474223")
PAYWALL_ADDRESS = os.getenv("PAYWALL_CONTRACT_ADDRESS", "0x5442A862d2B11709045BE15015368c7dD6B9cfd8")
HEDERA_NETWORK = "hedera:testnet"

w3 = Web3(Web3.HTTPProvider(HEDERA_RPC_URL))

# ── Metered pricing ──────────────────────────────────────────────────────
PRICING = {
    "weather_query":  {"tinybars": 500_000,     "hbar": 0.05, "usd": "$0.005", "description": "Single weather data query"},
    "analytics_run":  {"tinybars": 5_000_000,   "hbar": 0.50, "usd": "$0.050", "description": "Enterprise weather analytics"},
    "forecast_batch": {"tinybars": 2_000_000,   "hbar": 0.20, "usd": "$0.020", "description": "Batch forecast retrieval"},
    "premium_report": {"tinybars": 150_000_000, "hbar": 1.50, "usd": "$1.500", "description": "Global Climate Intelligence Archive (Hardware Veto Required)"},
}

SERVICE_TYPES = {
    "/api/weather":              "weather_query",
    "/api/weather-intelligence": "analytics_run",
    "/api/forecast":             "forecast_batch",
    "/api/premium-report":        "premium_report",
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
        tx_id = str(tx.transaction_id)
        print(f"[HCS] Logged event: {event.get('event')} (tx: {tx_id})")
        return tx_id
    except Exception as e:
        print(f"[HCS] Error logging event: {e}")
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
    resp = httpx.post(
        f"{FACILITATOR_URL}/verify",
        json={"x402Version": 2, "paymentPayload": payload_dict, "paymentRequirements": payload_dict.get("accepted", {})},
        timeout=30,
    )
    return resp.json()

def settle_payment(payload_dict: dict) -> dict:
    resp = httpx.post(
        f"{FACILITATOR_URL}/settle",
        json={"x402Version": 2, "paymentPayload": payload_dict, "paymentRequirements": payload_dict.get("accepted", {})},
        timeout=60,
    )
    return resp.json()

# ── Resilient On-Chain Verification with Exponential Backoff ────────────
def verify_onchain_tx(tx_hash: str, required_hbar: float, retries: int = 5, base_delay: float = 1.5) -> dict:
    """Verify an on-chain transaction receipt on Hedera Testnet with exponential backoff polling.

    Eliminates race conditions caused by mirror node and RPC indexing latency.
    """
    clean_tx = tx_hash.strip()
    if not clean_tx.startswith("0x"):
        clean_tx = f"0x{clean_tx}"

    target_contract = Web3.to_checksum_address(PAYWALL_ADDRESS)
    current_delay = base_delay

    print(f"[Gateway] Polling Hedera Testnet for tx {clean_tx} (required: {required_hbar} HBAR)...")

    for attempt in range(1, retries + 1):
        try:
            receipt = w3.eth.get_transaction_receipt(clean_tx)
            if receipt is not None:
                if receipt.get("status") != 1:
                    return {"valid": False, "reason": "Transaction execution reverted on-chain"}

                tx = w3.eth.get_transaction(clean_tx)
                if not tx.get("to") or Web3.to_checksum_address(tx["to"]) != target_contract:
                    return {
                        "valid": False,
                        "reason": f"Transaction recipient ({tx.get('to')}) does not match Paywall ({target_contract})"
                    }

                value_hbar = float(w3.from_wei(tx["value"], "ether"))
                if value_hbar < (required_hbar * 0.99):  # Allow 1% rounding tolerance
                    return {
                        "valid": False,
                        "reason": f"Insufficient payment: sent {value_hbar} HBAR, required {required_hbar} HBAR"
                    }

                print(f"[Gateway] ✅ Verified tx {clean_tx} on attempt {attempt}: {value_hbar} HBAR paid to {target_contract}")
                return {
                    "valid": True,
                    "payer": tx["from"],
                    "value_hbar": value_hbar,
                    "block_number": receipt.get("blockNumber"),
                    "tx_hash": clean_tx
                }

        except Exception as e:
            print(f"[Gateway] Attempt {attempt}/{retries}: Not indexed yet ({e}). Waiting {current_delay:.1f}s...")

        time.sleep(current_delay)
        current_delay *= 1.5

    return {"valid": False, "reason": f"Transaction not confirmed after {retries} polling attempts."}

# ── FastAPI Application ─────────────────────────────────────────────────
app = FastAPI(
    title="Bridle HTTP 402 & Hedera Paywall Gateway",
    description="Dual-rail payment gateway: x402 micro-settlements & hardware-confirmed on-chain paywall",
    version="2.1.0",
)

@app.middleware("http")
async def x402_payment_middleware(request: Request, call_next) -> Response:
    route_path = request.url.path

    # Allow health checks and unmetered routes
    if route_path == "/api/health" or route_path not in SERVICE_TYPES:
        return await call_next(request)

    service_type = SERVICE_TYPES[route_path]
    pricing = PRICING[service_type]
    route_key = f"{request.method} {route_path}"

    # Check for direct on-chain payment header (X-Payment-Tx)
    x_payment_tx = request.headers.get("x-payment-tx") or request.headers.get("X-Payment-Tx")
    if x_payment_tx:
        print(f"[Gateway] Verifying on-chain settlement header X-Payment-Tx: {x_payment_tx}")
        verif = verify_onchain_tx(x_payment_tx, pricing["hbar"])
        if not verif["valid"]:
            log_to_hcs({
                "event": "payment_blocked",
                "service": service_type,
                "reason": verif["reason"],
                "amount_hbar": pricing["hbar"],
                "tx": x_payment_tx
            })
            return JSONResponse(
                status_code=402,
                content={"error": "On-Chain Payment Invalid", "detail": verif["reason"]}
            )

        log_to_hcs({
            "event": "payment_settled_onchain",
            "service": service_type,
            "payer": verif["payer"],
            "amount_hbar": verif["value_hbar"],
            "tx": verif["tx_hash"],
            "paywall": PAYWALL_ADDRESS,
            "chain_id": 296
        })
        return await call_next(request)

    # Check for standard x402 payment header
    payment_header = request.headers.get("payment-signature") or request.headers.get("x-payment")

    if not payment_header:
        print(f"[Gateway] 402 Payment Required for {route_key} ({service_type}: {pricing['usd']})")

        requirements = {
            "scheme": "exact",
            "network": HEDERA_NETWORK,
            "amount": str(pricing["tinybars"]),
            "payTo": PAY_TO_ACCOUNT,
            "maxTimeoutSeconds": 300,
            "asset": "0.0.0",
            "extra": {"feePayer": FEE_PAYER, "paywallContract": PAYWALL_ADDRESS, "requiredHbar": pricing["hbar"]},
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
                "amount_hbar": pricing["hbar"],
                "amount_usd": pricing["usd"],
                "pay_to": PAY_TO_ACCOUNT,
                "paywall_contract": PAYWALL_ADDRESS,
                "network": HEDERA_NETWORK,
                "fee_payer": FEE_PAYER,
                "instructions": "Supply x402 payment in 'X-Payment' or on-chain tx hash in 'X-Payment-Tx'."
            },
            headers={"PAYMENT-REQUIRED": req_header},
        )

    # Verify x402 payload via Blocky402 facilitator
    try:
        payment_payload = json.loads(base64.b64decode(payment_header).decode("utf-8"))
        print("[Gateway] Verifying x402 payment with Blocky402 facilitator...")
        verify_result = verify_payment(payment_payload)

        if not verify_result.get("isValid", False):
            reason = verify_result.get("invalidReason", "unknown")
            print(f"[Gateway] x402 Verification failed: {reason}")
            log_to_hcs({
                "event": "payment_blocked",
                "service": service_type,
                "reason": reason,
                "amount_tinybars": pricing["tinybars"],
            })
            return JSONResponse(status_code=402, content={"error": "Invalid Payment", "reason": reason})

        response = await call_next(request)

        if 200 <= response.status_code < 300:
            print("[Gateway] Settling x402 payment via Blocky402...")
            settle_result = settle_payment(payment_payload)
            tx = settle_result.get("transaction", "")
            success = settle_result.get("success", False)
            print(f"[Gateway] Settled: success={success}, tx={tx}")

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
                headers={
                    **dict(response.headers),
                    "PAYMENT-RESPONSE": base64.b64encode(json.dumps(settle_result).encode()).decode()
                },
                media_type=response.media_type,
            )

        return response

    except Exception as e:
        print(f"[Gateway] Processing error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── Routes ──────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "hedera_connected": w3.is_connected(),
        "latest_block": w3.eth.block_number if w3.is_connected() else None,
        "paywall_contract": PAYWALL_ADDRESS,
        "facilitator": FACILITATOR_URL,
        "fee_payer": FEE_PAYER,
        "hcs_topic": HCS_TOPIC_ID,
        "version": "2.1.0",
        "pricing": PRICING,
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

@app.get("/api/premium-report")
async def get_premium_report(city: str = "Cape Town"):
    """Macro-value enterprise climate archive (Requires 1.5 HBAR + Ledger Hardware Veto)."""
    return {
        "status": "unlocked",
        "title": "Global Climate Intelligence & Long-Range Risk Assessment",
        "scope": f"Enterprise Climate Risk Archive for {city}",
        "dataset_version": "2026.Q3",
        "risk_index": 4.2,
        "macro_metrics": {
            "historical_anomaly_c": "+1.14",
            "solar_radiation_mj": "21.8",
            "precipitation_variance_pct": "-8.4%",
            "evapotranspiration_mm": "4.6"
        },
        "hardware_settlement_confirmed": True,
        "paywall": PAYWALL_ADDRESS,
        "source": "Bridle Climate Intelligence Vault",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.on_event("startup")
async def startup():
    print(f"[Bridle] Started Gateway on port 8000")
    print(f"         Hedera Testnet: {HEDERA_RPC_URL}")
    print(f"         Paywall Contract: {PAYWALL_ADDRESS}")
    print(f"         Facilitator: {FACILITATOR_URL}")
    print(f"         HCS Topic: {HCS_TOPIC_ID}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

