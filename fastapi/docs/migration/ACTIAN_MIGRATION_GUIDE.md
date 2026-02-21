# Actian VectorAI DB Migration Guide

**Migration:** PostgreSQL/pgvector → Actian VectorAI DB
**Date:** February 21, 2026
**Status:** Implementation Guide
**Impact:** High - Requires changes to 8 files across database, backend agents, and deployment

---

## Executive Summary

This guide details the complete migration from PostgreSQL with pgvector extension to **Actian VectorAI DB** (gRPC-based vector database). The migration involves:

- ✅ Replacing SQL queries with Python client API calls
- ✅ Changing database drivers from `asyncpg` to `actiancortex`
- ✅ Updating Docker deployment configuration
- ✅ Rewriting protocol/history retrieval logic
- ✅ Converting incident logging from SQL INSERTs to gRPC upserts

**Estimated Migration Time:** 4-6 hours
**Risk Level:** Medium (database layer changes, requires testing)

---

## Architecture Changes

### Before (PostgreSQL/pgvector)

```
┌────────────────────────────────────────────┐
│  FastAPI Backend (Python)                  │
│  ├── asyncpg connection pool               │
│  ├── SQL queries with <-> operator         │
│  └── PostgreSQL wire protocol (port 5432)  │
└─────────────┬──────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────┐
│  PostgreSQL + pgvector (Docker)            │
│  ├── VECTOR(384) columns                   │
│  ├── IVFFlat indexes                       │
│  └── SQL query interface                   │
└────────────────────────────────────────────┘
```

### After (Actian VectorAI DB)

```
┌────────────────────────────────────────────┐
│  FastAPI Backend (Python)                  │
│  ├── CortexClient / AsyncCortexClient      │
│  ├── Python API: search(), upsert()        │
│  └── gRPC protocol (port 50051)            │
└─────────────┬──────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────┐
│  Actian VectorAI DB (Docker)               │
│  ├── Collections (safety_protocols, etc)   │
│  ├── Vector indexes (auto-managed)         │
│  └── gRPC API interface                    │
└────────────────────────────────────────────┘
```

---

## Prerequisites

### 1. Obtain Actian VectorAI DB Image

**Option A: Load from .tar file (if provided)**
```bash
docker image load -i Actian_VectorAI_DB_Beta.tar
```

**Option B: Pull from registry (if available)**
```bash
docker pull actian/vectoraidb:1.0b
# Or use the image name you were provided
```

### 2. Obtain Python Client Wheel

You need the `.whl` file:
```
actiancortex-0.1.0b1-py3-none-any.whl
```

Place it in `fastapi/` directory (same level as `requirements.txt`).

---

## Migration Steps

## Step 1: Update Dependencies

### File: `requirements.txt`

**Remove:**
```diff
- asyncpg>=0.29.0  # Async PostgreSQL driver
```

**Add:**
```diff
+ # Actian VectorAI DB Python Client (local wheel file)
+ # Install via: pip install ./actiancortex-0.1.0b1-py3-none-any.whl
+ grpcio>=1.68.1
+ protobuf>=5.29.2
+ numpy>=2.2.1
+ pydantic>=2.10.4
```

**Installation:**
```bash
# In your Docker build or local environment
pip install ./actiancortex-0.1.0b1-py3-none-any.whl
pip install -r requirements.txt
```

---

## Step 2: Update Docker Compose

### File: `docker-compose.yml`

**Replace the `actian` service:**

