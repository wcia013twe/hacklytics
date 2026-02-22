# PROMPT 5: Integration & Deployment

**Objective:** Integrate all components (agents, orchestrator, Actian) and deploy full stack with E2E validation.

**Status:** ⚠️ Depends on ALL - Run after Prompts 1, 2, 3, and 4 complete

**Deliverables:**
- Full Docker Compose stack (ingest + rag + actian)
- Environment configuration
- E2E integration tests
- Deployment documentation

---

## Context from RAG.MD

This is the final integration phase where all components come together:
- **Agents** (Prompt 1) + **Orchestrator** (Prompt 2) + **Actian** (Prompt 4)
- **Dual-path validation** (Prompt 3 tests)
- **Production deployment** ready

Refer to RAG.MD sections 2.1 (Service Topology), 4 (Tech Stack), and 5 (Implementation Phases).

---

## Task 1: Full Docker Compose Stack

Create `docker-compose.yml` (root level):

```yaml
version: '3.8'

services:
  # ==========================================
  # Actian Vector DB (from Prompt 4)
  # ==========================================
  actian:
    image: ankane/pgvector:latest  # Use actian/vector if available
    container_name: hacklytics_actian
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: vectordb
      POSTGRES_PASSWORD: vectordb_pass
      POSTGRES_DB: safety_rag
    volumes:
      - actian_data:/var/lib/postgresql/data
      - ./docker/init.sql:/docker-entrypoint-initdb.d/01_schema.sql
    networks:
      - hacklytics_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vectordb"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ==========================================
  # Redis Cache Layer (from Prompt 4)
  # ==========================================
  redis:
    image: redis:7-alpine
    container_name: hacklytics_redis
    ports:
      - "6379:6379"
    networks:
      - hacklytics_network
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    restart: unless-stopped

  # ==========================================
  # Ingest Service (from Prompt 2)
  # ==========================================
  ingest:
    build:
      context: ./backend
      dockerfile: Dockerfile.ingest
    container_name: hacklytics_ingest
    ports:
      - "8000:8000"  # FastAPI + WebSocket
    environment:
      - ZMQ_SUBSCRIBE=tcp://host.docker.internal:5555  # Jetson publishes here
      - ACTIAN_HOST=actian
      - ACTIAN_USER=vectordb
      - ACTIAN_PASSWORD=vectordb_pass
      - ACTIAN_DATABASE=safety_rag
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=INFO
    depends_on:
      actian:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - hacklytics_network
    restart: unless-stopped
    volumes:
      - ./backend:/app  # Mount for development

  # ==========================================
  # RAG Service (Optional: Separate container)
  # ==========================================
  # For now, RAG logic runs inside ingest container
  # In production, split into separate service

networks:
  hacklytics_network:
    driver: bridge

volumes:
  actian_data:
    driver: local
  redis_data:
    driver: local
```

---

## Task 2: Dockerfiles

