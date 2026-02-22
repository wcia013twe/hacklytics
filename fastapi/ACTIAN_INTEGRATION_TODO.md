# Actian VectorAI DB Integration - TODO

## Current Status

### ✅ Working:
- Actian VectorAI DB container running (williamimoh/actian-vectorai-db:1.0b)
- Actian Python SDK installed (`cortex` module, version 0.1.0b1)
- Embedding model loaded (all-MiniLM-L6-v2, 384 dimensions)
- Safety protocols defined and embeddable (10 protocols ready)

### ❌ Missing Components:

## 1. Database Schema Mismatch

**Problem:** The agents are written for PostgreSQL but VectorAI DB uses gRPC

**Current Code (PostgreSQL/asyncpg style):**
```python
# protocol_retrieval.py, history_retrieval.py, incident_logger.py
sql = """
    SELECT protocol_text, severity
    FROM safety_protocols
    WHERE severity = ANY(%s)
    ORDER BY scenario_vector <=> %s::vector
"""
async with self.conn_pool.acquire() as conn:
    rows = await conn.fetch(sql, *params)
```

**Needs to be converted to:**
```python
# Using Cortex gRPC client
from cortex import AsyncCortexClient

client = AsyncCortexClient(host="vectoraidb", port=50051)
results = await client.search(
    collection_name="safety_protocols",
    query_vector=vector,
    limit=top_k,
    filters={"severity": {"$in": ["HIGH", "CRITICAL"]}}
)
```

## 2. Collection Initialization

**Missing:** Script to create VectorAI DB collections

**Needed:**
```python
# scripts/init_actian_collections.py
from cortex import AsyncCortexClient, CollectionConfig, DistanceMetric

async def init_collections():
    client = AsyncCortexClient(host="vectoraidb", port=50051)

    # Create safety_protocols collection
    await client.create_collection(
        name="safety_protocols",
        vector_size=384,  # all-MiniLM-L6-v2 embedding size
        distance=DistanceMetric.COSINE,
        metadata_schema={
            "protocol_text": "string",
            "severity": "string",
            "category": "string",
            "source": "string",
            "tags": "string[]"
        }
    )

    # Create incident_log collection
    await client.create_collection(
        name="incident_log",
        vector_size=384,
        distance=DistanceMetric.COSINE,
        metadata_schema={
            "raw_narrative": "string",
            "session_id": "string",
            "device_id": "string",
            "timestamp": "float",
            "trend_tag": "string",
            "hazard_level": "string",
            "fire_dominance": "float",
            "smoke_opacity": "float",
            "proximity_alert": "float"
        }
    )
```

**Status:** 🔴 Not implemented

---

## 3. Connection Pool Adapter

**Missing:** Actian connection pool to replace asyncpg pool

**Current:**
```python
# orchestrator.py line 87
self.protocol_agent = ProtocolRetrievalAgent(actian_pool) if actian_pool else None
# actian_pool is always None
```

**Needs:**
```python
# backend/db/actian_pool.py
from cortex import AsyncCortexClient
from cortex.transport import ConnectionPool, PoolConfig

class ActianConnectionPool:
    """Wrapper for Actian VectorAI DB connection pool"""

    def __init__(self, host: str, port: int, max_connections: int = 10):
        self.pool_config = PoolConfig(
            max_connections=max_connections,
            connection_timeout=5.0,
            request_timeout=10.0
        )
        self.pool = ConnectionPool(
            host=host,
            port=port,
            config=self.pool_config
        )

    async def get_client(self) -> AsyncCortexClient:
        """Get a client from the pool"""
        return await self.pool.acquire()

    async def close(self):
        """Close all connections"""
        await self.pool.close()
```

**Status:** 🔴 Not implemented

---

## 4. Update Three Agents to Use Cortex SDK

### 4.1 ProtocolRetrievalAgent

**File:** `backend/agents/protocol_retrieval.py`

**Changes needed:**
- Replace SQL query with `client.search()`
- Update `execute_vector_search()` to use Cortex client
- Map Cortex SearchResult to Protocol model

**Example:**
```python
async def execute_vector_search(
    self,
    vector: List[float],
    severity: List[str] = ["HIGH", "CRITICAL"],
    top_k: int = 3,
    timeout: int = 200
) -> List[Protocol]:
    start = time.perf_counter()

    client = await self.conn_pool.get_client()

    results = await client.search(
        collection_name="safety_protocols",
        query_vector=vector,
        limit=top_k,
        filters={"severity": {"$in": severity}}
    )

    protocols = []
    for result in results:
        protocols.append(Protocol(
            protocol_text=result.payload["protocol_text"],
            severity=result.payload["severity"],
            category=result.payload["category"],
            source=result.payload["source"],
            similarity_score=result.score,
            tags=result.payload.get("tags", [])
        ))

    return protocols
```

