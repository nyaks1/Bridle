#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "============================================================"
echo "  BRIDLE — Starting Ledger Speculos Emulator"
echo "============================================================"

# Check if Docker is available
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "--> Docker detected. Launching Speculos container..."
    docker-compose up -d speculos
    echo "--> Speculos container started on ports 5000 (HTTP) and 40000 (APDU)."
else
    echo "--> Docker not detected or inactive. Launching native Speculos emulator bridge..."
    if [ -d "server/venv" ]; then
        PYTHON_EXEC="server/venv/bin/python"
    elif [ -d "venv" ]; then
        PYTHON_EXEC="venv/bin/python"
    else
        PYTHON_EXEC="python3"
    fi

    # Check if port 5000 is already running
    if curl -s http://127.0.0.1:5000/health >/dev/null 2>&1; then
        echo "--> Speculos emulator is already running on http://127.0.0.1:5000"
    else
        nohup $PYTHON_EXEC server/speculos_emulator.py > speculos.log 2>&1 &
        SPECULOS_PID=$!
        echo $SPECULOS_PID > speculos.pid
        echo "--> Speculos emulator launched in background (PID: $SPECULOS_PID)."
        sleep 2
    fi
fi

# Verify health
HEALTH=$(curl -s http://127.0.0.1:5000/health || echo "error")
if [[ "$HEALTH" == *"healthy"* ]]; then
    echo "--> [OK] Speculos Emulator is healthy on http://127.0.0.1:5000"
else
    echo "--> [WAIT] Waiting for Speculos emulator to become ready..."
    sleep 2
    curl -s http://127.0.0.1:5000/health || true
fi
echo "============================================================"