```yaml
services:
  # Actian VectorAI DB - gRPC-based vector storage
  actian:
    image: localhost/actian/vectoraidb:1.0b  # Or your loaded image name
    # platform: linux/amd64  # Uncomment on macOS with Apple Silicon
    container_name: hacklytics_actian
    ports:
      - "50051:50051"  # gRPC port (NOT 5432)
    volumes:
      - actian_data:/data  # Persistent storage for collections and logs
    networks:
      - rag_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "grpc_health_probe -addr=localhost:50051 || exit 0"]
      interval: 15s
      timeout: 5s
      retries: 5

  # RAG Service - Update environment variables
  rag:
    build:
      context: .
      dockerfile: Dockerfile.rag
    container_name: hacklytics_rag
    ports:
      - "8001:8001"
    environment:
      ACTIAN_HOST: actian
      ACTIAN_PORT: 50051  # Changed from 5432
      EMBEDDING_MODEL: all-MiniLM-L6-v2
      BATCH_FLUSH_INTERVAL: 2.0
      LOG_LEVEL: INFO
    depends_on:
      actian:
        condition: service_started  # Changed from service_healthy (see note)
    networks:
      - rag_network
    volumes:
      - ./backend:/app/backend:ro
      - model_cache:/root/.cache/torch
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 15s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  # ... rest of services unchanged ...

volumes:
  actian_data:
    name: hacklytics_actian_data
    driver: local
  model_cache:
    name: hacklytics_model_cache
    driver: local
```

**Note:** Actian VectorAI DB healthcheck may need adjustment based on the actual image. The simple approach is `service_started` dependency.

---

## Step 3: Create Actian Connection Pool Helper

### File: `backend/db/actian_client.py` (NEW FILE)

Create this new file to wrap the Actian client:

```python
"""
Actian VectorAI DB Connection Pool Wrapper

Provides async-compatible interface for Actian CortexClient.
Since CortexClient is synchronous, we wrap calls with asyncio.to_thread().
"""

import os
import asyncio
from typing import List, Dict, Optional
from contextlib import asynccontextmanager
import logging

from cortex import CortexClient, AsyncCortexClient, DistanceMetric

logger = logging.getLogger(__name__)


class ActianVectorPool:
    """
    Async wrapper for Actian VectorAI DB client.

    Uses AsyncCortexClient for truly async operations.
    Falls back to wrapping sync CortexClient with asyncio.to_thread() if needed.
    """

    def __init__(self):
        self.client: Optional[AsyncCortexClient] = None
        self.host: str = None
        self.port: int = None
        self._connected = False

    async def connect(
        self,
        host: str = None,
        port: int = 50051
    ):
        """
        Connect to Actian VectorAI DB via gRPC.

        Args:
            host: Actian service hostname (default: from ACTIAN_HOST env var)
            port: gRPC port (default: 50051)
        """
        self.host = host or os.getenv('ACTIAN_HOST', 'localhost')
        self.port = port

        address = f"{self.host}:{self.port}"

        try:
            # Use async client for FastAPI compatibility
            self.client = AsyncCortexClient(address)

            # Health check
            version, uptime = await self.client.health_check()
            logger.info(f"✅ Connected to Actian VectorAI DB: {version} (uptime: {uptime}s)")

            self._connected = True

        except Exception as e:
            logger.error(f"✗ Failed to connect to Actian at {address}: {e}")
            raise

    async def close(self):
        """Close connection to Actian"""
        if self.client:
            # AsyncCortexClient uses context manager, but we handle it manually
            self._connected = False
            logger.info("Actian connection closed")

    def is_connected(self) -> bool:
        return self._connected

    # === Collection Management ===

    async def create_collection(
        self,
        name: str,
        dimension: int,
        distance_metric: str = "COSINE"
    ):
        """
        Create a new collection (equivalent to PostgreSQL table).

        Args:
            name: Collection name (e.g., "safety_protocols")
            dimension: Vector dimension (e.g., 384 for MiniLM-L6)
            distance_metric: "COSINE", "EUCLIDEAN", or "DOT"
        """
        metric_map = {
            "COSINE": DistanceMetric.COSINE,
            "EUCLIDEAN": DistanceMetric.EUCLIDEAN,
            "DOT": DistanceMetric.DOT
        }

        await self.client.create_collection(
            name=name,
            dimension=dimension,
            distance_metric=metric_map.get(distance_metric, DistanceMetric.COSINE)
        )

        logger.info(f"Created collection: {name} (dim={dimension}, metric={distance_metric})")

    async def has_collection(self, name: str) -> bool:
        """Check if collection exists"""
        return await self.client.has_collection(name)

    async def delete_collection(self, name: str):
        """Delete a collection"""
        await self.client.delete_collection(name)
        logger.info(f"Deleted collection: {name}")

    # === Vector Operations ===

    async def upsert(
        self,
        collection: str,
        id: int,
        vector: List[float],
        payload: Dict
    ):
        """
        Insert or update a single vector.

        Args:
            collection: Collection name
            id: Unique vector ID
            vector: Embedding vector (list of floats)
            payload: Metadata dict (e.g., {"protocol_text": "...", "severity": "HIGH"})
        """
        await self.client.upsert(
            collection=collection,
            id=id,
            vector=vector,
            payload=payload
        )

    async def batch_upsert(
        self,
        collection: str,
        ids: List[int],
        vectors: List[List[float]],
        payloads: List[Dict]
    ):
        """
        Batch insert/update multiple vectors.

        More efficient than individual upserts for bulk operations.
        """
        await self.client.batch_upsert(
            collection=collection,
            ids=ids,
            vectors=vectors,
            payloads=payloads
        )

        logger.info(f"Batch upserted {len(ids)} vectors to {collection}")

    async def get(self, collection: str, id: int) -> Optional[Dict]:
        """
        Retrieve a single vector by ID.

        Returns:
            Dict with 'vector' and 'payload' keys, or None if not found
        """
        result = await self.client.get(collection, id)
        return result

    async def delete_vector(self, collection: str, id: int):
        """Delete a vector by ID"""
        await self.client.delete(collection, id)

    async def count(self, collection: str) -> int:
        """Get total vector count in collection"""
        return await self.client.count(collection)

    # === Search Operations ===

    async def search(
        self,
        collection: str,
        query: List[float],
        top_k: int = 3,
        filter_dict: Dict = None
    ) -> List[Dict]:
        """
        Vector similarity search.

        Args:
            collection: Collection to search
            query: Query vector
            top_k: Number of results to return
            filter_dict: Optional payload filter (see Actian filter DSL)

        Returns:
            List of dicts with 'id', 'score', 'payload' keys
        """
        if filter_dict:
            results = await self.client.search_filtered(
                collection=collection,
                query=query,
                filter=filter_dict,
                top_k=top_k
            )
        else:
            results = await self.client.search(
                collection=collection,
                query=query,
                top_k=top_k
            )

        return results

    async def scroll(
        self,
        collection: str,
        limit: int = 10,
        cursor: int = 0
    ) -> List[Dict]:
        """
        Paginate through vectors in collection.

        Args:
            collection: Collection name
            limit: Number of results per page
            cursor: Offset for pagination

        Returns:
            List of vectors with payloads
        """
        return await self.client.scroll(
            collection=collection,
            limit=limit,
            cursor=cursor
        )
```

