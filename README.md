# Bridle 🐎

> **A hardware-confirmed trust layer and deterministic policy firewall for autonomous AI agent payments on Hedera.**

Built for **ETHOnline 2026**:
- 🏆 **Hedera Track**: *AI & Agentic Payments on Hedera*
- 🤖 **Ledger Track**: *AI Agents x Ledger*

---

## The Problem: The Uncontrolled Agent Economy

AI agents are increasingly holding crypto wallets and executing transactions autonomously—procuring compute, buying data, and calling paid APIs. Today, that typically means handing an LLM an API key or an unconstrained private key sitting in a `.env` file, with zero deterministic safeguards preventing catastrophic overspending.

When an agent hallucinates, loops, or encounters prompt injection:
1. **Financial Drain**: There is no hard circuit breaker to stop runaway spending.
2. **The Soft Guardrail Fallacy**: Prompt-based rules ("please don't spend more than $10") fail when context drifts.
3. **No Verifiable Audit Trail**: When funds move or workflows fail, operators have no tamper-proof cryptographic evidence of what happened, what reasoning was used, or where funds went.
4. **Subscription Waste**: Flat $50–$500/month SaaS subscriptions are ill-suited for autonomous agents that only need single queries.

---

## The Solution: Bridle's Dual-Rail Architecture

Bridle bridges **Hedera's sub-second, sub-cent payment rails** with **Ledger's hardware-backed device security** to create an intelligent payment gateway and deterministic policy firewall:

1. **x402 Protocol Access**: Metered APIs challenge agents via standard **HTTP 402 Payment Required** headers, settled in native HBAR via the **Blocky402 facilitator**—no pre-shared API keys or subscriptions required.
2. **Pay-Per-Call Metering**: Endpoints are priced per query (e.g., $0.005 for weather data, $0.020 for forecasts, $0.050 for analytics, 1.5 HBAR for enterprise intelligence).
3. **Two-Tiered Policy Firewall**:
   - **Micro-Payments (<= 1.0 HBAR)**: Autonomously signed via software ECDSA key and settled at machine speed on Hedera Testnet.
   - **Macro-Payments (> 1.0 HBAR)**: Execution is **instantly paused** and routed to a **Ledger hardware device** (emulated in development via Ledger's official **Speculos emulator**). A human operator must physically confirm or veto the transaction on the device OLED screen before funds can move.
4. **Resilient On-Chain Verification**: The gateway features exponential backoff polling (5 retries with 1.5s delay) to verify Hedera Testnet receipts, eliminating mirror node indexing latency.
5. **Immutable Audit Trail (HCS)**: Every action—payment settled, hardware approved, or hardware vetoed—is permanently recorded to **Hedera Consensus Service (HCS)** Topic `0.0.10474223`.

---

## Architecture Diagram

```
                              ┌─────────────────────────────┐
                              │     USER / AGENT TASK       │
                              │ "Get Cape Town Climate Data"│
                              └──────────────┬──────────────┘
                                             │
                                             ▼
                              ┌─────────────────────────────┐
                              │    BRIDLE x402 GATEWAY      │
                              │  Returns HTTP 402 Challenge │
                              └──────────────┬──────────────┘
                                             │
                                             ▼
                              ┌─────────────────────────────┐
                              │  GEMINI 3.6 FLASH REASONING │
                              │ Classifies Service Relevance│
                              └──────────────┬──────────────┘
                                             │
                                             ▼
                              ┌─────────────────────────────┐
                              │ DETERMINISTIC POLICY ENGINE │
                              │   Threshold: 1.0 HBAR       │
                              └──────────────┬──────────────┘
                                             │
                     ┌───────────────────────┴───────────────────────┐
                     │                                               │
                     ▼ [<= 1.0 HBAR: Micro-Payment]                  ▼ [> 1.0 HBAR: Macro-Payment]
       ┌───────────────────────────┐                   ┌───────────────────────────┐
       │ AUTONOMOUS SOFTWARE KEY   │                   │   LEDGER HARDWARE VETO    │
       │ - Sub-cent execution      │                   │ - Execution PAUSED        │
       │ - Signs TransferTx        │                   │ - Sent to Speculos OLED   │
       │ - Blocky402 Settles       │                   │ - Operator approves/vetos │
       └─────────────┬─────────────┘                   └─────────────┬─────────────┘
                     │                                               │
                     │                               ┌───────────────┴───────────────┐
                     │                               ▼ [Approved]                    ▼ [Vetoed (0x6985)]
                     │                 ┌───────────────────────────┐   ┌───────────────────────────┐
                     │                 │ - Signed with Ledger Key  │   │ - Abort execution         │
                     │                 │ - Broadcast to Hedera RPC │   │ - ZERO funds transferred  │
                     │                 │ - Settles on Paywall      │   │ - Log Veto to HCS         │
                     │                 └─────────────┬─────────────┘   └───────────────────────────┘
                     │                               │
                     └───────────────┬───────────────┘
                                     │
                                     ▼
                      ┌─────────────────────────────┐
                      │    GATEWAY VERIFICATION     │
                      │ - Resilient polling retry   │
                      │ - Unlocks protected resource│
                      └──────────────┬──────────────┘
                                     │
                                     ▼
                      ┌─────────────────────────────┐
                      │  HCS IMMUTABLE AUDIT LOG    │
                      │  Topic: 0.0.10474223        │
                      └─────────────────────────────┘
```

---

## Live Verified Deployments & Links (Hedera Testnet)

| Component | Identifier / Address | Explorer Link |
|---|---|---|
| **Hedera Consensus Service (HCS)** | Topic `0.0.10474223` | [HashScan HCS Topic](https://hashscan.io/testnet/topic/0.0.10474223) |
| **BridlePaywall Contract** | `0x5442A862d2B11709045BE15015368c7dD6B9cfd8` | [HashScan Smart Contract](https://hashscan.io/testnet/address/0x5442A862d2B11709045BE15015368c7dD6B9cfd8) |
| **Agent / Operator Account** | `0.0.10444198` (`0xCC88957C...`) | [HashScan Account](https://hashscan.io/testnet/account/0.0.10444198) |
| **Merchant Pay-To Account** | `0.0.10445587` | [HashScan Merchant Account](https://hashscan.io/testnet/account/0.0.10445587) |
| **Blocky402 Facilitator** | Hedera x402 Facilitator | `https://api.testnet.blocky402.com` (Fee Payer: `0.0.7162784`) |
| **Speculos Emulator API** | Port 5000 (REST & OLED display) | `http://127.0.0.1:5000` |

---

## Project Structure

```
Bridle/
├── docker-compose.yml         # Docker configuration for Ledger Speculos Nano S+ emulator
├── description.md             # 4-minute presentation pitch script and speaker notes
├── package.json               # Node.js dependencies & scripts (test, compile, deploy)
├── hardhat.config.ts          # Hardhat 3 configuration (Hedera Testnet Chain ID: 296)
├── .env.example               # Environment template
│
├── contracts/
│   └── BridlePaywall.sol      # Solidity 0.8.20 on-chain paywall with nonce replay protection
│
├── test/
│   └── BridlePaywall.ts       # Hardhat 3 + Mocha + Ethers smart contract unit test suite
│
├── scripts/
│   ├── demo.sh                # 1-Click Master Demo Script (Scenarios A, B, and C)
│   ├── run_speculos.sh        # Speculos launcher (Docker with automatic native fallback)
│   └── deploy.ts              # Hardhat deployment script for Hedera Testnet
│
├── app/                       # Alias symlink to server package (supports app.* imports)
└── server/
    ├── requirements.txt       # Python dependencies (FastAPI, web3, hiero-sdk, google-genai)
    ├── server.py              # Dual-rail gateway (x402 + on-chain verification + HCS)
    ├── main.py                # Gateway entrypoint alias
    ├── agent.py               # Autonomous AI agent with Ledger Hardware Veto Loop
    ├── ledger_client.py       # Speculos REST client & hardware button automation
    ├── speculos_emulator.py   # Speculos emulator bridge with terminal OLED visualization
    └── hedera_hts.py          # Hedera Token Service (HTS) helper module
```

---

## Quickstart & Setup

### Prerequisites
- **Node.js** v20+
- **Python** 3.10+
- (Optional) **Docker** for running Speculos container (native fallback included!)

### 1. Environment Configuration

```bash
cp .env.example .env
```

Verify the key variables in `.env`:
```env
HEDERA_RPC_URL="https://testnet.hashio.io/api"
OPERATOR_PRIVATE_KEY="0xYOUR_HEX_PRIVATE_KEY"
HEDERA_ACCOUNT_ID="0.0.YOUR_ACCOUNT_ID"
PAY_TO_ACCOUNT="0.0.YOUR_MERCHANT_ACCOUNT_ID"
GEMINI_API_KEY="your_gemini_api_key"
HCS_TOPIC_ID="0.0.10474223"
PAYWALL_CONTRACT_ADDRESS="0x5442A862d2B11709045BE15015368c7dD6B9cfd8"
FACILITATOR_URL="https://api.testnet.blocky402.com"
RESOURCE_SERVER_URL="http://127.0.0.1:8000"
HARDWARE_VETO_THRESHOLD_HBAR="1.0"
```

### 2. Smart Contract Testing

Run the Hardhat 3 unit test suite covering paywall payments, replay protection, and owner withdrawals:

```bash
npm install
npm test
```

Expected output:
```
  BridlePaywall
    ✔ should deploy with the correct owner
    ✔ should accept payment for a service and record it
    ✔ should prevent duplicate nonce replay
    ✔ should revert if payment value is zero
    ✔ should allow owner to withdraw settled funds
    ✔ should revert if non-owner attempts to withdraw

  6 passing
```

---

## Running the 1-Click Master Demo

To execute the entire multi-scenario demonstration (Scenarios A, B, and C):

```bash
bash scripts/demo.sh
```

### What this script demonstrates:
1. **Scenario A (Autonomous Micro-Payment <= 1.0 HBAR)**:
   - Endpoint: `GET /api/weather` (0.05 HBAR / $0.005)
   - Evaluated by Gemini $\rightarrow$ Verified under budget $\rightarrow$ Signed autonomously with software key $\rightarrow$ Settled on Hedera $\rightarrow$ Status 200 $\rightarrow$ Logged to HCS.
2. **Scenario B (Macro-Payment > 1.0 HBAR with Hardware Confirmation)**:
   - Endpoint: `GET /api/premium-report` (1.50 HBAR)
   - Evaluated by Gemini $\rightarrow$ Exceeds threshold $\rightarrow$ **Execution paused** $\rightarrow$ Routed to Ledger Speculos OLED screen $\rightarrow$ Approved on hardware $\rightarrow$ Broadcast to `BridlePaywall` contract on Hedera EVM $\rightarrow$ Verified with retry backoff $\rightarrow$ Status 200 $\rightarrow$ Logged to HCS.
3. **Scenario C (Macro-Payment > 1.0 HBAR with Hardware Veto)**:
   - Endpoint: `GET /api/premium-report` (1.50 HBAR)
   - Operator presses **LEFT BUTTON** on Ledger $\rightarrow$ Speculos returns `0x6985` (Action refused by user) $\rightarrow$ Transaction aborted $\rightarrow$ **Zero funds leave wallet** $\rightarrow$ `payment_rejected_by_hardware_veto` logged to HCS.

---

## Manual Step-by-Step Execution

If you prefer to run each service individually in separate terminals:

### Terminal 1: Start the Ledger Speculos Emulator
```bash
bash scripts/run_speculos.sh
```
Verify emulator health:
```bash
curl http://127.0.0.1:5000/health
```

### Terminal 2: Start the Bridle Gateway Server
```bash
cd server
source venv/bin/activate
uvicorn server:app --host 127.0.0.1 --port 8000
```
Verify gateway health:
```bash
curl http://127.0.0.1:8000/api/health
```

### Terminal 3: Run the Agent

**Activate the environment**
```bash
cd server
source venv/bin/activate
```

**Run Micro-Payment (Autonomous):**
```bash
python server/agent.py --endpoint=/api/weather
```

**Run Macro-Payment (Hardware Approved):**
```bash
python agent.py --endpoint=/api/premium-report --auto-approve
```

**Run Macro-Payment (Hardware Vetoed):**
```bash
python agent.py --endpoint=/api/premium-report --veto
```

**Run Interactive Hardware Approval (CLI Prompts):**
```bash
python agent.py --endpoint=/api/premium-report
```

---

## Metered Endpoints & Pricing Table

| Endpoint | Method | Cost (HBAR) | Cost (USD) | Settlement Path | Policy Gate |
|---|---|---|---|---|---|
| `/api/weather` | GET | 0.05 HBAR | $0.005 | x402 / Blocky402 | Autonomous Software Sign |
| `/api/forecast` | GET | 0.20 HBAR | $0.020 | x402 / Blocky402 | Autonomous Software Sign |
| `/api/weather-intelligence` | GET | 0.50 HBAR | $0.050 | x402 / Blocky402 | Autonomous Software Sign |
| `/api/premium-report` | GET | 1.50 HBAR | $1.500 | Hedera On-Chain Paywall | **Ledger Hardware Veto Hook** |
| `/api/health` | GET | Free | Free | N/A | Open |

---

## Verifying the Cryptographic Audit Trail on Hedera

Because every decision is anchored to Hedera Consensus Service, anyone can verify the agent's actions on HashScan:
👉 [https://hashscan.io/testnet/topic/0.0.10474223](https://hashscan.io/testnet/topic/0.0.10474223)

Or query the Hedera Mirror Node directly via HTTP:
```bash
curl -s "https://testnet.mirrornode.hedera.com/api/v1/topics/0.0.10474223/messages" | jq '.messages[-3:]'
```

### Sample Audit Records on HCS:

**Hardware Settlement Confirmed:**
```json
{
  "event": "payment_settled_with_hardware_approval",
  "agent": "0.0.10444198",
  "device": "0xCC88957C879b2A65E63065eB42264045c200Cf7A",
  "service": "Enterprise Climate Archive",
  "amount_hbar": 1.5,
  "tx": "0xf77045e20cd687e194ec65b9eb86a0127a5650194e9bb5f2a5397e7e03dd50e7",
  "paywall": "0x5442A862d2B11709045BE15015368c7dD6B9cfd8",
  "chain_id": 296,
  "timestamp": "2026-09-11T11:37:44Z"
}
```

**Hardware Veto Rejection:**
```json
{
  "event": "payment_rejected_by_hardware_veto",
  "agent": "0.0.10444198",
  "device": "0xCC88957C879b2A65E63065eB42264045c200Cf7A",
  "service": "Enterprise Climate Archive",
  "amount_hbar": 1.5,
  "threshold_hbar": 1.0,
  "reason": "operator_hardware_veto (status: 0x6985)",
  "timestamp": "2026-09-11T11:37:50Z"
}
```

---

## Track Qualification Checklist

### 🏆 Hedera — AI & Agentic Payments on Hedera
- [x] **Live x402-Gated Service on Hedera Testnet**: Real metered endpoints returning HTTP 402 challenges.
- [x] **Blocky402 Facilitator Integration**: Hedera-native facilitator integration with fee payer sponsorship (`0.0.7162784`).
- [x] **Autonomous Agent Consumer**: End-to-end payment construction, signing, and resource consumption.
- [x] **Pay-Per-Call Metering**: Query-based pricing (0.05 to 1.5 HBAR) instead of flat charges.
- [x] **Immutable HCS Audit Trail**: Real-time message submission to HCS Topic `0.0.10474223`.
- [x] **EVM Smart Contract Deployment**: Hardhat 3 tested contract `BridlePaywall.sol` on Hedera EVM (`0x5442A862d2B11709045BE15015368c7dD6B9cfd8`).

### 🤖 Ledger — AI Agents x Ledger
- [x] **Device-Backed Security for Autonomous Agents**: Hardware confirmation gate for high-value actions.
- [x] **Human-in-the-Loop Veto Hook**: Automatically pauses execution when payment > 1.0 HBAR threshold and displays details on device OLED screen.
- [x] **Ledger Speculos Emulator Integration**: Reproducible Docker & native REST API bridge (`http://127.0.0.1:5000`) for testing without physical hardware.
- [x] **Hardware Veto Protection**: Verifiable abort on `0x6985` user rejection; zero funds leave the wallet.
- [x] **Dual-Rail Safety**: Retains sub-second autonomous micro-payments while enforcing hardware protection for macro-transactions.

---

## License

[Apache-2.0](LICENSE)
