"""Bridle Autonomous Agent with Ledger Speculos Hardware Veto Loop.

Built for ETHOnline 2026:
- Hedera Track: AI & Agentic Payments on Hedera
- Ledger Track: AI Agents x Ledger

Workflow:
1. Service Discovery & Gemini Relevance Classification:
   Analyzes whether the metered API endpoint matches the user's task.
2. Two-Tiered Financial Policy Engine:
   - Micro-payments (<= 1.0 HBAR): Autonomously signs using software ECDSA key.
   - Macro-payments (> 1.0 HBAR): Pauses execution and routes the unsigned transaction
     to the Ledger Speculos Emulator (port 5000). Prompts operator on-screen for hardware approval.
3. Settlement & Access:
   - Micro-payments settle via Blocky402 facilitator / x402 on Hedera Testnet.
   - Macro-payments broadcast the hardware-signed transaction to BridlePaywall contract on Hedera EVM.
4. Tamper-Proof Audit:
   Logs every settlement, hardware confirmation, or hardware veto to Hedera Consensus Service (HCS).
"""

import os
import sys
import json
import time
import asyncio
import base64
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from dotenv import load_dotenv
import httpx
from web3 import Web3
from eth_account import Account
from google import genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from server.ledger_client import LedgerClient
except ImportError:
    from ledger_client import LedgerClient

# ── Environment & Config ─────────────────────────────────────────────────
env_path = Path(__file__).resolve().parent.parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

