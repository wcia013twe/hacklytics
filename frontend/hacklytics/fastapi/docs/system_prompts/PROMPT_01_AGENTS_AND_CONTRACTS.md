# PROMPT 1: Sub-Agent Implementation & Data Contracts

**Objective:** Implement all 8 specialized sub-agents with Pydantic data contracts, input/output validation, and unit tests.

**Status:** ✅ Independent - Can run in parallel with Prompts 3 and 4

**Deliverables:**
- `/backend/agents/` directory with 8 agent classes
- `/backend/contracts/` directory with Pydantic models
- Unit tests for each agent

---

## Context from RAG.MD

You are implementing the sub-agents for a safety-critical temporal RAG system. The system has a dual-path architecture:
- **Reflex Path** (3 agents): <50ms latency, synchronous, critical for safety
- **Cognition Path** (5 agents): <2s latency, asynchronous, enrichment only

**Reference Sections in RAG.MD:**
- Section 3.1: Inbound Payload schema and visual narrative generation
- Section 3.2: Actian Vector DB schema (safety_protocols and incident_log tables)
- Section 3.3.1: Actian SQL queries with `<->` operator for vector similarity
- Section 3.4.1: TemporalBuffer implementation (deque, time-based eviction, out-of-order handling)
- Section 3.4.2: Trend computation algorithm (linear regression, thresholds)
- Section 3.4.3: WebSocket message schemas (reflex_update and rag_recommendation)
- Section 3.4.4: RAG synthesis templates (v1 template-based, v2 LLM-based)
- Section 3.4.5: Batched incident writes (2-second flush intervals)
- Section 3.4.6: Pre-computed scenario cache (LRU, 20 common scenarios)

---

## Task 1: Create Pydantic Data Contracts

Create `backend/contracts/models.py` with the following models:

```python
from pydantic import BaseModel, Field, validator
from typing import Literal, List, Dict, Optional
from datetime import datetime

class TrackedObject(BaseModel):
    id: int
    label: str
    status: str
    duration_in_frame: float

class Scores(BaseModel):
    fire_dominance: float = Field(..., ge=0.0, le=1.0)
    smoke_opacity: float = Field(..., ge=0.0, le=1.0)
    proximity_alert: bool

class TelemetryPacket(BaseModel):
    device_id: str = Field(..., pattern=r"jetson_\w+")
    session_id: str = Field(..., pattern=r"mission_\w+")
    timestamp: float
    hazard_level: Literal["CLEAR", "LOW", "MODERATE", "HIGH", "CRITICAL"]
    scores: Scores
    tracked_objects: List[TrackedObject]
    visual_narrative: str = Field(..., max_length=200, min_length=1)

    @validator('timestamp')
    def validate_timestamp(cls, v):
        # Allow timestamps within 5 seconds of current time (tolerance for clock skew)
        import time
        current_time = time.time()
        if abs(v - current_time) > 5:
            raise ValueError(f"Timestamp {v} is >5s from current time {current_time}")
        return v

class TrendResult(BaseModel):
    """Fire growth trend result from TemporalBuffer analysis.

    Based on RAG.MD Section 3.4.2:
    - Uses linear regression over buffered fire_dominance values
    - Thresholds: RAPID_GROWTH >0.10/s, GROWING >0.02/s, STABLE -0.05 to +0.02, DIMINISHING <-0.05
    """
    trend_tag: Literal["RAPID_GROWTH", "GROWING", "STABLE", "DIMINISHING", "UNKNOWN"]
    growth_rate: float = Field(..., description="Change in fire_dominance per second")
    sample_count: int = Field(..., description="Number of packets in analysis")
    time_span: float = Field(..., description="Time range of buffer in seconds")

class EmbeddingResult(BaseModel):
    request_id: str
    vector: List[float]
    embedding_time_ms: float
    model: str = "all-MiniLM-L6-v2"

    @validator('vector')
    def validate_vector_dimension(cls, v):
        if len(v) != 384:
            raise ValueError(f"Vector must be 384-dim, got {len(v)}")
        return v

class Protocol(BaseModel):
    protocol_text: str
    severity: str
    category: str
    source: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    tags: List[str]

class HistoryEntry(BaseModel):
    raw_narrative: str
    timestamp: float
    trend_tag: str
    hazard_level: str
    similarity_score: float
    time_ago_seconds: float

class RAGRecommendation(BaseModel):
    recommendation: str = Field(..., max_length=300)
    matched_protocol: Optional[str]
    context_summary: str
    synthesis_time_ms: float
```

