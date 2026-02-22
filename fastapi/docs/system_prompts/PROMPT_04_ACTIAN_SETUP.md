# PROMPT 4: Actian Vector Database Setup

**Objective:** Deploy Actian Vector DB with schema, indexes, protocol seeding, and test queries.

**Status:** ✅ Independent - Can run in parallel with Prompts 1, 2, and 3

**Deliverables:**
- Docker Compose configuration for Actian
- SQL schema with vector indexes
- Protocol seeding script with 30-50 safety protocols
- Test queries to verify retrieval

---

## Context from RAG.MD

Actian Vector DB serves two critical functions:
1. **Static Knowledge Base** (`safety_protocols`): Pre-loaded NFPA/OSHA protocols (read-only during missions)
2. **Dynamic Temporal Memory** (`incident_log`): Real-time incident history for temporal reasoning

Refer to RAG.MD sections 3.2 (Actian Schema), 3.3 (Retrieval Queries), and 4 (Tech Stack).

---

## Task 1: Docker Compose Configuration

Create `docker/docker-compose.actian.yml`:

```yaml
version: '3.8'

services:
  actian:
    image: actian/vector:latest
    container_name: hacklytics_actian
    ports:
      - "5432:5432"  # PostgreSQL wire protocol
    environment:
      - POSTGRES_USER=vectordb
      - POSTGRES_PASSWORD=vectordb_pass
      - POSTGRES_DB=safety_rag
    volumes:
      - actian_data:/var/lib/actian
      - ./init.sql:/docker-entrypoint-initdb.d/01_schema.sql
      - ./seed_protocols.sql:/docker-entrypoint-initdb.d/02_seed.sql
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vectordb"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  actian_data:
    driver: local
```

**Note:** If `actian/vector:latest` is not available, use PostgreSQL with pgvector extension:

```yaml
  actian:
    image: ankane/pgvector:latest
    # ... rest same
```

---

## Task 2: Create SQL Schema

Create `docker/init.sql`:

```sql
-- Enable vector extension (if using pgvector)
CREATE EXTENSION IF NOT EXISTS vector;

-- ===========================================
-- Table 1: safety_protocols (Static KB)
-- ===========================================

CREATE TABLE IF NOT EXISTS safety_protocols (
    id              SERIAL PRIMARY KEY,
    scenario_vector vector(384) NOT NULL,          -- MiniLM-L6 embeddings
    protocol_text   TEXT NOT NULL,                 -- Actual safety instruction
    severity        VARCHAR(10) NOT NULL,          -- CLEAR | LOW | MODERATE | HIGH | CRITICAL
    category        VARCHAR(50) NOT NULL,          -- fire | structural | hazmat | medical
    tags            VARCHAR(200),                  -- Comma-separated: trapped, exit_blocked, etc.
    source          VARCHAR(100),                  -- Reference: NFPA_1001, OSHA_29CFR
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector similarity index (IVFFlat)
CREATE INDEX idx_protocol_vector ON safety_protocols
    USING ivfflat (scenario_vector vector_cosine_ops)
    WITH (lists = 50);

-- Severity filter index
CREATE INDEX idx_protocol_severity ON safety_protocols (severity);

-- Category index
CREATE INDEX idx_protocol_category ON safety_protocols (category);


-- ===========================================
-- Table 2: incident_log (Dynamic Memory)
-- ===========================================

CREATE TABLE IF NOT EXISTS incident_log (
    id                SERIAL PRIMARY KEY,
    timestamp         DOUBLE PRECISION NOT NULL,   -- Unix epoch from Jetson
    session_id        VARCHAR(50) NOT NULL,        -- mission_YYYY_MM_DD
    device_id         VARCHAR(50) NOT NULL,        -- jetson_alpha_01
    narrative_vector  vector(384) NOT NULL,        -- Enriched narrative embedding
    raw_narrative     TEXT NOT NULL,               -- Human-readable narrative
    trend_tag         VARCHAR(20),                 -- RAPID_GROWTH | GROWING | STABLE | DIMINISHING
    hazard_level      VARCHAR(10),                 -- CLEAR | LOW | MODERATE | HIGH | CRITICAL
    fire_dominance    DOUBLE PRECISION,            -- Denormalized from scores
    smoke_opacity     DOUBLE PRECISION,
    proximity_alert   BOOLEAN,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector similarity index
CREATE INDEX idx_incident_vector ON incident_log
    USING ivfflat (narrative_vector vector_cosine_ops)
    WITH (lists = 100);

-- Session + timestamp index (critical for history queries)
CREATE INDEX idx_incident_session ON incident_log (session_id, timestamp DESC);

-- Device + timestamp index
CREATE INDEX idx_incident_device ON incident_log (device_id, timestamp DESC);

-- Hazard level index (for filtering)
CREATE INDEX idx_incident_hazard ON incident_log (hazard_level);


-- ===========================================
-- Helper Functions
-- ===========================================

-- Function to compute cosine similarity (for debugging)
CREATE OR REPLACE FUNCTION cosine_similarity(a vector, b vector)
RETURNS DOUBLE PRECISION AS $$
    SELECT 1 - (a <-> b);  -- IMPORTANT: Use <-> for L2 distance
$$ LANGUAGE SQL IMMUTABLE STRICT;

```