HEDERA_RPC_URL = os.getenv("HEDERA_RPC_URL", "https://testnet.hashio.io/api")
PRIVATE_KEY = os.getenv("OPERATOR_PRIVATE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HEDERA_ACCOUNT_ID = os.getenv("HEDERA_ACCOUNT_ID")
PAY_TO_ACCOUNT = os.getenv("PAY_TO_ACCOUNT", HEDERA_ACCOUNT_ID)
HCS_TOPIC_ID = os.getenv("HCS_TOPIC_ID", "0.0.10474223")
PAYWALL_ADDRESS = os.getenv("PAYWALL_CONTRACT_ADDRESS", "0x5442A862d2B11709045BE15015368c7dD6B9cfd8")
RESOURCE_SERVER_URL = os.getenv("RESOURCE_SERVER_URL", "http://127.0.0.1:8000")
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://api.testnet.blocky402.com")

HARDWARE_VETO_THRESHOLD_HBAR = float(os.getenv("HARDWARE_VETO_THRESHOLD_HBAR", "1.0"))
AGENT_TASK = os.getenv("AGENT_TASK", "Retrieve current weather and complete enterprise climate risk intelligence for Cape Town")

if not PRIVATE_KEY:
    raise ValueError("OPERATOR_PRIVATE_KEY not configured in .env")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not configured in .env")
if not HEDERA_ACCOUNT_ID:
    raise ValueError("HEDERA_ACCOUNT_ID not configured in .env")

clean_key = PRIVATE_KEY if PRIVATE_KEY.startswith("0x") else f"0x{PRIVATE_KEY}"
w3 = Web3(Web3.HTTPProvider(HEDERA_RPC_URL))
software_account = Account.from_key(clean_key)
ledger_client = LedgerClient()

# Endpoints configuration
ENDPOINTS = [
    {
        "path": "/api/weather",
        "name": "Weather API",
        "service_type": "weather_query",
        "cost_hbar": 0.05,
        "cost_usd": "$0.005",
        "tinybars": 500_000,
        "category": "micro"
    },
    {
        "path": "/api/weather-intelligence",
        "name": "Weather Intelligence",
        "service_type": "analytics_run",
        "cost_hbar": 0.50,
        "cost_usd": "$0.050",
        "tinybars": 5_000_000,
        "category": "micro"
    },
    {
        "path": "/api/forecast",
        "name": "Forecast API",
        "service_type": "forecast_batch",
        "cost_hbar": 0.20,
        "cost_usd": "$0.020",
        "tinybars": 2_000_000,
        "category": "micro"
    },
    {
        "path": "/api/premium-report",
        "name": "Enterprise Climate Archive",
        "service_type": "premium_report",
        "cost_hbar": 1.50,
        "cost_usd": "$1.500",
        "tinybars": 150_000_000,
        "category": "macro"
    },
]

# ── Gemini Client ────────────────────────────────────────────────────────
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ── HCS Audit Logging ────────────────────────────────────────────────────
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
        tx_id = str(tx.transaction_id)
        print(f"  [HCS] 📝 Logged to Topic {HCS_TOPIC_ID} (tx: {tx_id})")
        return tx_id
    except Exception as e:
        print(f"  [HCS] ⚠️ Logging error: {e}")
        return ""

# ── Gemini Service Classifier ────────────────────────────────────────────
def classify_service(endpoint: dict, task: str) -> dict:
    prompt = f"""Analyze this API endpoint and determine its relevance to the task.

Endpoint: {json.dumps(endpoint, indent=2)}
User Task: {task}

Respond with strictly valid JSON:
{{
  "relevant": true/false,
  "reason": "concise explanation",
  "value_assessment": "low/medium/high"
}}"""
    for attempt in range(3):
        try:
            response = gemini_client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            if attempt < 2:
                time.sleep(1.5)
                continue
            print(f"  [Gemini] Model notice ({e}). Using heuristic classification fallback.")
            task_lower = task.lower()
            name_lower = endpoint.get("name", "").lower()
            path_lower = endpoint.get("path", "").lower()
            keywords = [w for w in task_lower.replace(",", "").split() if len(w) > 3]
            is_relevant = any(w in name_lower or w in path_lower for w in keywords)
            return {
                "relevant": is_relevant,
                "reason": f"Heuristic assessment: {'relevant to task keywords' if is_relevant else 'not primary match for task'}",
                "value_assessment": "high" if is_relevant else "low",
            }

# ── Facilitator & Signing Helpers ────────────────────────────────────────
def get_fee_payer() -> str:
    try:
        resp = httpx.get(f"{FACILITATOR_URL}/supported", timeout=10)
        data = resp.json()
        return data.get("signers", {}).get("hedera:*", ["0.0.7162784"])[0]
    except Exception:
        return "0.0.7162784"

def sign_hedera_micro_payment(amount_tinybars: int, pay_to: str, fee_payer: str) -> dict:
    """Construct and sign a native Hedera TransferTransaction for micro-payments."""
    from hiero_sdk_python import (
        Client, AccountId, PrivateKey, TransferTransaction, Hbar, TransactionId,
    )
    client = Client.for_testnet()
    payer_id = AccountId.from_string(HEDERA_ACCOUNT_ID)
    payee_id = AccountId.from_string(pay_to)
    fee_payer_id = AccountId.from_string(fee_payer)
    key = PrivateKey.from_string_ecdsa(clean_key)
    client.set_operator(payer_id, key)

    tx_id = TransactionId.generate(fee_payer_id)
    tx = TransferTransaction().set_transaction_id(tx_id)
    tx.add_hbar_transfer(payer_id, Hbar.from_tinybars(-amount_tinybars))
    tx.add_hbar_transfer(payee_id, Hbar.from_tinybars(amount_tinybars))

    frozen = tx.freeze_with(client)
    signed = frozen.sign(key)
    payload_b64 = base64.b64encode(signed.to_bytes()).decode("utf-8")

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
            "asset": "0.0.0",
            "extra": {"feePayer": fee_payer},
        },
        "payload": {
            "transaction": payload_b64,
        },
    }

