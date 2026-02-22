# Safety-Critical Temporal RAG — Backend PRD

**Author:** Wes · **Date:** February 21, 2026 · **Version:** 1.0 · **Status:** Draft

> **Scope:** This document covers the backend RAG architecture only. It does not cover the Jetson Nano edge inference pipeline, the dashboard frontend, or the ZeroMQ transport layer except where they interface with the RAG backend.

---

## 1. Executive Summary

### 1.1 Problem Statement

Current fire safety systems operate as stateless detectors. They identify hazards frame-by-frame but cannot reason about how a scene is evolving over time. A camera that sees fire cannot tell you that the fire has doubled in 30 seconds, that it is blocking a trapped person's only exit, or what protocol a firefighter should follow given that specific combination of factors.

### 1.2 Proposed Solution

This PRD defines the backend RAG (Retrieval-Augmented Generation) architecture for a safety-critical system that transforms raw edge telemetry into contextual, temporally-aware intelligence. The RAG backend receives tracked object data from a Jetson Nano edge device, maintains a sliding window of recent events, embeds scene narratives into vectors, and retrieves relevant safety protocols and incident history from Actian Vector DB.

### 1.3 What Makes This Different

The architecture implements a **Reflex-Cognition Split**. Safety-critical reflex alerts (hazard level, proximity warnings) are computed on the edge in under 40ms and pushed to the dashboard instantly. The RAG pipeline operates asynchronously as a secondary intelligence layer, providing expert protocol retrieval and temporal context within 0.5–2 seconds. If the RAG fails or is slow, the system degrades gracefully — reflex alerts continue uninterrupted.

---

## 2. System Architecture Overview

### 2.1 Service Topology

The backend runs as four Docker containers on a single laptop, connected via a shared bridge network. The Jetson Nano is external to Docker and connects via ZeroMQ over the local network.

| Container | Role | Responsibilities |
|-----------|------|------------------|
| **ingest** | Front Door | ZeroMQ subscriber, temporal buffer, trend computation, WebSocket push to dashboard, async forwarding to RAG |
| **rag** | Intelligence Layer | Narrative embedding, Redis cache lookup, Actian protocol retrieval (on cache miss), session history retrieval, incident logging, recommendation synthesis |
| **redis** | Cache Layer | Layer 1: Semantic protocol cache (YOLO fire buckets → protocols). Layer 2: Session history cache (sorted sets with vectorized similarity). 128-state semantic quantization for 94-95% hit rate. |
| **actian** | Vector Database | Stores `safety_protocols` (static knowledge base) and `incident_log` (dynamic temporal memory). Persistent Docker volume. Queried only on cache misses. |

### 2.2 Data Flow

The complete journey of a single telemetry packet through the RAG backend:

1. Jetson publishes JSON packet via ZeroMQ PUB socket
2. Ingest container receives packet, buffers it per-device in a time-based sliding window (10 seconds), and computes the fire growth trend
3. Ingest pushes reflex data (`hazard_level`, `scores`, `trend`) to the dashboard via WebSocket **immediately**
4. Ingest forwards the enriched payload to the RAG container via async HTTP POST (fire-and-forget, non-blocking)
5. RAG embeds the `visual_narrative` using sentence-transformers (`all-MiniLM-L6-v2`, 384 dimensions)
6. **[Cache Layer]** RAG checks Redis semantic protocol cache using YOLO fire buckets (fire_dominance, smoke_opacity, proximity_alert, hazard_level)
   - **Cache HIT (94-95% of requests):** Retrieve protocols from Redis in ~2ms, skip step 7
   - **Cache MISS:** Query Actian for matching safety protocols via vector cosine similarity, filtered by severity (50-200ms), then cache result in Redis
7. **[Cache Layer]** RAG checks Redis session history cache for similar past incidents
   - **Cache HIT:** Retrieve incidents from Redis sorted set, compute vectorized similarity in-memory (~5-10ms)
   - **Cache MISS:** Query Actian for similar past incidents within the current session (temporal context) (30-50ms), then append to Redis cache
8. RAG writes the current incident to Actian's `incident_log` table AND Redis session history cache — this closes the feedback loop so this event becomes retrievable history for future queries
9. RAG synthesizes a recommendation and returns it to ingest, which pushes it to the dashboard as a secondary update

### 2.3 The Reflex-Cognition Split

Two data paths operate in parallel with different latency contracts:

| | Reflex Path | Cognition Path (RAG) |
|---|---|---|
| **Latency** | < 40ms edge + < 15ms network | 50-150ms (cache hit) / 500ms–2s (cache miss) |
| **Computed By** | Jetson Nano (edge) | Laptop backend containers |
| **Data** | `hazard_level`, `fire_dominance`, `smoke_opacity`, `proximity_alert` | Matched protocols, incident history, trend analysis, synthesized recommendation |
| **Cache Hit Rate** | N/A | 94-95% (semantic quantization) |
| **Failure Mode** | System is blind (camera failure) | System still sees, just lacks expert context. Reflex alerts continue. Redis failure degrades to Actian-only (slower but functional). |
| **Dashboard** | Primary hazard indicators, real-time scores | "Recommended Protocol" panel, populated 0.05–2s after reflex data (typically <200ms with cache) |

---

## 3. Data Model

### 3.1 Inbound Payload (Jetson → Ingest)

The Jetson publishes a JSON payload over ZeroMQ containing three logical layers: reflex data for instant dashboard display, tracked objects with persistent IDs for temporal reasoning, and a semantic narrative for vector embedding.

| Field | Type | Purpose |
|-------|------|---------|
| `device_id` | string | Routes data to correct per-device buffer on backend |
| `session_id` | string | Groups all events into one mission for temporal retrieval |
| `timestamp` | float | Unix epoch. Used for trend computation and buffer eviction |
| `hazard_level` | enum | `CLEAR \| LOW \| MODERATE \| HIGH \| CRITICAL`. Drives instant dashboard UI |
| `scores` | object | `fire_dominance` (0–1), `smoke_opacity` (0–1), `proximity_alert` (bool) |
| `tracked_objects` | array | Objects with persistent BoT-SORT IDs, status, duration, growth rate |
| `visual_narrative` | string | Semantic scene description (<200 chars). This is embedded as the RAG query vector |

#### 3.1.1 Visual Narrative Generation Pipeline

The `visual_narrative` is a natural language scene description generated on the **Jetson edge device** using a lightweight Python heuristic **before** the payload enters the ZeroMQ queue. This design decision keeps narrative generation fast (<10ms), reduces payload bandwidth, and ensures the RAG backend receives immediately embeddable context.

**Generation Flow:**
```
YOLO Detection → BoT-SORT Tracking → Spatial Heuristics → Narrative Template → visual_narrative (→ ZeroMQ → Ingest → Buffer)
```

**Stage 1: Object Detection & Tracking**
- YOLOv8 runs inference on each camera frame, producing bounding boxes with class labels (fire, smoke, person, exit, etc.)
- BoT-SORT tracker maintains persistent IDs across frames and computes per-object metadata:
  - `duration_in_frame`: How long the object has been visible (seconds)
  - `status`: `stationary | moving | growing | diminishing`
  - `growth_rate`: Change in bounding box area per second (for fire/smoke)

**Stage 2: Spatial Heuristics (Edge Computation)**

Three spatial heuristics run on the Jetson to extract semantic relationships from raw bounding boxes:

1. **Proximity Heuristic** — Measures distance between hazards (fire, smoke) and vulnerable objects (person, exit). Outputs `proximity_alert: true` if any hazard is within 15% of frame diagonal from a person or blocking an exit. Uses IoU (Intersection over Union) to detect direct contact.