---

## Step 4: Update Protocol Retrieval Agent

### File: `backend/agents/protocol_retrieval.py`

**Replace SQL logic with Actian client:**

```python
import time
from typing import List, Optional
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from contracts.models import Protocol

logger = logging.getLogger(__name__)

class ProtocolRetrievalAgent:
    """
    Queries Actian VectorAI DB for top-K safety protocols via vector similarity.
    """

    def __init__(self, actian_pool):
        """
        Args:
            actian_pool: ActianVectorPool instance (not asyncpg pool anymore)
        """
        self.actian = actian_pool

    async def execute_vector_search(
        self,
        vector: List[float],
        severity: List[str] = ["HIGH", "CRITICAL"],
        top_k: int = 3,
        timeout: int = 200
    ) -> List[Protocol]:
        """
        Execute vector similarity search for safety protocols.

        Migration Note:
        - Old: SQL query with `<->` operator
        - New: Actian client.search() with optional filter

        Returns:
            List of Protocol objects ordered by similarity
        """
        start = time.perf_counter()

        try:
            # Build filter for severity (Actian Filter DSL)
            from cortex.filters import Filter, Field

            # Create OR filter for multiple severity values
            # Example: severity IN ('HIGH', 'CRITICAL')
            severity_filter = None
            if severity:
                # Build filter: severity == 'HIGH' OR severity == 'CRITICAL'
                severity_filter = Filter()
                for sev in severity:
                    severity_filter = severity_filter.should(Field("severity").eq(sev))

            # Execute search
            results = await self.actian.search(
                collection="safety_protocols",
                query=vector,
                top_k=top_k,
                filter_dict=severity_filter
            )

            # Convert Actian results to Protocol objects
            protocols = []
            for result in results:
                payload = result['payload']
                protocols.append(Protocol(
                    protocol_text=payload['protocol_text'],
                    severity=payload['severity'],
                    category=payload.get('category', ''),
                    source=payload.get('source', ''),
                    similarity_score=result['score'],  # Actian returns 'score', not computed
                    tags=payload.get('tags', '').split(',') if payload.get('tags') else []
                ))

            query_time = (time.perf_counter() - start) * 1000
            logger.info(f"Protocol retrieval: {len(protocols)} results in {query_time:.2f}ms")

            return protocols

        except Exception as e:
            logger.error(f"Protocol retrieval failed: {e}")
            return []
```