# ── Ledger Hardware Veto Execution ───────────────────────────────────────
def execute_hardware_veto_loop(
    endpoint: dict,
    auto_approve: bool = False,
    force_veto: bool = False
) -> Optional[str]:
    """Routes high-value transaction to Ledger Speculos emulator.

    Pauses autonomous loop and requires human device confirmation.
    Returns transaction hash if approved, or None if vetoed.
    """
    cost_hbar = endpoint["cost_hbar"]
    name = endpoint["name"]
    target_contract = Web3.to_checksum_address(PAYWALL_ADDRESS)

    border = "═" * 60
    print(f"\n╔{border}╗")
    print(f"║  🛡️  [HARDWARE VETO HOOK TRIGGERED]                       ║")
    print(f"╠{border}╣")
    print(f"║  Endpoint: {name.ljust(47)}║")
    print(f"║  Amount: {str(cost_hbar).ljust(5)} HBAR (> Threshold {HARDWARE_VETO_THRESHOLD_HBAR} HBAR)             ║")
    print(f"║  Policy: Execution paused. Hardware confirmation required. ║")
    print(f"║  Target Contract: {target_contract.ljust(41)}║")
    print(f"╚{border}╝\n")

    if not ledger_client.is_available():
        print("  [Ledger] ⚠️ Speculos emulator not responding at http://127.0.0.1:5000!")
        print("  [Ledger] Starting Speculos emulator bridge...")
        import subprocess
        subprocess.run(["bash", "scripts/run_speculos.sh"], capture_output=True)
        time.sleep(2)

    device_address = ledger_client.get_address() or software_account.address
    print(f"  [Ledger] Connected to Speculos (Device Address: {device_address})")

    # Fetch nonce on Hedera Testnet
    try:
        nonce = w3.eth.get_transaction_count(Web3.to_checksum_address(device_address))
    except Exception:
        nonce = 0

    print(f"  [Ledger] Routing unsigned transaction to Speculos OLED screen...")
    review_res = ledger_client.submit_for_hardware_review(
        to_address=target_contract,
        value_hbar=cost_hbar,
        nonce=nonce,
        chain_id=296,
        auto_approve=auto_approve and not force_veto
    )

    if force_veto:
        print("  [Ledger] 🛑 Human Operator pressed [LEFT BUTTON] -> VETO TRANSACTION!")
        veto_res = ledger_client.veto_transaction()
        print(f"  [Ledger] Speculos Response: {veto_res.get('message', 'Action refused by user')}")
        log_to_hcs({
            "event": "payment_rejected_by_hardware_veto",
            "agent": HEDERA_ACCOUNT_ID,
            "device": device_address,
            "service": name,
            "amount_hbar": cost_hbar,
            "threshold_hbar": HARDWARE_VETO_THRESHOLD_HBAR,
            "reason": "operator_hardware_veto (status: 0x6985)"
        })
        return None

    # Check if review was auto-approved or requires confirmation
    if review_res.get("status") == "approved":
        signed_raw = review_res.get("signed_tx_raw")
    else:
        # Prompt human operator in CLI if interactive
        if not auto_approve:
            print("\n  👉 Please confirm on the Speculos screen:")
            print("     Type 'y' to APPROVE (press both buttons) or 'n' to VETO (press left button):")
            choice = input("     [y/n]: ").strip().lower()
            if choice != "y":
                print("  [Ledger] 🛑 Operator selected VETO.")
                ledger_client.veto_transaction()
                log_to_hcs({
                    "event": "payment_rejected_by_hardware_veto",
                    "agent": HEDERA_ACCOUNT_ID,
                    "device": device_address,
                    "service": name,
                    "amount_hbar": cost_hbar,
                    "reason": "operator_manual_veto"
                })
                return None
            confirm_res = ledger_client.approve_transaction()
            signed_raw = confirm_res.get("signed_tx_raw")
        else:
            confirm_res = ledger_client.approve_transaction()
            signed_raw = confirm_res.get("signed_tx_raw")

    print(f"  [Ledger] ✅ Hardware signature received! Broadcasting to Hedera Testnet...")
    try:
        raw_bytes = bytes.fromhex(signed_raw[2:] if signed_raw.startswith("0x") else signed_raw)
        tx_hash_bytes = w3.eth.send_raw_transaction(raw_bytes)
        tx_hash = w3.to_hex(tx_hash_bytes)
        print(f"  [Ledger] 🚀 Broadcast successful! Tx Hash: {tx_hash}")

        log_to_hcs({
            "event": "payment_settled_with_hardware_approval",
            "agent": HEDERA_ACCOUNT_ID,
            "device": device_address,
            "service": name,
            "amount_hbar": cost_hbar,
            "tx": tx_hash,
            "paywall": target_contract,
            "chain_id": 296
        })
        return tx_hash

    except Exception as e:
        print(f"  [Ledger] ⚠️ Broadcast failed: {e}")
        # Even if Hedera RPC returned nonce collision, use hash if present
        return None

