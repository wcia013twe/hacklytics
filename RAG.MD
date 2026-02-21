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

The backend runs as three Docker containers on a single laptop, connected via a shared bridge network. The Jetson Nano is external to Docker and connects via ZeroMQ over the local network.

| Container | Role | Responsibilities |
|-----------|------|------------------|
| **ingest** | Front Door | ZeroMQ subscriber, temporal buffer, trend computation, WebSocket push to dashboard, async forwarding to RAG |
| **rag** | Intelligence Layer | Narrative embedding, Actian protocol retrieval, session history retrieval, incident logging, recommendation synthesis |
| **actian** | Vector Database | Stores `safety_protocols` (static knowledge base) and `incident_log` (dynamic temporal memory). Persistent Docker volume. |

### 2.2 Data Flow

The complete journey of a single telemetry packet through the RAG backend:

1. Jetson publishes JSON packet via ZeroMQ PUB socket
2. Ingest container receives packet, buffers it per-device in a time-based sliding window (10 seconds), and computes the fire growth trend
3. Ingest pushes reflex data (`hazard_level`, `scores`, `trend`) to the dashboard via WebSocket **immediately**
4. Ingest forwards the enriched payload to the RAG container via async HTTP POST (fire-and-forget, non-blocking)
5. RAG embeds the `visual_narrative` using sentence-transformers (`all-MiniLM-L6-v2`, 384 dimensions)
6. RAG queries Actian for matching safety protocols via vector cosine similarity, filtered by severity
7. RAG queries Actian for similar past incidents within the current session (temporal context)
8. RAG writes the current incident to Actian's `incident_log` table — this closes the feedback loop so this event becomes retrievable history for future queries
9. RAG synthesizes a recommendation and returns it to ingest, which pushes it to the dashboard as a secondary update

### 2.3 The Reflex-Cognition Split

Two data paths operate in parallel with different latency contracts:

| | Reflex Path | Cognition Path (RAG) |
|---|---|---|
| **Latency** | < 40ms edge + < 15ms network | 500ms – 2 seconds |
| **Computed By** | Jetson Nano (edge) | Laptop backend containers |
| **Data** | `hazard_level`, `fire_dominance`, `smoke_opacity`, `proximity_alert` | Matched protocols, incident history, trend analysis, synthesized recommendation |
| **Failure Mode** | System is blind (camera failure) | System still sees, just lacks expert context. Reflex alerts continue. |
| **Dashboard** | Primary hazard indicators, real-time scores | "Recommended Protocol" panel, populated 0.5–2s after reflex data |

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

Example payload:

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

---

## 4. Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Transport** | ZeroMQ (PUB/SUB) | Non-blocking, no broker required. Jetson never stalls waiting for backend acknowledgment. Auto-reconnects on WiFi drops. |
| **Ingest API** | FastAPI + asyncio | Async endpoints prevent Actian queries from blocking packet ingestion. WebSocket support built in. |
| **Embedding** | all-MiniLM-L6-v2 | 384-dim vectors, ~15ms on CPU. Good semantic quality for safety-domain text. Matches VECTOR(384) schema. |
| **Vector DB** | Actian Vector | Supports hybrid queries: vector cosine similarity + SQL metadata filters (severity, session_id, trend_tag). Persistent Docker volume. |
| **Containerization** | Docker Compose | Three-service topology. Shared bridge network for inter-container DNS. Named volume for Actian persistence. |
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