**Status:** 🔴 Not implemented

---

### 4.2 HistoryRetrievalAgent

**File:** `backend/agents/history_retrieval.py`

**Changes needed:**
- Replace SQL query with `client.search()`
- Add session_id filter
- Add similarity threshold filter

**Example:**
```python
async def execute_history_search(
    self,
    vector: List[float],
    session_id: str,
    similarity_threshold: float = 0.70,
    top_k: int = 5,
    timeout: int = 200
) -> List[HistoryEntry]:
    start = time.perf_counter()
    current_time = time.time()

    client = await self.conn_pool.get_client()

    results = await client.search(
        collection_name="incident_log",
        query_vector=vector,
        limit=top_k,
        filters={"session_id": {"$eq": session_id}},
        score_threshold=similarity_threshold
    )

    history = []
    for result in results:
        time_ago = current_time - result.payload["timestamp"]
        history.append(HistoryEntry(
            raw_narrative=result.payload["raw_narrative"],
            timestamp=result.payload["timestamp"],
            trend_tag=result.payload["trend_tag"],
            hazard_level=result.payload["hazard_level"],
            similarity_score=result.score,
            time_ago_seconds=time_ago
        ))

    return history
```

**Status:** 🔴 Not implemented

---

### 4.3 IncidentLoggerAgent

**File:** `backend/agents/incident_logger.py`

**Changes needed:**
- Replace SQL INSERT with `client.upsert()`
- Use PointStruct for data format
- Keep batching logic

**Example:**
```python
async def _flush_batch(self) -> Dict:
    if not self.write_buffer:
        return {"inserted_count": 0, "failed_count": 0, "flush_time_ms": 0}

    start = time.perf_counter()
    batch = list(self.write_buffer)
    self.write_buffer.clear()

    client = await self.conn_pool.get_client()

    # Convert batch to PointStruct format
    points = []
    for i, row in enumerate(batch):
        points.append({
            "id": f"{row['session_id']}_{row['timestamp']}",
            "vector": row["narrative_vector"],
            "payload": {
                "raw_narrative": row["raw_narrative"],
                "session_id": row["session_id"],
                "device_id": row["device_id"],
                "timestamp": row["timestamp"],
                "trend_tag": row["trend_tag"],
                "hazard_level": row["hazard_level"],
                "fire_dominance": row["fire_dominance"],
                "smoke_opacity": row["smoke_opacity"],
                "proximity_alert": row["proximity_alert"]
            }
        })

    try:
        await client.upsert(
            collection_name="incident_log",
            points=points
        )
        inserted = len(points)
        failed = 0
    except Exception as e:
        logger.error(f"Batch flush failed: {e}")
        inserted = 0
        failed = len(points)

    flush_time = (time.perf_counter() - start) * 1000
    return {"inserted_count": inserted, "failed_count": failed, "flush_time_ms": flush_time}
```

**Status:** 🔴 Not implemented

---

## 5. Update Seeding Script

**File:** `scripts/seed_protocols.py`

**Changes needed:**
- Replace asyncpg connection with Cortex client
- Use `client.upsert()` to insert protocol vectors
- Test vector search after seeding

**Example:**
```python
async def seed_protocols():
    print("Loading model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    print("Connecting to Actian VectorAI DB...")
    client = AsyncCortexClient(host=ACTIAN_HOST, port=ACTIAN_PORT)

    # Check if collection exists
    collections = await client.list_collections()
    if "safety_protocols" not in [c.name for c in collections]:
        print("Creating safety_protocols collection...")
        # (Use init_actian_collections.py instead)

    print(f"Embedding {len(PROTOCOLS)} protocols...")
    points = []
    for i, protocol in enumerate(PROTOCOLS):
        vector = model.encode(protocol["scenario"], normalize_embeddings=True).tolist()

        points.append({
            "id": f"protocol_{i+1}",
            "vector": vector,
            "payload": {
                "protocol_text": protocol["protocol_text"],
                "severity": protocol["severity"],
                "category": protocol["category"],
                "source": protocol["source"],
                "tags": protocol["tags"]
            }
        })

    print("Inserting into VectorAI DB...")
    await client.upsert(
        collection_name="safety_protocols",
        points=points
    )

    print(f"✓ Inserted {len(points)} protocols")

    # Test search
    test_vector = model.encode("Person trapped with fire blocking exit").tolist()
    results = await client.search(
        collection_name="safety_protocols",
        query_vector=test_vector,
        limit=3
    )

    print(f"\nTest search returned {len(results)} results")
    for result in results:
        print(f"  - {result.payload['severity']}: {result.score:.3f}")
```