# ── Main Endpoint Processing Flow ────────────────────────────────────────
async def process_endpoint(
    endpoint: dict,
    auto_approve_hardware: bool = False,
    force_hardware_veto: bool = False
) -> bool:
    url = f"{RESOURCE_SERVER_URL}{endpoint['path']}"
    name = endpoint["name"]
    service_type = endpoint["service_type"]
    cost_hbar = endpoint["cost_hbar"]
    tinybars = endpoint["tinybars"]

    print(f"\n{'='*60}")
    print(f"  {name} — {url}")
    print(f"  Pricing: {cost_hbar} HBAR ({endpoint['cost_usd']})")
    print(f"{'='*60}")

    # Stage 1: Gemini Service Classification
    print("  [Gemini] Analyzing service relevance to agent task...")
    analysis = classify_service(endpoint, AGENT_TASK)
    print(f"  [Gemini] Relevant: {analysis.get('relevant')} | Reason: {analysis.get('reason')}")

    if not analysis.get("relevant", True):
        print(f"  [SKIP] Skipping endpoint: {analysis.get('reason')}")
        log_to_hcs({
            "event": "service_skipped",
            "agent": HEDERA_ACCOUNT_ID,
            "service": name,
            "reason": analysis.get("reason"),
        })
        return False

    # Stage 2: Deterministic Policy Check (Hardware Veto vs Autonomous Signing)
    if cost_hbar > HARDWARE_VETO_THRESHOLD_HBAR:
        print(f"  [POLICY] Amount ({cost_hbar} HBAR) exceeds autonomous threshold ({HARDWARE_VETO_THRESHOLD_HBAR} HBAR).")
        print("  [POLICY] Pausing autonomous execution -> Routing to Ledger Speculos Emulator...")

        tx_hash = execute_hardware_veto_loop(
            endpoint,
            auto_approve=auto_approve_hardware,
            force_veto=force_hardware_veto
        )

        if not tx_hash:
            print(f"  [BLOCKED] Transaction aborted by hardware veto. Zero funds transferred.")
            return False

        # Access resource with on-chain payment proof
        print(f"  [Access] Requesting resource with hardware payment proof: X-Payment-Tx: {tx_hash}...")
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers={"X-Payment-Tx": tx_hash},
                timeout=30
            )
            print(f"  [Access] Status: {resp.status_code}")
            try:
                print(f"  [Access] Payload:\n{json.dumps(resp.json(), indent=2)}")
            except Exception:
                print(f"  [Access] Content: {resp.text[:300]}")
        return True

    # Stage 3: Autonomous Micro-Payment (< 1.0 HBAR)
    print(f"  [POLICY] Amount ({cost_hbar} HBAR) <= threshold ({HARDWARE_VETO_THRESHOLD_HBAR} HBAR) -> Auto-Signing allowed.")

    # Request resource to get 402 challenge
    print(f"  [x402] Requesting {url}...")
    async with httpx.AsyncClient() as client:
        initial_resp = await client.get(url, timeout=30)
        if initial_resp.status_code != 402:
            print(f"  [x402] Unexpected status: {initial_resp.status_code}")
            return False

        print("  [x402] Received 402 Payment Required. Constructing Hedera transfer...")
        body = initial_resp.json()
        amount_tinybars = int(body.get("amount_tinybars", tinybars))
        pay_to = body.get("pay_to", PAY_TO_ACCOUNT)
        fee_payer = body.get("fee_payer", get_fee_payer())

    # Sign micro-payment using software ECDSA key
    payment_payload = sign_hedera_micro_payment(amount_tinybars, pay_to, fee_payer)
    x_payment_b64 = base64.b64encode(json.dumps(payment_payload).encode()).decode()

    # Submit to gateway
    print("  [x402] Submitting signed payment to gateway for execution and settlement...")
    async with httpx.AsyncClient() as client:
        resource_resp = await client.get(
            url,
            headers={"X-PAYMENT": x_payment_b64},
            timeout=30
        )
        print(f"  [x402] Status: {resource_resp.status_code}")

        pay_resp_header = resource_resp.headers.get("payment-response") or resource_resp.headers.get("PAYMENT-RESPONSE")
        tx_hash = ""
        if pay_resp_header:
            try:
                settle_data = json.loads(base64.b64decode(pay_resp_header).decode("utf-8"))
                tx_hash = settle_data.get("transaction", "")
                if tx_hash:
                    print(f"  [x402] Payment settled on Hedera Testnet: {tx_hash}")
            except Exception:
                pass

        try:
            print(f"  [x402] Unlocked Response:\n{json.dumps(resource_resp.json(), indent=2)}")
        except Exception:
            print(f"  [x402] Response: {resource_resp.text[:300]}")

    log_to_hcs({
        "event": "payment_settled",
        "agent": HEDERA_ACCOUNT_ID,
        "service": name,
        "service_type": service_type,
        "amount_tinybars": amount_tinybars,
        "amount_hbar": cost_hbar,
        "tx": tx_hash,
        "gemini_reasoning": analysis.get("reason", "")
    })
    return True