**CRITICAL NOTE:** The operator is `<->` for L2 distance (NOT `<=>`). This is the Actian/pgvector standard.

**Validation:** Run `docker-compose -f docker/docker-compose.actian.yml up -d`, check container health.

---

## Task 2.5: Implement SQL Retrieval Queries (from RAG.MD 3.3.1)

These are the exact queries used by the Protocol and History agents. Include these for reference.

### Protocol Retrieval Query

```sql
-- Retrieve top 3 matching safety protocols
-- $1: narrative_vector (VECTOR(384), pre-normalized during embedding)
-- Returns: protocol text, source, and similarity score

SELECT
    protocol_text,
    source,
    severity,
    tags,
    (1 - (scenario_vector <-> $1)) AS similarity_score
FROM safety_protocols
WHERE severity IN ('HIGH', 'CRITICAL')
ORDER BY scenario_vector <-> $1 ASC  -- L2 distance ascending = most similar first
LIMIT 3;
```

**Key Points:**
- Uses `<->` operator for L2 distance (NOT `<=>`)
- Similarity computed as `1 - distance` (higher = more similar)
- Filters to HIGH and CRITICAL severity only
- Orders by distance ASC (closest first)

### Session History Retrieval Query

```sql
-- Retrieve up to 5 similar incidents from current session
-- $1: narrative_vector (VECTOR(384), pre-normalized)
-- $2: session_id (VARCHAR)
-- $3: current_timestamp (FLOAT) - to exclude future packets (clock skew)

WITH scored_incidents AS (
    SELECT
        raw_narrative,
        trend_tag,
        hazard_level,
        fire_dominance,
        timestamp,
        (1 - (narrative_vector <-> $1)) AS similarity_score
    FROM incident_log
    WHERE session_id = $2
      AND timestamp <= $3  -- Only past incidents
    ORDER BY narrative_vector <-> $1 ASC
    LIMIT 20  -- Pre-filter to top 20 by similarity for efficiency
)
SELECT *
FROM scored_incidents
WHERE similarity_score > 0.70  -- Semantic similarity threshold
ORDER BY timestamp DESC  -- Most recent first
LIMIT 5;
```

**Key Points:**
- Two-stage query: IVFFlat index returns top 20, then post-filters by threshold
- Filters by session_id to scope history to current mission
- timestamp <= $3 prevents future packets due to clock skew
- Orders by recency (timestamp DESC) after similarity filter

---

## Task 2.6: Incident Batch Writer Implementation (from RAG.MD 3.4.5)

The incident logger uses batched writes to reduce Actian load. Here's the implementation for reference:

Create `backend/db/batch_writer.py`:

```python
import asyncio
import time
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class IncidentBatchWriter:
    """
    Accumulates incident_log writes and flushes to Actian periodically.

    Design (from RAG.MD 3.4.5):
    - Time-based trigger: flushes every flush_interval_seconds
    - Background asyncio task runs flush loop
    - Thread-safe for concurrent add_incident() calls
    - Graceful shutdown: flushes remaining incidents on cleanup
    """

    def __init__(self, db_connection_pool, flush_interval_seconds: float = 2.0):
        self.db_pool = db_connection_pool
        self.flush_interval = flush_interval_seconds
        self.buffer: List[Dict] = []
        self.buffer_lock = asyncio.Lock()
        self.flush_task = None
        self.running = False

    async def start(self):
        """Start the background flush task."""
        self.running = True
        self.flush_task = asyncio.create_task(self._flush_loop())
        logger.info(f"IncidentBatchWriter started (flush every {self.flush_interval}s)")

    async def stop(self):
        """Stop the background task and flush remaining incidents."""
        self.running = False
        if self.flush_task:
            await self.flush_task
        await self._flush()  # Final flush
        logger.info("IncidentBatchWriter stopped")

    async def add_incident(self, incident: Dict):
        """
        Add an incident to the batch buffer.

        Args:
            incident: Dict with keys matching incident_log schema:
                - timestamp, session_id, device_id
                - narrative_vector, raw_narrative
                - trend_tag, hazard_level
                - fire_dominance, smoke_opacity, proximity_alert
        """
        async with self.buffer_lock:
            self.buffer.append(incident)

            # Safety: if buffer grows too large (>100 incidents), flush immediately
            if len(self.buffer) >= 100:
                logger.warning(f"Buffer overflow at {len(self.buffer)} incidents, flushing early")
                await self._flush()

    async def _flush_loop(self):
        """Background task that flushes buffer every flush_interval seconds."""
        while self.running:
            await asyncio.sleep(self.flush_interval)
            await self._flush()

    async def _flush(self):
        """Write all buffered incidents to Actian in a single transaction."""
        async with self.buffer_lock:
            if not self.buffer:
                return  # Nothing to flush

            incidents = self.buffer.copy()
            self.buffer.clear()

        # Execute batch insert in a transaction
        start = time.perf_counter()
        try:
            await self._batch_insert(incidents)
            flush_time = (time.perf_counter() - start) * 1000
            logger.info(f"✓ Flushed {len(incidents)} incidents to Actian in {flush_time:.2f}ms")
        except Exception as e:
            logger.error(f"✗ Batch write failed: {e}")
            # For safety-critical systems, log failure and continue (don't retry to avoid blocking)

    async def _batch_insert(self, incidents: List[Dict]):
        """
        Insert multiple incidents using parameterized batch query.

        Uses Actian's executemany() for efficient batch inserts.
        """
        query = """
        INSERT INTO incident_log (
            timestamp, session_id, device_id,
            narrative_vector, raw_narrative,
            trend_tag, hazard_level,
            fire_dominance, smoke_opacity, proximity_alert
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """

        async with self.db_pool.acquire() as conn:
            await conn.executemany(query, [
                (
                    inc['timestamp'],
                    inc['session_id'],
                    inc['device_id'],
                    inc['narrative_vector'],
                    inc['raw_narrative'],
                    inc['trend_tag'],
                    inc['hazard_level'],
                    inc['fire_dominance'],
                    inc['smoke_opacity'],
                    inc['proximity_alert']
                )
                for inc in incidents
            ])
```

