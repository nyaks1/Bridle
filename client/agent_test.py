import os
import time
from pathlib import Path
from dotenv import load_dotenv
import requests
from web3 import Web3

# Load credentials from project root .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

RPC_URL = os.getenv("HEDERA_RPC_URL", "https://testnet.hashio.io/api")
PRIVATE_KEY = os.getenv("OPERATOR_PRIVATE_KEY")
GATEWAY_URL = "http://127.0.0.1:8000/api/protected-resource"

# Bridle policy threshold
SPENDING_THRESHOLD_HBAR = 5.0

if not PRIVATE_KEY:
    raise ValueError("OPERATOR_PRIVATE_KEY not set in .env")

w3 = Web3(Web3.HTTPProvider(RPC_URL))
clean_key = PRIVATE_KEY if PRIVATE_KEY.startswith("0x") else f"0x{PRIVATE_KEY}"
account = w3.eth.account.from_key(clean_key)

print(f"Agent Wallet Address: {account.address}")
balance_wei = w3.eth.get_balance(account.address)
print(f"Current Balance: {w3.from_wei(balance_wei, 'ether')} HBAR\n")

# 1. Initial request to gated resource
print(f"--> Calling {GATEWAY_URL}...")
res = requests.get(GATEWAY_URL)

if res.status_code != 402:
    print(f"Unexpected status code: {res.status_code}")
    print(res.text)
    exit(0)

# 2. Parse 402 challenge
challenge = res.json()
print("Received 402 Payment Required Challenge:")
print(f"  - Paywall: {challenge.get('paywall_contract')}")
print(f"  - Required Amount: {challenge.get('amount_hbar')} HBAR")

amount_hbar = float(challenge.get("amount_hbar", 1.0))
paywall_target = challenge.get("paywall_contract")

# 3. Policy Gate: Check threshold
if amount_hbar > SPENDING_THRESHOLD_HBAR:
    print(f"\n[ALERT] Amount ({amount_hbar} HBAR) exceeds auto-approval threshold ({SPENDING_THRESHOLD_HBAR} HBAR).")
    print("--> Pausing for hardware confirmation (Ledger prompt required)...")
    # In full integration, Nyaks' Ledger CLI hook fires here
else:
    print(f"\n[OK] Amount ({amount_hbar} HBAR) within threshold ({SPENDING_THRESHOLD_HBAR} HBAR). Auto-settling on Hedera...")

# 4. Broadcast payment to contract
nonce = w3.eth.get_transaction_count(account.address)
tx = {
    "nonce": nonce,
    "to": Web3.to_checksum_address(paywall_target),
    "value": w3.to_wei(amount_hbar, "ether"),
    "gas": 100000,
    "gasPrice": w3.eth.gas_price,
    "chainId": 296,
}

print("Broadcasting transaction...")
signed_tx = w3.eth.account.sign_transaction(tx, private_key=clean_key)
tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
tx_hex = w3.to_hex(tx_hash)
print(f"Transaction sent! Hash: {tx_hex}")
print("Waiting for on-chain settlement confirmation...")

receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
if receipt.get("status") != 1:
    print("[ERROR] Transaction failed on-chain.")
    exit(1)

print("[SUCCESS] Payment settled on Hedera Testnet.")

# 5. Unlock protected resource with proof of payment
print("\n--> Requesting resource with 'X-Payment-Tx' header...")
headers = {"X-Payment-Tx": tx_hex}
unlock_res = requests.get(GATEWAY_URL, headers=headers)

print(f"Final Response ({unlock_res.status_code}):")
print(unlock_res.json())
