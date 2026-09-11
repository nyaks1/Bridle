#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "================================================================================"
echo "  BRIDLE — DUAL-TRACK DEMONSTRATION RUNNER"
echo "  Hedera AI & Agentic Payments x Ledger AI Agents x Ledger "
echo "================================================================================"

# Step 1: Check Python venv
if [ -d "server/venv" ]; then
    PYTHON_EXEC="server/venv/bin/python"
    UVICORN_EXEC="server/venv/bin/uvicorn"
else
    PYTHON_EXEC="python3"
    UVICORN_EXEC="uvicorn"
fi

# Step 2: Ensure Speculos Emulator is active on port 5000
echo -e "\n[1/5] Checking Ledger Speculos Emulator..."
if curl -s http://127.0.0.1:5000/health >/dev/null 2>&1; then
    echo "  ✅ Speculos Emulator running on http://127.0.0.1:5000"
else
    echo "  Starting Speculos Emulator..."
    bash scripts/run_speculos.sh
    sleep 2
fi

# Step 3: Ensure Gateway Server is active on port 8000
echo -e "\n[2/5] Checking Bridle Payment Gateway..."
if curl -s http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    echo "  ✅ Bridle Gateway running on http://127.0.0.1:8000"
else
    echo "  Starting Bridle Gateway in background..."
    nohup $UVICORN_EXEC server.server:app --host 127.0.0.1 --port 8000 > server.log 2>&1 &
    SERVER_PID=$!
    echo $SERVER_PID > server.pid
    sleep 2
    echo "  ✅ Bridle Gateway started (PID: $SERVER_PID)"
fi

echo -e "\n================================================================================"
echo "  SCENARIO A: AUTONOMOUS MICRO-PAYMENT (<= 1.0 HBAR)"
echo "  Endpoint: /api/weather (0.05 HBAR / $0.005)"
echo "  Policy: Within budget -> Autonomous software ECDSA signing on Hedera Testnet"
echo "================================================================================"
AGENT_TASK="Get current weather data for Cape Town, South Africa" \
$PYTHON_EXEC server/agent.py --endpoint=/api/weather

echo -e "\n================================================================================"
echo "  SCENARIO B: MACRO-PAYMENT (> 1.0 HBAR) WITH HARDWARE APPROVAL"
echo "  Endpoint: /api/premium-report (1.50 HBAR / $1.500)"
echo "  Policy: Exceeds threshold -> Execution paused -> Speculos OLED Hardware Approval"
echo "================================================================================"
AGENT_TASK="Get enterprise climate risk archive and premium report for Cape Town" \
$PYTHON_EXEC server/agent.py --endpoint=/api/premium-report --auto-approve

echo -e "\n================================================================================"
echo "  SCENARIO C: MACRO-PAYMENT (> 1.0 HBAR) WITH HARDWARE VETO / REJECTION"
echo "  Endpoint: /api/premium-report (1.50 HBAR)"
echo "  Policy: Operator presses LEFT BUTTON on Ledger -> Transaction aborted -> HCS audit"
echo "================================================================================"
AGENT_TASK="Get enterprise climate risk archive and premium report for Cape Town" \
$PYTHON_EXEC server/agent.py --endpoint=/api/premium-report --veto

echo -e "\n================================================================================"
echo "  DEMO COMPLETE — VERIFY IMMUTABLE AUDIT TRAIL ON HEDERA"
echo "================================================================================"
echo "  HashScan HCS Topic:     https://hashscan.io/testnet/topic/0.0.10474223"
echo "  BridlePaywall Contract: https://hashscan.io/testnet/address/0x5442A862d2B11709045BE15015368c7dD6B9cfd8"
echo "================================================================================"