2. **Dominance Heuristic** — Calculates what percentage of the visual field is covered by fire/smoke. Maps to severity levels:
   - < 10%: "spot fire"
   - 10–30%: "moderate fire"
   - 30–60%: "major fire"
   - > 60%: "flashover risk"

3. **Obstruction Heuristic** — Uses first-person perspective (FPV) center-lane logic. Checks if hazards occupy > 30% of the center corridor (30–70% of frame width). Outputs `path_obstructed: true` if the forward path is blocked.

**Stage 3: Template-Based Narrative Synthesis**

The Jetson uses a deterministic template system (not an LLM) to construct the narrative from heuristic outputs. This is a **rule-based heuristic**, not a neural model, to ensure sub-10ms latency and zero additional GPU overhead.

**Template Priority Hierarchy:**

| Priority | Condition | Template |
|----------|-----------|----------|
| 1 (CRITICAL) | `proximity_alert == true` AND `fire_dominance > 0.3` | `"CRITICAL: {hazard} in {proximity_desc} {victim}. Fire {fire_severity}, {obstruction_desc}."` |
| 2 (HIGH) | `path_obstructed == true` OR `fire_dominance > 0.6` | `"{fire_severity}. {obstruction_desc}."` |
| 3 (MODERATE) | `fire_dominance > 0.1` OR `proximity_alert == true` | `"{hazard} detected {proximity_desc} {victim}. {fire_severity}."` |
| 4 (LOW) | Any tracked objects present | `"{object_count} objects detected: {object_summary}."` |
| 5 (SAFE) | No detections | `"No hazards detected."` |

**Example Narrative Construction:**

Given this detection state:
```python
tracked_objects = [
    {"id": 42, "label": "person", "bbox": [100, 200, 150, 350], "status": "stationary", "duration": 15.0},
    {"id": 7, "label": "fire", "bbox": [120, 180, 200, 320], "status": "growing", "growth_rate": 0.1}
]
```

Spatial heuristics compute:
```python
proximity_alert = True  # Fire bbox overlaps with person (IoU > 0.1)
fire_dominance = 0.45   # Fire covers 45% of frame
path_obstructed = True  # Fire occupies 60% of center corridor
```

Template rendering produces:
```python
narrative = "CRITICAL: Fire in DIRECT CONTACT with person #42. Fire dominates 45% of view, blocking exit path."
```

**Implementation Notes:**
- The narrative generator runs in the same process as YOLO inference on the Jetson.
- Maximum latency: < 10ms (simple string formatting + heuristic computation).
- Character limit enforced: Narratives longer than 200 chars are truncated with "..." to fit embedding model token limits.
- Tracked object IDs are included when relevant for temporal reasoning (e.g., "Person #42" allows RAG to correlate incidents across frames).

**Why Edge Generation Instead of Server-Side?**

1. **Latency**: Template-based narrative generation takes < 10ms on Jetson. Sending raw detections to backend and generating narrative server-side would add 50–200ms of round-trip latency.
2. **Bandwidth**: Sending a 200-char narrative string (200 bytes) vs. sending full bounding box arrays for 10+ objects (1–2KB) reduces ZeroMQ payload size by 80%.
3. **Statelessness**: The backend RAG service receives a pre-formatted narrative ready for embedding. No need to maintain object tracking state server-side.
4. **Decoupling**: If the RAG backend crashes, the Jetson continues generating narratives for local logging or fallback protocols.

**Placement in Data Flow:**

The complete pipeline with narrative generation placement:

1. **Jetson Edge Device:**
   - YOLOv8 inference → Bounding boxes
   - BoT-SORT tracking → Tracked objects with persistent IDs
   - **Spatial heuristics → `visual_narrative` generation** ← **HAPPENS HERE**
   - ZeroMQ PUB → Send payload (with narrative) to ingest

2. **Ingest Container (Sliding Window Buffer):**
   - ZeroMQ SUB receives payload with pre-generated `visual_narrative`
   - Buffer payload in 10-second sliding window (time-based eviction)
   - Compute trend (fire growth rate over buffered history)
   - Push reflex data to dashboard via WebSocket
   - Forward enriched payload (with narrative) to RAG service via async HTTP POST

3. **RAG Container:**
   - Embed `visual_narrative` using sentence-transformers (MiniLM-L6)
   - Query Actian for matching safety protocols (vector similarity)
   - Query Actian for session history (temporal context)
   - Log current incident to `incident_log` (closes feedback loop)
   - Synthesize recommendation and return to ingest

The `visual_narrative` is created **before ZeroMQ transmission** and travels through the entire pipeline as immutable context, never re-generated.

**Example Payload:**
```json
{
  "device_id": "jetson_alpha_01",
  "session_id": "mission_2026_02_21",
  "timestamp": 1708549201.45,
  "hazard_level": "CRITICAL",
  "scores": {
    "fire_dominance": 0.45,
    "smoke_opacity": 0.80,
    "proximity_alert": true
  },
  "tracked_objects": [
    { "id": 42, "label": "person", "status": "stationary", "duration_in_frame": 15.0 },
    { "id": 7, "label": "fire", "status": "growing", "growth_rate": 0.1 }
  ],
  "visual_narrative": "CRITICAL: Person #42 stationary in corner. Fire #7 growing 10% over 5s, blocking exit."
}
```

### 3.2 Actian Vector DB Schema

#### 3.2.1 `safety_protocols` (Static Knowledge Base)

Pre-loaded before deployment with fire safety standards, NFPA protocols, and operational procedures. Each protocol is embedded as a 384-dimensional vector representing its scenario description. This table is read-only during missions.

| Column | Type | Description |
|--------|------|-------------|
| `scenario_vector` | VECTOR(384) | MiniLM-L6 embedding of the scenario this protocol addresses |
| `protocol_text` | TEXT | The actual safety instruction or procedure |
| `severity` | VARCHAR(10) | `LOW \| MEDIUM \| HIGH \| CRITICAL` |
| `category` | VARCHAR(50) | `fire \| structural \| hazmat \| medical` |
| `tags` | VARCHAR(200) | Searchable metadata: `trapped`, `exit_blocked`, `growing` |
| `source` | VARCHAR(100) | Reference standard: `NFPA_1001`, `OSHA_29CFR` |

#### 3.2.2 `incident_log` (Dynamic Temporal Memory)

Written in real-time during each session. Every processed packet generates one row. This table enables temporal reasoning — when the RAG queries "find similar past incidents," it searches against its own previous writes from 10, 30, or 60 seconds ago. This is the short-term memory of the system.

| Column | Type | Description |
|--------|------|-------------|
| `narrative_vector` | VECTOR(384) | Embedding of the enriched narrative |
| `raw_narrative` | TEXT | Human-readable narrative for debugging and display |
| `session_id` | VARCHAR(50) | Scopes history retrieval to current mission only |
| `trend_tag` | VARCHAR(20) | `RAPID_GROWTH \| GROWING \| STABLE \| DIMINISHING` |
| `hazard_level` | VARCHAR(10) | Mirrors the edge-computed hazard level |
| `fire_dominance` | FLOAT | Denormalized from scores for fast SQL filtering |
| `timestamp` | FLOAT | Unix epoch from the Jetson |

#### 3.2.3 SQL Schema

