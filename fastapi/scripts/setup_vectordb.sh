#!/bin/bash
# ================================================================
# Actian Vector DB and Redis Setup Script
# ================================================================
# This script orchestrates the complete setup for PROMPT 4:
# 1. Start Actian and Redis containers
# 2. Wait for health checks
# 3. Run protocol seeding script in Docker
# 4. Run tests in Docker
# 5. Report results
#
# Usage:
#   bash scripts/setup_vectordb.sh

set -e  # Exit on error

echo "================================================================"
echo "Actian Vector DB & Redis Setup - PROMPT 4"
echo "================================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to fastapi directory
cd "$(dirname "$0")/.."

echo ""
echo "Step 1/5: Starting Actian and Redis containers..."
echo "================================================================"

# Start containers
docker compose up -d actian redis

echo ""
echo "${GREEN}✓ Containers started${NC}"

echo ""
echo "Step 2/5: Waiting for health checks..."
echo "================================================================"

# Wait for Actian to be healthy
echo -n "Waiting for Actian (PostgreSQL) to be ready..."
for i in {1..30}; do
    if docker compose exec -T actian pg_isready -U vectordb > /dev/null 2>&1; then
        echo " ${GREEN}✓ Ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo " ${RED}✗ Timeout${NC}"
        echo "${RED}Error: Actian container failed to become healthy${NC}"
        exit 1
    fi
    echo -n "."
    sleep 1
done

# Wait for Redis to be healthy
echo -n "Waiting for Redis to be ready..."
for i in {1..30}; do
    if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo " ${GREEN}✓ Ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo " ${RED}✗ Timeout${NC}"
        echo "${RED}Error: Redis container failed to become healthy${NC}"
        exit 1
    fi
    echo -n "."
    sleep 1
done

echo ""
echo "${GREEN}✓ All services healthy${NC}"

echo ""
echo "Step 3/5: Verifying database schema..."
echo "================================================================"