Create `backend/Dockerfile.ingest`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download and cache embedding model at build time
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application code
COPY . .

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run FastAPI with uvicorn
CMD ["uvicorn", "ingest_service:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
```

Create `backend/requirements.txt`:

```txt
# FastAPI + ASGI server
fastapi==0.104.1
uvicorn[standard]==0.24.0
websockets==12.0

# ZeroMQ
pyzmq==25.1.1

# Actian/PostgreSQL
asyncpg==0.29.0

# Redis cache
redis==5.0.1

# Embeddings
sentence-transformers==2.2.2
torch==2.1.0

# Data validation
pydantic==2.5.0

# Numerical computing
numpy==1.26.2

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
```

---

## Task 3: Environment Configuration

Create `.env`:

```bash
# Actian Configuration
ACTIAN_HOST=localhost  # Use 'actian' when running in Docker
ACTIAN_PORT=5432
ACTIAN_USER=vectordb
ACTIAN_PASSWORD=vectordb_pass
ACTIAN_DATABASE=safety_rag

# Redis Cache Configuration
REDIS_URL=redis://localhost:6379  # Use 'redis://redis:6379' when running in Docker
REDIS_MAX_CONNECTIONS=10
REDIS_SOCKET_TIMEOUT_MS=100

# ZeroMQ Configuration
ZMQ_SUBSCRIBE=tcp://localhost:5555  # Jetson endpoint

# Service Configuration
LOG_LEVEL=INFO
REFLEX_LATENCY_THRESHOLD_MS=50
RAG_LATENCY_THRESHOLD_MS=2000  # With cache: typically 50-150ms (cache hit) / 500-2000ms (cache miss)

# Temporal Buffer
BUFFER_WINDOW_SECONDS=10

# Embedding Model
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_TIMEOUT_MS=50

# Actian Query Timeouts (used only on cache miss)
PROTOCOL_RETRIEVAL_TIMEOUT_MS=200
HISTORY_RETRIEVAL_TIMEOUT_MS=200

# Incident Logging
INCIDENT_BATCH_INTERVAL_SECONDS=2

# Cache Settings
CACHE_PROTOCOL_TTL_SECONDS=300  # 5 minutes
CACHE_SESSION_TTL_SECONDS=1800  # 30 minutes
CACHE_ENABLED=true  # Set to false to disable cache (Actian-only mode)
```

---

## Task 4: Update Orchestrator with Actian Integration

Update `backend/orchestrator.py` to use Actian pool:

```python
# In RAGOrchestrator.__init__
async def startup(self):
    """
    Initialize orchestrator: warmup models, connect to Actian
    """
    logger.info("RAGOrchestrator starting up...")

    # Connect to Actian
    if self.actian_pool:
        logger.info("Connecting to Actian...")
        # Pool is already connected from ingest_service.py
    else:
        logger.warning("No Actian pool provided - RAG will run in degraded mode")

    # Warmup embedding model
    await self.embedding_agent.warmup_model()

    # Warmup Actian with test query
    if self.protocol_agent:
        try:
            test_vector = [0.0] * 384
            await self.protocol_agent.execute_vector_search(
                vector=test_vector,
                severity=["HIGH"],
                top_k=1,
                timeout=500
            )
            logger.info("Actian warmup query successful")
        except Exception as e:
            logger.warning(f"Actian warmup failed: {e}")

    logger.info("RAGOrchestrator ready")
```

Update `backend/ingest_service.py` to create Actian pool:

```python
from actian_pool import ActianPool

actian_pool: ActianPool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator, actian_pool, zmq_task

    logger.info("Starting ingest service...")

    # Connect to Actian
    actian_pool = ActianPool()
    try:
        await actian_pool.connect()
    except Exception as e:
        logger.error(f"Actian connection failed: {e}. Running in degraded mode.")
        actian_pool = None

    # Initialize orchestrator with Actian pool
    orchestrator = RAGOrchestrator(actian_pool=actian_pool)
    await orchestrator.startup()

    # Start ZMQ listener
    zmq_task = asyncio.create_task(zmq_listener())

    logger.info("Ingest service ready")

    yield

    # Shutdown
    logger.info("Shutting down ingest service...")
    if zmq_task:
        zmq_task.cancel()
    if actian_pool:
        await actian_pool.close()
```

---

## Task 5: E2E Integration Tests

Create `tests/integration/test_e2e_pipeline.py`:

```python
import pytest
import json
import time
import asyncio
from backend.orchestrator import RAGOrchestrator
from backend.actian_pool import ActianPool


@pytest.fixture
async def orchestrator_with_actian():
    """Create orchestrator with real Actian connection"""
    pool = ActianPool()
    await pool.connect(
        host='localhost',
        port=5432,
        user='vectordb',
        password='vectordb_pass',
        database='safety_rag'
    )

    orchestrator = RAGOrchestrator(actian_pool=pool)
    await orchestrator.startup()

    yield orchestrator

    await pool.close()


@pytest.mark.asyncio
async def test_e2e_critical_packet_with_rag(orchestrator_with_actian):
    """
    E2E Test: Send CRITICAL packet, verify both reflex AND RAG execute
    """
    packet = {
        "device_id": "jetson_e2e_test",
        "session_id": "e2e_session_001",
        "timestamp": time.time(),
        "hazard_level": "CRITICAL",
        "scores": {
            "fire_dominance": 0.85,
            "smoke_opacity": 0.75,
            "proximity_alert": True
        },
        "tracked_objects": [
            {"id": 42, "label": "person", "status": "stationary", "duration_in_frame": 10.0},
            {"id": 7, "label": "fire", "status": "growing", "duration_in_frame": 5.0}
        ],
        "visual_narrative": "CRITICAL: Person trapped in corner, fire growing rapidly, exit blocked"
    }

    raw_message = json.dumps(packet)

    # Process packet
    result = await orchestrator_with_actian.process_packet(raw_message)

    # Verify reflex path succeeded
    assert result["success"] == True
    assert "reflex_result" in result
    assert result["reflex_result"]["latency_ms"] < 100

    # Verify RAG was invoked (async, need to wait)
    await asyncio.sleep(2)  # Allow RAG to complete

    # Check metrics
    metrics = orchestrator_with_actian.metrics.summary()
    assert metrics["counters"]["packets.valid"] >= 1

    # Check RAG health
    assert orchestrator_with_actian.rag_health.is_healthy()

    print(f"✅ E2E test passed")
    print(f"   Reflex latency: {result['reflex_result']['latency_ms']:.2f}ms")
    print(f"   RAG healthy: {orchestrator_with_actian.rag_health.is_healthy()}")


@pytest.mark.asyncio
async def test_e2e_temporal_escalation(orchestrator_with_actian):
    """
    E2E Test: Send escalation sequence, verify history retrieval works
    """
    session_id = "e2e_escalation_001"
    base_time = time.time()

    escalation = [
        ("Smoke detected", "LOW", 0.15),
        ("Fire growing in corner", "MODERATE", 0.35),
        ("Person visible near fire", "HIGH", 0.60),
        ("Person trapped, exit blocked", "CRITICAL", 0.85)
    ]

    for i, (narrative, hazard, fire_dom) in enumerate(escalation):
        packet = {
            "device_id": "jetson_escalation",
            "session_id": session_id,
            "timestamp": base_time + i,
            "hazard_level": hazard,
            "scores": {
                "fire_dominance": fire_dom,
                "smoke_opacity": 0.5,
                "proximity_alert": i == 3  # Only on last packet
            },
            "tracked_objects": [],
            "visual_narrative": narrative
        }

        result = await orchestrator_with_actian.process_packet(json.dumps(packet))
        assert result["success"] == True

        # Wait for RAG to complete (if invoked)
        await asyncio.sleep(0.5)

    # On 4th packet (CRITICAL), check that incident_log has entries
    conn = await orchestrator_with_actian.actian_pool.pool.acquire()
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM incident_log WHERE session_id = $1",
        session_id
    )
    await orchestrator_with_actian.actian_pool.pool.release(conn)

    print(f"\nIncident log entries for session: {count}")
    assert count >= 2, f"Expected ≥2 incident log entries, got {count}"

    # Cleanup
    conn = await orchestrator_with_actian.actian_pool.pool.acquire()
    await conn.execute("DELETE FROM incident_log WHERE session_id = $1", session_id)
    await orchestrator_with_actian.actian_pool.pool.release(conn)

    print("✅ Temporal escalation test passed")