```sql
CREATE TABLE IF NOT EXISTS safety_protocols (
    id              INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scenario_vector VECTOR(384),
    protocol_text   TEXT NOT NULL,
    severity        VARCHAR(10),
    category        VARCHAR(50),
    tags            VARCHAR(200),
    source          VARCHAR(100),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS incident_log (
    id                INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    timestamp         FLOAT NOT NULL,
    session_id        VARCHAR(50) NOT NULL,
    device_id         VARCHAR(50) NOT NULL,
    narrative_vector  VECTOR(384),
    raw_narrative     TEXT,
    trend_tag         VARCHAR(20),
    hazard_level      VARCHAR(10),
    fire_dominance    FLOAT,
    smoke_opacity     FLOAT,
    proximity_alert   BOOLEAN,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_protocol_vector ON safety_protocols
    USING ivfflat (scenario_vector) WITH (lists = 50);

CREATE INDEX idx_incident_vector ON incident_log
    USING ivfflat (narrative_vector) WITH (lists = 100);

CREATE INDEX idx_incident_session ON incident_log (session_id, timestamp);

CREATE INDEX idx_protocol_severity ON safety_protocols (severity);
```

### 3.3 Retrieval Queries

The RAG service executes two vector similarity queries against Actian per incoming packet:

**Query 1 — Protocol Retrieval:** Finds the top 3 safety protocols whose `scenario_vector` is most similar to the current narrative embedding. Filtered to HIGH and CRITICAL severity. Returns the protocol text, source reference, and relevance score.

**Query 2 — Session History:** Finds the 5 most recent entries in `incident_log` for the current `session_id` where cosine similarity exceeds 0.70. This provides temporal context: what was happening 30 seconds ago that resembles what is happening now.

#### 3.3.1 Actian SQL Implementation

Actian Vector uses the `<->` operator for L2 distance (lower is more similar). To get cosine similarity, we compute `1 - (vector1 <-> vector2)` after normalizing vectors during embedding.

**Protocol Retrieval Query:**
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

**Session History Retrieval Query:**
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

**Notes:**
- Vectors MUST be normalized to unit length during embedding (using `sentence_transformers` automatic normalization) for L2 distance to approximate cosine similarity.
- The IVFFlat index accelerates the `<->` operator by avoiding full table scans.
- The session history query uses a two-stage approach: IVFFlat index returns top 20 candidates, then post-filters by similarity threshold and orders by recency.

---

## 3.4 Implementation Specifications

This section provides detailed algorithms, data structures, and message formats required to implement the RAG backend.

### 3.4.1 Temporal Buffer Implementation

The `TemporalBuffer` class maintains a sliding window of recent packets per device, evicts stale data, and computes fire growth trends.

**Data Structure:**

```python
from collections import deque
from typing import Dict, List, Optional
import time

class TemporalBuffer:
    """
    Time-based sliding window buffer for telemetry packets.

    Design:
    - One buffer instance per device_id
    - Stores packets in a deque (efficient FIFO operations)
    - Evicts packets older than window_seconds on every access
    - Packets are kept in chronological order (oldest first)
    """

    def __init__(self, device_id: str, window_seconds: float = 10.0):
        self.device_id = device_id
        self.window_seconds = window_seconds
        self.packets = deque()  # Stores raw packet dicts
        self.last_eviction_time = time.time()

    def add_packet(self, packet: dict) -> None:
        """
        Add a packet to the buffer and evict stale packets.

        Handles out-of-order packets by maintaining sorted order.
        If packet timestamp is older than buffer window, it's discarded.
        """
        packet_time = packet['timestamp']
        current_time = time.time()

        # Discard packets outside retention window
        if current_time - packet_time > self.window_seconds:
            return  # Packet is too old, don't buffer it

        # Evict stale packets first
        self._evict_stale_packets(current_time)

        # Insert packet in chronological order (handle out-of-order arrivals)
        # Most packets arrive in order, so append is O(1) in common case
        if not self.packets or packet_time >= self.packets[-1]['timestamp']:
            self.packets.append(packet)  # Common case: in-order arrival
        else:
            # Rare case: out-of-order packet (WiFi jitter)
            # Find insertion point using binary search
            import bisect
            insert_idx = bisect.bisect_left(
                [p['timestamp'] for p in self.packets],
                packet_time
            )
            self.packets.insert(insert_idx, packet)

    def _evict_stale_packets(self, current_time: float) -> None:
        """
        Remove packets older than window_seconds.
        Assumes packets are in chronological order.
        """
        cutoff_time = current_time - self.window_seconds

        # Remove from left (oldest packets) until we hit a recent one
        while self.packets and self.packets[0]['timestamp'] < cutoff_time:
            self.packets.popleft()

        self.last_eviction_time = current_time

    def get_packets(self) -> List[dict]:
        """
        Return all packets in the buffer (oldest to newest).
        Automatically evicts stale packets before returning.
        """
        self._evict_stale_packets(time.time())
        return list(self.packets)

    def get_trend(self) -> dict:
        """
        Compute fire growth trend from buffered packets.
        See section 3.4.2 for algorithm details.
        """
        self._evict_stale_packets(time.time())
        return compute_fire_trend(list(self.packets))


# Global buffer registry (one buffer per device)
_buffers: Dict[str, TemporalBuffer] = {}

def get_buffer(device_id: str, window_seconds: float = 10.0) -> TemporalBuffer:
    """Retrieve or create buffer for a device."""
    if device_id not in _buffers:
        _buffers[device_id] = TemporalBuffer(device_id, window_seconds)
    return _buffers[device_id]
```

**Key Design Decisions:**

1. **Time-based eviction** (not count-based): Ensures consistent temporal context. A 10-second window might contain 30 packets at 3 FPS or 100 packets at 10 FPS.

2. **Deque data structure**: O(1) append and popleft for common in-order case. Out-of-order packets trigger O(n) insertion, but WiFi jitter is rare.

3. **Per-device buffers**: Supports multi-device deployments. Each Jetson's data is buffered independently.

4. **Lazy eviction**: Eviction happens on access (add/get), not via background timer. Simpler and sufficient for this use case.

---

### 3.4.2 Trend Computation Algorithm

The `compute_fire_trend()` function analyzes the buffer to determine if fire is growing, stable, or diminishing.

**Algorithm:**

