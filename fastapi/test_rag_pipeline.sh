#!/bin/bash
# Complete RAG Pipeline Test Script

echo "=================================="
echo "RAG Pipeline System Test"
echo "=================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check Docker services
echo "1. Checking Docker Services..."
docker compose ps
echo ""

# Test 2: RAG Service Health
echo "2. Testing RAG Service Health..."
response=$(curl -s http://localhost:8001/health)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ RAG service responding${NC}"
    echo "$response" | python3 -m json.tool
else
    echo -e "${RED}✗ RAG service not responding${NC}"
fi
echo ""

# Test 3: PostgreSQL Connection
echo "3. Testing PostgreSQL Connection..."
docker exec hacklytics_postgres pg_isready -U hacklytics
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ PostgreSQL ready${NC}"
else
    echo -e "${RED}✗ PostgreSQL not ready${NC}"
fi
echo ""

# Test 4: Redis Connection
echo "4. Testing Redis Connection..."
docker exec hacklytics_redis redis-cli ping
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Redis ready${NC}"
else
    echo -e "${RED}✗ Redis not ready${NC}"
fi
echo ""

# Test 5: Send Test Packet
echo "5. Sending Test Packet to RAG..."
test_packet='{
  "device_id": "jetson_test_001",
  "session_id": "mission_test_001",
  "timestamp": '$(date +%s.%N)',
  "hazard_level": "CRITICAL",
  "scores": {
    "fire_dominance": 0.85,
    "smoke_opacity": 0.70,
    "proximity_alert": true
  },
  "tracked_objects": [
    {
      "id": 1,
      "label": "fire",
      "status": "growing",
      "duration_in_frame": 5.0
    }
  ],
  "visual_narrative": "Test packet: Large fire detected with high smoke opacity"
}'

response=$(curl -s -X POST http://localhost:8001/process \
  -H "Content-Type: application/json" \
  -d "$test_packet")

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Packet processed successfully${NC}"
    echo "$response" | python3 -m json.tool
else
    echo -e "${RED}✗ Failed to process packet${NC}"
fi
echo ""

# Test 6: Dashboard Access
echo "6. Checking Dashboard..."
if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${GREEN}✓ Dashboard server running on port 8080${NC}"
    echo "   Access at: http://localhost:8080/realtime_dashboard.html"
else
    echo -e "${YELLOW}⚠ Dashboard server not running${NC}"
    echo "   Start with: python3 -m http.server 8080 --directory static"
fi
echo ""

# Test 7: Mock Stream Test
echo "7. Testing Mock Stream (5 packets)..."
python3 scripts/mock_nano_stream.py --scenario growing_warehouse_fire --duration 2
echo ""

echo "=================================="
echo "Test Complete!"
echo "=================================="
echo ""
echo "To run continuous monitoring:"
echo "  1. Open: http://localhost:8080/realtime_dashboard.html"
echo "  2. Run: python3 scripts/mock_nano_stream.py --scenario growing_warehouse_fire --loop"
echo ""