**Benefits (from RAG.MD 3.4.5):**
- **10x write reduction**: At 1 packet/sec, reduces from 1800 writes/30min to ~180 batched writes
- **Lower Actian load**: Batch inserts are more efficient than individual INSERTs
- **Non-blocking**: add_incident() returns immediately; flushing happens in background

**Trade-offs:**
- **Delayed persistence**: Incidents are in-memory for up to 2 seconds before being written
- **Risk of loss**: If RAG container crashes, up to 2 seconds of incidents are lost
- **Mitigation**: Acceptable for non-critical incident logging. Reflex data is still transmitted immediately.

---

## Task 3: Protocol Seeding Script

Create `scripts/seed_protocols.py`:

```python
#!/usr/bin/env python3
"""
Seed Actian safety_protocols table with NFPA/OSHA protocols.

This script:
1. Loads 30-50 safety protocols from protocols.json
2. Embeds each scenario description using MiniLM-L6
3. Inserts into Actian safety_protocols table
"""

import json
import asyncpg
from sentence_transformers import SentenceTransformer
import asyncio


# Sample protocols (expand to 30-50)
SAFETY_PROTOCOLS = [
    {
        "scenario": "Person trapped in room with fire blocking exit",
        "protocol": "Initiate immediate rescue. Use secondary exit if available. Deploy fire suppression to create safe corridor. Request additional rescue units.",
        "severity": "CRITICAL",
        "category": "fire",
        "tags": "trapped,exit_blocked,rescue,fire",
        "source": "NFPA_1001_5.3.9"
    },
    {
        "scenario": "Fire spreading rapidly with high heat conditions",
        "protocol": "Evacuate immediately. Establish defensive perimeter. Do not attempt interior attack. Monitor for structural failure.",
        "severity": "CRITICAL",
        "category": "fire",
        "tags": "spreading,rapid_growth,evacuation,defensive",
        "source": "NFPA_1001_5.3.10"
    },
    {
        "scenario": "Smoke inhalation risk with low visibility",
        "protocol": "All personnel must use SCBA. Establish ventilation. Monitor air quality. Provide medical attention for smoke exposure.",
        "severity": "HIGH",
        "category": "fire",
        "tags": "smoke,visibility,scba,ventilation",
        "source": "NFPA_1001_5.3.1"
    },
    {
        "scenario": "Structural damage visible with collapse risk",
        "protocol": "Evacuate structure immediately. Establish collapse zone. Request structural engineer assessment. Do not re-enter.",
        "severity": "CRITICAL",
        "category": "structural",
        "tags": "structural,collapse,evacuation,unsafe",
        "source": "NFPA_1001_5.3.4"
    },
    {
        "scenario": "Person unconscious near fire requiring immediate rescue",
        "protocol": "Deploy rapid intervention team. Establish clear path for evacuation. Provide immediate medical care upon extraction.",
        "severity": "CRITICAL",
        "category": "medical",
        "tags": "unconscious,rescue,medical,immediate",
        "source": "NFPA_1001_5.3.9"
    },
    {
        "scenario": "Fire diminishing with clear exit paths available",
        "protocol": "Continue monitoring. Maintain suppression efforts. Ensure complete extinguishment. Check for hidden fire.",
        "severity": "MODERATE",
        "category": "fire",
        "tags": "diminishing,clear_exit,monitoring,suppression",
        "source": "NFPA_1001_5.3.7"
    },
    {
        "scenario": "Flashover conditions imminent with rising temperature",
        "protocol": "EVACUATE IMMEDIATELY. Flashover imminent. All personnel exit structure. Transition to defensive operations only.",
        "severity": "CRITICAL",
        "category": "fire",
        "tags": "flashover,temperature,evacuation,imminent",
        "source": "NFPA_1001_5.3.11"
    },
    {
        "scenario": "Backdraft risk detected during door breach",
        "protocol": "DO NOT BREACH. Ventilate from exterior. Cool door surface. Monitor for pressure equalization before entry.",
        "severity": "CRITICAL",
        "category": "fire",
        "tags": "backdraft,breach,ventilation,danger",
        "source": "NFPA_1001_5.3.12"
    },
    {
        "scenario": "Multiple casualties requiring triage and medical attention",
        "protocol": "Establish triage area. Prioritize life-threatening injuries. Request additional medical units. Maintain scene safety.",
        "severity": "HIGH",
        "category": "medical",
        "tags": "casualties,triage,medical,priorities",
        "source": "OSHA_29CFR_1910"
    },
    {
        "scenario": "Hazardous material leak detected requiring evacuation",
        "protocol": "Identify material using SDS. Establish hot zone. Evacuate downwind areas. Request HAZMAT team. Use appropriate PPE.",
        "severity": "CRITICAL",
        "category": "hazmat",
        "tags": "hazmat,leak,evacuation,ppe",
        "source": "OSHA_29CFR_1910.120"
    },
    # TODO: Add 20-40 more protocols covering:
    # - Fire growth stages (incipient, growth, fully developed, decay)
    # - Rescue scenarios (window, roof, basement)
    # - Ventilation strategies
    # - Water supply issues
    # - Exposure protection
    # - Overhaul operations
]


async def seed_protocols():
    """
    Main seeding function.
    """
    print("Loading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    print(f"Connecting to Actian at localhost:5432...")
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='vectordb',
        password='vectordb_pass',
        database='safety_rag'
    )

    print(f"Seeding {len(SAFETY_PROTOCOLS)} protocols...")

    for i, protocol in enumerate(SAFETY_PROTOCOLS):
        # Embed scenario description
        # CRITICAL: Use normalize_embeddings=True for L2 distance compatibility
        # (from RAG.MD 3.3.1: vectors MUST be normalized to unit length)
        scenario_text = protocol["scenario"]
        vector = model.encode(scenario_text, normalize_embeddings=True).tolist()

        # Insert into database
        await conn.execute(
            """
            INSERT INTO safety_protocols (
                scenario_vector, protocol_text, severity, category, tags, source
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            vector,
            protocol["protocol"],
            protocol["severity"],
            protocol["category"],
            protocol["tags"],
            protocol["source"]
        )

        print(f"  [{i+1}/{len(SAFETY_PROTOCOLS)}] {protocol['scenario'][:50]}...")

    print("✅ Seeding complete")

    # Verify
    count = await conn.fetchval("SELECT COUNT(*) FROM safety_protocols")
    print(f"Total protocols in database: {count}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_protocols())
```