```python
from typing import List

def compute_fire_trend(packets: List[dict]) -> dict:
    """
    Compute fire growth trend from buffered packets.

    Returns:
        {
            'trend_tag': str,  # RAPID_GROWTH | GROWING | STABLE | DIMINISHING | UNKNOWN
            'growth_rate': float,  # Change in fire_dominance per second
            'sample_count': int,  # Number of packets analyzed
            'time_span': float  # Time range of buffer in seconds
        }
    """
    if len(packets) < 2:
        return {
            'trend_tag': 'UNKNOWN',
            'growth_rate': 0.0,
            'sample_count': len(packets),
            'time_span': 0.0
        }

    # Extract fire_dominance values and timestamps
    # Sort by timestamp (should already be sorted, but ensure)
    sorted_packets = sorted(packets, key=lambda p: p['timestamp'])

    timestamps = [p['timestamp'] for p in sorted_packets]
    fire_values = [p['scores']['fire_dominance'] for p in sorted_packets]

    # Compute time span
    time_span = timestamps[-1] - timestamps[0]

    if time_span < 0.5:  # Less than 500ms of data
        return {
            'trend_tag': 'UNKNOWN',
            'growth_rate': 0.0,
            'sample_count': len(packets),
            'time_span': time_span
        }

    # Use simple linear regression to compute trend
    # This is more robust than endpoint delta (reduces noise)
    growth_rate = _linear_regression_slope(timestamps, fire_values)

    # Classify trend based on growth rate thresholds
    # Thresholds are calibrated for fire_dominance range [0.0, 1.0]

    if growth_rate > 0.10:  # Increasing by >10% per second
        trend_tag = 'RAPID_GROWTH'
    elif growth_rate > 0.02:  # Increasing by >2% per second
        trend_tag = 'GROWING'
    elif growth_rate < -0.05:  # Decreasing by >5% per second
        trend_tag = 'DIMINISHING'
    else:  # [-0.05, 0.02] range
        trend_tag = 'STABLE'

    return {
        'trend_tag': trend_tag,
        'growth_rate': round(growth_rate, 4),
        'sample_count': len(packets),
        'time_span': round(time_span, 2)
    }


def _linear_regression_slope(x_values: List[float], y_values: List[float]) -> float:
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

**Threshold Justification:**

| Growth Rate (per second) | Trend Tag | Real-World Meaning |
|-------------------------|-----------|-------------------|
| > +0.10 | `RAPID_GROWTH` | Fire doubles in size in 10 seconds. Flashover imminent. |
| +0.02 to +0.10 | `GROWING` | Fire expanding steadily. Active combustion. |
| -0.05 to +0.02 | `STABLE` | Fire contained or steady-state burning. |
| < -0.05 | `DIMINISHING` | Fire being suppressed or fuel exhausted. |

**Why linear regression vs. simple delta?**
- Delta (latest - earliest) is sensitive to single noisy frames.
- Linear regression smooths over the entire window, providing more stable trends.
- Computational cost is negligible (~10 packets × 1 multiplication = 10 ops).

---

### 3.4.3 WebSocket Message Schemas

The ingest service pushes two types of messages to the dashboard via WebSocket.

**Message Type 1: Reflex Update** (sent immediately upon packet ingestion)

```json
{
  "type": "reflex_update",
  "device_id": "jetson_alpha_01",
  "timestamp": 1708549201.45,
  "hazard_level": "CRITICAL",
  "scores": {
    "fire_dominance": 0.45,
    "smoke_opacity": 0.80,
    "proximity_alert": true
  },
  "trend": {
    "trend_tag": "RAPID_GROWTH",
    "growth_rate": 0.12,
    "sample_count": 8,
    "time_span": 9.5
  }
}
```

**Message Type 2: RAG Recommendation** (sent 0.5–2s after reflex update)

```json
{
  "type": "rag_recommendation",
  "device_id": "jetson_alpha_01",
  "timestamp": 1708549201.45,
  "protocols": [
    {
      "protocol_text": "NFPA 1001: Immediate evacuation required when fire occupies >40% of visual field and victims are present. Establish defensive perimeter.",
      "source": "NFPA_1001",
      "severity": "CRITICAL",
      "similarity_score": 0.92
    },
    {
      "protocol_text": "OSHA 29CFR: Ensure all personnel have clear egress path. If path is obstructed by fire, initiate rescue protocol.",
      "source": "OSHA_29CFR",
      "severity": "HIGH",
      "similarity_score": 0.87
    }
  ],
  "session_history": [
    {
      "raw_narrative": "Fire growing near person #42. Path partially obstructed.",
      "trend_tag": "GROWING",
      "timestamp": 1708549195.30,
      "similarity_score": 0.85,
      "seconds_ago": 6.15
    },
    {
      "raw_narrative": "Smoke detected. Person #42 stationary.",
      "trend_tag": "STABLE",
      "timestamp": 1708549189.10,
      "similarity_score": 0.73,
      "seconds_ago": 12.35
    }
  ],
  "recommendation": "CRITICAL ALERT: Fire rapidly expanding (12% per second). Victim #42 in immediate danger. Protocol: Evacuate victim via secondary exit. Fire has blocked primary path. Trend analysis shows fire doubled in last 10 seconds—flashover risk HIGH.",
  "processing_time_ms": 680
}
```

**WebSocket Protocol Notes:**
- Messages are sent as JSON strings over WebSocket.
- Dashboard should handle `type` field to route to appropriate UI components.
- `reflex_update` messages arrive first (< 50ms latency).
- `rag_recommendation` messages arrive asynchronously (500–2000ms latency).
- Both message types share the same `device_id` and `timestamp` for correlation.

---

### 3.4.4 RAG Synthesis Template

The RAG service combines retrieved protocols, session history, and trend data into a natural language recommendation using a template-based approach (v1) or LLM synthesis (v2).

**Template-Based Synthesis (Phase 2 Deliverable):**

```python
def synthesize_recommendation_v1(
    protocols: List[dict],
    history: List[dict],
    trend: dict,
    payload: dict
) -> str:
    """
    Template-based synthesis for deterministic, low-latency recommendations.

    Template structure:
    1. Alert level + trend summary
    2. Top protocol instruction
    3. Historical context (if available)
    4. Actionable guidance
    """
    hazard_level = payload['hazard_level']
    trend_tag = trend['trend_tag']
    growth_rate = trend['growth_rate']

    # Section 1: Alert header
    if trend_tag == 'RAPID_GROWTH':
        header = f"{hazard_level} ALERT: Fire rapidly expanding ({growth_rate*100:.0f}% per second)."
    elif trend_tag == 'GROWING':
        header = f"{hazard_level}: Fire expanding steadily."
    elif trend_tag == 'DIMINISHING':
        header = f"{hazard_level}: Fire appears to be diminishing."
    else:
        header = f"{hazard_level}: Fire status stable."

    # Section 2: Top protocol (highest similarity)
    if protocols:
        top_protocol = protocols[0]
        protocol_text = f"Protocol: {top_protocol['protocol_text']}"
    else:
        protocol_text = "No matching safety protocols found."

    # Section 3: Historical context
    if len(history) >= 2:
        earliest = history[-1]  # Oldest event
        context = f"Situation escalated from '{earliest['trend_tag']}' {earliest['seconds_ago']:.0f}s ago."
    else:
        context = "Insufficient history for trend analysis."

    # Section 4: Combine
    recommendation = f"{header} {protocol_text} {context}"

    # Truncate to 500 chars for dashboard display
    if len(recommendation) > 500:
        recommendation = recommendation[:497] + "..."

    return recommendation
```

**Example Output:**

```
CRITICAL ALERT: Fire rapidly expanding (12% per second). Protocol: NFPA 1001: Immediate evacuation required when fire occupies >40% of visual field and victims are present. Establish defensive perimeter. Situation escalated from 'GROWING' 12s ago.
```

**LLM-Based Synthesis (Phase 4 Optional):**

For more natural language, swap the template for a local LLM (phi3:mini via Ollama):

```python
async def synthesize_recommendation_v2(protocols, history, trend, payload):
    """LLM synthesis using Ollama phi3:mini."""
    prompt = f"""You are a fire safety AI assistant. Synthesize a brief recommendation.

Situation: {payload['visual_narrative']}
Trend: {trend['trend_tag']} ({trend['growth_rate']*100:.1f}% per second)

Top Safety Protocol:
{protocols[0]['protocol_text'] if protocols else 'None available'}

Recent History:
{format_history(history)}

Provide a concise (2-3 sentence) recommendation for first responders."""

    response = await ollama_generate(prompt, max_tokens=100)
    return response
```

---

### 3.4.5 Batched Incident Log Writes

To reduce Actian write load under high packet rates, incident log inserts are batched and flushed periodically.

**Implementation:**

```python
import asyncio
from typing import List
from datetime import datetime

