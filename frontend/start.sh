#!/bin/bash
# ──────────────────────────────────────────────────────────────
#  Hacklytics Startup Script
#  Starts VectorDB, Gateway, and Frontend dev server
# ──────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR"
FASTAPI_DIR="$SCRIPT_DIR/../fastapi"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Hacklytics — Full Stack Startup${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"

# ── Step 1: Start VectorDB (Docker) ──────────────────────────
echo -e "\n${YELLOW}[1/3]${NC} Starting VectorDB container..."
if command -v docker &> /dev/null; then
    (cd "$FASTAPI_DIR" && docker compose up -d vectoraidb 2>/dev/null) || \
        echo -e "  ${YELLOW}⚠  Docker not available or vectoraidb failed to start. Gateway will use fallback data.${NC}"
else
    echo -e "  ${YELLOW}⚠  Docker not installed. Gateway will skip VectorDB.${NC}"
fi

# ── Step 2: Start Gateway ────────────────────────────────────
echo -e "\n${YELLOW}[2/3]${NC} Starting Gemini Reasoning Gateway..."
ACTIAN_HOST=localhost "$FASTAPI_DIR/.venv/bin/python3" "$FRONTEND_DIR/gateway.py" &
GATEWAY_PID=$!
echo -e "  ${GREEN}✓${NC} Gateway PID: $GATEWAY_PID"

# Wait for gateway to be ready
echo -n "  Waiting for gateway..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:8080/health > /dev/null 2>&1; then
        echo -e " ${GREEN}ready!${NC}"
        break
    fi
    sleep 1
    echo -n "."
done

# ── Step 3: Start Frontend ───────────────────────────────────
echo -e "\n${YELLOW}[3/3]${NC} Starting Frontend dev server..."
(cd "$FRONTEND_DIR" && npm run dev) &
FRONTEND_PID=$!
echo -e "  ${GREEN}✓${NC} Frontend PID: $FRONTEND_PID"

sleep 2

echo -e "\n${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  All services started!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e ""
echo -e "  ${CYAN}Dashboard:${NC}  http://localhost:5173"
echo -e "  ${CYAN}Gateway:${NC}    http://127.0.0.1:8080"
echo -e "  ${CYAN}Health:${NC}     http://127.0.0.1:8080/health"
echo -e ""
echo -e "  ${YELLOW}Press the ▶ START SIM button on the dashboard to begin streaming.${NC}"
echo -e ""
echo -e "  Press Ctrl+C to stop all services."
echo -e ""

# Trap Ctrl+C to kill both processes
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    kill $GATEWAY_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    wait $GATEWAY_PID 2>/dev/null
    wait $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}Done.${NC}"
}
trap cleanup EXIT INT TERM

# Wait for either to exit
wait