**Validation:** Run `pytest tests/test_contracts.py` - all models should accept valid data and reject invalid data.

---

## Task 2: Implement TelemetryIngestAgent

Create `backend/agents/telemetry_ingest.py`:

```python
import json
import logging
from typing import Dict, Tuple
from contracts.models import TelemetryPacket

logger = logging.getLogger(__name__)

class TelemetryIngestAgent:
    """
    Validates incoming ZMQ packets and routes to device-specific buffers.
    """

    def __init__(self):
        self.malformed_count = 0
        self.valid_count = 0

    async def validate_schema(self, raw_json: str) -> Tuple[bool, Dict]:
        """
        Task 1.2: Validate schema

        Returns:
            (valid, result) where result contains either parsed_packet or errors
        """
        try:
            data = json.loads(raw_json)
            packet = TelemetryPacket(**data)
            self.valid_count += 1
            return True, {"parsed_packet": packet, "errors": []}
        except json.JSONDecodeError as e:
            self.malformed_count += 1
            logger.error(f"Invalid JSON: {e}")
            return False, {"parsed_packet": None, "errors": [f"JSON decode error: {str(e)}"]}
        except Exception as e:
            self.malformed_count += 1
            logger.error(f"Schema validation failed: {e}")
            return False, {"parsed_packet": None, "errors": [str(e)]}

    async def route_to_buffer(self, packet: TelemetryPacket) -> str:
        """
        Task 1.3: Route to buffer

        Returns:
            buffer_key (device_id)
        """
        return packet.device_id

    def get_stats(self) -> Dict:
        return {
            "valid_count": self.valid_count,
            "malformed_count": self.malformed_count,
            "error_rate": self.malformed_count / max(1, self.valid_count + self.malformed_count)
        }
```

**Validation:** Create test with valid/invalid packets, verify error handling.

---

## Task 3: Implement TemporalBufferAgent

Create `backend/agents/temporal_buffer.py`:

**Implementation Note:** This follows RAG.MD Section 3.4.1 (TemporalBuffer) and Section 3.4.2 (Trend Computation) exactly.

