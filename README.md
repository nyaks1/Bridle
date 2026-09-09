# Bridle

A hardware-confirmed trust layer for AI agent payments.

Agents pay for what they use — autonomously, over x402 on Hedera — but nothing above a spending threshold moves without a human holding the reins. A Ledger hardware device confirms or rejects every high-value payment before it settles.

Built for ETHGlobal Online 2026.

---

## The problem

AI agents are starting to hold wallets and spend money on their own — calling paid APIs, buying data, paying for compute. Today that mostly means an API key sitting in a `.env` file, and an agent with no real limit on what it can spend. This maps directly to OWASP LLM Top 10 — **LLM08: Excessive Agency**: systems that let an AI act on money or resources with no meaningful human checkpoint.

## The solution

Bridle sits between an agent and its money.

1. The agent discovers a metered service and attempts to pay for it via x402 (HTTP 402 Payment Required), settled on Hedera — sub-cent fees, no subscriptions, no leaked API keys.
2. Payments under a set threshold settle automatically.
3. Payments over the threshold pause the agent and send a confirmation request to a Ledger hardware device. A human taps to confirm or reject — physically, on hardware, before any funds move.
4. Every settlement (confirmed or rejected) is logged and auditable.

The agent keeps its autonomy for everyday spend. The human keeps the veto for everything that matters.

## Architecture

```
Agent (Python)
   │
   ├─ discovers service → attempts call
   │
   ▼
x402 gate (HTTP 402 Payment Required)
   │
   ├─ under threshold ──► auto-settle on Hedera ──► response returned to agent
   │
   └─ over threshold ──► Ledger confirmation prompt
                              │
                    ┌─────────┴─────────┐
                 confirmed            rejected
                    │                     │
              settle on Hedera      transaction blocked,
                                     agent logs rejection
```

## Tracks

- Hedera — AI & Agentic Payments
- Ledger — AI Agents x Ledger

## Team

- **Nyakallo (Nyaks)** — agent logic (Python), Ledger Key Ring CLI integration
- **Liyabona** — Hedera-side x402-gated service (Solidity, EVM-compatible)

## Status

In progress — building for ETHGlobal Online, submission deadline Sun Sept 13, 2026, 12:00pm EDT.

---

## Project Structure

```
Bridle/
├── .env                       # Hedera RPC, operator private key, paywall address
├── .env.example               # Template environment configuration
├── hardhat.config.ts          # Hardhat 3 configuration (EVM Shanghai, Hedera Testnet)
├── package.json               # Node.js dependencies and scripts
│
├── contracts/                 # [Smart Contract Layer]
│   └── BridlePaywall.sol      # Solidity 0.8.20 paywall logic
├── scripts/
│   └── deploy.ts              # Hardhat 3 Hedera Testnet deployment runner
│
└── app/                       # [Combined Server & Agent Layer]
    ├── venv/                  # Python virtual environment
    ├── requirements.txt       # Dependencies (fastapi, uvicorn, web3, requests, etc.)
    ├── server.py              # FastAPI x402 gateway & Hedera transaction verification
    └── agent.py               # Agent client (402 handler, spending threshold, settlement)
```

---

## Project Setup & Running

### Prerequisites

- Node.js: v20+ (supports ESM and native module resolution)
- Python: 3.10+
- Hedera Testnet Account & ECDSA Private Key (from Hedera Portal)

### 1. Environment Configuration

Create a root `.env` file:

```bash
cp .env.example .env
```

Set the required environment variables:

```env
HEDERA_RPC_URL="https://testnet.hashio.io/api"
CHAIN_ID=296
OPERATOR_PRIVATE_KEY="0xYOUR_HEDERA_TESTNET_OPERATOR_PRIVATE_KEY"
PAYWALL_CONTRACT_ADDRESS="0x5442A862d2B11709045BE15015368c7dD6B9cfd8"
```

### 2. Smart Contract: Compile & Deploy (Hardhat 3)

Install root dependencies:

```bash
npm install
```

Compile the Solidity 0.8.20 contracts:

```bash
npx hardhat compile
```

Deploy the `BridlePaywall` contract to Hedera Testnet:

```bash
npx hardhat run scripts/deploy.ts --network hedera_testnet
```

### 3. Application Setup (`app/`)

Set up the shared Python environment:

```bash
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Running the End-to-End System

**Terminal 1: Start the x402 Server**

```bash
cd server
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Terminal 2: Run the Agent Flow**

```bash
cd server
source venv/bin/activate
python3 agent_test.py
```

**Verification Steps:**

1. Agent attempts access to `http://127.0.0.1:8000/api/protected-resource`.
2. Server responds with `402 Payment Required` challenge.
3. Agent checks spending policy against threshold (≤ 5.0 HBAR auto-settles; > 5.0 HBAR prompts Ledger).
4. Agent submits on-chain payment to `BridlePaywall` on Hedera Testnet.
5. Agent presents confirmed transaction hash in `X-Payment-Tx` header to unlock the resource.

---

## License

Apache-2.0