**Validation:** Run `python scripts/seed_protocols.py`, verify protocols inserted.

---

## Task 4: Test Queries

Create `scripts/test_actian_queries.py`:

```python
#!/usr/bin/env python3
"""
Test Actian vector similarity queries.

Tests:
1. Protocol retrieval by vector similarity
2. Session history retrieval
3. Index performance
"""

import asyncpg
from sentence_transformers import SentenceTransformer
import time


async def test_protocol_retrieval():
    """
    Test Query 1: Protocol Retrieval

    Embed a test narrative and find top-3 matching protocols.
    """
    print("\n=== Test 1: Protocol Retrieval ===")

    model = SentenceTransformer('all-MiniLM-L6-v2')
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='vectordb',
        password='vectordb_pass',
        database='safety_rag'
    )

    # Test narrative
    test_narrative = "Person trapped in corner, fire growing rapidly, exit blocked"
    print(f"Query: {test_narrative}")

    # Embed
    vector = model.encode(test_narrative).tolist()

    # Query Actian
    start = time.perf_counter()
    results = await conn.fetch(
        """
        SELECT
            protocol_text,
            severity,
            category,
            source,
            tags,
            1 - (scenario_vector <=> $1::vector) AS similarity_score
        FROM safety_protocols
        WHERE severity = ANY($2)
        ORDER BY scenario_vector <=> $1::vector
        LIMIT 3
        """,
        vector,
        ['HIGH', 'CRITICAL']
    )
    query_time = (time.perf_counter() - start) * 1000

    print(f"\nTop 3 Protocols (retrieved in {query_time:.2f}ms):")
    for i, row in enumerate(results, 1):
        print(f"\n{i}. Similarity: {row['similarity_score']:.4f}")
        print(f"   Source: {row['source']}")
        print(f"   Severity: {row['severity']} | Category: {row['category']}")
        print(f"   Tags: {row['tags']}")
        print(f"   Protocol: {row['protocol_text'][:100]}...")

    await conn.close()

    # Validation
    assert len(results) > 0, "No protocols retrieved"
    assert results[0]['similarity_score'] > 0.60, "Top result has low similarity"
    assert query_time < 300, f"Query too slow: {query_time:.2f}ms"

    print("\n✅ Protocol retrieval test PASSED")


async def test_session_history_retrieval():
    """
    Test Query 2: Session History Retrieval

    Insert test incidents and query for similar ones in same session.
    """
    print("\n=== Test 2: Session History Retrieval ===")

    model = SentenceTransformer('all-MiniLM-L6-v2')
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='vectordb',
        password='vectordb_pass',
        database='safety_rag'
    )

    session_id = "test_session_001"

    # Insert test incidents
    test_incidents = [
        "Smoke detected in hallway",
        "Fire growing in corner room",
        "Person spotted near fire",
        "Person trapped, exit blocked"
    ]

    print(f"Inserting {len(test_incidents)} test incidents...")
    for i, narrative in enumerate(test_incidents):
        vector = model.encode(narrative).tolist()
        await conn.execute(
            """
            INSERT INTO incident_log (
                timestamp, session_id, device_id, narrative_vector,
                raw_narrative, trend_tag, hazard_level,
                fire_dominance, smoke_opacity, proximity_alert
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            time.time() + i,
            session_id,
            "jetson_test",
            vector,
            narrative,
            "GROWING",
            "HIGH",
            0.5,
            0.5,
            False
        )

    # Query for similar incidents
    query_narrative = "Person in danger near fire"
    query_vector = model.encode(query_narrative).tolist()

    print(f"\nQuerying similar incidents in session '{session_id}'...")
    print(f"Query: {query_narrative}")

    start = time.perf_counter()
    results = await conn.fetch(
        """
        SELECT
            raw_narrative,
            timestamp,
            trend_tag,
            hazard_level,
            1 - (narrative_vector <=> $1::vector) AS similarity_score
        FROM incident_log
        WHERE session_id = $2
          AND 1 - (narrative_vector <=> $1::vector) > $3
        ORDER BY
            narrative_vector <=> $1::vector,
            timestamp DESC
        LIMIT 5
        """,
        query_vector,
        session_id,
        0.60  # similarity threshold
    )
    query_time = (time.perf_counter() - start) * 1000

    print(f"\nSimilar Incidents (retrieved in {query_time:.2f}ms):")
    for i, row in enumerate(results, 1):
        time_ago = time.time() - row['timestamp']
        print(f"\n{i}. Similarity: {row['similarity_score']:.4f} | {time_ago:.1f}s ago")
        print(f"   {row['raw_narrative']}")
        print(f"   Trend: {row['trend_tag']} | Hazard: {row['hazard_level']}")

    # Cleanup
    await conn.execute("DELETE FROM incident_log WHERE session_id = $1", session_id)
    await conn.close()

    # Validation
    assert len(results) > 0, "No history retrieved"
    assert query_time < 300, f"Query too slow: {query_time:.2f}ms"

    print("\n✅ Session history retrieval test PASSED")


async def test_index_performance():
    """
    Test index performance with varying dataset sizes.
    """
    print("\n=== Test 3: Index Performance ===")

    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='vectordb',
        password='vectordb_pass',
        database='safety_rag'
    )

    # Check index usage
    result = await conn.fetch(
        """
        SELECT
            schemaname,
            tablename,
            indexname,
            idx_scan,
            idx_tup_read
        FROM pg_stat_user_indexes
        WHERE tablename IN ('safety_protocols', 'incident_log')
        """
    )

    print("\nIndex Statistics:")
    for row in result:
        print(f"  {row['tablename']}.{row['indexname']}")
        print(f"    Scans: {row['idx_scan']} | Tuples read: {row['idx_tup_read']}")

    await conn.close()

    print("\n✅ Index performance check complete")


async def main():
    """Run all tests"""
    await test_protocol_retrieval()
    await test_session_history_retrieval()
    await test_index_performance()
    print("\n🎉 All Actian tests PASSED")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

**Validation:** Run `python scripts/test_actian_queries.py`, all tests pass.

---

## Task 5: Create Actian Connection Pool Helper

Create `backend/actian_pool.py`:

```python
"""
Actian connection pool for async agents.
"""

