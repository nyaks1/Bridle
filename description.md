# Bridle — ETHOnline 2026 Presentation Brief (4-Minute Pitch)

> **Dual-Track Submission**:
> - **Hedera**: *AI & Agentic Payments on Hedera* ($6,000)
> - **Ledger**: *AI Agents x Ledger* ($3,500)
> 
> **Repository**: [https://github.com/nyaks1/Bridle](https://github.com/nyaks1/Bridle)  
> **Target Video Duration**: ≤ 4 Minutes (Compliant with hackathon < 5-minute requirement)

---

## 1. Quick Reference & Verified Live Links

| Component | Network / Details | Explorer / URL |
|---|---|---|
| **Hedera Consensus Service (HCS) Topic** | Topic ID: `0.0.10474223` | [View HCS Audit Stream on HashScan](https://hashscan.io/testnet/topic/0.0.10474223) |
| **BridlePaywall Smart Contract** | Hedera Testnet (Chain ID 296) | [`0x5442A862d2B11709045BE15015368c7dD6B9cfd8`](https://hashscan.io/testnet/address/0x5442A862d2B11709045BE15015368c7dD6B9cfd8) |
| **Agent / Deployer Address** | Hedera EVM / Account `0.0.10444198` | `0xCC88957C879b2A65E63065eB42264045c200Cf7A` |
| **Merchant Pay-To Account** | Hedera Native Account | `0.0.10445587` |
| **Blocky402 Facilitator API** | Hedera x402 Facilitator | `https://api.testnet.blocky402.com` (Fee Payer: `0.0.7162784`) |
| **Ledger Emulator Stack** | Speculos Nano S+ REST / APDU API | `http://127.0.0.1:5000` (Docker / Native Bridge) |

---

## 2. Four-Minute Timed Presentation Script

### ⏱️ [0:00 - 0:45] The Hook & The Problem
**Speaker Voiceover:**
> *"Autonomous AI agents are beginning to hold crypto wallets and execute real-world financial transactions. Today, that means handing an LLM an API key or an unconstrained private key, hoping prompt engineering prevents it from overspending.
> 
> But LLMs are probabilistic. They hallucinate, they get stuck in infinite retry loops, and they are vulnerable to prompt injection. When an agent spends corporate funds, there are zero hard circuit breakers—and when things go wrong, operators have no tamper-proof cryptographic audit trail explaining why funds moved.
> 
> Current blockchains are either too slow or too expensive for micro-payments, and hardware security has never been connected to autonomous agent loops. Until now."*

**Visual Cue:**
- Display title slide: *Bridle: Hardware-Confirmed Trust Layer for Autonomous Agent Payments*.
- Show problem diagram: API keys in plaintext, unconstrained agents, and no audit trail.

---

### ⏱️ [0:45 - 1:45] The Solution: Bridle's Dual-Rail Architecture
**Speaker Voiceover:**
> *"Introducing **Bridle**. Bridle is an intelligent payment gateway and deterministic policy firewall that bridges the **Hedera network** with **Ledger hardware device security**.
> 
> Here is how it works:
> 1. When an agent discovers a metered API, the gateway challenges it with **x402 (HTTP 402 Payment Required)**.
> 2. Google **Gemini 3.6 Flash** evaluates whether the service matches the user's intent.
> 3. Then, our **deterministic policy firewall** takes over. Notice that we never delegate financial limits to an LLM.
> 4. If a payment is a **micro-transaction below 1.0 HBAR** (such as our \$0.005 weather query), the agent signs autonomously with software ECDSA and settles in sub-seconds via the **Blocky402 facilitator** on Hedera.
> 5. But if a payment is a **macro-transaction above 1.0 HBAR**, Bridle pauses autonomous execution and routes the unsigned transaction to a **Ledger device**—emulated in our demo via **Ledger's official Speculos emulator**. The human operator must physically approve the transaction on the device OLED screen before a single tinybar moves.
> 6. Every decision—settled, approved, or rejected—is logged to **Hedera Consensus Service (HCS)** as a permanent, immutable record."*

**Visual Cue:**
- Show the Bridle Dual-Rail Architecture Diagram (Micro-payment autonomous branch vs Macro-payment Ledger hardware branch).

---

### ⏱️ [1:45 - 3:15] The Live Demonstration (3 Scenarios)
**Speaker Voiceover:**
> *"Let's see Bridle in action by executing our unified demo script (`bash scripts/demo.sh`)."*

#### Scenario 1: Autonomous Micro-Payment (<= 1.0 HBAR)
> *"In Scenario A, the agent needs Cape Town weather data priced at 0.05 HBAR ($0.005). Gemini confirms task relevance. The policy engine verifies 0.05 HBAR is under our 1.0 HBAR threshold. The agent signs the Hedera transfer, the gateway verifies it via Blocky402, unlocks the weather data with HTTP 200, and writes the settlement receipt to HCS. Complete autonomy at machine speed."*
**Visual**: Terminal output showing 402 $\rightarrow$ signing 500,000 tinybars $\rightarrow$ 200 OK $\rightarrow$ HCS Tx.

#### Scenario 2: High-Value Macro-Payment with Hardware Confirmation (> 1.0 HBAR)
> *"In Scenario B, the agent requests our Enterprise Climate Risk Archive, priced at 1.5 HBAR. Notice what happens: the policy firewall immediately pauses execution. It displays the transaction on the Ledger Nano OLED screen: 1.5 HBAR to our on-chain BridlePaywall contract on Hedera Testnet.
> 
> The operator approves on the Ledger device. The hardware key signs the transaction, broadcasts it to Hedera Testnet, and passes the tx hash in the `X-Payment-Tx` header. The gateway verifies the on-chain receipt with resilient exponential backoff polling, unlocks the enterprise archive, and records the hardware-confirmed settlement to HCS."*
**Visual**: Show ASCII Ledger Nano S+ OLED screen with `Amount: 1.5 HBAR`, `Target Contract`, `APPROVE` button press $\rightarrow$ On-chain tx hash $\rightarrow$ HTTP 200 Unlocked.

#### Scenario 3: The Hardware Veto (Human Rejection)
> *"In Scenario C, an unauthorized or high-risk 1.5 HBAR payment is attempted. This time, the human operator presses the LEFT button on the Ledger device to VETO.
> 
> Speculos returns status `0x6985` (Action refused by user). The transaction is immediately aborted—zero funds leave the wallet—and a `payment_rejected_by_hardware_veto` event is permanently recorded on Hedera Consensus Service, proving that the hardware safety layer prevented the unauthorized spend."*
**Visual**: Show Ledger OLED displaying `Transaction Vetoed`, terminal displaying `[BLOCKED] Transaction aborted by hardware veto`, and HCS logging receipt.

---

### ⏱️ [3:15 - 3:45] Cryptographic Verification on HashScan
**Speaker Voiceover:**
> *"Because Bridle anchors every decision to Hedera Consensus Service, anyone can audit the agent's history on HashScan without trusting our server.
> 
> Looking at Topic `0.0.10474223` on HashScan, we can see the exact sequence of events:
> - Sequence 17: `payment_settled_with_hardware_approval` with the on-chain tx hash.
> - Sequence 18: Gateway confirmation to `BridlePaywall` contract `0x5442A862d2B11709045BE15015368c7dD6B9cfd8`.
> - Sequence 19: `payment_rejected_by_hardware_veto` recording the human operator's intervention.
> 
> No operator, developer, or compromised model can alter this history."*

**Visual Cue:**
- Open browser to `https://hashscan.io/testnet/topic/0.0.10474223` showing the decoded JSON messages.

---

### ⏱️ [3:45 - 4:00] Conclusion & Why Bridle Wins Both Tracks
**Speaker Voiceover:**
> *"Bridle satisfies the requirements of both tracks:
> - For **Hedera**, we deliver a real, live x402-gated service with Blocky402 facilitator settlement, pay-per-call metering, and an immutable HCS audit trail.
> - For **Ledger**, we bring device-backed security to autonomous agents, proving that hardware confirmation can prevent catastrophic AI overspending without sacrificing autonomous micro-transactions.
> 
> Bridle is the trust layer the agentic economy has been waiting for. Thank you."*

---

## 3. Step-by-Step Demo Instructions for Presenters

1. **Terminal Setup**:
   Open a terminal in the project directory:
   ```bash
   cd /home/g33k/Documents/Projects/Bridle
   ```

2. **Run the 1-Click Master Demo Script**:
   ```bash
   bash scripts/demo.sh
   ```
   This script automatically:
   - Verifies the Speculos Ledger emulator is running on `http://127.0.0.1:5000`.
   - Verifies the Bridle gateway is running on `http://127.0.0.1:8000`.
   - Executes Scenario A (micro-payment auto-approved).
   - Executes Scenario B (macro-payment hardware approved on Speculos).
   - Executes Scenario C (macro-payment hardware vetoed on Speculos).

3. **Verify HCS Topic**:
   Open the HashScan link in your browser:
   [https://hashscan.io/testnet/topic/0.0.10474223](https://hashscan.io/testnet/topic/0.0.10474223)

4. **Verify On-Chain Smart Contract**:
   [https://hashscan.io/testnet/address/0x5442A862d2B11709045BE15015368c7dD6B9cfd8](https://hashscan.io/testnet/address/0x5442A862d2B11709045BE15015368c7dD6B9cfd8)