**Status:** 🟡 Partially implemented (embeddings work, DB insert missing)

---

## 6. Update Orchestrator Initialization

**File:** `backend/main_rag.py`

**Changes needed:**
- Create ActianConnectionPool
- Pass pool to RAGOrchestrator

**Example:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator

    logger.info("Starting RAG service...")

    # Initialize Actian connection pool
    from backend.db.actian_pool import ActianConnectionPool
    actian_pool = ActianConnectionPool(
        host=os.getenv("ACTIAN_HOST", "vectoraidb"),
        port=int(os.getenv("ACTIAN_PORT", "50051")),
        max_connections=10
    )

    # Initialize orchestrator with Actian pool
    orchestrator = RAGOrchestrator(
        actian_pool=actian_pool,
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379")
    )
    await orchestrator.startup()

    logger.info("RAG service ready")

    yield

    # Shutdown
    await actian_pool.close()
    logger.info("RAG service shut down")
```

**Status:** 🔴 Not implemented

---

## Implementation Checklist

### Phase 1: Database Setup
- [ ] Create `scripts/init_actian_collections.py`
- [ ] Run script to create `safety_protocols` collection
- [ ] Run script to create `incident_log` collection
- [ ] Verify collections exist with Cortex client

### Phase 2: Connection Pool
- [ ] Create `backend/db/actian_pool.py`
- [ ] Implement ActianConnectionPool class
- [ ] Add connection pooling tests

### Phase 3: Update Agents
- [ ] Update `ProtocolRetrievalAgent` to use Cortex SDK
- [ ] Update `HistoryRetrievalAgent` to use Cortex SDK
- [ ] Update `IncidentLoggerAgent` to use Cortex SDK
- [ ] Test each agent individually

### Phase 4: Seeding
- [ ] Update `scripts/seed_protocols.py` to use Cortex client
- [ ] Run seeding script
- [ ] Verify protocols inserted correctly
- [ ] Test vector search retrieval

### Phase 5: Integration
- [ ] Update `main_rag.py` to initialize Actian pool
- [ ] Update `orchestrator.py` to use Actian pool
- [ ] End-to-end testing
- [ ] Performance validation (latency targets)

### Phase 6: Testing
- [ ] Create `tests/test_actian_integration.py`
- [ ] Test protocol retrieval
- [ ] Test history retrieval
- [ ] Test incident logging
- [ ] Test vector search accuracy

---

## Estimated Effort

- **Phase 1 (DB Setup):** 1-2 hours
- **Phase 2 (Connection Pool):** 1-2 hours
- **Phase 3 (Update Agents):** 3-4 hours
- **Phase 4 (Seeding):** 1 hour
- **Phase 5 (Integration):** 2-3 hours
- **Phase 6 (Testing):** 2-3 hours

**Total: 10-15 hours of development work**

---

## Key API Documentation

### Cortex Client API (from installed SDK)

```python
from cortex import AsyncCortexClient, CollectionConfig, DistanceMetric

# Initialize client
client = AsyncCortexClient(host="vectoraidb", port=50051)

# Create collection
await client.create_collection(
    name="my_collection",
    vector_size=384,
    distance=DistanceMetric.COSINE
)

# Insert vectors
await client.upsert(
    collection_name="my_collection",
    points=[
        {
            "id": "point_1",
            "vector": [0.1, 0.2, ...],  # 384-dim vector
            "payload": {"key": "value"}
        }
    ]
)

# Search
results = await client.search(
    collection_name="my_collection",
    query_vector=[0.1, 0.2, ...],
    limit=10,
    filters={"key": {"$eq": "value"}},
    score_threshold=0.7
)

# Each result has:
# - result.id: point ID
# - result.score: similarity score
# - result.payload: metadata dictionary
# - result.vector: the vector (if requested)
```

---

## Next Steps

1. **Start with Phase 1** - Create collections
2. **Verify VectorAI DB is accessible** - Test basic upsert/search
3. **Implement one agent at a time** - Start with ProtocolRetrievalAgent
4. **Test incrementally** - Don't wait until everything is done

---

## Questions?

- Check Cortex SDK docs: `python -c "from cortex import AsyncCortexClient; help(AsyncCortexClient)"`
- Review VectorAI DB logs: `docker compose logs vectoraidb`
- Test connection: `nc -zv localhost 50051`
