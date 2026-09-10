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

def verify_payment(x_payment_tx: str, required_amount: float) -> dict:
    """Verify a payment transaction on Hedera."""
    tx_hash = x_payment_tx.strip()
    tx = w3.eth.get_transaction(tx_hash)
    receipt = w3.eth.get_transaction_receipt(tx_hash)

    if receipt is None or receipt.get("status") != 1:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Transaction pending, failed, or reverted on Hedera."
        )

    target_contract = Web3.to_checksum_address(PAYWALL_ADDRESS)
    if not tx.get("to") or Web3.to_checksum_address(tx["to"]) != target_contract:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transaction recipient does not match paywall contract {target_contract}"
        )

    value_in_hbar = float(w3.from_wei(tx["value"], "ether"))
    if value_in_hbar < required_amount:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient payment: sent {value_in_hbar} HBAR, required {required_amount} HBAR"
        )

    return {
        "payer": tx["from"],
        "settled_amount_hbar": value_in_hbar,
        "tx_hash": tx_hash
    }

@app.get("/api/protected-resource")
def get_protected_resource(
    response: Response,
    x_payment_tx: str | None = Header(default=None, convert_underscores=True)
):
    REQUIRED_AMOUNT_HBAR = 1.0

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

    try:
        payment = verify_payment(x_payment_tx, REQUIRED_AMOUNT_HBAR)
        return {
            "status": "unlocked",
            "payer": payment["payer"],
            "settled_amount_hbar": payment["settled_amount_hbar"],
            "tx_hash": payment["tx_hash"],
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

@app.get("/api/premium-data")
def get_premium_data(
    response: Response,
    x_payment_tx: str | None = Header(default=None, convert_underscores=True)
):
    REQUIRED_AMOUNT_HBAR = 10.0

    if not x_payment_tx:
        response.status_code = status.HTTP_402_PAYMENT_REQUIRED
        return {
            "error": "Payment Required",
            "message": "Premium data access requires payment via BridlePaywall",
            "chain_id": 296,
            "paywall_contract": PAYWALL_ADDRESS,
            "amount_hbar": REQUIRED_AMOUNT_HBAR,
            "service": {
                "name": "Bridle Global Weather Intelligence",
                "description": "Enterprise-grade weather intelligence with 90-day historical data, severe weather alerts, agricultural forecasting, and climate trend analysis. Covers all global locations with 1-minute resolution data.",
                "endpoint": "/api/weather-intelligence",
                "data_returned": "JSON with historical weather, alerts, forecasts, and climate trends"
            },
            "instructions": "Submit a transfer to the contract and supply tx hash in 'X-Payment-Tx' header."
        }

    try:
        payment = verify_payment(x_payment_tx, REQUIRED_AMOUNT_HBAR)
        return {
            "status": "unlocked",
            "payer": payment["payer"],
            "settled_amount_hbar": payment["settled_amount_hbar"],
            "tx_hash": payment["tx_hash"],
            "data": {
                "secret_payload": "Bridle Global Weather Intelligence: Access granted to enterprise weather data."
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error verifying transaction: {str(e)}"
        )