# Check if tables exist
TABLE_COUNT=$(docker compose exec -T actian psql -U vectordb -d safety_rag -t -c "
    SELECT COUNT(*) FROM information_schema.tables
    WHERE table_name IN ('safety_protocols', 'incident_log')
" 2>/dev/null | tr -d ' ')

if [ "$TABLE_COUNT" -eq "2" ]; then
    echo "${GREEN}✓ Schema tables exist (safety_protocols, incident_log)${NC}"
else
    echo "${YELLOW}⚠ Schema not initialized, creating tables...${NC}"
    docker compose exec -T actian psql -U vectordb -d safety_rag < init.sql
    echo "${GREEN}✓ Schema created${NC}"
fi

echo ""
echo "Step 4/5: Seeding safety protocols..."
echo "================================================================"

# Check if protocols already exist
PROTOCOL_COUNT=$(docker compose exec -T actian psql -U vectordb -d safety_rag -t -c "
    SELECT COUNT(*) FROM safety_protocols
" 2>/dev/null | tr -d ' ')

if [ "$PROTOCOL_COUNT" -gt "0" ]; then
    echo "${YELLOW}⚠ Found $PROTOCOL_COUNT existing protocols${NC}"
    echo -n "Clear and re-seed? (y/n): "
    read -r RESPONSE
    if [ "$RESPONSE" != "y" ]; then
        echo "${YELLOW}Skipping seeding (keeping existing protocols)${NC}"
        SKIP_SEEDING=true
    fi
fi

if [ "$SKIP_SEEDING" != "true" ]; then
    # Run seeding script in Docker
    echo "Running seeding script in Docker container..."
    docker run --rm \
        --network hacklytics_rag_network \
        -v "$(pwd)/scripts/seed_protocols.py:/app/seed_protocols.py" \
        -e ACTIAN_HOST=actian \
        -e ACTIAN_PORT=5432 \
        -e ACTIAN_USER=vectordb \
        -e ACTIAN_PASSWORD=vectordb_pass \
        -e ACTIAN_DATABASE=safety_rag \
        python:3.11-slim \
        bash -c "
            pip install -q asyncpg sentence-transformers && \
            python /app/seed_protocols.py
        "

    echo ""
    echo "${GREEN}✓ Protocols seeded successfully${NC}"
fi

# Verify protocol count
FINAL_COUNT=$(docker compose exec -T actian psql -U vectordb -d safety_rag -t -c "
    SELECT COUNT(*) FROM safety_protocols
" 2>/dev/null | tr -d ' ')

echo "${GREEN}✓ Total protocols in database: $FINAL_COUNT${NC}"

echo ""
echo "Step 5/5: Running tests in Docker..."
echo "================================================================"

# Run Actian tests
echo ""
echo "Running Actian setup tests..."
docker run --rm \
    --network hacklytics_rag_network \
    -v "$(pwd)/tests:/app/tests" \
    -v "$(pwd)/backend:/app/backend" \
    -e ACTIAN_HOST=actian \
    -e ACTIAN_PORT=5432 \
    -e ACTIAN_USER=vectordb \
    -e ACTIAN_PASSWORD=vectordb_pass \
    -e ACTIAN_DATABASE=safety_rag \
    -e PYTHONPATH=/app \
    python:3.11-slim \
    bash -c "
        pip install -q asyncpg sentence-transformers pytest pytest-asyncio && \
        pytest /app/tests/test_actian_setup.py -v -s
    "

ACTIAN_TEST_EXIT=$?

# Run Redis cache tests
echo ""
echo "Running Redis cache tests..."
docker run --rm \
    --network hacklytics_rag_network \
    -v "$(pwd)/tests:/app/tests" \
    -v "$(pwd)/backend:/app/backend" \
    -e REDIS_URL=redis://redis:6379 \
    -e PYTHONPATH=/app \
    python:3.11-slim \
    bash -c "
        pip install -q redis pytest pytest-asyncio numpy sentence-transformers && \
        pytest /app/tests/test_redis_cache.py -v -s
    "

REDIS_TEST_EXIT=$?

echo ""
echo "================================================================"
echo "Setup Complete - Results Summary"
echo "================================================================"

# Display service status
echo ""
echo "Service Status:"
docker compose ps actian redis

# Display protocol coverage
echo ""
echo "Protocol Coverage:"
docker compose exec -T actian psql -U vectordb -d safety_rag -c "
    SELECT severity, category, COUNT(*) as count
    FROM safety_protocols
    GROUP BY severity, category
    ORDER BY severity, category
" 2>/dev/null

# Test results
echo ""
echo "Test Results:"
if [ $ACTIAN_TEST_EXIT -eq 0 ]; then
    echo "  ${GREEN}✓ Actian setup tests: PASSED${NC}"
else
    echo "  ${RED}✗ Actian setup tests: FAILED${NC}"
fi

if [ $REDIS_TEST_EXIT -eq 0 ]; then
    echo "  ${GREEN}✓ Redis cache tests: PASSED${NC}"
else
    echo "  ${RED}✗ Redis cache tests: FAILED${NC}"
fi

echo ""
echo "================================================================"

# Exit with error if any tests failed
if [ $ACTIAN_TEST_EXIT -ne 0 ] || [ $REDIS_TEST_EXIT -ne 0 ]; then
    echo "${RED}✗ PROMPT 4 setup FAILED - see errors above${NC}"
    exit 1
fi

echo "${GREEN}✓ PROMPT 4 setup COMPLETE and ready for PROMPT 5 integration${NC}"
echo ""
echo "Next steps:"
echo "  - Actian and Redis are running and healthy"
echo "  - $FINAL_COUNT safety protocols loaded"
echo "  - All tests passing"
echo "  - Ready to integrate with RAG orchestrator (PROMPT 5)"
echo ""
echo "To view logs:"
echo "  docker compose logs -f actian"
echo "  docker compose logs -f redis"
echo ""
echo "To query database:"
echo "  docker compose exec actian psql -U vectordb -d safety_rag"
echo ""
echo "To test Redis:"
echo "  docker compose exec redis redis-cli"
echo "================================================================"