@pytest.mark.asyncio
async def test_e2e_protocol_retrieval(orchestrator_with_actian):
    """
    E2E Test: Verify protocol retrieval returns relevant protocols
    """
    packet = {
        "device_id": "jetson_protocol_test",
        "session_id": "protocol_test_001",
        "timestamp": time.time(),
        "hazard_level": "CRITICAL",
        "scores": {
            "fire_dominance": 0.9,
            "smoke_opacity": 0.8,
            "proximity_alert": True
        },
        "tracked_objects": [],
        "visual_narrative": "Flashover conditions imminent, temperature rising rapidly"
    }

    # Embed narrative
    embedding = await orchestrator_with_actian.embedding_agent.embed_text(
        packet["visual_narrative"],
        request_id="protocol_test"
    )

    # Retrieve protocols
    protocols = await orchestrator_with_actian.protocol_agent.execute_vector_search(
        vector=embedding.vector,
        severity=["HIGH", "CRITICAL"],
        top_k=3
    )

    print(f"\nRetrieved {len(protocols)} protocols for: {packet['visual_narrative']}")
    for i, p in enumerate(protocols, 1):
        print(f"{i}. {p.source} (sim={p.similarity_score:.3f})")
        print(f"   Tags: {p.tags}")

    assert len(protocols) > 0, "No protocols retrieved"
    assert protocols[0].similarity_score > 0.50, "Top protocol has low similarity"

    # Check if "flashover" or "temperature" appears in top result tags
    top_tags = set(protocols[0].tags)
    assert any(tag in top_tags for tag in ["flashover", "temperature"]), \
        f"Expected 'flashover' or 'temperature' in tags, got {top_tags}"

    print("✅ Protocol retrieval test passed")