```python
import time
import bisect
from collections import deque
from typing import Dict, List
from contracts.models import TelemetryPacket, TrendResult

class TemporalBufferAgent:
    """
    Maintains 10-second sliding window per device, computes fire growth trends.

    Design (from RAG.MD 3.4.1):
    - One buffer instance per device_id
    - Stores packets in a deque (efficient FIFO operations)
    - Evicts packets older than window_seconds on every access
    - Packets are kept in chronological order (oldest first)
    - Handles out-of-order packets using binary search insertion
    """

    def __init__(self, window_seconds: float = 10.0):
        self.buffers: Dict[str, deque] = {}
        self.window_seconds = window_seconds
        self.last_eviction_time: Dict[str, float] = {}

    async def insert_packet(self, device_id: str, packet: TelemetryPacket) -> Dict:
        """
        Task 2.1: Insert packet with out-of-order handling

        Handles WiFi jitter by maintaining chronological order.
        Discards packets older than buffer window.
        """
        if device_id not in self.buffers:
            self.buffers[device_id] = deque()
            self.last_eviction_time[device_id] = time.time()

        buffer = self.buffers[device_id]
        packet_time = packet.timestamp
        current_time = time.time()

        # Discard packets outside retention window
        if current_time - packet_time > self.window_seconds:
            return {"inserted": False, "reason": "too_old", "buffer_size": len(buffer)}

        # Evict stale packets first
        await self.evict_stale(device_id, current_time)

        # Insert packet in chronological order
        packet_dict = {
            "timestamp": packet_time,
            "scores": packet.scores.dict(),
            "packet": packet
        }

        # Common case: in-order arrival (O(1) append)
        if not buffer or packet_time >= buffer[-1]["timestamp"]:
            buffer.append(packet_dict)
        else:
            # Rare case: out-of-order packet (O(n) insertion with binary search)
            timestamps = [p["timestamp"] for p in buffer]
            insert_idx = bisect.bisect_left(timestamps, packet_time)
            buffer.insert(insert_idx, packet_dict)

        return {
            "inserted": True,
            "buffer_size": len(buffer),
            "out_of_order": packet_time < buffer[-1]["timestamp"] if len(buffer) > 1 else False
        }

    async def evict_stale(self, device_id: str, current_time: float) -> Dict:
        """
        Task 2.2: Evict stale packets (>window_seconds old)

        Lazy eviction on access (not background timer).
        """
        if device_id not in self.buffers:
            return {"evicted_count": 0, "buffer_size": 0}

        buffer = self.buffers[device_id]
        evicted = 0
        cutoff_time = current_time - self.window_seconds

        # Remove from left (oldest) until we hit a recent one
        while buffer and buffer[0]["timestamp"] < cutoff_time:
            buffer.popleft()
            evicted += 1

        self.last_eviction_time[device_id] = current_time

        return {"evicted_count": evicted, "buffer_size": len(buffer)}

    async def compute_trend(self, device_id: str) -> TrendResult:
        """
        Task 2.3: Compute fire growth trend using linear regression

        Algorithm (from RAG.MD 3.4.2):
        - Uses linear regression over fire_dominance values
        - Smooths noise better than simple delta
        - Thresholds calibrated for fire_dominance [0.0, 1.0] range

        Classification thresholds:
        - RAPID_GROWTH: growth_rate > 0.10/s (fire doubles in 10s, flashover imminent)
        - GROWING: 0.02 < growth_rate ≤ 0.10/s (steady expansion, active combustion)
        - STABLE: -0.05 ≤ growth_rate ≤ 0.02/s (contained or steady-state)
        - DIMINISHING: growth_rate < -0.05/s (suppression or fuel exhausted)
        - UNKNOWN: <2 packets in buffer or time_span <0.5s
        """
        if device_id not in self.buffers or len(self.buffers[device_id]) < 2:
            return TrendResult(
                trend_tag="UNKNOWN",
                growth_rate=0.0,
                sample_count=len(self.buffers.get(device_id, [])),
                time_span=0.0
            )

        buffer = list(self.buffers[device_id])  # Convert deque to list
        sorted_packets = sorted(buffer, key=lambda p: p["timestamp"])

        timestamps = [p["timestamp"] for p in sorted_packets]
        fire_values = [p["scores"]["fire_dominance"] for p in sorted_packets]

        time_span = timestamps[-1] - timestamps[0]

        if time_span < 0.5:  # Less than 500ms of data
            return TrendResult(
                trend_tag="UNKNOWN",
                growth_rate=0.0,
                sample_count=len(sorted_packets),
                time_span=time_span
            )

        # Linear regression slope
        growth_rate = self._linear_regression_slope(timestamps, fire_values)

        # Classify trend based on thresholds from RAG.MD 3.4.2
        if growth_rate > 0.10:
            trend_tag = "RAPID_GROWTH"
        elif growth_rate > 0.02:
            trend_tag = "GROWING"
        elif growth_rate < -0.05:
            trend_tag = "DIMINISHING"
        else:  # -0.05 to 0.02 range
            trend_tag = "STABLE"

        return TrendResult(
            trend_tag=trend_tag,
            growth_rate=round(growth_rate, 4),
            sample_count=len(sorted_packets),
            time_span=round(time_span, 2)
        )

    def _linear_regression_slope(self, x_values: List[float], y_values: List[float]) -> float:
        """
        Compute slope of best-fit line using least squares regression.

        Formula: slope = Σ((x - x_mean)(y - y_mean)) / Σ((x - x_mean)²)
        """
        n = len(x_values)
        x_mean = sum(x_values) / n
        y_mean = sum(y_values) / n

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)

        if denominator == 0:
            return 0.0  # All timestamps identical (shouldn't happen)

        return numerator / denominator
```

