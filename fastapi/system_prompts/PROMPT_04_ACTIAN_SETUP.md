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
    SELECT 1 - (a <=> b);
$$ LANGUAGE SQL IMMUTABLE STRICT;

```

**Validation:** Run `docker-compose -f docker/docker-compose.actian.yml up -d`, check container health.

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
        scenario_text = protocol["scenario"]
        vector = model.encode(scenario_text).tolist()

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

## Ready for Integration When:

- ✅ Actian container running and healthy
- ✅ Schema created with vector indexes
- ✅ 30-50 protocols seeded
- ✅ Test queries return results <200ms
- ✅ Connection pool helper created

---

## Handoff to Prompt 5

Once complete, you'll have:
- Fully operational Actian Vector DB
- Seeded knowledge base (safety_protocols)
- Empty temporal memory (incident_log) ready for writes
- Connection pool for agents

**Next:** Prompt 5 will integrate Actian with the orchestrator and run end-to-end tests.