```

**Validation:** Run `pytest tests/integration/test_e2e_pipeline.py -v -s` with Actian and Redis running.

---

## Task 5.5: E2E Cache Performance Tests

Create `tests/integration/test_e2e_cache_performance.py`:

```python
import pytest
import json
import time
import asyncio
from backend.orchestrator import RAGOrchestrator
from backend.actian_pool import ActianPool
from backend.agents.redis_cache import RAGCacheAgent


@pytest.fixture
async def orchestrator_with_cache():
    """Create orchestrator with Actian + Redis."""
    actian_pool = ActianPool()
    await actian_pool.connect(
        host='localhost',
        port=5432,
        user='vectordb',
        password='vectordb_pass',
        database='safety_rag'
    )

    redis_cache = RAGCacheAgent(redis_url="redis://localhost:6379")
    redis_cache.reset_metrics()

    orchestrator = RAGOrchestrator(
        actian_pool=actian_pool,
        redis_cache=redis_cache
    )
    await orchestrator.startup()

    yield orchestrator, redis_cache

    await actian_pool.close()
    await redis_cache.close()


@pytest.mark.asyncio
async def test_cache_hit_rate_under_realistic_load(orchestrator_with_cache):
    """
    E2E Test: Send 50 packets with realistic fire growth dynamics.
    Verify cache hit rate ≥ 90%.
    """
    orchestrator, redis_cache = orchestrator_with_cache

    session_id = "e2e_cache_test_001"
    base_time = time.time()

    # Simulate fire growing from 5% → 75% over 50 packets
    # Fire buckets: MINOR (3 packets), MODERATE (15 packets), MAJOR (20 packets), CRITICAL (12 packets)
    # Expected cache misses: 4 (one per bucket transition)
    # Expected cache hits: 46/50 = 92%

    for i in range(50):
        fire_dominance = 0.05 + (i * 0.014)  # Slow linear growth
        smoke_opacity = 0.15 + (i * 0.012)
        proximity_alert = i > 35
        hazard_level = (
            "LOW" if fire_dominance < 0.15 else
            "MODERATE" if fire_dominance < 0.35 else
            "HIGH" if fire_dominance < 0.60 else
            "CRITICAL"
        )

        packet = {
            "device_id": "jetson_cache_test",
            "session_id": session_id,
            "timestamp": base_time + i,
            "hazard_level": hazard_level,
            "scores": {
                "fire_dominance": fire_dominance,
                "smoke_opacity": smoke_opacity,
                "proximity_alert": proximity_alert
            },
            "tracked_objects": [],
            "visual_narrative": f"Fire growing steadily, frame {i}"
        }

        result = await orchestrator.process_packet(json.dumps(packet))
        assert result["success"] == True

        # Small delay to simulate realistic packet rate
        await asyncio.sleep(0.01)

    # Check cache stats
    stats = redis_cache.get_cache_stats()
    semantic_stats = stats["semantic_protocol_cache"]

    hit_rate = semantic_stats["hit_rate"]
    avg_latency = semantic_stats["avg_latency_ms"]

    print(f"\n  Cache Performance:")
    print(f"    Hits: {semantic_stats['hits']}")
    print(f"    Misses: {semantic_stats['misses']}")
    print(f"    Hit Rate: {hit_rate*100:.1f}%")
    print(f"    Avg Latency: {avg_latency:.2f}ms")

    # Assertions
    assert hit_rate >= 0.90, f"Expected hit rate ≥90%, got {hit_rate*100:.1f}%"
    assert avg_latency < 5.0, f"Expected avg latency <5ms, got {avg_latency:.2f}ms"

    print("✅ Cache hit rate test PASSED")