**Validation:** Test with synthetic sequences from RAG.MD Test 3:
- Test case A: Linear increase from 0.1 to 0.6 over 10 packets → `RAPID_GROWTH`
- Test case B: Hold at 0.3 over 10 packets → `STABLE`
- Test case C: Decrease from 0.5 to 0.2 over 10 packets → `DIMINISHING`

---

## Task 4: Implement ReflexPublisherAgent

Create `backend/agents/reflex_publisher.py`:

```python
import json
import time
from typing import Dict, List, Set
from contracts.models import TelemetryPacket, TrendResult

class ReflexPublisherAgent:
    """
    Formats and broadcasts reflex updates to dashboard via WebSocket.
    """

    def __init__(self):
        # session_id -> Set[websocket_connection]
        self.ws_clients: Dict[str, Set] = {}

    async def format_reflex_message(self, packet: TelemetryPacket, trend: TrendResult) -> Dict:
        """Task 3.1: Format reflex message"""
        return {
            "message_type": "reflex_update",
            "device_id": packet.device_id,
            "session_id": packet.session_id,
            "hazard_level": packet.hazard_level,
            "scores": {
                "fire_dominance": packet.scores.fire_dominance,
                "smoke_opacity": packet.scores.smoke_opacity,
                "proximity_alert": packet.scores.proximity_alert
            },
            "trend": {
                "tag": trend.trend_tag,
                "growth_rate": trend.growth_rate,
                "confidence": trend.confidence
            },
            "timestamp": packet.timestamp
        }

    async def websocket_broadcast(self, message: Dict, session_id: str, timeout_ms: int = 10) -> Dict:
        """
        Task 3.2: Broadcast to all WebSocket clients in session

        Returns:
            {"clients_reached": int, "send_time_ms": float}
        """
        start = time.perf_counter()

        if session_id not in self.ws_clients or not self.ws_clients[session_id]:
            # No clients connected - this is OK, not an error
            return {"clients_reached": 0, "send_time_ms": 0}

        clients_reached = 0
        failed_clients = set()

        for ws in self.ws_clients[session_id]:
            try:
                await ws.send_json(message)
                clients_reached += 1
            except Exception as e:
                # Client disconnected, mark for removal
                failed_clients.add(ws)

        # Remove failed clients
        self.ws_clients[session_id] -= failed_clients

        send_time = (time.perf_counter() - start) * 1000
        return {"clients_reached": clients_reached, "send_time_ms": send_time}

    def register_client(self, session_id: str, ws):
        """Add WebSocket client to broadcast group"""
        if session_id not in self.ws_clients:
            self.ws_clients[session_id] = set()
        self.ws_clients[session_id].add(ws)

    def unregister_client(self, session_id: str, ws):
        """Remove WebSocket client from broadcast group"""
        if session_id in self.ws_clients:
            self.ws_clients[session_id].discard(ws)
```

**Validation:** Mock WebSocket connections, verify broadcast reaches all clients.

---

## Task 5: Implement EmbeddingAgent

Create `backend/agents/embedding.py`:

```python
import time
from typing import Optional
from sentence_transformers import SentenceTransformer
from contracts.models import EmbeddingResult
import logging

logger = logging.getLogger(__name__)

class EmbeddingAgent:
    """
    Converts text narratives to 384-dim semantic vectors using MiniLM-L6.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        self.warmup_complete = False

    async def warmup_model(self) -> Dict:
        """Task 4.2: Warmup model (first call is slow ~500ms)"""
        start = time.perf_counter()
        self.model = SentenceTransformer(self.model_name)
        # Warm up with dummy text
        _ = self.model.encode("warmup text")
        warmup_time = (time.perf_counter() - start) * 1000
        self.warmup_complete = True
        logger.info(f"Model warmed up in {warmup_time:.2f}ms")
        return {"warmup_complete": True, "warmup_time_ms": warmup_time}

    async def embed_text(self, text: str, request_id: str) -> EmbeddingResult:
        """
        Task 4.1: Embed text to 384-dim vector

        Returns:
            EmbeddingResult with vector, timing, metadata
        """
        if not self.model:
            await self.warmup_model()

        # Truncate to 200 chars if needed
        if len(text) > 200:
            logger.warning(f"Text exceeds 200 chars, truncating: {text[:50]}...")
            text = text[:200]

        # Handle empty text
        if not text.strip():
            logger.warning("Empty text provided, returning zero vector")
            return EmbeddingResult(
                request_id=request_id,
                vector=[0.0] * 384,
                embedding_time_ms=0.0,
                model=self.model_name
            )

        start = time.perf_counter()
        vector = self.model.encode(text).tolist()
        embed_time = (time.perf_counter() - start) * 1000

        return EmbeddingResult(
            request_id=request_id,
            vector=vector,
            embedding_time_ms=embed_time,
            model=self.model_name
        )
```

**Validation:** Test embedding quality with Test 1 from RAG.MD (semantic similarity check).

---

## Task 6: Implement ProtocolRetrievalAgent

Create `backend/agents/protocol_retrieval.py`:

```python
import time
from typing import List, Optional
from contracts.models import Protocol
import logging

logger = logging.getLogger(__name__)

class ProtocolRetrievalAgent:
    """
    Queries Actian for top-K safety protocols via vector similarity.
    """

    def __init__(self, actian_connection_pool):
        self.conn_pool = actian_connection_pool

    def build_query(self, vector: List[float], severity_filter: List[str], top_k: int = 3) -> tuple:
        """Task 5.1: Build parameterized query"""
        sql = """
        SELECT
            protocol_text,
            severity,
            category,
            source,
            tags,
            1 - (scenario_vector <=> %s::vector) AS similarity_score
        FROM safety_protocols
        WHERE severity = ANY(%s)
        ORDER BY scenario_vector <=> %s::vector
        LIMIT %s
        """
        return sql, (vector, severity_filter, vector, top_k)

    async def execute_vector_search(
        self,
        vector: List[float],
        severity: List[str] = ["HIGH", "CRITICAL"],
        top_k: int = 3,
        timeout: int = 200
    ) -> List[Protocol]:
        """
        Task 5.2: Execute vector search

        Returns:
            List of Protocol objects ordered by similarity
        """
        start = time.perf_counter()

        try:
            sql, params = self.build_query(vector, severity, top_k)

            async with self.conn_pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)

            protocols = []
            for row in rows:
                protocols.append(Protocol(
                    protocol_text=row['protocol_text'],
                    severity=row['severity'],
                    category=row['category'],
                    source=row['source'],
                    similarity_score=float(row['similarity_score']),
                    tags=row['tags'].split(',') if row['tags'] else []
                ))

            query_time = (time.perf_counter() - start) * 1000
            logger.info(f"Protocol retrieval: {len(protocols)} results in {query_time:.2f}ms")

            return protocols

        except Exception as e:
            logger.error(f"Protocol retrieval failed: {e}")
            return []
```

**Validation:** Requires Actian running. For now, create mock that returns sample protocols.

---

## Task 7: Implement HistoryRetrievalAgent

Create `backend/agents/history_retrieval.py`:

```python
import time
from typing import List
from contracts.models import HistoryEntry
import logging

logger = logging.getLogger(__name__)

class HistoryRetrievalAgent:
    """
    Queries Actian for similar past incidents in current session.
    """

    def __init__(self, actian_connection_pool):
        self.conn_pool = actian_connection_pool

    def build_history_query(
        self,
        vector: List[float],
        session_id: str,
        threshold: float = 0.70,
        top_k: int = 5
    ) -> tuple:
        """Task 6.1: Build history query with session filter"""
        sql = """
        SELECT
            raw_narrative,
            timestamp,
            trend_tag,
            hazard_level,
            1 - (narrative_vector <=> %s::vector) AS similarity_score
        FROM incident_log
        WHERE session_id = %s
          AND 1 - (narrative_vector <=> %s::vector) > %s
        ORDER BY
            narrative_vector <=> %s::vector,
            timestamp DESC
        LIMIT %s
        """
        return sql, (vector, session_id, vector, threshold, vector, top_k)

    async def execute_history_search(
        self,
        vector: List[float],
        session_id: str,
        similarity_threshold: float = 0.70,
        top_k: int = 5,
        timeout: int = 200
    ) -> List[HistoryEntry]:
        """
        Task 6.2: Execute history search

        Returns:
            List of HistoryEntry objects from same session
        """
        start = time.perf_counter()
        current_time = time.time()

        try:
            sql, params = self.build_history_query(vector, session_id, similarity_threshold, top_k)

            async with self.conn_pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)

            history = []
            for row in rows:
                time_ago = current_time - row['timestamp']
                history.append(HistoryEntry(
                    raw_narrative=row['raw_narrative'],
                    timestamp=row['timestamp'],
                    trend_tag=row['trend_tag'],
                    hazard_level=row['hazard_level'],
                    similarity_score=float(row['similarity_score']),
                    time_ago_seconds=time_ago
                ))

            query_time = (time.perf_counter() - start) * 1000
            logger.info(f"History retrieval: {len(history)} results in {query_time:.2f}ms")

            return history

        except Exception as e:
            logger.error(f"History retrieval failed: {e}")
            return []
```

**Validation:** Mock Actian, verify session filtering and similarity threshold.

---

## Task 8: Implement IncidentLoggerAgent

Create `backend/agents/incident_logger.py`:

```python
import time
import asyncio
from typing import List, Dict
from collections import deque
import logging

logger = logging.getLogger(__name__)

class IncidentLoggerAgent:
    """
    Writes incidents to Actian incident_log table (batched every 2s).
    """

    def __init__(self, actian_connection_pool, batch_interval: int = 2):
        self.conn_pool = actian_connection_pool
        self.batch_interval = batch_interval
        self.write_buffer = deque()
        self.batch_task = None

    def format_incident_row(self, vector: List[float], narrative: str, metadata: Dict) -> Dict:
        """Task 7.1: Format incident row"""
        return {
            "narrative_vector": vector,
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

    async def write_to_actian(self, vector: List[float], packet, trend) -> Dict:
        """
        Task 7.2: Write incident (buffered, batched)

        Returns:
            {"incident_id": Optional[int], "write_time_ms": float, "success": bool}
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

        return {"incident_id": None, "write_time_ms": 0.0, "success": True}  # Queued

    async def _batch_flush_loop(self):
        """Background task: Flush buffer every 2s"""
        while True:
            await asyncio.sleep(self.batch_interval)
            if self.write_buffer:
                await self._flush_batch()

    async def _flush_batch(self) -> Dict:
        """Task 7.3: Batch flush to Actian"""
        if not self.write_buffer:
            return {"inserted_count": 0, "failed_count": 0, "flush_time_ms": 0}

        start = time.perf_counter()
        batch = list(self.write_buffer)
        self.write_buffer.clear()

        inserted = 0
        failed = 0

        try:
            async with self.conn_pool.acquire() as conn:
                for row in batch:
                    try:
                        await conn.execute("""
                            INSERT INTO incident_log (
                                narrative_vector, raw_narrative, session_id, device_id,
                                timestamp, trend_tag, hazard_level, fire_dominance,
                                smoke_opacity, proximity_alert
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """, row["narrative_vector"], row["raw_narrative"], row["session_id"],
                            row["device_id"], row["timestamp"], row["trend_tag"],
                            row["hazard_level"], row["fire_dominance"], row["smoke_opacity"],
                            row["proximity_alert"])
                        inserted += 1
                    except Exception as e:
                        logger.error(f"Failed to insert incident: {e}")
                        failed += 1
        except Exception as e:
            logger.error(f"Batch flush failed: {e}")
            failed = len(batch)

        flush_time = (time.perf_counter() - start) * 1000
        logger.info(f"Flushed {inserted} incidents in {flush_time:.2f}ms ({failed} failed)")

        return {"inserted_count": inserted, "failed_count": failed, "flush_time_ms": flush_time}
```