class IncidentBatchWriter:
    """
    Accumulates incident_log writes and flushes to Actian periodically.

    Design:
    - Time-based trigger: flushes every flush_interval_seconds
    - Background asyncio task runs flush loop
    - Thread-safe for concurrent add_incident() calls
    - Graceful shutdown: flushes remaining incidents on cleanup
    """

    def __init__(self, db_connection, flush_interval_seconds: float = 2.0):
        self.db = db_connection
        self.flush_interval = flush_interval_seconds
        self.buffer: List[dict] = []
        self.buffer_lock = asyncio.Lock()
        self.flush_task = None
        self.running = False

    async def start(self):
        """Start the background flush task."""
        self.running = True
        self.flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self):
        """Stop the background task and flush remaining incidents."""
        self.running = False
        if self.flush_task:
            await self.flush_task
        await self._flush()  # Final flush

    async def add_incident(self, incident: dict):
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
        try:
            await self._batch_insert(incidents)
            print(f"✓ Flushed {len(incidents)} incidents to Actian")
        except Exception as e:
            print(f"✗ Batch write failed: {e}")
            # Re-add incidents to buffer for retry (optional, may cause duplicates)
            # For safety-critical systems, log failure and continue

    async def _batch_insert(self, incidents: List[dict]):
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
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # Convert incidents to tuple rows
        rows = [
            (
                inc['timestamp'],
                inc['session_id'],
                inc['device_id'],
                inc['narrative_vector'],  # Already a VECTOR(384) type
                inc['raw_narrative'],
                inc['trend_tag'],
                inc['hazard_level'],
                inc['fire_dominance'],
                inc['smoke_opacity'],
                inc['proximity_alert']
            )
            for inc in incidents
        ]

        async with self.db.transaction():
            await self.db.executemany(query, rows)
```

**Usage in RAG Service:**

```python
# In RAG service startup (FastAPI lifespan)
batch_writer = IncidentBatchWriter(actian_db, flush_interval_seconds=2.0)
await batch_writer.start()

# In /retrieve endpoint
async def retrieve_endpoint(payload: dict):
    # ... embed narrative, retrieve protocols, etc ...

    # Add incident to batch (non-blocking)
    await batch_writer.add_incident({
        'timestamp': payload['timestamp'],
        'session_id': payload['session_id'],
        'device_id': payload['device_id'],
        'narrative_vector': embedding,
        'raw_narrative': payload['visual_narrative'],
        'trend_tag': trend['trend_tag'],
        'hazard_level': payload['hazard_level'],
        'fire_dominance': payload['scores']['fire_dominance'],
        'smoke_opacity': payload['scores']['smoke_opacity'],
        'proximity_alert': payload['scores']['proximity_alert']
    })

    # Return recommendation immediately (don't wait for flush)
    return recommendation

# In shutdown
await batch_writer.stop()
```

**Benefits:**
- **10x write reduction**: At 1 packet/sec, reduces from 1800 writes/30min to ~180 batched writes.
- **Lower Actian load**: Batch inserts are more efficient than individual INSERTs.
- **Non-blocking**: add_incident() returns immediately; flushing happens in background.

**Trade-offs:**
- **Delayed persistence**: Incidents are in-memory for up to 2 seconds before being written to Actian.
- **Risk of loss**: If RAG container crashes, up to 2 seconds of incidents are lost.
- **Mitigation**: Acceptable for non-critical incident logging. Reflex data is still transmitted immediately.

---

### 3.4.6 Redis-Based Semantic Cache (YOLO Fire Bucket Quantization)

**Design Philosophy:** Instead of caching exact narrative strings (low hit rate due to natural language variation), quantize fire scenarios into discrete buckets based on YOLO detection thresholds. This creates a finite state space (128 possible states) with 94-95% expected hit rate.

**Architecture:**

The cache operates as a two-layer system:

1. **Layer 1: Semantic Protocol Cache** — Maps fire severity buckets to retrieved protocols
2. **Layer 2: Session History Cache** — Stores temporal incident history with vectorized similarity search

**Implementation:**

Create `backend/agents/redis_cache.py`:

```python
"""
Simplified Redis cache for RAG pipeline using YOLO semantic buckets.

Architecture:
- Layer 1: Semantic Protocol Cache (fire/smoke buckets → protocols, 300s TTL)
- Layer 2: Session History Cache (sorted set with similarity, 1800s TTL)

128 possible cache states, 94-95% expected hit rate.
"""

