# Bridle

An x402 payment gateway that lets AI agents pay for services autonomously on Hedera — with a policy engine that blocks high-value transactions and writes every decision to an immutable audit trail.

Built for ETHOnline 2026.

---

## The problem

AI agents are starting to hold wallets and spend money on their own — calling paid APIs, buying data, paying for compute. Today that mostly means an API key sitting in a `.env` file, and an agent with no real limit on what it can spend. When something goes wrong, there's no proof of what happened or why.

## The solution

Bridle sits between an agent and its money.

1. The agent discovers a metered service and attempts to pay for it via **x402** (HTTP 402 Payment Required), settled on **Hedera** through the **Blocky402** facilitator — sub-cent fees, no subscriptions, no leaked API keys.
2. Each API call is metered — the agent pays **per query**, not a flat rate.
3. Payments under a set threshold settle automatically. Payments over the threshold are **blocked by policy** before any funds move.
4. Settlement uses **Hedera Token Service (HTS)** fungible tokens — BridleCredits (BRC) — not raw HBAR.
5. Every decision — payment settled or payment blocked — is written to **Hedera Consensus Service (HCS)** as a tamper-proof, timestamped record.

Nobody, not even the operator, can quietly edit or delete the audit trail after the fact.

## Architecture

```
Agent (Python + Gemini)
   │
   ├─ requests service → gets 402 challenge
   │
   ▼
Gemini classifies service relevance
   │
   ├─ not relevant ──► skip
   │
   ▼
Policy gate (deterministic, never LLM)
   │
   ├─ under threshold ──► x402 payment via Blocky402 facilitator
   │                        │
   │                        ├─ settle on Hedera (HTS tokens)
   │                        ├─ log to HCS
   │                        └─ unlock resource
   │
   └─ over threshold ──► blocked by policy ──► log rejection to HCS
```

## Key features

| Feature | How it works |
|---|---|
| **x402 protocol** | Standard HTTP 402 payment flow via `x402` Python SDK — no custom contracts needed |
| **Blocky402 facilitator** | Payment verification and settlement delegated to Hedera-native facilitator |
| **Pay-per-call metering** | Each endpoint has a per-query price (weather: $0.005, analytics: $0.05, forecast: $0.02) |
| **HTS token settlement** | Payments in BridleCredits (BRC) — a Hedera Token Service fungible token — not raw HBAR |
| **Policy engine** | Deterministic threshold check — never delegated to LLM |
| **HCS audit trail** | Every payment or rejection is an immutable message on Hedera Consensus Service |
| **Gemini classification** | Agent evaluates service relevance before paying |

## Track

- Hedera — AI & Agentic Payments on Hedera ($6,000)

### Hedera extra points checklist

- [x] Verifiable payment audit trails on HCS
- [x] Pay-per-call metering (per-query pricing, not flat rate)
- [x] HTS tokens (BridleCredits fungible token)
- [x] Blocky402 facilitator (Hedera-native x402 facilitator)
- [ ] Multi-agent negotiation
- [ ] Agent discovery / UCP directory
- [ ] Scheduled / streamed payments

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
    ├── main.py                # FastAPI x402 gateway with Blocky402 facilitator
    ├── agent.py               # Gemini-powered agent (x402 client, policy gate, HCS)
    └── hedera_hts.py          # HTS token creation, transfer, and query helpers
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
GEMINI_API_KEY="your_gemini_api_key_here"
HCS_TOPIC_ID="0.0.YOUR_TOPIC_ID"
FACILITATOR_URL="https://api.testnet.blocky402.com"
RESOURCE_SERVER_URL="http://127.0.0.1:8000"
PAY_TO_ACCOUNT="0.0.RECIPIENT_ACCOUNT_ID"
SPENDING_THRESHOLD_HBAR="5.0"
AGENT_TASK="Get current weather data for Cape Town, South Africa"
```

### 2. Create HTS token (optional, one-time)

```bash
cd server
source venv/bin/activate
python3 hedera_hts.py
```

This creates a BridleCredits (BRC) token and prints the `HTS_TOKEN_ID` to add to `.env`.

### 3. Run the server

```bash
cd server
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 4. Run the agent

```bash
cd server
source venv/bin/activate
python3 agent.py
```

## Endpoints

| Endpoint | Per-query price | Description |
|---|---|---|
| `GET /api/weather?city=Cape Town` | $0.005 | Current weather conditions |
| `GET /api/weather-intelligence?city=Cape Town` | $0.050 | Enterprise analytics with 5-day forecast and alerts |
| `GET /api/forecast?city=Cape Town&days=3` | $0.020 | Batch forecast retrieval |
| `GET /api/health` | Free | Server status and configuration |

## The audit trail

Every agent action produces an HCS message:

```json
{
  "event": "payment_settled",
  "agent": "0xCC88957C879b2A65E63065eB42264045c200Cf7A",
  "service": "Weather API",
  "service_type": "weather_query",
  "price": "$0.005",
  "tx": "0.0.10465769@1726100000.000000000",
  "timestamp": "2026-09-11T12:00:00Z"
}
```

```json
{
  "event": "payment_blocked",
  "agent": "0xCC88957C879b2A65E63065eB42264045c200Cf7A",
  "service": "Premium Analytics",
  "service_type": "analytics_run",
  "reason": "exceeds_policy_threshold",
  "timestamp": "2026-09-11T12:00:05Z"
}
```

Immutable. Auditable. Verifiable by anyone.

## Verification

1. Agent requests `http://127.0.0.1:8000/api/weather`
2. Server returns `402 Payment Required` with x402 payment requirements (Blocky402 facilitator, Hedera testnet)
3. Gemini classifies the service as relevant to the agent's task
4. Policy gate checks the price against the spending threshold — under limit
5. Agent signs a Hedera `TransferTransaction` (fee payer = Blocky402 facilitator)
6. Agent sends the signed transaction to Blocky402 for verification — passes
7. Blocky402 settles the payment on Hedera testnet
8. Agent accesses the protected resource with the payment proof
9. Both events (settled/blocked) appear in HCS topic as immutable records

## License

Apache-2.0
