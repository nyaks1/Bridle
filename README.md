# Bridle

> **A hardware-confirmed trust layer and deterministic policy firewall for autonomous AI agent payments on Hedera.**

Built for **ETHOnline 2026**:
- **Hedera Track**: *AI & Agentic Payments on Hedera* 
- **Ledger Track**: *AI Agents x Ledger* 

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
├── specifications.md          # Complete system specifications, architecture, and design rationale
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

### 2. Python Virtual Environment Setup (venv)

Create the Python virtual environment and install all dependencies:

```bash
# Create the virtual environment
python3 -m venv server/venv

# Activate the virtual environment
source server/venv/bin/activate

# Install required Python packages
pip install -r server/requirements.txt
```

> [!TIP]
> A root symlink (`venv -> server/venv`) is included, allowing you to run either `source server/venv/bin/activate` or `source venv/bin/activate`.

### 3. Smart Contract Testing

Run the Hardhat 3 unit test suite covering paywall payments, replay protection, and owner withdrawals:

```bash
npm install
npm test
```

Expected output:
```
  BridlePaywall
    passed - should deploy with the correct owner
    passed - should accept payment for a service and record it
    passed - should prevent duplicate nonce replay
    passed - should revert if payment value is zero
    passed - should allow owner to withdraw settled funds
    passed - should revert if non-owner attempts to withdraw

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
   - Evaluated by Gemini -> Verified under budget -> Signed autonomously with software key -> Settled on Hedera -> Status 200 -> Logged to HCS.
2. **Scenario B (Macro-Payment > 1.0 HBAR with Hardware Confirmation)**:
   - Endpoint: `GET /api/premium-report` (1.50 HBAR)
   - Evaluated by Gemini -> Exceeds threshold -> **Execution paused** -> Routed to Ledger Speculos OLED screen -> Approved on hardware -> Broadcast to `BridlePaywall` contract on Hedera EVM -> Verified with retry backoff -> Status 200 -> Logged to HCS.
3. **Scenario C (Macro-Payment > 1.0 HBAR with Hardware Veto)**:
   - Endpoint: `GET /api/premium-report` (1.50 HBAR)
   - Operator presses **LEFT BUTTON** on Ledger -> Speculos returns `0x6985` (Action refused by user) -> Transaction aborted -> **Zero funds leave wallet** -> `payment_rejected_by_hardware_veto` logged to HCS.

---

## Viewing and Interacting with the Ledger Speculos Emulator

When macro-payments exceed the policy threshold (> 1.0 HBAR), autonomous execution is **instantly paused** and routed to the Ledger Speculos emulator for human hardware confirmation. You can view, monitor, and interact with the emulated Ledger Nano S+ in two ways:

### 1. Interactive Web GUI (Browser Dashboard)
Open your web browser and navigate to:
**`http://localhost:5000`** (or `http://127.0.0.1:5000`)

The web emulator provides a real-time, interactive simulation of the physical hardware device:
- **Ledger Nano S+ Chassis**: Renders the hardware casing with functional Left, Right, and Both buttons.
- **Live 500ms OLED Screen**: Automatically refreshes every 500ms by querying `GET /screen`. When an agent initiates a macro-payment, the screen instantly updates to:
  ```
  +==============================================+
  |              REVIEW TRANSACTION              |
  |  Amount: 1.5 HBAR                            |
  |  To: 0x5442A862...c7dD6B9cfd8                |
  |  Chain ID: 296 (Hedera Testnet)              |
  |  Press Both: APPROVE | Left: VETO            |
  +==============================================+
  ```
- **Real-Time Clickable Controls**:
  - **Left Button (VETO)**: Sends a rejection event (`0x6985: Action refused by user`). The agent immediately detects the veto via live polling, aborts execution, transfers zero funds, and records the veto event to HCS.
  - **Right Button (Next)**: Simulates scrolling through transaction metadata screens on the device.
  - **Both Buttons (APPROVE)**: Signs the raw EVM transaction with the device private key. The running agent instantly detects the approval, receives the signed payload, and broadcasts it to Hedera Testnet.
- **Live In-Page Notification Banner**: Shows current hardware state (`Action Required`, `Approved`, or `Vetoed`) without blocking browser popups.
- **Device and Network Metadata**: Displays the active device EVM address, Hedera Testnet Chain ID (296), `BridlePaywall` contract address, and HCS topic ID.

### 2. Terminal ASCII OLED Display
If running in a headless environment or server terminal, `server/speculos_emulator.py` also renders an ASCII OLED screen box directly into stdout whenever a transaction arrives or changes state.

### 3. Interactive vs Automated Modes
- **Interactive Mode**: Run `python server/agent.py --endpoint=/api/premium-report`. The agent pauses execution and listens simultaneously to both:
  1. **Web GUI at `http://localhost:5000`**: Click **Both Buttons (APPROVE)** or **Left Button (VETO)** in your web browser. The agent detects the click in under 400ms and responds immediately.
  2. **Terminal Prompt**: Type `y` to approve or `n` to veto and press Enter.
- **Automated Demo Approval**: Pass `--auto-approve` to simulate pressing both buttons programmatically without waiting.
- **Automated Demo Veto**: Pass `--veto` to simulate pressing the left button programmatically without waiting.
- **Direct Endpoint Targeting**: Pass `--endpoint=/api/...` to bypass semantic relevance filtering and execute against a specific endpoint directly.

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
source server/venv/bin/activate
uvicorn server.server:app --host 127.0.0.1 --port 8000
```
Verify gateway health:
```bash
curl http://127.0.0.1:8000/api/health
```

### Terminal 3: Run the Agent

**Activate the virtual environment:**
```bash
source server/venv/bin/activate
```

**Run Micro-Payment (Autonomous Software Sign <= 1.0 HBAR):**
```bash
python server/agent.py --endpoint=/api/weather
```

**Run Macro-Payment with Live Hardware Interaction (Web GUI or Terminal):**
```bash
python server/agent.py --endpoint=/api/premium-report
```
*When execution pauses, approve or veto directly by clicking the button on `http://localhost:5000` or by typing `y`/`n` into the terminal.*

**Run Macro-Payment with Automated Hardware Approval:**
```bash
python server/agent.py --endpoint=/api/premium-report --auto-approve
```

**Run Macro-Payment with Automated Hardware Veto (Abort / Zero funds):**
```bash
python server/agent.py --endpoint=/api/premium-report --veto
```

**Run Full Autonomous Discovery Across All Endpoints:**
```bash
python server/agent.py
```
*(The agent discovers all endpoints advertised by the gateway, evaluates their relevance to `AGENT_TASK` using Gemini 3.6 Flash reasoning, and executes eligible calls within budget.)*

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
[https://hashscan.io/testnet/topic/0.0.10474223](https://hashscan.io/testnet/topic/0.0.10474223)

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



## License

[Apache-2.0](LICENSE)
