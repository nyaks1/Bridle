"""Hedera Token Service (HTS) helpers for Bridle.

Creates a fungible token on Hedera testnet and provides transfer + query functions.
Used by the server (settlement verification) and agent (token payment).
"""
import os
import json
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

HEDERA_ACCOUNT_ID = os.getenv("HEDERA_ACCOUNT_ID")
HEDERA_PRIVATE_KEY = os.getenv("OPERATOR_PRIVATE_KEY")
HCS_TOPIC_ID = os.getenv("HCS_TOPIC_ID", "")
HTS_TOKEN_ID = os.getenv("HTS_TOKEN_ID", "")  # set after first creation

_client = None
_token_id = HTS_TOKEN_ID


def _get_client():
    global _client
    if _client is None:
        from hiero_sdk_python import Client, AccountId, PrivateKey
        _client = Client.for_testnet()
        aid = AccountId.from_string(HEDERA_ACCOUNT_ID)
        key = PrivateKey.from_string_ecdsa(HEDERA_PRIVATE_KEY)
        _client.set_operator(aid, key)
    return _client


def create_token(name: str = "BridleCredits", symbol: str = "BRC", initial_supply: int = 1_000_000) -> str:
    """Create a new HTS fungible token. Returns the token ID."""
    from hiero_sdk_python import TokenCreateTransaction, TokenSupplyType

    client = _get_client()
    tx = (
        TokenCreateTransaction()
        .set_token_name(name)
        .set_token_symbol(symbol)
        .set_initial_supply(initial_supply)
        .set_supply_type(TokenSupplyType.FINITE)
        .set_max_supply(10_000_000)
        .set_decimals(2)
        .freeze_with(client)
        .execute(client)
    )
    receipt = client.get_receipt(tx)
    tid = str(receipt.token_id)
    print(f"[HTS] Created token {name} ({symbol}): {tid}")
    return tid


def get_balance(token_id: str = "") -> int:
    """Get the operator's balance for an HTS token. Returns raw amount (with decimals)."""
    from hiero_sdk_python import TokenBalanceQuery, AccountId

    tid = token_id or _token_id
    if not tid:
        raise ValueError("No HTS_TOKEN_ID set. Create a token first or set HTS_TOKEN_ID in .env.")

    client = _get_client()
    query = TokenBalanceQuery().set_account_id(AccountId.from_string(HEDERA_ACCOUNT_ID)).set_token_id(
        __import__("hiero_sdk_python").TokenId.from_string(tid)
    )
    result = query.execute(client)
    return result.balances[0].balance if result.balances else 0


def transfer_tokens(to_account: str, amount: int, token_id: str = "") -> str:
    """Transfer HTS tokens to another account. Returns transaction ID."""
    from hiero_sdk_python import (
        TokenTransferTransaction,
        AccountId,
        TokenId,
    )

    tid = token_id or _token_id
    if not tid:
        raise ValueError("No HTS_TOKEN_ID set.")

    client = _get_client()
    tx = (
        TokenTransferTransaction()
        .add_token_transfer(TokenId.from_string(tid), AccountId.from_string(HEDERA_ACCOUNT_ID), -amount)
        .add_token_transfer(TokenId.from_string(tid), AccountId.from_string(to_account), amount)
        .freeze_with(client)
        .execute(client)
    )
    receipt = client.get_receipt(tx)
    tx_id = str(tx.transaction_id)
    print(f"[HTS] Transferred {amount} {tid} to {to_account} — tx={tx_id}")
    return tx_id


def verify_token_payment(token_id: str, from_account: str, required_amount: int) -> bool:
    """Verify the operator holds at least `required_amount` of the token."""
    from hiero_sdk_python import TokenBalanceQuery, AccountId

    client = _get_client()
    query = (
        TokenBalanceQuery()
        .set_account_id(AccountId.from_string(from_account))
        .set_token_id(__import__("hiero_sdk_python").TokenId.from_string(token_id))
    )
    result = query.execute(client)
    balance = result.balances[0].balance if result.balances else 0
    return balance >= required_amount


def log_hts_event(event: dict):
    """Log an HTS event to HCS if topic is configured."""
    if not HCS_TOPIC_ID:
        return ""
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    event["token_id"] = _token_id
    message = json.dumps(event)
    try:
        from hiero_sdk_python import TopicMessageSubmitTransaction, TopicId
        client = _get_client()
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
        print(f"[HTS] HCS error: {e}")
        return ""


# Auto-create token if none set
if __name__ == "__main__":
    if not _token_id:
        _token_id = create_token()
        print(f"\nAdd to .env:\nHTS_TOKEN_ID={_token_id}")
    else:
        bal = get_balance()
        print(f"[HTS] Token {_token_id} balance: {bal}")
