# Bridle

**A hardware-confirmed trust layer for AI agent payments.**

Agents pay for what they use — autonomously, over [x402](https://github.com/x402-foundation/x402) on [Hedera](https://hedera.com/) — but nothing above a spending threshold moves without a human holding the reins. A [Ledger](https://www.ledger.com/) hardware device confirms or rejects every high-value payment before it settles.

Built for [ETHGlobal Online](https://ethglobal.com/) 2026.

---

## The problem

AI agents are starting to hold wallets and spend money on their own — calling paid APIs, buying data, paying for compute. Today that mostly means an API key sitting in a `.env` file, and an agent with no real limit on what it can spend. This maps directly to **OWASP LLM Top 10 — LLM08: Excessive Agency**: systems that let an AI act on money or resources with no meaningful human checkpoint.

## The solution

Bridle sits between an agent and its money.

1. The agent discovers a metered service and attempts to pay for it via **x402** (HTTP 402 Payment Required), settled on **Hedera** — sub-cent fees, no subscriptions, no leaked API keys.
2. Payments under a set threshold settle automatically.
3. Payments **over** the threshold pause the agent and send a confirmation request to a **Ledger** hardware device. A human taps to confirm or reject — physically, on hardware, before any funds move.
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

- **Hedera — AI & Agentic Payments**
- **Ledger — AI Agents x Ledger**

## Team

- **Nyakallo (Nyaks)** — agent logic (Python), Ledger Key Ring CLI integration
- **Liyabona** — Hedera-side x402-gated service (Solidity, EVM-compatible)

## Status

🚧 In progress — building for ETHGlobal Online, submission deadline Sun Sept 13, 2026, 12:00pm EDT.

## Setup

_(to be filled in as the build progresses)_

## License

_(to be decided)_