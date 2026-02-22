#!/bin/bash
# Multi-Responder Demo Launcher
# Starts all mock responders + aggregator in parallel

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  🏢  Multi-Location Fire Response Demo                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Change to scripts directory
cd "$(dirname "$0")"

# Check if GEMINI_API_KEY is set
if [ -z "$GEMINI_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  GEMINI_API_KEY not set - aggregator will use fallback synthesis${NC}"
    echo -e "${YELLOW}   (Set with: export GEMINI_API_KEY=your-key-here)${NC}"
    echo ""
fi

# Store PIDs for cleanup
PIDS=()

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping all services...${NC}"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    echo -e "${GREEN}✅ Demo stopped${NC}"
    exit 0
}

# Trap Ctrl+C
trap cleanup INT TERM

# Step 1: Start Aggregator Service
echo -e "${YELLOW}[1/4]${NC} Starting Aggregator Service..."
python3 aggregator_service.py > /tmp/aggregator.log 2>&1 &
AGGREGATOR_PID=$!
PIDS+=($AGGREGATOR_PID)
sleep 2

# Check if aggregator started successfully
if ! curl -s http://localhost:8002/health > /dev/null; then
    echo -e "${RED}❌ Aggregator failed to start${NC}"
    echo -e "${RED}   Check logs: tail /tmp/aggregator.log${NC}"
    cleanup
fi
echo -e "${GREEN}✅ Aggregator running on :8002${NC}"

# Step 2: Start Kitchen Responder
echo -e "${YELLOW}[2/4]${NC} Starting Kitchen Responder..."
python3 mock_responder.py scenarios/kitchen_fire_progression.json > /tmp/kitchen.log 2>&1 &
KITCHEN_PID=$!
PIDS+=($KITCHEN_PID)
sleep 0.5

# Step 3: Start Hallway Responder
echo -e "${YELLOW}[3/4]${NC} Starting Hallway Responder..."
python3 mock_responder.py scenarios/hallway_smoke_spread.json > /tmp/hallway.log 2>&1 &
HALLWAY_PID=$!
PIDS+=($HALLWAY_PID)
sleep 0.5

# Step 4: Start Living Room Responder
echo -e "${YELLOW}[4/4]${NC} Starting Living Room Responder..."
python3 mock_responder.py scenarios/living_room_structural.json > /tmp/living_room.log 2>&1 &
LIVING_ROOM_PID=$!
PIDS+=($LIVING_ROOM_PID)
sleep 0.5

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  🎬  Demo Running!                                         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Endpoints:${NC}"
echo -e "  Aggregator Status: ${GREEN}http://localhost:8002/status${NC}"
echo -e "  Dashboard:         ${GREEN}http://localhost:3000${NC}"
echo -e "  Backend:           ${GREEN}http://localhost:8000${NC}"
echo ""
echo -e "${BLUE}Logs:${NC}"
echo -e "  Aggregator: tail -f /tmp/aggregator.log"
echo -e "  Kitchen:    tail -f /tmp/kitchen.log"
echo -e "  Hallway:    tail -f /tmp/hallway.log"
echo -e "  Living Room: tail -f /tmp/living_room.log"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for any process to exit
wait