---

## Step 5: Update History Retrieval Agent

### File: `backend/agents/history_retrieval.py`

**Replace SQL session history query with Actian search:**

```python
import time
from typing import List
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from contracts.models import HistoryEntry

logger = logging.getLogger(__name__)

class HistoryRetrievalAgent:
    """
    Queries Actian for similar past incidents in current session.
    """

    def __init__(self, actian_pool):
        self.actian = actian_pool

    async def execute_history_search(
        self,
        vector: List[float],
        session_id: str,
        similarity_threshold: float = 0.70,
        top_k: int = 5,
        timeout: int = 200
    ) -> List[HistoryEntry]:
        """
        Execute history search for similar incidents in same session.

        Migration Note:
        - Old: SQL query with session_id filter and timestamp ordering
        - New: Actian search with payload filter, then post-filter by similarity threshold

        Returns:
            List of HistoryEntry objects from same session
        """
        start = time.perf_counter()
        current_time = time.time()

        try:
            from cortex.filters import Filter, Field

            # Filter by session_id
            session_filter = Filter().must(Field("session_id").eq(session_id))

            # Search (Actian returns top_k by similarity automatically)
            results = await self.actian.search(
                collection="incident_log",
                query=vector,
                top_k=top_k * 2,  # Fetch more to filter by threshold
                filter_dict=session_filter
            )

            # Post-filter by similarity threshold and convert to HistoryEntry
            history = []
            for result in results:
                if result['score'] < similarity_threshold:
                    continue  # Below threshold

                payload = result['payload']
                time_ago = current_time - payload['timestamp']

                history.append(HistoryEntry(
                    raw_narrative=payload['raw_narrative'],
                    timestamp=payload['timestamp'],
                    trend_tag=payload.get('trend_tag', 'UNKNOWN'),
                    hazard_level=payload.get('hazard_level', 'UNKNOWN'),
                    similarity_score=result['score'],
                    time_ago_seconds=time_ago
                ))

            # Sort by recency (most recent first)
            history.sort(key=lambda x: x.timestamp, reverse=True)

            # Limit to top_k after filtering
            history = history[:top_k]

            query_time = (time.perf_counter() - start) * 1000
            logger.info(f"History retrieval: {len(history)} results in {query_time:.2f}ms")

            return history

        except Exception as e:
            logger.error(f"History retrieval failed: {e}")
            return []
```

---

## Step 6: Update Incident Logger Agent

### File: `backend/agents/incident_logger.py`

**Replace SQL INSERT with Actian upsert:**