import redis
import pickle
import time
import numpy as np
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class RAGCacheAgent:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=10,
            socket_keepalive=True,
            socket_connect_timeout=0.1,
            decode_responses=False
        )
        self.redis = redis.Redis(connection_pool=self.pool)

        self.metrics = {
            "semantic_hits": 0,
            "semantic_misses": 0,
            "session_hits": 0,
            "session_misses": 0,
            "semantic_latency_ms": [],
            "session_latency_ms": []
        }

        try:
            self.redis.ping()
            logger.info(f"Connected to Redis at {redis_url}")
        except redis.RedisError as e:
            logger.warning(f"Redis unavailable: {e}")

    # ==================================================================
    # LAYER 1: SEMANTIC PROTOCOL CACHE
    # ==================================================================

    def get_semantic_cache_key(self, packet) -> str:
        """
        Generate cache key from YOLO fire classification buckets.

        Aligns with spatial_heuristics.py fire severity levels:
        - MINOR: <10% coverage (extinguisher-level)
        - MODERATE: 10-30% (hose line required)
        - MAJOR: 30-60% (defensive operations)
        - CRITICAL: >60% (flashover risk, evacuate)

        Returns:
            String like "FIRE_MODERATE|SMOKE_DENSE|PROX_NEAR|HIGH"
        """
        fire_pct = packet.fire_dominance * 100
        fire_bucket = (
            "MINOR" if fire_pct < 10 else
            "MODERATE" if fire_pct < 30 else
            "MAJOR" if fire_pct < 60 else
            "CRITICAL"
        )

        smoke_pct = packet.smoke_opacity * 100
        smoke_bucket = (
            "CLEAR" if smoke_pct < 20 else
            "HAZY" if smoke_pct < 50 else
            "DENSE" if smoke_pct < 80 else
            "BLINDING"
        )

        prox = "NEAR" if packet.proximity_alert else "FAR"
        hazard = packet.hazard_level

        return f"FIRE_{fire_bucket}|SMOKE_{smoke_bucket}|PROX_{prox}|{hazard}"

    async def get_protocols_by_semantic_key(self, packet) -> Optional[List[Dict]]:
        """
        Retrieve cached protocols using YOLO fire buckets.

        Expected performance:
        - Hit rate: 94-95% (fire stays in same bucket 3-10 seconds)
        - Latency: 2ms on cache hit
        - Memory: 128 possible states × 1KB = 128KB total
        """
        start = time.perf_counter()

        try:
            cache_key = f"proto_semantic:{self.get_semantic_cache_key(packet)}"
            cached = self.redis.get(cache_key)

            latency_ms = (time.perf_counter() - start) * 1000
            self.metrics["semantic_latency_ms"].append(latency_ms)

            if cached:
                self.metrics["semantic_hits"] += 1
                logger.debug(f"[CACHE HIT] Protocols ({latency_ms:.2f}ms)")
                return pickle.loads(cached)
            else:
                self.metrics["semantic_misses"] += 1
                return None

        except redis.RedisError as e:
            logger.error(f"Redis error: {e}")
            self.metrics["semantic_misses"] += 1
            return None

    async def cache_protocols_by_semantic_key(
        self,
        packet,
        protocols: List[Dict],
        ttl: int = 300
    ):
        """
        Cache protocols under YOLO fire scenario bucket.

        Args:
            packet: TelemetryPacket with fire_dominance, smoke_opacity, etc.
            protocols: List of protocol dicts to cache
            ttl: Time-to-live in seconds (default: 300s = 5 min)
        """
        try:
            cache_key = f"proto_semantic:{self.get_semantic_cache_key(packet)}"
            serialized = pickle.dumps(protocols)
            self.redis.setex(cache_key, ttl, serialized)
            logger.debug(f"[CACHE WRITE] Protocols for {self.get_semantic_cache_key(packet)} (TTL: {ttl}s)")
        except redis.RedisError as e:
            logger.error(f"Failed to cache protocols: {e}")

    # ==================================================================
    # LAYER 2: SESSION HISTORY CACHE
    # ==================================================================

    async def append_session_history(
        self,
        session_id: str,
        device_id: str,
        narrative: str,
        vector: List[float],
        timestamp: float,
        trend: str,
        hazard_level: str
    ):
        """
        Append incident to Redis sorted set.

        Data Structure:
            Key: "session:{session_id}:{device_id}"
            Type: Sorted Set
            Score: timestamp (for chronological order)
            Member: pickle({narrative, vector, trend, hazard, timestamp})
        """
        try:
            cache_key = f"session:{session_id}:{device_id}"

            incident = {
                "narrative": narrative,
                "vector": vector,
                "timestamp": timestamp,
                "trend": trend,
                "hazard_level": hazard_level
            }

            serialized = pickle.dumps(incident)
            self.redis.zadd(cache_key, {serialized: timestamp})
            self.redis.expire(cache_key, 1800)

            logger.debug(f"[CACHE WRITE] Session history for {session_id}:{device_id}")

        except redis.RedisError as e:
            logger.error(f"Failed to append session history: {e}")

    async def get_session_history(
        self,
        session_id: str,
        device_id: str,
        current_vector: List[float],
        similarity_threshold: float = 0.70,
        max_results: int = 5
    ) -> List[Dict]:
        """
        Retrieve similar past incidents using in-memory cosine similarity.

        Performance:
        - Redis retrieval: ~2ms
        - Similarity computation: ~0.5ms per incident (NumPy vectorized)
        - Total: ~5-10ms for 10 incidents vs 30-50ms Actian query
        """
        start = time.perf_counter()

        try:
            cache_key = f"session:{session_id}:{device_id}"
            cached_incidents = self.redis.zrange(cache_key, 0, -1)

            latency_ms = (time.perf_counter() - start) * 1000
            self.metrics["session_latency_ms"].append(latency_ms)

            if not cached_incidents:
                self.metrics["session_misses"] += 1
                return []

            self.metrics["session_hits"] += 1

            # Deserialize
            incidents = [pickle.loads(inc) for inc in cached_incidents]

            # Vectorized similarity computation
            current_vec = np.array(current_vector)
            incident_vecs = np.array([inc["vector"] for inc in incidents])

            similarities = np.dot(incident_vecs, current_vec) / (
                np.linalg.norm(incident_vecs, axis=1) * np.linalg.norm(current_vec)
            )

            # Filter and format
            similar_incidents = []
            for inc, sim in zip(incidents, similarities):
                if sim >= similarity_threshold:
                    similar_incidents.append({
                        "narrative": inc["narrative"],
                        "timestamp": inc["timestamp"],
                        "trend": inc["trend"],
                        "hazard_level": inc["hazard_level"],
                        "similarity": float(sim),
                        "time_ago": time.time() - inc["timestamp"]
                    })

            similar_incidents.sort(key=lambda x: x["similarity"], reverse=True)

            logger.debug(
                f"[CACHE HIT] Session history: {len(similar_incidents)} similar "
                f"incidents ({latency_ms:.2f}ms)"
            )

            return similar_incidents[:max_results]

        except redis.RedisError as e:
            logger.error(f"Redis error in get_session_history: {e}")
            self.metrics["session_misses"] += 1
            return []
        except Exception as e:
            logger.error(f"Unexpected error in get_session_history: {e}")
            self.metrics["session_misses"] += 1
            return []

    # ==================================================================
    # METRICS & MONITORING
    # ==================================================================

    def get_cache_stats(self) -> Dict:
        """
        Get cache performance statistics.

        Returns:
            {
                "semantic_protocol_cache": {
                    "hits": X,
                    "misses": Y,
                    "hit_rate": Z,
                    "avg_latency_ms": W
                },
                "session_history_cache": {...}
            }
        """
        def calc_hit_rate(hits: int, misses: int) -> float:
            total = hits + misses
            return hits / total if total > 0 else 0.0

        def calc_avg_latency(latencies: List[float]) -> float:
            return sum(latencies) / len(latencies) if latencies else 0.0

        return {
            "semantic_protocol_cache": {
                "hits": self.metrics["semantic_hits"],
                "misses": self.metrics["semantic_misses"],
                "hit_rate": calc_hit_rate(
                    self.metrics["semantic_hits"],
                    self.metrics["semantic_misses"]
                ),
                "avg_latency_ms": calc_avg_latency(self.metrics["semantic_latency_ms"])
            },
            "session_history_cache": {
                "hits": self.metrics["session_hits"],
                "misses": self.metrics["session_misses"],
                "hit_rate": calc_hit_rate(
                    self.metrics["session_hits"],
                    self.metrics["session_misses"]
                ),
                "avg_latency_ms": calc_avg_latency(self.metrics["session_latency_ms"])
            }
        }

    async def health_check(self) -> bool:
        """Check if Redis connection is healthy."""
        try:
            self.redis.ping()
            return True
        except redis.RedisError:
            return False

    async def close(self):
        """Close Redis connection pool."""
        try:
            self.redis.close()
            self.pool.disconnect()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
