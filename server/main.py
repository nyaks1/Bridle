import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Response, status
from pydantic import BaseModel
from web3 import Web3

# Load .env from project root or server root
env_path = Path(__file__).resolve().parent.parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

RPC_URL = os.getenv("HEDERA_RPC_URL", "https://testnet.hashio.io/api")
PAYWALL_ADDRESS = os.getenv("PAYWALL_CONTRACT_ADDRESS", "0x5442A862d2B11709045BE15015368c7dD6B9cfd8")
REQUIRED_AMOUNT_HBAR = 1.0  # Challenge cost in HBAR

w3 = Web3(Web3.HTTPProvider(RPC_URL))

app = FastAPI(title="Bridle HTTP 402 Paywall Gateway")

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "hedera_connected": w3.is_connected(),
        "paywall_address": PAYWALL_ADDRESS,
        "latest_block": w3.eth.block_number if w3.is_connected() else None
    }

@app.get("/api/protected-resource")
def get_protected_resource(
    response: Response,
    x_payment_tx: str | None = Header(default=None, convert_underscores=True)
):
    # Case 1: No payment header provided -> Return 402 Payment Required
    if not x_payment_tx:
        response.status_code = status.HTTP_402_PAYMENT_REQUIRED
        return {
            "error": "Payment Required",
            "message": "Access requires payment via BridlePaywall",
            "chain_id": 296,
            "paywall_contract": PAYWALL_ADDRESS,
            "amount_hbar": REQUIRED_AMOUNT_HBAR,
            "service": {
                "name": "Bridle Weather API",
                "description": "Real-time weather data for any location. Returns temperature, humidity, wind speed, and 5-day forecast. Rate-limited to 100 requests per hour after payment.",
                "endpoint": "/api/weather",
                "data_returned": "JSON with current conditions and forecast"
            },
            "instructions": "Submit a transfer to the contract and supply tx hash in 'X-Payment-Tx' header."
        }

    # Case 2: Verify the provided transaction hash on Hedera Testnet
    try:
        tx_hash = x_payment_tx.strip()
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)

        if receipt is None or receipt.get("status") != 1:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Transaction pending, failed, or reverted on Hedera."
            )

        # Check destination address matches the Paywall contract
        target_contract = Web3.to_checksum_address(PAYWALL_ADDRESS)
        if not tx.get("to") or Web3.to_checksum_address(tx["to"]) != target_contract:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transaction recipient does not match paywall contract {target_contract}"
            )

        # Check value delivered matches required threshold
        value_in_hbar = float(w3.from_wei(tx["value"], "ether"))
        if value_in_hbar < REQUIRED_AMOUNT_HBAR:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Insufficient payment: sent {value_in_hbar} HBAR, required {REQUIRED_AMOUNT_HBAR} HBAR"
            )

        # Payment validated successfully -> return protected content
        return {
            "status": "unlocked",
            "payer": tx["from"],
            "settled_amount_hbar": value_in_hbar,
            "tx_hash": tx_hash,
            "data": {
                "secret_payload": "Bridle Protocol Gateway: Access granted to protected API payload."
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error verifying transaction: {str(e)}"
        )