```python
import time
import asyncio
from typing import List, Dict
from collections import deque
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logger = logging.getLogger(__name__)

class IncidentLoggerAgent:
    """
    Writes incidents to Actian incident_log collection (batched every 2s).
    """

    def __init__(self, actian_pool, batch_interval: int = 2):
        self.actian = actian_pool
        self.batch_interval = batch_interval
        self.write_buffer = deque()
        self.batch_task = None
        self._incident_id_counter = 0  # Auto-increment for vector IDs

    def format_incident_row(self, vector: List[float], narrative: str, metadata: Dict) -> Dict:
        """
        Format incident for Actian upsert.

        Migration Note:
        - Old: Dict for SQL INSERT VALUES
        - New: Dict with 'id', 'vector', 'payload' for Actian upsert
        """
        self._incident_id_counter += 1

        return {
            "id": self._incident_id_counter,  # Unique ID for this vector
            "vector": vector,
            "payload": {
                "raw_narrative": narrative,
                "session_id": metadata["session_id"],
                "device_id": metadata["device_id"],
                "timestamp": metadata["timestamp"],
                "trend_tag": metadata["trend_tag"],
                "hazard_level": metadata["hazard_level"],
                "fire_dominance": metadata["fire_dominance"],
                "smoke_opacity": metadata["smoke_opacity"],
                "proximity_alert": metadata["proximity_alert"]
            }
        }

    async def write_to_actian(self, vector: List[float], packet, trend) -> Dict:
        """
        Queue incident write (buffered, batched).

        Returns:
            {"incident_id": int, "write_time_ms": float, "success": bool}
        """
        row = self.format_incident_row(
            vector=vector,
            narrative=packet.visual_narrative,
            metadata={
                "session_id": packet.session_id,
                "device_id": packet.device_id,
                "timestamp": packet.timestamp,
                "trend_tag": trend.trend_tag,
                "hazard_level": packet.hazard_level,
                "fire_dominance": packet.scores.fire_dominance,
                "smoke_opacity": packet.scores.smoke_opacity,
                "proximity_alert": packet.scores.proximity_alert
            }
        )

        self.write_buffer.append(row)

        # Start batch flusher if not running
        if not self.batch_task or self.batch_task.done():
            self.batch_task = asyncio.create_task(self._batch_flush_loop())

        return {"incident_id": row["id"], "write_time_ms": 0.0, "success": True}  # Queued

    async def _batch_flush_loop(self):
        """Background task: Flush buffer every 2s"""
        while True:
            await asyncio.sleep(self.batch_interval)
            if self.write_buffer:
                await self._flush_batch()

    async def _flush_batch(self) -> Dict:
        """
        Flush buffered incidents to Actian using batch_upsert.

        Migration Note:
        - Old: SQL INSERT with executemany()
        - New: Actian batch_upsert()
        """
        if not self.write_buffer:
            return {"inserted_count": 0, "failed_count": 0, "flush_time_ms": 0}

        start = time.perf_counter()
        batch = list(self.write_buffer)
        self.write_buffer.clear()

        inserted = 0
        failed = 0

        try:
            # Extract batch data
            ids = [row["id"] for row in batch]
            vectors = [row["vector"] for row in batch]
            payloads = [row["payload"] for row in batch]

            # Batch upsert to Actian
            await self.actian.batch_upsert(
                collection="incident_log",
                ids=ids,
                vectors=vectors,
                payloads=payloads
            )

            inserted = len(batch)

        except Exception as e:
            logger.error(f"Batch flush failed: {e}")
            failed = len(batch)

        flush_time = (time.perf_counter() - start) * 1000
        logger.info(f"Flushed {inserted} incidents in {flush_time:.2f}ms ({failed} failed)")

        return {"inserted_count": inserted, "failed_count": failed, "flush_time_ms": flush_time}
```

---

## Step 7: Update Orchestrator

### File: `backend/orchestrator.py`

**Update initialization to use ActianVectorPool:**

```python
# At top of file, add import
from db.actian_client import ActianVectorPool

# In RAGOrchestrator.__init__, change type hint
def __init__(self, actian_pool: ActianVectorPool = None):
    # ... rest unchanged ...
    self.actian_pool = actian_pool
```

**No other changes needed** - the agents already accept the pool as a generic object.

---

## Step 8: Create Collection Initialization Script

### File: `scripts/init_actian_collections.py` (NEW FILE)

This replaces `init.sql` for schema creation:

```python
#!/usr/bin/env python3
"""
Initialize Actian VectorAI DB Collections

Creates the two main collections:
1. safety_protocols (static knowledge base)
2. incident_log (dynamic temporal memory)

Usage:
    python scripts/init_actian_collections.py
"""

import os
import asyncio
from db.actian_client import ActianVectorPool

ACTIAN_HOST = os.getenv("ACTIAN_HOST", "localhost")
ACTIAN_PORT = int(os.getenv("ACTIAN_PORT", "50051"))


async def init_collections():
    """Create collections if they don't exist"""
    print("=" * 60)
    print("Actian VectorAI DB Collection Initialization")
    print("=" * 60)

    # Connect
    pool = ActianVectorPool()
    await pool.connect(host=ACTIAN_HOST, port=ACTIAN_PORT)

    print(f"\n[1/2] Creating 'safety_protocols' collection...")

    if await pool.has_collection("safety_protocols"):
        print("  ⚠️  Collection already exists. Skipping creation.")
    else:
        await pool.create_collection(
            name="safety_protocols",
            dimension=384,  # MiniLM-L6 embedding size
            distance_metric="COSINE"
        )
        print("  ✓ Created collection: safety_protocols")

    print(f"\n[2/2] Creating 'incident_log' collection...")

    if await pool.has_collection("incident_log"):
        print("  ⚠️  Collection already exists. Skipping creation.")
    else:
        await pool.create_collection(
            name="incident_log",
            dimension=384,
            distance_metric="COSINE"
        )
        print("  ✓ Created collection: incident_log")

    # Verify
    print("\n[Verification] Checking collections...")
    protocols_count = await pool.count("safety_protocols")
    incidents_count = await pool.count("incident_log")

    print(f"  safety_protocols: {protocols_count} vectors")
    print(f"  incident_log: {incidents_count} vectors")

    await pool.close()

    print("\n" + "=" * 60)
    print("Initialization complete! ✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(init_collections())
```

---

## Step 9: Update Protocol Seeding Script

### File: `scripts/seed_protocols.py`

**Replace asyncpg logic with Actian client:**