```

**Semantic Quantization Buckets:**

| Dimension | Buckets | Thresholds | States |
|-----------|---------|-----------|--------|
| Fire Coverage | 4 (MINOR, MODERATE, MAJOR, CRITICAL) | <10%, 10-30%, 30-60%, >60% | 4 |
| Smoke Opacity | 4 (CLEAR, HAZY, DENSE, BLINDING) | <20%, 20-50%, 50-80%, >80% | 4 |
| Proximity | 2 (NEAR, FAR) | Boolean alert | 2 |
| Hazard Level | 4 (LOW, MODERATE, HIGH, CRITICAL) | Edge classification | 4 |

**Total State Space:** 4 × 4 × 2 × 4 = **128 possible cache keys**

**Performance Impact:**

| Metric | Actian Query | Redis Cache Hit | Improvement |
|--------|-------------|-----------------|-------------|
| Protocol retrieval | 50–200ms | ~2ms | **25–100x faster** |
| Session history | 30–50ms | ~5-10ms | **3–10x faster** |
| Memory footprint | N/A | ~128KB total | Minimal |
| Expected hit rate | N/A | 94-95% | High stability |

**Cache Hit Rate Analysis:**

Fire severity buckets change infrequently during typical incidents:
- **MINOR → MODERATE transition:** Fire grows from 8% → 12% coverage (takes 5-15 seconds at typical growth rates)
- **Bucket persistence:** Fire stays within same bucket for 3-10 seconds on average
- **At 1 FPS ingestion:** 3-10 consecutive packets hit cache before bucket transition
- **Expected hit rate:** 94-95% under realistic fire growth dynamics

---

## 4. Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Transport** | ZeroMQ (PUB/SUB) | Non-blocking, no broker required. Jetson never stalls waiting for backend acknowledgment. Auto-reconnects on WiFi drops. |
| **Ingest API** | FastAPI + asyncio | Async endpoints prevent Actian queries from blocking packet ingestion. WebSocket support built in. |
| **Embedding** | all-MiniLM-L6-v2 | 384-dim vectors, ~15ms on CPU. Good semantic quality for safety-domain text. Matches VECTOR(384) schema. |
| **Vector DB** | Actian Vector | Supports hybrid queries: vector cosine similarity + SQL metadata filters (severity, session_id, trend_tag). Persistent Docker volume. |
| **Cache Layer** | Redis | Two-layer cache: (1) Semantic protocol cache using YOLO fire buckets (128 states, 94-95% hit rate, 2ms latency), (2) Session history cache with in-memory similarity search (5-10ms vs 30-50ms Actian). Reduces cognition path latency by 10-25x on cache hits. |
| **Containerization** | Docker Compose | Four-service topology (ingest + rag + actian + redis). Shared bridge network for inter-container DNS. Named volumes for Actian and Redis persistence. |
| **Synthesis** | Template-based (v1) | Deterministic, ~0ms. Safety-critical systems need predictable outputs. Can swap for local LLM (phi3:mini) in v2. |

### 4.1 Explicit Exclusions

- **LangChain** — The RAG pipeline is a 3-step linear flow (embed → retrieve → synthesize). LangChain adds abstraction overhead without value for this use case.
- **External LLM APIs** — No network calls to OpenAI/Anthropic during inference. All processing is local for latency and reliability.
- **Kafka/RabbitMQ** — ZeroMQ handles single-unit message transport without requiring a broker process.

---

## 5. Implementation Phases

### Phase 1: Actian Schema & Protocol Seeding

**Goal:** Stand up the Actian container with the correct schema and seed it with safety protocols so the RAG has something to retrieve against.

1. Deploy Actian Vector via Docker with persistent volume and `init.sql` schema
2. Curate 30–50 safety protocols from NFPA 1001, OSHA standards, and operational SOPs
3. Write a seeding script that embeds each protocol scenario description with MiniLM-L6 and inserts into `safety_protocols`
4. Verify retrieval: embed a test narrative and confirm cosine similarity returns relevant protocols

**Deliverable:** Actian container running with indexed `safety_protocols` table, verified via manual query.

### Phase 2: RAG Service Core

**Goal:** Build the RAG container that accepts enriched payloads, embeds them, retrieves from Actian, logs incidents, and returns recommendations.

1. Implement the `/retrieve` FastAPI endpoint with the full pipeline: embed → retrieve protocols → retrieve history → log incident → synthesize
2. Bake the MiniLM-L6 model into the Docker image at build time to avoid runtime downloads
3. Implement template-based synthesis that formats the top protocol with trend context
4. Add a `/health` endpoint and `processing_time_ms` to every response for latency monitoring

**Deliverable:** RAG container accepting POST requests and returning recommendations with sub-2s latency.

### Phase 3: Ingest Service & Temporal Buffer

**Goal:** Build the ingest container that receives Jetson telemetry, buffers packets, computes trends, and coordinates the reflex and cognition paths.

1. Implement ZeroMQ SUB socket listener as a background asyncio task
2. Build the `TemporalBuffer` class with time-based eviction (not count-based) and fire growth rate computation
3. Implement the dual-push pattern: instant WebSocket push for reflex data, async HTTP POST to RAG for cognition
4. Add debug endpoints: `/buffer/{device_id}` to inspect buffer state, `/health` for service status

**Deliverable:** Full pipeline from simulated Jetson packets through to dashboard WebSocket output with RAG recommendations.

### Phase 4: Integration & Latency Hardening

**Goal:** Connect the live Jetson feed, verify end-to-end latency, and optimize the critical path.

1. Connect Jetson ZeroMQ PUB to ingest container SUB over local WiFi
2. Instrument every stage with timestamps: ZMQ receive, buffer compute, RAG POST, embed, Actian query, synthesis, WS push
3. Pre-compute embeddings for the 20 most common scenario types and cache Actian results for fast-path retrieval
4. Batch `incident_log` writes every 2 seconds instead of per-packet to reduce Actian write load
5. Load test with synthetic packets at 10 FPS to verify buffer and RAG handle sustained throughput

**Deliverable:** End-to-end system with measured latency breakdown and optimized hot paths.

---

## 6. Latency Analysis & Concerns

### 6.1 Latency Budget Breakdown

| Stage | Expected | Risk Factors |
|-------|----------|--------------|
| ZeroMQ receive (ingest) | 2–5ms | WiFi jitter can spike to 50–100ms. Mitigate with wired Ethernet for demos. |
| Buffer + trend compute | < 5ms | Negligible. Pure in-memory computation. |
| HTTP POST to RAG | 1–2ms | Container-to-container over Docker bridge. Minimal. |
| Embedding (MiniLM-L6) | 15–30ms | CPU-bound. First call may be slow due to model warmup. Subsequent calls are fast. |
| Actian: protocol retrieval | 50–200ms | Depends on index size and vector dimension. IVFFlat index with 50 lists keeps this fast. |
| Actian: session history | 50–200ms | Grows with session length. Index on `session_id + timestamp` essential. |
| Actian: incident write | 5–15ms | Single row insert. Batch to every 2s under high load. |
| Synthesis (template) | < 1ms | String formatting. Negligible. |
| WebSocket push | < 1ms | In-memory broadcast to connected clients. |

**Total reflex path:** < 50ms (edge compute + ZMQ transport + WS push)

**Total RAG path:** 120–450ms typical, up to 2s worst case

### 6.2 Key Latency Risks

**Risk 1: WiFi Jitter.** ZeroMQ over WiFi introduces non-deterministic latency. In controlled environments this is 2–5ms but can spike to 50–100ms on congested networks. For hackathon demos, use a wired Ethernet connection or a dedicated WiFi access point to eliminate this variable.

**Risk 2: Actian Cold Start.** The first vector similarity query after container startup may be slow as Actian loads indexes into memory. Mitigate by issuing a warmup query during the lifespan startup of the RAG service before accepting real traffic.

**Risk 3: Incident Log Growth.** At 1 packet/second over a 30-minute session, the `incident_log` accumulates approximately 1,800 rows. The session history query scans these rows with a vector similarity threshold. Without the composite index on `(session_id, timestamp)`, this query degrades as sessions lengthen. The IVFFlat index on `narrative_vector` with 100 lists keeps similarity search sublinear.

**Risk 4: Embedding Model Warmup.** The first call to sentence-transformers after process start takes 200–500ms as the model loads into CPU memory. Pre-warm during container startup by embedding a dummy string in the lifespan handler.

### 6.3 Latency Optimization Strategies

- **Pre-computed scenario cache:** Embed and cache Actian results for the 20 most common scenario descriptions. At runtime, compute cosine similarity against this cache before hitting Actian. Cache hit serves in < 5ms.
- **Batched incident writes:** Accumulate `incident_log` inserts in a buffer and flush every 2 seconds. Reduces Actian write operations by up to 10x under high packet rates.
- **Parallel Actian queries:** Execute protocol retrieval and session history queries concurrently using `asyncio.gather()` instead of sequentially. Cuts retrieval time nearly in half.
- **Optimistic dashboard updates:** Push reflex data to the dashboard the instant it arrives. The RAG recommendation populates a secondary panel 0.5–2s later with a loading animation. Users perceive the system as working, not waiting.

---

## 7. Validation Tests

Each test validates a specific layer of the RAG pipeline in isolation before full integration. All tests can be run against the Dockerized services without a live Jetson feed.

### Test 1: Embedding Sanity Check

**Validates:** The embedding model produces meaningful vectors that capture semantic similarity.

**Method:** Embed three narratives: (A) "Person trapped, fire growing, exit blocked," (B) "Person trapped, fire diminishing, exit clear," and (C) "Empty room, no hazards detected." Compute pairwise cosine similarity.

**Pass Criteria:** `sim(A, B) > sim(A, C)`. Narratives A and B share structural similarity (trapped person) and should score higher than A vs C. If `sim(A, C) > sim(A, B)`, the embedding model is not capturing safety-relevant semantics and should be fine-tuned or replaced.

```python
from sentence_transformers import SentenceTransformer, util
model = SentenceTransformer('all-MiniLM-L6-v2')