@pytest.mark.asyncio
async def test_cache_vs_actian_latency_comparison(orchestrator_with_cache):
    """
    E2E Test: Compare latency with cache enabled vs cache disabled.
    """
    orchestrator, redis_cache = orchestrator_with_cache

    packet = {
        "device_id": "jetson_latency_test",
        "session_id": "latency_test_001",
        "timestamp": time.time(),
        "hazard_level": "HIGH",
        "scores": {
            "fire_dominance": 0.45,
            "smoke_opacity": 0.60,
            "proximity_alert": True
        },
        "tracked_objects": [],
        "visual_narrative": "Fire spreading rapidly, exit blocked"
    }

    # Round 1: Cache MISS (first call)
    start = time.perf_counter()
    result1 = await orchestrator.process_packet(json.dumps(packet))
    latency_miss = (time.perf_counter() - start) * 1000

    await asyncio.sleep(0.1)  # Allow async RAG to complete

    # Round 2: Cache HIT (same semantic bucket)
    packet["timestamp"] = time.time()
    packet["scores"]["fire_dominance"] = 0.47  # Still MAJOR bucket
    start = time.perf_counter()
    result2 = await orchestrator.process_packet(json.dumps(packet))
    latency_hit = (time.perf_counter() - start) * 1000

    print(f"\n  Latency Comparison:")
    print(f"    Cache MISS: {latency_miss:.2f}ms")
    print(f"    Cache HIT: {latency_hit:.2f}ms")
    print(f"    Speedup: {latency_miss / latency_hit:.1f}x")

    # Cache hit should be significantly faster
    assert latency_hit < latency_miss, "Cache hit should be faster than cache miss"
    assert latency_hit < 20, f"Cache hit latency too high: {latency_hit:.2f}ms"

    print("✅ Latency comparison test PASSED")


@pytest.mark.asyncio
async def test_graceful_degradation_redis_failure(orchestrator_with_cache):
    """
    E2E Test: Verify system continues working if Redis fails.
    """
    orchestrator, redis_cache = orchestrator_with_cache

    # Simulate Redis failure by closing connection
    await redis_cache.close()

    packet = {
        "device_id": "jetson_degradation_test",
        "session_id": "degradation_test_001",
        "timestamp": time.time(),
        "hazard_level": "CRITICAL",
        "scores": {
            "fire_dominance": 0.75,
            "smoke_opacity": 0.85,
            "proximity_alert": True
        },
        "tracked_objects": [],
        "visual_narrative": "Critical fire, immediate evacuation required"
    }

    # Should still work (fallback to Actian-only)
    result = await orchestrator.process_packet(json.dumps(packet))
    assert result["success"] == True, "System should degrade gracefully when Redis fails"

    print("✅ Graceful degradation test PASSED")
