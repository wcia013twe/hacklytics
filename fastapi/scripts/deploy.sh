#!/bin/bash
set -e

echo "======================================"
echo "Deploying Hacklytics RAG Backend"
echo "======================================"

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Prerequisites OK${NC}"

# 2. Build Docker images
echo ""
echo -e "${YELLOW}Building Docker images...${NC}"
docker compose build
echo -e "${GREEN}✅ Images built${NC}"

# 3. Start services
echo ""
echo -e "${YELLOW}Starting services...${NC}"
docker compose up -d
echo -e "${GREEN}✅ Services started${NC}"

# 4. Wait for VectorAI DB to be healthy
echo ""
echo -e "${YELLOW}Waiting for Actian VectorAI DB to be ready...${NC}"
RETRY_COUNT=0
MAX_RETRIES=60  # 2 minutes (60 * 2s)
until docker exec hacklytics_vectoraidb timeout 3 bash -c '</dev/tcp/localhost/50051' &> /dev/null; do
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo -e "${RED}❌ Actian VectorAI DB failed to start within 2 minutes${NC}"
        docker compose logs vectoraidb
        exit 1
    fi
    echo "  Waiting for VectorAI DB... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done
echo -e "${GREEN}✅ Actian VectorAI DB ready${NC}"

# 5. Wait for Redis to be healthy
echo ""
echo -e "${YELLOW}Waiting for Redis to be ready...${NC}"
RETRY_COUNT=0
MAX_RETRIES=30  # 30 seconds
until docker exec hacklytics_redis redis-cli ping &> /dev/null; do
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo -e "${RED}❌ Redis failed to start within 30 seconds${NC}"
        docker compose logs redis
        exit 1
    fi
    echo "  Waiting for Redis... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))
done
echo -e "${GREEN}✅ Redis ready${NC}"

# 6. Wait for RAG service to be healthy
echo ""
echo -e "${YELLOW}Waiting for RAG service to be ready...${NC}"
RETRY_COUNT=0
MAX_RETRIES=60  # 2 minutes
until curl -sf http://localhost:8001/health &> /dev/null; do
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo -e "${RED}❌ RAG service failed to start within 2 minutes${NC}"
        docker compose logs rag
        exit 1
    fi
    echo "  Waiting for RAG service... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done
echo -e "${GREEN}✅ RAG service ready${NC}"

# 7. Wait for Ingest service to be healthy
echo ""
echo -e "${YELLOW}Waiting for Ingest service to be ready...${NC}"
RETRY_COUNT=0
MAX_RETRIES=30
until curl -sf http://localhost:8000/health &> /dev/null; do
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo -e "${RED}❌ Ingest service failed to start within 1 minute${NC}"
        docker compose logs ingest
        exit 1
    fi
    echo "  Waiting for Ingest service... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done
echo -e "${GREEN}✅ Ingest service ready${NC}"

# 8. Initialize VectorAI DB collections (if not already done)
echo ""
echo -e "${YELLOW}Checking VectorAI DB collections...${NC}"
if docker exec hacklytics_rag python -c "from backend.actian_pool import ActianPool; import asyncio; asyncio.run(ActianPool().check_collections())" &> /dev/null; then
    echo -e "${GREEN}✅ Collections already initialized${NC}"
else
    echo -e "${YELLOW}Initializing VectorAI DB collections...${NC}"
    docker exec hacklytics_rag python scripts/init_actian_collections.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Collections initialized${NC}"
    else
        echo -e "${RED}❌ Collection initialization failed${NC}"
        exit 1
    fi
fi

# 9. Seed protocols (if needed)
echo ""
echo -e "${YELLOW}Checking safety protocols...${NC}"
PROTOCOL_COUNT=$(docker exec hacklytics_rag python -c "from backend.actian_pool import ActianPool; import asyncio; print(asyncio.run(ActianPool().count_protocols()))" 2>/dev/null || echo "0")

if [ "$PROTOCOL_COUNT" -lt 10 ]; then
    echo -e "${YELLOW}Seeding safety protocols...${NC}"
    docker exec hacklytics_rag python scripts/seed_protocols.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Protocols seeded${NC}"
    else
        echo -e "${RED}❌ Protocol seeding failed (this is optional, continuing...)${NC}"
    fi
else
    echo -e "${GREEN}✅ Protocols already seeded ($PROTOCOL_COUNT protocols)${NC}"
fi

# 10. Verify deployment
echo ""
echo -e "${YELLOW}Verifying deployment...${NC}"

# Check RAG health
RAG_HEALTH=$(curl -s http://localhost:8001/health | grep -o '"status":"healthy"' || echo "")
if [ -z "$RAG_HEALTH" ]; then
    echo -e "${RED}❌ RAG service not healthy${NC}"
    docker compose logs rag --tail=50
    exit 1
fi

# Check Ingest health
INGEST_HEALTH=$(curl -s http://localhost:8000/health | grep -o '"status":"healthy"' || echo "")
if [ -z "$INGEST_HEALTH" ]; then
    echo -e "${RED}❌ Ingest service not healthy${NC}"
    docker compose logs ingest --tail=50
    exit 1
fi

# Check Redis health
REDIS_HEALTH=$(docker exec hacklytics_redis redis-cli ping 2>/dev/null || echo "")
if [ "$REDIS_HEALTH" != "PONG" ]; then
    echo -e "${YELLOW}⚠️  Redis not responding (cache layer degraded)${NC}"
else
    echo -e "${GREEN}✅ Redis cache healthy${NC}"
fi

echo -e "${GREEN}✅ All services healthy${NC}"

echo ""
echo "======================================"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo "======================================"
echo ""
echo "Services:"
echo "  - Actian VectorAI DB:  gRPC on localhost:50051"
echo "  - Redis Cache:         localhost:6379"
echo "  - RAG Service:         http://localhost:8001"
echo "  - Ingest Service:      http://localhost:8000"
echo "  - WebSocket:           ws://localhost:8000/ws/{session_id}"
echo ""
echo "Quick Commands:"
echo "  Health check:    curl http://localhost:8000/health"
echo "  Cache stats:     curl http://localhost:8001/cache/stats"
echo "  View logs:       docker compose logs -f"
echo "  Stop services:   docker compose down"
echo ""
echo "Next Steps:"
echo "  1. Run tests:    pytest tests/test_e2e_integration.py -v"
echo "  2. See docs:     cat docs/QUICKSTART.md"
echo ""