a = model.encode('Person trapped, fire growing, exit blocked')
b = model.encode('Person trapped, fire diminishing, exit clear')
c = model.encode('Empty room, no hazards detected')

assert util.cos_sim(a, b) > util.cos_sim(a, c)  # Must pass
```

### Test 2: Protocol Retrieval Precision

**Validates:** Actian returns the correct safety protocol for a given scenario.

**Method:** Seed Actian with 10 known protocols covering distinct scenarios (trapped person + growing fire, clear exit + diminishing fire, smoke inhalation risk, structural collapse). For each seeded protocol, craft a narrative that should match it. Query Actian and check if the correct protocol appears in the top 3 results.

**Pass Criteria:** Precision@3 ≥ 0.8 across all 10 test narratives. If a protocol consistently ranks below position 3, its `scenario_vector` may need to be re-embedded with a more descriptive scenario string.

### Test 3: Temporal Buffer Trend Accuracy

**Validates:** The `TemporalBuffer` correctly detects fire growth trends from a sequence of packets.

**Method:** Feed 10 synthetic packets into the buffer with timestamps 1 second apart. In test case A, increase `fire_dominance` linearly from 0.1 to 0.6 (should produce `RAPID_GROWTH`). In test case B, hold `fire_dominance` at 0.3 (should produce `STABLE`). In test case C, decrease from 0.5 to 0.2 (should produce `DIMINISHING`).

**Pass Criteria:** Computed trend tag matches expected value for all three test cases. Growth rate calculation falls within ±0.01 of the expected value.

### Test 4: Incident Log Temporal Retrieval

**Validates:** The RAG can retrieve its own recently-written incidents, proving the temporal feedback loop works.

**Method:** Send 5 sequential packets to the `/retrieve` endpoint with `session_id = "test_session"` and progressively escalating narratives (clear → smoke detected → fire growing → person spotted → person trapped). On the 5th call, verify that the session history response includes entries from packets 1–4 with similarity > 0.70.

**Pass Criteria:** The 5th retrieval response contains at least 2 history entries from the same session. The most recent history entry has a higher similarity score than the oldest, confirming temporal proximity correlates with semantic relevance.

### Test 5: End-to-End Latency Benchmark

**Validates:** The full RAG pipeline meets the 2-second latency target.

**Method:** Send 100 synthetic packets to the ingest container via ZeroMQ at 1 packet/second. Record the `processing_time_ms` field from each RAG response. Compute p50, p95, and p99 latency.

**Pass Criteria:** p50 < 500ms, p95 < 1500ms, p99 < 2000ms. If p95 exceeds 1500ms, investigate Actian query plans and consider enabling the pre-computed scenario cache.

```python
import zmq, json, time

ctx = zmq.Context()
sock = ctx.socket(zmq.PUB)
sock.connect('tcp://localhost:5555')
time.sleep(1)  # Allow ZMQ connection to establish

for i in range(100):
    packet = build_test_packet(fire_dominance=0.1 + i * 0.005)
    sock.send_string(json.dumps(packet))
    time.sleep(1)
```

### Test 6: Graceful Degradation

**Validates:** The reflex path continues working when the RAG service is unavailable.

**Method:** Stop the RAG container (`docker compose stop rag`). Send packets to ingest via ZeroMQ. Connect a WebSocket client to the dashboard endpoint.

**Pass Criteria:** The dashboard WebSocket continues to receive `reflex_update` messages with `hazard_level` and `scores`. No `rag_recommendation` messages arrive (expected). The ingest service logs a non-fatal error for each failed RAG call but does not crash or stop processing packets.

### Test 7: Delta Filter Validation

**Validates:** The system correctly handles hazard level transitions that fall below the 5% delta threshold.

**Method:** Send two packets: first with `fire_dominance = 0.44`, second with `fire_dominance = 0.46` (a 4.5% change, below the 5% delta threshold, but potentially a critical safety transition). The second packet should still be transmitted because the `hazard_level` may have changed from HIGH to CRITICAL.

**Pass Criteria:** The delta filter on the Jetson side correctly prioritizes `hazard_level` transitions and `proximity_alert = true` over the raw percentage change in `fire_dominance`. Both packets are received by the ingest service.

---

## 8. Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Actian container crashes mid-session | **HIGH** | Persistent volume preserves data. Ingest catches RAG errors and continues reflex path. Auto-restart via Docker restart policy. |
| Embedding model produces poor similarity | **MEDIUM** | Validated by Test 1 and Test 2. If precision drops, fine-tune MiniLM on fire safety corpus or switch to a domain-specific model. |
| Incident log grows unbounded | **MEDIUM** | Partition by `session_id`. Add TTL-based cleanup that drops `incident_log` rows older than 24 hours. Batch writes reduce insert rate. |
| WiFi drops between Jetson and laptop | **MEDIUM** | ZeroMQ auto-reconnects. Dashboard shows last-known-good state with a staleness indicator. Use Ethernet for critical deployments. |
| Template synthesis produces unhelpful recommendations | **LOW** | Phase 4 optimization: swap template for local LLM (phi3:mini via Ollama) that synthesizes natural language from retrieved context. |
| Narrative embedding does not capture domain nuance | **LOW** | MiniLM is a general-purpose model. If safety-specific semantics are weak, fine-tune on a fire safety text corpus or enrich narratives with more descriptive templates. |

---

## 9. Success Criteria

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| RAG p95 latency | < 1500ms | `processing_time_ms` from `/retrieve` |
| Protocol retrieval precision@3 | ≥ 80% | Test 2 across 10+ scenarios |
| Temporal retrieval accuracy | Returns ≥ 2 history entries by packet 5 | Test 4 sequential escalation |
| Trend computation accuracy | 100% correct across 3 trend types | Test 3 synthetic sequences |
| Graceful degradation | Reflex path unaffected by RAG failure | Test 6 with RAG container stopped |
| Sustained throughput | 10 FPS for 30 minutes without crash | Load test with synthetic packets |

---

## 10. Future Considerations

- **Local LLM synthesis:** Replace template-based synthesis with phi3:mini or llama3 via Ollama for natural language recommendations. Adds a 4th container to Docker Compose.
- **Multi-responder scaling:** Replace ZeroMQ with NATS for message routing across multiple Jetson units. Add per-device buffer dictionaries and cross-session Actian queries for shared situational awareness.
- **Domain-specific embeddings:** Fine-tune MiniLM on a fire safety text corpus (NFPA documents, incident reports) to improve retrieval precision for safety-specific terminology.
- **Streaming RAG response:** If switching to LLM synthesis, stream tokens to the dashboard. First token appearing in 200ms feels faster than a complete response at 1.5s.