```

**Run tests:**
```bash
# Ensure both Actian and Redis are running
docker-compose up -d actian redis

# Run cache performance tests
pytest tests/integration/test_e2e_cache_performance.py -v -s
```

**Expected output:**
```
test_cache_hit_rate_under_realistic_load PASSED
  Cache Performance:
    Hits: 46
    Misses: 4
    Hit Rate: 92.0%
    Avg Latency: 2.1ms
  ✅ Cache hit rate test PASSED

test_cache_vs_actian_latency_comparison PASSED
  Latency Comparison:
    Cache MISS: 485.2ms
    Cache HIT: 18.3ms
    Speedup: 26.5x
  ✅ Latency comparison test PASSED

test_graceful_degradation_redis_failure PASSED
  ✅ Graceful degradation test PASSED
```

---

## Task 6: Deployment Scripts

Create `scripts/deploy.sh`:

```bash
#!/bin/bash
set -e

echo "======================================"
echo "Deploying Hacklytics RAG Backend"
echo "======================================"

# 1. Build Docker images
echo "Building Docker images..."
docker-compose build

# 2. Start services
echo "Starting services..."
docker-compose up -d

# 3. Wait for Actian to be healthy
echo "Waiting for Actian to be ready..."
until docker exec hacklytics_actian pg_isready -U vectordb > /dev/null 2>&1; do
    echo "  Waiting for Actian..."
    sleep 2
done
echo "✅ Actian ready"

# 3.5. Wait for Redis to be healthy
echo "Waiting for Redis to be ready..."
until docker exec hacklytics_redis redis-cli ping > /dev/null 2>&1; do
    echo "  Waiting for Redis..."
    sleep 1
done
echo "✅ Redis ready"

# 4. Seed protocols (if not already seeded)
echo "Checking if protocols are seeded..."
PROTOCOL_COUNT=$(docker exec hacklytics_actian psql -U vectordb -d safety_rag -t -c "SELECT COUNT(*) FROM safety_protocols;" | tr -d ' ')

if [ "$PROTOCOL_COUNT" -lt 10 ]; then
    echo "Seeding protocols..."
    python scripts/seed_protocols.py
    echo "✅ Protocols seeded"
else
    echo "✅ Protocols already seeded ($PROTOCOL_COUNT protocols)"
fi

