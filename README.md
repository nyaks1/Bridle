# Bridle

An x402 payment gateway that lets AI agents pay for services autonomously on Hedera — with a policy engine that blocks high-value transactions and writes every decision to an immutable audit trail.

Built for ETHGlobal Online 2026.

---

## The problem

AI agents are starting to hold wallets and spend money on their own — calling paid APIs, buying data, paying for compute. Today that mostly means an API key sitting in a `.env` file, and an agent with no real limit on what it can spend. When something goes wrong, there's no proof of what happened or why.

## The solution

Bridle sits between an agent and its money.

1. The agent discovers a metered service and attempts to pay for it via **x402** (HTTP 402 Payment Required), settled on **Hedera** — sub-cent fees, no subscriptions, no leaked API keys.
2. Payments under a set threshold settle automatically.
3. Payments over the threshold are **blocked by policy** before any funds move.
4. Every decision — payment settled or payment blocked — is written to **Hedera Consensus Service (HCS)** as a tamper-proof, timestamped record.

Nobody, not even the operator, can quietly edit or delete the audit trail after the fact. "Here's the on-chain record showing the system said no" is the proof that safeguards fired.

## Architecture

```
Agent (Python)
   │
   ├─ discovers service → attempts call
   │
   ▼
x402 gate (HTTP 402 Payment Required)
   │
   ├─ under threshold ──► auto-settle on Hedera ──► log to HCS ──► response returned
   │
   └─ over threshold ──► blocked by policy ──► log rejection to HCS
```

## The audit trail

Every agent action produces an HCS message:

```json
{
  "event": "payment_blocked",
  "agent": "0x...",
  "amount_hbar": 10.0,
  "threshold": 5.0,
  "reason": "exceeds_policy_threshold",
  "timestamp": "2026-09-13T14:32:01Z"
}
```

```json
{
  "event": "payment_settled",
  "agent": "0x...",
  "amount_hbar": 1.0,
  "tx_hash": "0x...",
  "paywall": "0x...",
  "timestamp": "2026-09-13T14:32:15Z"
}
```

Immutable. Auditable. Verifiable by anyone.

## Track

- Hedera — AI & Agentic Payments

## Team

- **Nyakallo** — agent logic (Python), x402 integration, HCS audit trail
- **Liyabona** — Hedera-side x402-gated service (Solidity, EVM-compatible)

## Project Structure

```
Bridle/
├── .env.example               # Template environment configuration
├── hardhat.config.ts          # Hardhat 3 configuration (EVM Shanghai, Hedera Testnet)
├── package.json               # Node.js dependencies and scripts
│
├── contracts/
│   └── BridlePaywall.sol      # Solidity 0.8.20 paywall logic
├── scripts/
│   └── deploy.ts              # Hardhat 3 Hedera Testnet deployment runner
│
└── server/
    ├── requirements.txt       # Python dependencies
    ├── main.py                # FastAPI x402 gateway & Hedera transaction verification
    └── agent_test.py          # Agent client (402 handler, policy gate, settlement)
```

## Setup

### Prerequisites

- Node.js v20+
- Python 3.10+
- Hedera Testnet account with ECDSA private key
- Hedera topic ID for HCS audit trail

### 1. Environment

```bash
cp .env.example .env
```

Set variables:

```env
HEDERA_RPC_URL="https://testnet.hashio.io/api"
OPERATOR_PRIVATE_KEY="0xYOUR_HEX_KEY_HERE"
HEDERA_ACCOUNT_ID="0.0.YOUR_ACCOUNT_ID"
PAYWALL_CONTRACT_ADDRESS="0x5442A862d2B11709045BE15015368c7dD6B9cfd8"
HCS_TOPIC_ID="0.0.YOUR_TOPIC_ID"
```

### 2. Deploy contract

```bash
npm install
npx hardhat compile
npx hardhat run scripts/deploy.ts --network hedera_testnet
```

### 3. Run the server

```bash
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 4. Run the agent

```bash
cd server
source venv/bin/activate
python3 agent_test.py
```

## Verification

1. Agent requests `http://127.0.0.1:8000/api/protected-resource`
2. Server returns `402 Payment Required` with paywall contract details
3. Agent checks threshold — under limit auto-settles, over limit blocks
4. Agent pays via Hedera, submits tx hash in `X-Payment-Tx` header
5. Server verifies on-chain, returns protected resource
6. Both events (settled/blocked) appear in HCS topic as immutable records

## License

Apache-2.0