import asyncpg
import os
from typing import Optional


class ActianPool:
    """Async connection pool for Actian Vector DB"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(
        self,
        host: str = None,
        port: int = 5432,
        user: str = None,
        password: str = None,
        database: str = None,
        min_size: int = 2,
        max_size: int = 10
    ):
        """
        Create connection pool.

        Args from env vars if not provided:
        - ACTIAN_HOST
        - ACTIAN_USER
        - ACTIAN_PASSWORD
        - ACTIAN_DATABASE
        """
        host = host or os.getenv('ACTIAN_HOST', 'localhost')
        user = user or os.getenv('ACTIAN_USER', 'vectordb')
        password = password or os.getenv('ACTIAN_PASSWORD', 'vectordb_pass')
        database = database or os.getenv('ACTIAN_DATABASE', 'safety_rag')

        self.pool = await asyncpg.create_pool(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            min_size=min_size,
            max_size=max_size
        )

        print(f"✅ Actian connection pool created: {host}:{port}/{database}")

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            print("Actian connection pool closed")

    def acquire(self):
        """
        Acquire connection from pool.

        Usage:
            async with pool.acquire() as conn:
                await conn.execute(...)
        """
        if not self.pool:
            raise RuntimeError("Pool not connected. Call connect() first.")
        return self.pool.acquire()

    async def fetch(self, query: str, *args):
        """Execute query and fetch results"""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)

    async def execute(self, query: str, *args):
        """Execute query without fetching results"""
        async with self.acquire() as conn:
            return await conn.execute(query, *args)
```

**Usage in agents:**

```python
# In orchestrator startup
from actian_pool import ActianPool

actian_pool = ActianPool()
await actian_pool.connect()

orchestrator = RAGOrchestrator(actian_pool=actian_pool)
```

---

## Verification Steps

1. **Start Actian container:**
   ```bash
   docker-compose -f docker/docker-compose.actian.yml up -d
   ```

2. **Check health:**
   ```bash
   docker exec hacklytics_actian pg_isready -U vectordb
   # Should return: /tmp:5432 - accepting connections
   ```

3. **Verify schema:**
   ```bash
   docker exec -it hacklytics_actian psql -U vectordb -d safety_rag -c "\dt"
   # Should show: safety_protocols, incident_log
   ```

4. **Seed protocols:**
   ```bash
   python scripts/seed_protocols.py
   # Should insert 10+ protocols (expand to 30-50)
   ```

5. **Run test queries:**
   ```bash
   python scripts/test_actian_queries.py
   # All 3 tests should PASS
   ```

6. **Performance check:**
   - Protocol retrieval: <200ms
   - History retrieval: <200ms
   - Index scans > 0 (confirms indexes are used)

---

---

## Task 6: Redis Cache Layer Setup

### Context: Cache-First Architecture

To reduce Actian query load and improve latency, we implement a two-layer Redis cache using **semantic quantization** (YOLO fire buckets). See RAG.MD section 3.4.6 for full design.

**Expected Performance:**
- Protocol retrieval: 50-200ms (Actian) → 2ms (Redis cache hit)
- Session history: 30-50ms (Actian) → 5-10ms (Redis cache hit)
- Cache hit rate: 94-95% (128-state semantic quantization)

### Task 6.1: Add Redis to Docker Compose

Update `docker/docker-compose.actian.yml` to include Redis:

```yaml
version: '3.8'

services:
  actian:
    image: ankane/pgvector:latest
    container_name: hacklytics_actian
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: vectordb
      POSTGRES_PASSWORD: vectordb_pass
      POSTGRES_DB: safety_rag
    volumes:
      - actian_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/01_schema.sql
    networks:
      - hacklytics_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vectordb"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ====================================
  # Redis Cache Layer (NEW)
  # ====================================
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

networks:
  hacklytics_network:
    driver: bridge

volumes:
  actian_data:
    driver: local
  redis_data:
    driver: local
```

**Configuration Notes:**
- `--appendonly yes`: Persist cache to disk (survives restarts)
- `--maxmemory 256mb`: Limit memory usage (128 cache states × ~1KB = ~128KB, plus session history)
- `--maxmemory-policy allkeys-lru`: Evict least-recently-used keys when memory limit reached

### Task 6.2: Create Redis Cache Agent

**Already implemented at `backend/agents/redis_cache.py`** (see RAG.MD 3.4.6 for full code).

Key features:
- Layer 1: Semantic protocol cache (YOLO fire buckets)
- Layer 2: Session history cache (sorted sets with vectorized similarity)
- Metrics tracking (hit rate, latency)
- Graceful degradation on Redis failure

### Task 6.3: Test Redis Cache

Create `scripts/test_redis_cache.py`:

```python
#!/usr/bin/env python3
"""
Test Redis cache layer for RAG pipeline.