# 5. Check ingest service health
echo "Checking ingest service health..."
sleep 5  # Wait for service to start
HEALTH=$(curl -s http://localhost:8000/health | grep -o '"status":"healthy"' || echo "")

if [ -z "$HEALTH" ]; then
    echo "❌ Ingest service not healthy"
    docker-compose logs ingest
    exit 1
fi
echo "✅ Ingest service healthy"

echo ""
echo "======================================"
echo "✅ Deployment Complete!"
echo "======================================"
echo ""
echo "Services:"
echo "  - Actian:  http://localhost:5432"
echo "  - Redis:   http://localhost:6379"
echo "  - Ingest:  http://localhost:8000"
echo "  - WebSocket: ws://localhost:8000/ws/{session_id}"
echo ""
echo "Health check: curl http://localhost:8000/health"
echo "Cache stats: curl http://localhost:8000/cache/stats"
echo "Logs: docker-compose logs -f"
echo ""
```

Make executable:
```bash
chmod +x scripts/deploy.sh
```

---

## Task 7: Quick Start Guide

Create `docs/QUICKSTART.md`:

```markdown
# Hacklytics RAG Backend - Quick Start

## Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development/testing)
- 8GB RAM minimum

## Deployment

### 1. Deploy Full Stack

```bash
./scripts/deploy.sh
```

This will:
- Build Docker images
- Start Actian, Redis, and Ingest services
- Seed safety protocols
- Verify health (all services)

### 2. Verify Deployment

```bash
# Check service health
curl http://localhost:8000/health

# Should return:
{
  "status": "healthy",
  "rag_healthy": true,
  "redis_healthy": true,
  "metrics": { ... }
}

# Check cache performance
curl http://localhost:8000/cache/stats

# Should return:
{
  "semantic_protocol_cache": {
    "hits": 0,
    "misses": 0,
    "hit_rate": 0.0,
    "avg_latency_ms": 0.0
  },
  "session_history_cache": {
    "hits": 0,
    "misses": 0,
    "hit_rate": 0.0,
    "avg_latency_ms": 0.0
  }
}
```

### 3. Test with Sample Packet

```bash
curl -X POST http://localhost:8000/test/inject \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "jetson_test_01",
    "session_id": "mission_quickstart",
    "timestamp": 1708549201.45,
    "hazard_level": "CRITICAL",
    "scores": {
      "fire_dominance": 0.85,
      "smoke_opacity": 0.7,
      "proximity_alert": true
    },
    "tracked_objects": [],
    "visual_narrative": "Person trapped, fire growing rapidly, exit blocked"
  }'
```

### 4. Connect WebSocket Client

```python
import websockets
import asyncio
import json

async def listen():
    uri = "ws://localhost:8000/ws/mission_quickstart"
    async with websockets.connect(uri) as ws:
        print("Connected to dashboard WebSocket")
        while True:
            message = await ws.recv()
            data = json.loads(message)
            print(f"Received: {data['message_type']}")
            if data['message_type'] == 'reflex_update':
                print(f"  Hazard: {data['hazard_level']}")
                print(f"  Trend: {data['trend']['tag']}")
            elif data['message_type'] == 'rag_recommendation':
                print(f"  Recommendation: {data['recommendation']}")

asyncio.run(listen())
```

## Architecture

```
Jetson (ZMQ PUB) → Ingest Service → [Reflex Path | Cognition Path]
                                          ↓              ↓
                                     WebSocket   Redis Cache (94-95% hit rate)
                                          ↓              ↓ (cache miss)
                                      Dashboard    Actian Vector DB
                                                        ↓
                                                   Protocols + History
```

## Monitoring

```bash
# View logs
docker-compose logs -f ingest

# Check metrics
curl http://localhost:8000/health | jq '.metrics'

# Check cache performance
curl http://localhost:8000/cache/stats | jq

# Inspect buffer
curl http://localhost:8000/buffer/jetson_test_01
```

## Troubleshooting

### Actian not starting
```bash
docker-compose logs actian
docker-compose restart actian
```

### Redis not starting
```bash
docker-compose logs redis
docker-compose restart redis
# Check Redis health
docker exec hacklytics_redis redis-cli ping
```

### Ingest service crashes
```bash
docker-compose logs ingest
# Check for Actian or Redis connection errors
```

### RAG latency high
```bash
# Check cache hit rate first
curl http://localhost:8000/cache/stats

# Low hit rate? Check semantic quantization buckets
# Expected: 94-95% hit rate under realistic fire growth

# If cache is working, check Actian query performance
docker exec -it hacklytics_actian psql -U vectordb -d safety_rag
SELECT * FROM pg_stat_user_indexes WHERE tablename = 'safety_protocols';
```

### Cache performance degraded
```bash
# Check Redis memory usage
docker exec hacklytics_redis redis-cli INFO memory

# Check cache eviction rate
docker exec hacklytics_redis redis-cli INFO stats | grep evicted

# Monitor cache hit rate in real-time
watch -n 1 'curl -s http://localhost:8000/cache/stats | jq ".semantic_protocol_cache.hit_rate"'
```

## Next Steps

1. Connect real Jetson device: Update `ZMQ_SUBSCRIBE` in `.env`
2. Expand protocol library: Add more entries to `scripts/seed_protocols.py`
3. Deploy dashboard: Connect to WebSocket endpoint
4. Production hardening: Add TLS, authentication, monitoring
```

---

## Verification Steps

1. **Deploy full stack:**
   ```bash
   ./scripts/deploy.sh
   ```

2. **Verify all services running:**
   ```bash
   docker-compose ps
   # All services should be "Up" and "healthy"
   ```

3. **Run E2E tests:**
   ```bash
   pytest tests/integration/test_e2e_pipeline.py -v -s
   ```

4. **Run cache performance tests:**
   ```bash
   pytest tests/integration/test_e2e_cache_performance.py -v -s
   # Verify cache hit rate ≥90%
   ```

5. **Inject test packet:**
   ```bash
   curl -X POST http://localhost:8000/test/inject -H "Content-Type: application/json" -d @tests/fixtures/critical_packet.json
   ```

6. **Check latency metrics:**
   ```bash
   curl http://localhost:8000/health | jq '.metrics'
   # Verify:
   # - reflex p95 < 50ms
   # - rag p95 < 200ms (with cache) / < 2000ms (without cache)
   ```

7. **Check cache performance:**
   ```bash
   curl http://localhost:8000/cache/stats | jq
   # Verify:
   # - semantic hit_rate > 0.90 (after warm-up)
   # - avg_latency_ms < 5ms
   ```

8. **Verify incident logging:**
   ```bash
   docker exec -it hacklytics_actian psql -U vectordb -d safety_rag -c "SELECT COUNT(*) FROM incident_log;"
   # Should increase with each packet
   ```

---

## Production Readiness Checklist

- ✅ All services start successfully (Actian, Redis, Ingest)
- ✅ Reflex path latency p95 < 50ms
- ✅ RAG path latency p95 < 200ms (with cache) / p99 < 2s (without cache)
- ✅ **Redis cache hit rate ≥ 90% (after warm-up period)**
- ✅ **Redis cache latency < 5ms average**
- ✅ Protocol retrieval returns relevant results
- ✅ Incident logging writes successfully (both Actian and Redis)
- ✅ Graceful degradation when Actian fails (cache continues working)
- ✅ **Graceful degradation when Redis fails (fallback to Actian-only)**
- ✅ WebSocket connections stable
- ✅ E2E tests pass (including cache performance tests)
- ✅ No memory leaks under sustained load
- ✅ Logs structured and readable
- ✅ **Cache metrics exposed via /cache/stats endpoint**

---

## Final Deliverables

Once all verification steps pass:

1. **Codebase:**
   - `/backend/agents/` - 8 sub-agents
   - `/backend/orchestrator.py` - Master coordinator
   - `/backend/ingest_service.py` - FastAPI service
   - `/backend/actian_pool.py` - Connection pool

2. **Infrastructure:**
   - `docker-compose.yml` - Full stack
   - `Dockerfile.ingest` - Ingest container
   - `docker/init.sql` - Actian schema

3. **Data:**
   - `scripts/seed_protocols.py` - 30-50 safety protocols
   - Seeded `safety_protocols` table

4. **Tests:**
   - 7 test profiles (Prompt 3)
   - E2E integration tests
   - Performance benchmarks

5. **Documentation:**
   - `docs/QUICKSTART.md`
   - `RAG.MD` (original spec)
   - Architecture documentation (this prompt series)

---

## Next Phase (Post-Hackathon)

After validating the system:

1. **Phase 2: LLM Synthesis** - Replace templates with Ollama phi3:mini
2. **Phase 3: Multi-Device** - Scale to multiple Jetson units with NATS
3. **Phase 4: Dashboard** - Build React dashboard with live WebSocket updates
4. **Phase 5: Fine-tuning** - Domain-specific embeddings for fire safety

---

🎉 **Congratulations!** You now have a production-grade dual-path RAG system for safety-critical fire detection.
