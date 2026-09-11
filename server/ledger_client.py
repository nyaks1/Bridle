"""Ledger Speculos Client for Bridle.

Interacts with the Ledger Speculos emulator via REST API (port 5000).
Enforces the Hardware Veto Loop for high-value agent transactions (> 1.0 HBAR).
"""

import time
import httpx
from typing import Dict, Any, Optional

SPECULOS_API_URL = "http://127.0.0.1:5000"

class LedgerClient:
    def __init__(self, base_url: str = SPECULOS_API_URL):
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        """Check if the Speculos emulator API is accessible."""
        try:
            resp = httpx.get(f"{self.base_url}/health", timeout=2.0)
            return resp.status_code == 200
        except Exception:
            return False

    def get_device_info(self) -> Dict[str, Any]:
        """Fetch emulated device information."""
        resp = httpx.get(f"{self.base_url}/health", timeout=3.0)
        return resp.json()

    def get_address(self) -> str:
        """Fetch the public address managed by the Ledger device."""
        try:
            info = self.get_device_info()
            return info.get("address", "")
        except Exception:
            return ""

    def submit_for_hardware_review(
        self,
        to_address: str,
        value_hbar: float,
        nonce: int,
        data: str = "0x",
        chain_id: int = 296,
        auto_approve: bool = False
    ) -> Dict[str, Any]:
        """Send a high-value transaction to the Ledger OLED screen for human review."""
        payload = {
            "to": to_address,
            "value_hbar": value_hbar,
            "nonce": nonce,
            "data": data,
            "chain_id": chain_id,
            "auto_approve": auto_approve
        }
        resp = httpx.post(f"{self.base_url}/sign-tx", json=payload, timeout=10.0)
        return resp.json()

    def approve_transaction(self) -> Dict[str, Any]:
        """Simulate pressing both hardware buttons to approve and sign the transaction."""
        resp = httpx.post(f"{self.base_url}/confirm-approval", timeout=5.0)
        return resp.json()

    def veto_transaction(self) -> Dict[str, Any]:
        """Simulate pressing the left hardware button to reject/veto the transaction."""
        resp = httpx.post(f"{self.base_url}/confirm-veto", timeout=5.0)
        return resp.json()

    def press_left_button(self) -> Dict[str, Any]:
        """Press left button (Veto / Cancel)."""
        resp = httpx.post(f"{self.base_url}/button/left", timeout=5.0)
        return resp.json()

    def press_right_button(self) -> Dict[str, Any]:
        """Press right button (Scroll / Next)."""
        resp = httpx.post(f"{self.base_url}/button/right", timeout=5.0)
        return resp.json()

    def press_both_buttons(self) -> Dict[str, Any]:
        """Press both buttons (Approve / Confirm)."""
        resp = httpx.post(f"{self.base_url}/button/both", timeout=5.0)
        return resp.json()

