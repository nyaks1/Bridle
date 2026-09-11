"""Speculos Ledger Nano Emulator Bridge for Bridle.

Provides the official Speculos REST API on port 5000:
- POST /apdu: Raw APDU execution
- POST /sign-tx: High-level hardware signing endpoint with OLED screen visualization
- POST /events & /button/*: Hardware button press simulation
- GET /screen: Current OLED screen text
- GET /health: Healthcheck endpoint

Allows full reproduction of the Ledger Hardware Veto Loop with or without Docker.
"""

import os
import sys
import json
import base64
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Hardware wallet seed / key simulation (Ledger Nano S+ Test Mnemonic key)
LEDGER_PRIVATE_KEY = os.getenv("LEDGER_DEVICE_KEY") or os.getenv("OPERATOR_PRIVATE_KEY", "0xdfa3dd44ffffb63c749114974eb9bab0d6429e27c57ab9577723b8919f4be965")
if not LEDGER_PRIVATE_KEY.startswith("0x"):
    LEDGER_PRIVATE_KEY = f"0x{LEDGER_PRIVATE_KEY}"

ledger_account = Account.from_key(LEDGER_PRIVATE_KEY)

app = FastAPI(title="Speculos Ledger Nano Emulator", version="1.0.0")

class ApduRequest(BaseModel):
    data: str

class ButtonEvent(BaseModel):
    action: str = "press-and-release"

class TxSignRequest(BaseModel):
    to: str
    value_hbar: float
    data: Optional[str] = "0x"
    nonce: int
    gas_limit: int = 100000
    gas_price_wei: Optional[int] = None
    chain_id: int = 296
    auto_approve: bool = False

current_screen: Dict[str, Any] = {
    "title": "Ethereum App Ready",
    "lines": ["Ledger Nano S+", "Awaiting command..."],
    "pending_tx": None,
    "status": "idle"
}

def render_oled(title: str, lines: list):
    border = "═" * 46
    print(f"\n┌{border}┐")
    print(f"│  📟 [LEDGER NANO S+ OLED SCREEN]             │")
    print(f"├{border}┤")
    print(f"│  {title.center(44)}│")
    for line in lines:
        print(f"│  {line.ljust(44)}│")
    print(f"└{border}┘\n")

from fastapi.responses import JSONResponse, HTMLResponse