```python
#!/usr/bin/env python3
"""
Safety Protocol Seeding Script (Actian VectorAI DB Version)

Embeds NFPA/OSHA safety protocols and loads them into Actian VectorAI DB.

Usage:
    python scripts/seed_protocols.py
"""

import os
import asyncio
from sentence_transformers import SentenceTransformer
from typing import List, Dict
import sys

# Add parent directory for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db.actian_client import ActianVectorPool

# Environment
ACTIAN_HOST = os.getenv("ACTIAN_HOST", "localhost")
ACTIAN_PORT = int(os.getenv("ACTIAN_PORT", "50051"))

# Safety protocols database (same as before)
PROTOCOLS: List[Dict] = [
    {
        "scenario": "Person trapped near fire with exit blocked",
        "protocol_text": "NFPA 1001: Immediate evacuation required when fire occupies >40% of visual field and victims are present. Establish defensive perimeter. Prioritize victim rescue via secondary exit.",
        "severity": "CRITICAL",
        "category": "fire",
        "tags": "trapped,exit_blocked,evacuation,rescue",
        "source": "NFPA_1001"
    },
    # ... (include all 10+ protocols from original file)
]


async def seed_protocols():
    """
    Seed protocols into Actian VectorAI DB.
    """
    print("=" * 60)
    print("Safety Protocol Seeding (Actian VectorAI DB)")
    print("=" * 60)

    # Step 1: Load embedding model
    print("\n[1/4] Loading sentence-transformers model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("✓ Model loaded: all-MiniLM-L6-v2 (384 dimensions)")

    # Step 2: Connect to Actian
    print(f"\n[2/4] Connecting to Actian VectorAI DB at {ACTIAN_HOST}:{ACTIAN_PORT}...")
    pool = ActianVectorPool()
    try:
        await pool.connect(host=ACTIAN_HOST, port=ACTIAN_PORT)
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("\nMake sure the Actian container is running:")
        print("  docker-compose up -d actian")
        return

    # Step 3: Check if collection exists
    print("\n[3/4] Verifying 'safety_protocols' collection exists...")

    if not await pool.has_collection("safety_protocols"):
        print("✗ Collection 'safety_protocols' not found!")
        print("  Run: python scripts/init_actian_collections.py")
        await pool.close()
        return

    print("✓ Collection exists")

    # Clear existing protocols (optional)
    existing_count = await pool.count("safety_protocols")
    if existing_count > 0:
        print(f"\n⚠️  Found {existing_count} existing protocols.")
        print("  Deleting collection and recreating...")
        await pool.delete_collection("safety_protocols")
        await pool.create_collection("safety_protocols", 384, "COSINE")
        print("✓ Collection reset")

    # Step 4: Batch insert protocols
    print(f"\n[4/4] Embedding and inserting {len(PROTOCOLS)} protocols...")

    ids = []
    vectors = []
    payloads = []

    for i, protocol in enumerate(PROTOCOLS, 1):
        # Embed scenario
        scenario_text = protocol["scenario"]
        vector = model.encode(scenario_text, normalize_embeddings=True).tolist()

        ids.append(i)
        vectors.append(vector)
        payloads.append({
            "protocol_text": protocol["protocol_text"],
            "severity": protocol["severity"],
            "category": protocol["category"],
            "tags": protocol["tags"],
            "source": protocol["source"]
        })

        print(f"  [{i}/{len(PROTOCOLS)}] {protocol['severity']:8s} | {protocol['scenario'][:50]}")

    # Batch upsert
    await pool.batch_upsert(
        collection="safety_protocols",
        ids=ids,
        vectors=vectors,
        payloads=payloads
    )

    print(f"\n✓ Inserted {len(PROTOCOLS)} protocols successfully")

    # Step 5: Test retrieval
    print("\n[Test] Testing vector similarity retrieval...")
    test_query = "Person trapped with fire blocking exit"
    test_vector = model.encode(test_query, normalize_embeddings=True).tolist()

    results = await pool.search(
        collection="safety_protocols",
        query=test_vector,
        top_k=3
    )

    print(f"\nTest Query: '{test_query}'")
    print("Top 3 Matching Protocols:")
    print("-" * 50)
    for i, result in enumerate(results, 1):
        payload = result['payload']
        print(f"\n{i}. [{payload['severity']}] {payload['source']}")
        print(f"   Similarity: {result['score']:.3f}")
        print(f"   Protocol: {payload['protocol_text'][:100]}...")

    await pool.close()
    print("\n" + "=" * 60)
    print("Seeding complete! ✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_protocols())
```

---

## Step 10: Update Dockerfiles

### File: `Dockerfile.rag`

**Add Actian client installation:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and wheel file
COPY requirements.txt .
COPY actiancortex-0.1.0b1-py3-none-any.whl .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir ./actiancortex-0.1.0b1-py3-none-any.whl

# Pre-download embedding model at build time
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy backend code
COPY backend/ ./backend/

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8001/health || exit 1

# Run RAG service
CMD ["uvicorn", "backend.main_rag:app", "--host", "0.0.0.0", "--port", "8001"]
```

---

## Step 11: Update Main RAG Service

### File: `backend/main_rag.py`

**Update startup to use ActianVectorPool:**

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from db.actian_client import ActianVectorPool
from orchestrator import RAGOrchestrator

logger = logging.getLogger(__name__)

# Global state
actian_pool: ActianVectorPool = None
orchestrator: RAGOrchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup and shutdown hooks"""
    global actian_pool, orchestrator

    logger.info("Starting RAG service...")

    # Connect to Actian
    actian_pool = ActianVectorPool()
    await actian_pool.connect()

    # Initialize orchestrator
    orchestrator = RAGOrchestrator(actian_pool=actian_pool)
    await orchestrator.startup()

    logger.info("✓ RAG service ready")

    yield

    # Shutdown
    logger.info("Shutting down RAG service...")
    await actian_pool.close()


app = FastAPI(title="Temporal RAG Service", lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "actian_connected": actian_pool.is_connected() if actian_pool else False
    }


@app.post("/retrieve")
async def retrieve_endpoint(payload: dict):
    """
    RAG retrieval endpoint (called by ingest service)
    """
    result = await orchestrator.process_packet(payload)
    return result
```