Tests:
1. Semantic protocol cache (YOLO fire buckets)
2. Session history cache (sorted sets)
3. Cache hit rate under realistic scenarios
"""

import asyncio
import time
from backend.agents.redis_cache import RAGCacheAgent
from backend.contracts.models import TelemetryPacket


class MockPacket:
    """Mock packet for testing semantic cache keys."""
    def __init__(self, fire_dominance, smoke_opacity, proximity_alert, hazard_level):
        self.fire_dominance = fire_dominance
        self.smoke_opacity = smoke_opacity
        self.proximity_alert = proximity_alert
        self.hazard_level = hazard_level


async def test_semantic_cache_key_generation():
    """
    Test 1: Verify semantic cache keys are deterministic and cover 128 states.
    """
    print("\n=== Test 1: Semantic Cache Key Generation ===")

    cache = RAGCacheAgent(redis_url="redis://localhost:6379")

    # Test boundary conditions for fire buckets
    test_cases = [
        (0.05, 0.1, False, "LOW", "FIRE_MINOR|SMOKE_CLEAR|PROX_FAR|LOW"),
        (0.15, 0.3, False, "MODERATE", "FIRE_MODERATE|SMOKE_HAZY|PROX_FAR|MODERATE"),
        (0.45, 0.6, True, "HIGH", "FIRE_MAJOR|SMOKE_DENSE|PROX_NEAR|HIGH"),
        (0.75, 0.9, True, "CRITICAL", "FIRE_CRITICAL|SMOKE_BLINDING|PROX_NEAR|CRITICAL"),
    ]

    for fire, smoke, prox, hazard, expected_key in test_cases:
        packet = MockPacket(fire, smoke, prox, hazard)
        key = cache.get_semantic_cache_key(packet)
        assert key == expected_key, f"Expected {expected_key}, got {key}"
        print(f"  ✓ {expected_key}")

    print("\n✅ Semantic cache key generation test PASSED")


async def test_protocol_caching():
    """
    Test 2: Verify protocol caching and retrieval.
    """
    print("\n=== Test 2: Protocol Caching & Retrieval ===")

    cache = RAGCacheAgent(redis_url="redis://localhost:6379")

    packet = MockPacket(
        fire_dominance=0.35,
        smoke_opacity=0.55,
        proximity_alert=True,
        hazard_level="HIGH"
    )

    # Cache miss on first call
    result = await cache.get_protocols_by_semantic_key(packet)
    assert result is None, "Expected cache miss on first call"
    print("  ✓ Cache miss on first call (expected)")

    # Cache protocols
    mock_protocols = [
        {"protocol_text": "Evacuate immediately", "severity": "CRITICAL", "source": "NFPA_1001"},
        {"protocol_text": "Use SCBA", "severity": "HIGH", "source": "OSHA_29CFR"}
    ]

    await cache.cache_protocols_by_semantic_key(packet, mock_protocols, ttl=300)
    print("  ✓ Cached protocols")

    # Cache hit on second call
    result = await cache.get_protocols_by_semantic_key(packet)
    assert result is not None, "Expected cache hit on second call"
    assert len(result) == 2, f"Expected 2 protocols, got {len(result)}"
    assert result[0]["protocol_text"] == "Evacuate immediately"
    print(f"  ✓ Cache hit: retrieved {len(result)} protocols")

    # Verify same semantic bucket hits cache (slightly different fire values)
    similar_packet = MockPacket(
        fire_dominance=0.40,  # Still MAJOR bucket (30-60%)
        smoke_opacity=0.60,   # Still DENSE bucket (50-80%)
        proximity_alert=True,
        hazard_level="HIGH"
    )

    result = await cache.get_protocols_by_semantic_key(similar_packet)
    assert result is not None, "Expected cache hit for same semantic bucket"
    print("  ✓ Cache hit for similar packet in same bucket")

    print("\n✅ Protocol caching test PASSED")


async def test_session_history_cache():
    """
    Test 3: Verify session history caching and vectorized similarity search.
    """
    print("\n=== Test 3: Session History Cache ===")

    cache = RAGCacheAgent(redis_url="redis://localhost:6379")

    session_id = "test_session_001"
    device_id = "jetson_test"

    # Append 3 incidents to session history
    incidents = [
        ("Smoke detected in hallway", [0.1] * 384, 1.0, "STABLE", "LOW"),
        ("Fire growing in corner", [0.5] * 384, 2.0, "GROWING", "MODERATE"),
        ("Person spotted near fire", [0.8] * 384, 3.0, "RAPID_GROWTH", "HIGH"),
    ]

    for narrative, vector, timestamp, trend, hazard in incidents:
        await cache.append_session_history(
            session_id=session_id,
            device_id=device_id,
            narrative=narrative,
            vector=vector,
            timestamp=time.time() - (4.0 - timestamp),  # Make timestamps realistic
            trend=trend,
            hazard_level=hazard
        )

    print(f"  ✓ Appended {len(incidents)} incidents to session history")

    # Query for similar incidents (using vector similar to incident #2)
    similar_vector = [0.55] * 384
    results = await cache.get_session_history(
        session_id=session_id,
        device_id=device_id,
        current_vector=similar_vector,
        similarity_threshold=0.70,
        max_results=5
    )

    assert len(results) > 0, "Expected at least 1 similar incident"
    print(f"  ✓ Retrieved {len(results)} similar incidents")

    # Verify results are sorted by similarity
    for i, incident in enumerate(results):
        print(f"    {i+1}. {incident['narrative']} (sim={incident['similarity']:.3f}, {incident['time_ago']:.1f}s ago)")

    print("\n✅ Session history cache test PASSED")


async def test_cache_hit_rate_simulation():
    """
    Test 4: Simulate realistic fire growth and measure cache hit rate.
    """
    print("\n=== Test 4: Cache Hit Rate Simulation ===")

    cache = RAGCacheAgent(redis_url="redis://localhost:6379")
    cache.reset_metrics()

    # Simulate fire growing from 5% → 70% over 20 packets
    # Fire buckets: MINOR (5-9%), MODERATE (10-29%), MAJOR (30-59%), CRITICAL (60-70%)
    # Expected: 3-5 packets per bucket before transition = high hit rate

    for i in range(20):
        fire_dominance = 0.05 + (i * 0.035)  # Gradual growth
        smoke_opacity = 0.20 + (i * 0.03)
        proximity_alert = i > 12  # Alert triggered at packet 13
        hazard_level = (
            "LOW" if fire_dominance < 0.15 else
            "MODERATE" if fire_dominance < 0.35 else
            "HIGH" if fire_dominance < 0.60 else
            "CRITICAL"
        )

        packet = MockPacket(fire_dominance, smoke_opacity, proximity_alert, hazard_level)

        # Try cache first
        result = await cache.get_protocols_by_semantic_key(packet)

        # On miss, simulate Actian query and cache result
        if result is None:
            mock_protocols = [{"protocol_text": f"Protocol for {packet.hazard_level}", "severity": hazard_level}]
            await cache.cache_protocols_by_semantic_key(packet, mock_protocols, ttl=300)

    # Get metrics
    stats = cache.get_cache_stats()
    semantic_stats = stats["semantic_protocol_cache"]

    hit_rate = semantic_stats["hit_rate"]
    print(f"\n  Cache Performance:")
    print(f"    Hits: {semantic_stats['hits']}")
    print(f"    Misses: {semantic_stats['misses']}")
    print(f"    Hit Rate: {hit_rate*100:.1f}%")
    print(f"    Avg Latency: {semantic_stats['avg_latency_ms']:.2f}ms")

    # Expect 75%+ hit rate (some buckets have 3-5 consecutive packets)
    assert hit_rate >= 0.70, f"Expected hit rate ≥70%, got {hit_rate*100:.1f}%"

    print("\n✅ Cache hit rate simulation PASSED")


async def main():
    """Run all Redis cache tests."""
    await test_semantic_cache_key_generation()
    await test_protocol_caching()
    await test_session_history_cache()
    await test_cache_hit_rate_simulation()

    print("\n🎉 All Redis cache tests PASSED")


if __name__ == "__main__":
    asyncio.run(main())
```

**Run tests:**
```bash
# Start Redis
docker-compose -f docker/docker-compose.actian.yml up -d redis

# Run tests
python scripts/test_redis_cache.py
```

**Expected output:**
```
=== Test 1: Semantic Cache Key Generation ===
  ✓ FIRE_MINOR|SMOKE_CLEAR|PROX_FAR|LOW
  ✓ FIRE_MODERATE|SMOKE_HAZY|PROX_FAR|MODERATE
  ✓ FIRE_MAJOR|SMOKE_DENSE|PROX_NEAR|HIGH
  ✓ FIRE_CRITICAL|SMOKE_BLINDING|PROX_NEAR|CRITICAL
✅ Semantic cache key generation test PASSED

=== Test 2: Protocol Caching & Retrieval ===
  ✓ Cache miss on first call (expected)
  ✓ Cached protocols
  ✓ Cache hit: retrieved 2 protocols
  ✓ Cache hit for similar packet in same bucket
✅ Protocol caching test PASSED

=== Test 3: Session History Cache ===
  ✓ Appended 3 incidents to session history
  ✓ Retrieved 2 similar incidents
    1. Person spotted near fire (sim=0.985, 1.2s ago)
    2. Fire growing in corner (sim=0.905, 2.1s ago)
✅ Session history cache test PASSED

=== Test 4: Cache Hit Rate Simulation ===
  Cache Performance:
    Hits: 15
    Misses: 5
    Hit Rate: 75.0%
    Avg Latency: 1.8ms
✅ Cache hit rate simulation PASSED

🎉 All Redis cache tests PASSED
```

---

## Ready for Integration When:

- ✅ Actian container running and healthy
- ✅ Schema created with vector indexes
- ✅ 30-50 protocols seeded
- ✅ Test queries return results <200ms
- ✅ Connection pool helper created
- ✅ **Redis container running and healthy**
- ✅ **Redis cache tests passing (hit rate ≥70%)**

---

## Handoff to Prompt 5

Once complete, you'll have:
- Fully operational Actian Vector DB
- Seeded knowledge base (safety_protocols)
- Empty temporal memory (incident_log) ready for writes
- Connection pool for agents
- **Redis cache layer with 94-95% expected hit rate**
- **Dual-path retrieval: cache-first → Actian fallback**

**Next:** Prompt 5 will integrate Actian + Redis with the orchestrator and run end-to-end tests.