@app.get("/", response_class=HTMLResponse)
def index_ui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ledger Nano S+ — Speculos Hardware Emulator</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: #0b0f19;
            color: #f1f5f9;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 24px;
        }
        .container {
            max-width: 820px;
            width: 100%;
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 20px;
            padding: 36px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
        }
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 28px;
            border-bottom: 1px solid #1f2937;
            padding-bottom: 16px;
        }
        .header h1 {
            font-size: 1.4rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
            color: #ffffff;
        }
        .badge {
            background: #065f46;
            color: #6ee7b7;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .badge::before {
            content: "";
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #10b981;
            border-radius: 50%;
            box-shadow: 0 0 8px #10b981;
        }

        /* Ledger Hardware Chassis */
        .ledger-chassis {
            background: linear-gradient(145deg, #1e2530, #141820);
            border-radius: 18px;
            padding: 24px;
            margin: 28px auto;
            max-width: 620px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.1);
            position: relative;
            border: 2px solid #2d3748;
        }
        .hardware-buttons {
            display: flex;
            justify-content: space-between;
            margin-bottom: 16px;
            padding: 0 40px;
        }
        .hw-btn {
            background: #2b3544;
            color: #e2e8f0;
            border: 1px solid #4a5568;
            border-radius: 8px;
            padding: 8px 18px;
            font-size: 0.8rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.15s ease;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            user-select: none;
        }
        .hw-btn:hover { background: #3b4759; transform: translateY(-1px); }
        .hw-btn:active { background: #1a202c; transform: translateY(2px); box-shadow: none; }
        .hw-btn.both-btn {
            background: #3b82f6;
            color: #ffffff;
            border-color: #60a5fa;
        }
        .hw-btn.both-btn:hover { background: #2563eb; }
        .hw-btn.veto-btn {
            background: #dc2626;
            color: #ffffff;
            border-color: #f87171;
        }
        .hw-btn.veto-btn:hover { background: #b91c1c; }

        /* OLED Display */
        .oled-screen {
            background: #020617;
            border: 3px solid #1e293b;
            border-radius: 10px;
            padding: 20px 24px;
            font-family: "Courier New", Courier, monospace;
            color: #38bdf8;
            min-height: 140px;
            box-shadow: inset 0 0 20px rgba(56, 189, 248, 0.15), 0 0 10px rgba(0, 0, 0, 0.8);
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .oled-title {
            font-size: 1.15rem;
            font-weight: 800;
            color: #ffffff;
            text-align: center;
            letter-spacing: 1px;
            margin-bottom: 12px;
            text-transform: uppercase;
            border-bottom: 1px dashed #1e3a8a;
            padding-bottom: 6px;
        }
        .oled-line {
            font-size: 0.95rem;
            color: #7dd3fc;
            line-height: 1.6;
            white-space: pre-wrap;
            word-break: break-all;
        }

        /* Controls & Metadata */
        .controls {
            display: flex;
            gap: 12px;
            justify-content: center;
            margin-top: 24px;
        }
        .btn {
            padding: 12px 24px;
            border-radius: 10px;
            font-weight: 600;
            font-size: 0.95rem;
            border: none;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .btn-success { background: #10b981; color: white; }
        .btn-success:hover { background: #059669; }
        .btn-danger { background: #ef4444; color: white; }
        .btn-danger:hover { background: #dc2626; }
        .btn-secondary { background: #374151; color: #f3f4f6; }
        .btn-secondary:hover { background: #4b5563; }

        .meta-grid {
            margin-top: 32px;
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            font-size: 0.85rem;
        }
        .meta-card {
            background: #1f2937;
            border: 1px solid #374151;
            padding: 12px 16px;
            border-radius: 10px;
        }
        .meta-label { color: #9ca3af; margin-bottom: 4px; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; }
        .meta-val { color: #e2e8f0; font-family: monospace; word-break: break-all; font-size: 0.85rem; }
        .pulse { animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 8h10M7 12h10M7 16h6"/></svg>
                Ledger Speculos Hardware Emulator
            </h1>
            <span class="badge" id="conn-badge">Hardware Connected</span>
        </div>

        <p style="color: #94a3b8; font-size: 0.9rem; text-align: center; margin-bottom: 8px;">
            Human-in-the-loop Hardware Veto Hook for autonomous AI agent transactions (> 1.0 HBAR).
        </p>

        <!-- Simulated Physical Device -->
        <div class="ledger-chassis">
            <div class="hardware-buttons">
                <button class="hw-btn veto-btn" onclick="triggerVeto()">◀ Left (VETO)</button>
                <button class="hw-btn" onclick="triggerRight()">Right (Next) ▶</button>
                <button class="hw-btn both-btn" onclick="triggerApproval()">● Both Buttons (APPROVE)</button>
            </div>

            <div class="oled-screen" id="oled-display">
                <div class="oled-title" id="screen-title">Ethereum App Ready</div>
                <div id="screen-lines">
                    <div class="oled-line">Ledger Nano S+ (Chain ID: 296)</div>
                    <div class="oled-line">Awaiting macro-payment challenge...</div>
                </div>
            </div>
        </div>

        <!-- Action Bar -->
        <div class="controls">
            <button class="btn btn-danger" onclick="triggerVeto()">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                Veto Transaction (Left Button)
            </button>
            <button class="btn btn-success" onclick="triggerApproval()">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                Approve & Sign on Hardware (Both Buttons)
            </button>
        </div>

        <!-- Device & Network Metadata -->
        <div class="meta-grid">
            <div class="meta-card">
                <div class="meta-label">Device Address</div>
                <div class="meta-val" id="dev-addr">""" + ledger_account.address + """</div>
            </div>
            <div class="meta-card">
                <div class="meta-label">Target Network</div>
                <div class="meta-val">Hedera Testnet (Chain ID 296)</div>
            </div>
            <div class="meta-card">
                <div class="meta-label">BridlePaywall Contract</div>
                <div class="meta-val">0x5442A862d2B11709045BE15015368c7dD6B9cfd8</div>
            </div>
            <div class="meta-card">
                <div class="meta-label">Hedera HCS Audit Stream</div>
                <div class="meta-val">Topic ID: 0.0.10474223</div>
            </div>
        </div>
    </div>

    <script>
        async function fetchScreen() {
            try {
                const res = await fetch('/screen');
                const data = await res.json();
                document.getElementById('screen-title').innerText = data.title || 'Ledger Ready';
                const linesContainer = document.getElementById('screen-lines');
                linesContainer.innerHTML = '';
                (data.lines || []).forEach(line => {
                    const el = document.createElement('div');
                    el.className = 'oled-line';
                    el.innerText = line;
                    linesContainer.appendChild(el);
                });
            } catch (err) {
                console.error('Polling error:', err);
            }
        }

        async function triggerApproval() {
            try {
                const res = await fetch('/confirm-approval', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'approved') {
                    alert('✅ Transaction APPROVED on Ledger Hardware! Tx Hash: ' + data.tx_hash);
                }
                fetchScreen();
            } catch (err) {
                alert('Approval notice: ' + err);
            }
        }

        async function triggerVeto() {
            try {
                const res = await fetch('/confirm-veto', { method: 'POST' });
                const data = await res.json();
                alert('🛑 Transaction VETOED! Hardware status 0x6985 returned.');
                fetchScreen();
            } catch (err) {
                alert('Veto notice: ' + err);
            }
        }

        async function triggerRight() {
            await fetch('/button/right', { method: 'POST' });
            fetchScreen();
        }

        // Live polling every 500ms
        setInterval(fetchScreen, 500);
        fetchScreen();
    </script>
</body>
</html>
"""

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "model": "nanosp",
        "app": "Ethereum",
        "version": "1.12.0",
        "address": ledger_account.address,
        "screen_status": current_screen["status"]
    }

@app.get("/screen")
def get_screen():
    return current_screen

@app.post("/apdu")
def handle_apdu(req: ApduRequest):
    """Handle standard Ethereum app APDU bytes (hex)."""
    raw_hex = req.data.strip().lower()
    if raw_hex.startswith("0x"):
        raw_hex = raw_hex[2:]

    # E.g. get public address APDU (CLA: e0, INS: 02)
    if raw_hex.startswith("e002"):
        addr_bytes = ledger_account.address.encode("utf-8")
        resp_hex = addr_bytes.hex() + "9000"
        return {"data": resp_hex}

    # Default success response
    return {"data": "9000"}

@app.post("/button/left")
@app.post("/events/left")
def press_left(event: Optional[ButtonEvent] = None):
    """Simulate left button press: Reject / Cancel."""
    if current_screen["pending_tx"]:
        print("[Speculos] ❌ Left button pressed: Transaction VETOED by human operator.")
        current_screen["status"] = "vetoed"
        current_screen["title"] = "Transaction Vetoed"
        current_screen["lines"] = ["Action cancelled by operator.", "Status: 0x6985 (VETO)"]
        render_oled(current_screen["title"], current_screen["lines"])
        return {"status": "vetoed", "code": "0x6985", "message": "Action refused by user"}
    return {"status": "idle"}

@app.post("/button/right")
@app.post("/events/right")
def press_right(event: Optional[ButtonEvent] = None):
    """Simulate right button press: Scroll / Next screen."""
    return {"status": "scrolled"}

@app.post("/button/both")
@app.post("/events")
def press_both(event: Optional[ButtonEvent] = None):
    """Simulate pressing both buttons: Approve / Confirm."""
    if current_screen["pending_tx"]:
        print("[Speculos] ✅ Both buttons pressed: Transaction APPROVED on hardware device.")
        tx = current_screen["pending_tx"]
        current_screen["status"] = "approved"
        current_screen["title"] = "Transaction Approved"
        current_screen["lines"] = ["Signing transaction with", f"Device Key: {ledger_account.address[:10]}..."]
        render_oled(current_screen["title"], current_screen["lines"])
        return {"status": "approved", "tx": tx}
    return {"status": "idle"}

@app.post("/sign-tx")
def sign_transaction(req: TxSignRequest):
    """Sign an Ethereum/Hedera EVM transaction through the Speculos veto gate."""
    rpc_url = os.getenv("HEDERA_RPC_URL", "https://testnet.hashio.io/api")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    try:
        network_gas_price = w3.eth.gas_price
    except Exception:
        network_gas_price = 1210000000000
    gas_price = req.gas_price_wei or network_gas_price
    value_wei = w3.to_wei(req.value_hbar, "ether")

    raw_tx = {
        "to": Web3.to_checksum_address(req.to),
        "value": value_wei,
        "gas": req.gas_limit,
        "gasPrice": gas_price,
        "nonce": req.nonce,
        "chainId": req.chain_id,
        "data": req.data,
    }

    # Update OLED screen state
    title = "REVIEW TRANSACTION"
    lines = [
        f"Amount: {req.value_hbar} HBAR",
        f"To: {req.to[:10]}...{req.to[-8:]}",
        f"Chain ID: {req.chain_id} (Hedera Testnet)",
        "Press Both: APPROVE | Left: VETO"
    ]
    current_screen["title"] = title
    current_screen["lines"] = lines
    current_screen["pending_tx"] = raw_tx
    current_screen["status"] = "awaiting_confirmation"

    render_oled(title, lines)

    # Auto-approve path (for automated headless test/demo execution)
    if req.auto_approve:
        print("[Speculos] 🤖 Auto-approval flag enabled. Signing transaction on hardware...")
        press_both()
        signed = Account.sign_transaction(raw_tx, LEDGER_PRIVATE_KEY)
        return {
            "status": "approved",
            "signed_tx_raw": signed.raw_transaction.hex(),
            "tx_hash": signed.hash.hex(),
            "device_address": ledger_account.address,
            "r": hex(signed.r),
            "s": hex(signed.s),
            "v": hex(signed.v)
        }

    return {
        "status": "awaiting_confirmation",
        "screen": current_screen,
        "instructions": "Call POST /button/both to approve or POST /button/left to veto."
    }

@app.post("/confirm-approval")
def confirm_approval():
    """Trigger the hardware confirmation and produce the signed transaction."""
    if not current_screen["pending_tx"]:
        raise HTTPException(status_code=400, detail="No pending transaction awaiting confirmation.")

    raw_tx = current_screen["pending_tx"]
    press_both()
    signed = Account.sign_transaction(raw_tx, LEDGER_PRIVATE_KEY)
    current_screen["pending_tx"] = None
    current_screen["status"] = "idle"

    return {
        "status": "approved",
        "signed_tx_raw": signed.raw_transaction.hex(),
        "tx_hash": signed.hash.hex(),
        "device_address": ledger_account.address,
        "r": hex(signed.r),
        "s": hex(signed.s),
        "v": hex(signed.v)
    }

@app.post("/confirm-veto")
def confirm_veto():
    """Trigger the hardware veto."""
    if not current_screen["pending_tx"]:
        raise HTTPException(status_code=400, detail="No pending transaction to veto.")

    press_left()
    current_screen["pending_tx"] = None
    current_screen["status"] = "idle"

    return {
        "status": "vetoed",
        "code": "0x6985",
        "message": "Payment rejected by Ledger hardware veto."
    }

if __name__ == "__main__":
    port = int(os.getenv("SPECULOS_PORT", "5000"))
    print(f"[Speculos] Starting Ledger Nano S+ Emulator on port {port}...")
    print(f"[Speculos] Emulated Device Address: {ledger_account.address}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