**Validation:** Test batching logic, verify writes queue correctly.

---

## Task 9: Implement SynthesisAgent

Create `backend/agents/synthesis.py`:

```python
import time
from typing import List, Dict
from contracts.models import Protocol, HistoryEntry, RAGRecommendation

class SynthesisAgent:
    """
    Generates actionable recommendations from retrieved context (template-based v1).
    """

    FALLBACK_TEMPLATES = {
        "CRITICAL": "CRITICAL hazard detected. Fire trend: {trend}. Evacuate immediately. Follow emergency protocols.",
        "HIGH": "HIGH hazard detected. Fire trend: {trend}. Prepare for evacuation. Monitor situation closely.",
        "default": "Hazard conditions detected. Fire trend: {trend}. Follow standard safety procedures."
    }

    async def select_primary_protocol(self, protocols: List[Protocol], context: Dict) -> Protocol:
        """Task 8.1: Select primary protocol (highest similarity)"""
        if not protocols:
            return None
        return protocols[0]  # Already sorted by similarity

    async def render_template(
        self,
        protocols: List[Protocol],
        history: List[HistoryEntry],
        current_context: Dict
    ) -> RAGRecommendation:
        """
        Task 8.2: Render template-based recommendation

        Returns:
            RAGRecommendation with synthesized text
        """
        start = time.perf_counter()

        hazard = current_context["hazard_level"]
        trend = current_context["trend_tag"]
        growth = current_context["growth_rate"]
        proximity = current_context["proximity_alert"]

        primary_protocol = await self.select_primary_protocol(protocols, current_context)

        if primary_protocol:
            # Use retrieved protocol
            recommendation = f"{primary_protocol.protocol_text}\n\n"
            recommendation += f"Current trend: {trend} ({growth:+.3f}/s). "

            if proximity:
                recommendation += "⚠️ Personnel in proximity to hazard. "

            if history:
                recommendation += f"Similar to {len(history)} recent incident(s)."

            matched_protocol = primary_protocol.source
        else:
            # Use fallback template
            template = self.FALLBACK_TEMPLATES.get(hazard, self.FALLBACK_TEMPLATES["default"])
            recommendation = template.format(trend=trend)
            matched_protocol = "fallback"

        # Truncate to 300 chars
        if len(recommendation) > 300:
            recommendation = recommendation[:297] + "..."

        synthesis_time = (time.perf_counter() - start) * 1000

        return RAGRecommendation(
            recommendation=recommendation,
            matched_protocol=matched_protocol,
            context_summary=f"{hazard} | {trend} | {len(protocols)} protocols | {len(history)} history",
            synthesis_time_ms=synthesis_time
        )
```

**Validation:** Test with empty protocols (fallback), with protocols (template), verify 300-char limit.

---

## Verification Steps

After implementing all agents:

1. **Run unit tests:**
   ```bash
   pytest tests/agents/ -v
   ```

2. **Verify contract validation:**
   ```bash
   pytest tests/test_contracts.py -v
   ```

3. **Check imports:**
   ```bash
   python -c "from backend.agents import *; print('All agents imported successfully')"
   ```

4. **Performance baseline:**
   - EmbeddingAgent: First call <500ms, subsequent <30ms
   - TemporalBuffer: All operations <5ms
   - Synthesis: <1ms

5. **Ready for integration when:**
   - ✅ All 8 agent files created
   - ✅ All Pydantic contracts pass validation
   - ✅ Unit tests pass
   - ✅ No import errors

---

## Handoff to Prompt 2

Once complete, you'll have:
- `/backend/agents/` with 8 agent classes
- `/backend/contracts/models.py` with data contracts
- Unit tests proving each agent works in isolation

**Next:** Prompt 2 will use these agents to build the orchestrator that coordinates them.
