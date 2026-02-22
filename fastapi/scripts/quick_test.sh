#!/bin/bash
#
# Quick Test Script - Fire Detection Pipeline
#
# This script demonstrates the complete streaming pipeline:
# 1. Starts FastAPI backend
# 2. Opens dashboard in browser
# 3. Starts mock streaming service
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FASTAPI_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==========================================="
echo "Fire Detection Pipeline - Quick Test"
echo "==========================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

# Check if dependencies are installed
echo "[1/5] Checking dependencies..."
if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -q fastapi uvicorn websockets httpx
fi
echo "✓ Dependencies OK"
echo ""

# Start FastAPI in background
echo "[2/5] Starting FastAPI backend..."
cd "$FASTAPI_DIR"
python3 -m uvicorn backend.main_ingest:app --port 8000 &
FASTAPI_PID=$!
echo "✓ FastAPI started (PID: $FASTAPI_PID)"
echo ""

# Wait for FastAPI to be ready
echo "[3/5] Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health &>/dev/null; then
        echo "✓ Backend ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Error: Backend failed to start"
        kill $FASTAPI_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done
echo ""

# Open dashboard in browser
echo "[4/5] Opening dashboard..."
if command -v open &> /dev/null; then
    # macOS
    open http://localhost:8000/
elif command -v xdg-open &> /dev/null; then
    # Linux
    xdg-open http://localhost:8000/
else
    echo "Please manually open: http://localhost:8000/"
fi
echo "✓ Dashboard: http://localhost:8000/"
echo ""

# Give user time to see dashboard
sleep 3

# Start mock streaming
echo "[5/5] Starting mock streaming service..."
echo ""
echo "==========================================="
echo "Pipeline is running!"
echo "==========================================="
echo ""
echo "  Dashboard:      http://localhost:8000/"
echo "  Health Check:   http://localhost:8000/health"
echo "  WebSocket:      ws://localhost:8000/ws/dashboard-001"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Trap Ctrl+C to cleanup
trap 'echo ""; echo "Stopping services..."; kill $FASTAPI_PID 2>/dev/null || true; exit 0' INT

# Run mock streamer (foreground)
python3 "$SCRIPT_DIR/mock_stream_service.py"

# Cleanup on exit
kill $FASTAPI_PID 2>/dev/null || true