# ── Runner Loop ──────────────────────────────────────────────────────────
async def run_agent(auto_approve: bool = False, force_veto: bool = False, single_endpoint: Optional[str] = None):
    print("=" * 60)
    print("  BRIDLE AGENT — Dual-Rail Hedera & Ledger Security")
    print("=" * 60)
    print(f"  Hedera Account:     {HEDERA_ACCOUNT_ID}")
    print(f"  Paywall Contract:   {PAYWALL_ADDRESS}")
    print(f"  Facilitator:        {FACILITATOR_URL}")
    print(f"  HCS Audit Topic:    {HCS_TOPIC_ID}")
    print(f"  Hardware Threshold: {HARDWARE_VETO_THRESHOLD_HBAR} HBAR")
    print(f"  Task:               {AGENT_TASK}")
    print(f"  Speculos Available: {ledger_client.is_available()}")
    print("=" * 60)

    selected = [ep for ep in ENDPOINTS if single_endpoint is None or ep["path"] == single_endpoint]
    settled = 0
    blocked = 0

    for ep in selected:
        ok = await process_endpoint(ep, auto_approve_hardware=auto_approve, force_hardware_veto=force_veto)
        if ok:
            settled += 1
        else:
            blocked += 1

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    print(f"  Settled Transactions: {settled}")
    print(f"  Blocked / Vetoed:     {blocked}")
    print(f"  Total Audit Events:   {settled + blocked}")
    print(f"{'='*60}")

if __name__ == "__main__":
    auto = "--auto-approve" in sys.argv or os.getenv("LEDGER_AUTO_APPROVE", "0") == "1"
    veto = "--veto" in sys.argv or os.getenv("LEDGER_FORCE_VETO", "0") == "1"
    target = None
    for arg in sys.argv:
        if arg.startswith("--endpoint="):
            target = arg.split("=", 1)[1]

    asyncio.run(run_agent(auto_approve=auto, force_veto=veto, single_endpoint=target))
