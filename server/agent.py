import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
import requests
import google.generativeai as genai
from web3 import Web3

# Load environment
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Configuration
RPC_URL = os.getenv("HEDERA_RPC_URL", "https://testnet.hashio.io/api")
PRIVATE_KEY = os.getenv("OPERATOR_PRIVATE_KEY")
GATEWAY_URL = "http://127.0.0.1:8000/api/protected-resource"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SPENDING_THRESHOLD_HBAR = float(os.getenv("SPENDING_THRESHOLD_HBAR", "5.0"))
HCS_TOPIC_ID = os.getenv("HCS_TOPIC_ID", "")

# Validate
if not PRIVATE_KEY:
    raise ValueError("OPERATOR_PRIVATE_KEY not set in .env")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set in .env")

# Initialize
w3 = Web3(Web3.HTTPProvider(RPC_URL))
clean_key = PRIVATE_KEY if PRIVATE_KEY.startswith("0x") else f"0x{PRIVATE_KEY}"
account = w3.eth.account.from_key(clean_key)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

def log_to_hcs(event: dict) -> str:
    """Log an event to Hedera Consensus Service.
    Returns the message ID or empty string if no topic configured."""
    if not HCS_TOPIC_ID:
        print("[HCS] No topic ID configured, skipping log")
        return ""

    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    message = json.dumps(event)

    print(f"[HCS] Logging: {event.get('event', 'unknown')} - {message}")

    # TODO: Submit to HCS via Hedera SDK or REST API
    return f"hcs-message-{int(time.time())}"

def is_payment_allowed(amount: float, threshold: float) -> bool:
    """Deterministic policy check — never delegate this to LLM."""
    return amount <= threshold

def classify_service(service_desc: str, task: str) -> str:
    """Use Gemini to classify whether a service matches a task."""
    response = model.generate_content(
        f"Given this service description: {service_desc}, "
        f"does it match the task: {task}? Answer yes or no with a one-line reason."
    )
    return response.text

def run_agent():
    """Main agent loop."""
    print("=" * 60)
    print("BRIDLE AGENT - x402 Payment Gateway")
    print("=" * 60)
    print(f"Agent Wallet: {account.address}")
    balance_wei = w3.eth.get_balance(account.address)
    print(f"Balance: {w3.from_wei(balance_wei, 'ether')} HBAR")
    print(f"Threshold: {SPENDING_THRESHOLD_HBAR} HBAR")
    print("=" * 60)

    # Step 1: Request gated resource
    print(f"\n--> Requesting {GATEWAY_URL}...")
    res = requests.get(GATEWAY_URL)

    if res.status_code != 402:
        print(f"Unexpected status: {res.status_code}")
        print(res.text)
        return

    # Step 2: Parse 402 challenge
    challenge = res.json()
    print("Received 402 Payment Required:")
    print(json.dumps(challenge, indent=2))

    amount = float(challenge.get("amount_hbar", 0))
    paywall = challenge.get("paywall_contract")

    # Step 3: Policy gate — deterministic, not LLM
    if not is_payment_allowed(amount, SPENDING_THRESHOLD_HBAR):
        event = {
            "event": "payment_blocked",
            "agent": account.address,
            "amount_hbar": amount,
            "threshold": SPENDING_THRESHOLD_HBAR,
            "reason": "exceeds_policy_threshold",
            "paywall": paywall,
        }
        log_to_hcs(event)
        print(f"\n[BLOCKED] Payment of {amount} HBAR rejected by policy.")
        return

    # Step 4: Auto-settle
    print(f"\n[OK] Amount ({amount} HBAR) within threshold. Settling on Hedera...")

    nonce = w3.eth.get_transaction_count(account.address)
    tx = {
        "nonce": nonce,
        "to": Web3.to_checksum_address(paywall),
        "value": w3.to_wei(amount, "ether"),
        "gas": 100000,
        "gasPrice": w3.eth.gas_price,
        "chainId": 296,
    }

    print("Broadcasting transaction...")
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=clean_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    tx_hex = w3.to_hex(tx_hash)
    print(f"Transaction sent: {tx_hex}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt.get("status") != 1:
        print("[ERROR] Transaction failed on-chain.")
        return

    print("[SUCCESS] Payment settled on Hedera Testnet.")

    event = {
        "event": "payment_settled",
        "agent": account.address,
        "amount_hbar": amount,
        "tx_hash": tx_hex,
        "paywall": paywall,
    }
    log_to_hcs(event)

    # Step 5: Unlock resource
    print("\n--> Unlocking protected resource...")
    headers = {"X-Payment-Tx": tx_hex}
    unlock_res = requests.get(GATEWAY_URL, headers=headers)

    print(f"\nFinal Response ({unlock_res.status_code}):")
    print(json.dumps(unlock_res.json(), indent=2))

if __name__ == "__main__":
    run_agent()