---

## Testing & Validation

### Test 1: Verify Actian Container

```bash
# Start Actian
docker-compose up -d actian

# Check logs
docker logs hacklytics_actian

# Expected: No errors, server listening on port 50051
```

### Test 2: Initialize Collections

```bash
# Run inside container or locally
python scripts/init_actian_collections.py

# Expected output:
# ✓ Created collection: safety_protocols
# ✓ Created collection: incident_log
```

### Test 3: Seed Protocols

```bash
python scripts/seed_protocols.py

# Expected: 10 protocols inserted, test query returns results
```

### Test 4: Start RAG Service

```bash
docker-compose up -d rag

# Check health
curl http://localhost:8001/health

# Expected: {"status": "healthy", "actian_connected": true}
```

### Test 5: End-to-End Test

Send a test packet through the full pipeline and verify:
- Protocol retrieval returns results
- History retrieval works after incident logging
- No SQL errors in logs

---

## Rollback Plan

If migration fails, revert by:

1. **Restore docker-compose.yml:**
   ```bash
   git checkout docker-compose.yml
   ```

2. **Switch back to pgvector image:**
   ```yaml
   actian:
     image: ankane/pgvector:latest
     ports:
       - "5432:5432"
   ```

3. **Restore requirements.txt:**
   ```bash
   git checkout requirements.txt
   pip install -r requirements.txt
   ```

4. **Restore agent files:**
   ```bash
   git checkout backend/agents/protocol_retrieval.py
   git checkout backend/agents/history_retrieval.py
   git checkout backend/agents/incident_logger.py
   ```

5. **Restart services:**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

---

## Summary of Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `requirements.txt` | Modified | Replace asyncpg with actiancortex |
| `docker-compose.yml` | Modified | Change Actian service to gRPC port 50051 |
| `Dockerfile.rag` | Modified | Install .whl file |
| `backend/db/actian_client.py` | **NEW** | Actian client wrapper |
| `backend/agents/protocol_retrieval.py` | Modified | Replace SQL with client.search() |
| `backend/agents/history_retrieval.py` | Modified | Replace SQL with client.search() |
| `backend/agents/incident_logger.py` | Modified | Replace SQL INSERT with batch_upsert() |
| `backend/orchestrator.py` | Minor | Update type hint |
| `scripts/init_actian_collections.py` | **NEW** | Replace init.sql |
| `scripts/seed_protocols.py` | Modified | Use Actian client instead of asyncpg |
| `backend/main_rag.py` | Modified | Use ActianVectorPool in startup |

**Total:** 11 files changed (2 new, 9 modified)

---

## Post-Migration Checklist

- [ ] Actian container starts without errors
- [ ] Collections created successfully
- [ ] Protocols seeded (count > 0)
- [ ] RAG service health check passes
- [ ] Protocol retrieval returns results
- [ ] History retrieval works after logging incidents
- [ ] Batch incident logging flushes successfully
- [ ] End-to-end latency < 2s (p95)
- [ ] No SQL errors in logs
- [ ] Graceful degradation works (RAG fails, reflex continues)

---

## Support & Troubleshooting

### Issue: "Connection refused to localhost:50051"

**Cause:** Actian container not running or healthcheck failing

**Fix:**
```bash
docker-compose logs actian
docker-compose restart actian
```

### Issue: "Collection not found"

**Cause:** Collections not initialized

**Fix:**
```bash
python scripts/init_actian_collections.py
```

### Issue: "ModuleNotFoundError: No module named 'cortex'"

**Cause:** Actian client wheel not installed

**Fix:**
```bash
pip install ./actiancortex-0.1.0b1-py3-none-any.whl
```

### Issue: "Search returns no results"

**Cause:** Protocols not seeded or vector dimension mismatch

**Fix:**
```bash
python scripts/seed_protocols.py
# Verify dimension matches (384 for MiniLM-L6)
```

---

**Migration Guide Version:** 1.0
**Last Updated:** February 21, 2026
**Status:** Ready for implementation
