# Temporal LLM + Redis Caching Implementation Plan

**Author:** Planning Session
**Date:** February 21, 2026
**Status:** Planning Phase
**Estimated Effort:** 8-11 hours

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Files to Create/Modify](#files-to-createmodify)
4. [Implementation Phases](#implementation-phases)
5. [Low-Latency Optimizations](#low-latency-optimizations)
6. [Test Strategy](#test-strategy)
7. [Success Criteria](#success-criteria)
8. [Risk Mitigation](#risk-mitigation)

---

## Executive Summary

### Problem Statement

Current architecture sends single-frame narratives to the RAG pipeline, losing critical temporal context:
- ❌ "Fire at 45%" vs. ✅ "Fire grew from 8% to 45% in 3 seconds"
- No understanding of fire progression, escalation patterns, or temporal relationships
- Each vector search happens independently, no caching of repeated scenarios

### Proposed Solution

Implement a two-part enhancement:

1. **Temporal LLM Agent:** Use Gemini Flash to synthesize 3-5 seconds of frame narratives into coherent temporal stories
2. **Redis Caching:** 3-layer cache (embeddings, protocols, session history) to reduce latency by 30-50%

### Expected Impact

| Metric | Current | With Implementation | Improvement |
|--------|---------|-------------------|-------------|
| **Narrative Quality** | Single frame snapshot | Rich temporal context | 5x semantic depth |
| **Protocol Matching** | Generic scenarios | Specific fire patterns | 3x relevance |
| **RAG Latency (warm)** | 200-500ms | 120-300ms | 30-40% faster |
| **RAG Latency (hot)** | 200-500ms | 80-180ms | 50-60% faster |
| **Vector Quality** | ⭐⭐ Shallow | ⭐⭐⭐⭐⭐ Deep | Matches flashover patterns |

---

## Architecture Overview

### Current Flow (Single-Frame Narratives)

```
Jetson → ZeroMQ → Temporal Buffer → [Latest Narrative] → Embed → Search → Protocols
                                      "Fire 45%"
```

### Enhanced Flow (Temporal LLM + Caching)

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: Edge (Jetson) - UNCHANGED                             │
├─────────────────────────────────────────────────────────────────┤
│ YOLO → Spatial Heuristics → Template Narrative                  │
│ Output: "Major fire 45% coverage. Path blocked."                │
└─────────────────────────────────────────────────────────────────┘
                            ↓ ZeroMQ
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: Temporal Buffer (Backend) - ENHANCED                  │
├─────────────────────────────────────────────────────────────────┤
│ 1. Receive frame narrative                                      │
│ 2. Buffer last 3-5 seconds (priority queue)                     │
│ 3. ✨ GEMINI FLASH SYNTHESIS (100-150ms) ✨                    │
│    Input: [T-3s: "8%", T-2s: "22%", T-1s: "38%", T-0s: "45%"] │
│    Output: "Fire escalated 8%→45% in 3s. Path now blocked.     │
│             Person trapped. Flashover acceleration pattern."    │
│                                                                  │
│ 4. ✨ CHECK REDIS CACHE ✨                                     │
│    - Embedding cache hit? Skip sentence-transformers (15ms)    │
│    - Protocol cache hit? Skip Actian search (50-100ms)         │
│                                                                  │
│ 5. Embed synthesized narrative → 384-dim vector                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: RAG (Enhanced with Caching)                           │
├─────────────────────────────────────────────────────────────────┤
│ - Vector search → Protocol retrieval → Recommendation          │
│ - Write-through cache: Store results in Redis                  │
│ - Session history from Redis (not Actian)                      │
└─────────────────────────────────────────────────────────────────┘
```

### Redis Caching Strategy - 3 Layers

```
┌──────────────────────────────────────────────────────────┐
│ Layer 1: Narrative → Vector Cache (Embedding Cache)     │
├──────────────────────────────────────────────────────────┤
│ Key: SHA256(narrative_text)[:16]                        │
│ Value: pickle([384-dim vector])                         │
│ TTL: 60 seconds                                         │
│ Hit Rate: ~30-50% (scenes repeat frequently)            │
│ Savings: Skip 15ms sentence-transformer inference       │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│ Layer 2: Vector → Protocols Cache (RAG Result Cache)    │
├──────────────────────────────────────────────────────────┤
│ Key: SHA256(quantized_vector + severity_filter)         │
│ Value: JSON([Protocol, Protocol, Protocol])             │
│ TTL: 300 seconds (5 min)                                │
│ Hit Rate: ~60-80% (similar situations → same protocols) │
│ Savings: Skip 50-100ms Actian vector search             │
│ Optimization: Vector quantization for fuzzy matching    │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│ Layer 3: Session History Cache (Temporal Context)       │
├──────────────────────────────────────────────────────────┤
│ Key: session:{session_id}:{device_id}                   │
│ Value: Sorted Set (score=timestamp, pickle(incident))   │
│ TTL: 1800 seconds (30 min)                              │
│ Hit Rate: ~90% (read-heavy during active session)       │
│ Savings: Skip session history DB query (30-50ms)        │
│ Optimization: Cosine similarity in-memory               │
└──────────────────────────────────────────────────────────┘
```

---

## Files to Create/Modify

### NEW FILES (4)

#### 1. `backend/agents/temporal_narrative.py` (~400 lines)

**Purpose:** Synthesize temporal narratives from buffered frame observations using Gemini Flash

**Class:** `TemporalNarrativeAgent`

**Key Methods:**
```python
async def synthesize_temporal_narrative(
    self,
    buffer_packets: List[Dict],
    lookback_seconds: float = 3.0
) -> TemporalSynthesisResult:
    """
    Synthesize coherent temporal narrative from recent buffer events.

    Algorithm:
    1. Filter packets to lookback window (3s default)
    2. Build timeline prompt with T-Xs annotations
    3. Call Gemini Flash with strict 200-char limit
    4. Validate output quality
    5. Fallback to concatenation on API failure

    Returns:
        TemporalSynthesisResult with synthesized narrative, timing, cache status
    """
```

**Methods:**
- `__init__(api_key, model_name, max_tokens, temperature)`
- `synthesize_temporal_narrative()` - Main synthesis
- `_build_timeline_prompt()` - Format buffer into timeline
- `_call_gemini_api()` - Async API call with retry
- `_validate_synthesis()` - Quality checks
- `_fallback_concatenation()` - Safe fallback
- `get_metrics()` - Performance stats

**Key Features:**
- Async Gemini API integration
- Exponential backoff retry (3 attempts)
- 200-char output enforcement
- <150ms latency target
- Fallback to simple concatenation on failure
- Detailed logging and metrics

**Error Handling:**
```python
try:
    response = await self.model.generate_content_async(prompt)
except asyncio.TimeoutError:
    logger.warning("Gemini timeout, using fallback")
    return self._fallback_concatenation(packets)
except Exception as e:
    logger.error(f"Gemini error: {e}")
    return self._fallback_concatenation(packets)
```

---

#### 2. `backend/agents/redis_cache.py` (~500 lines)

**Purpose:** Multi-layer Redis caching for RAG pipeline optimization

**Class:** `RAGCacheAgent`

**Layer 1: Embedding Cache**
```python
async def get_cached_embedding(self, narrative: str) -> Optional[List[float]]:
    """Retrieve cached 384-dim vector for narrative."""

async def cache_embedding(self, narrative: str, vector: List[float], ttl: int = 60):
    """Cache embedding with 60s TTL."""
```

**Layer 2: Protocol Cache**
```python
async def get_cached_protocols(
    self,
    vector: List[float],
    severity_filter: List[str]
) -> Optional[List[Dict]]:
    """
    Retrieve cached protocol results.
    Uses vector quantization for fuzzy matching.
    """

async def cache_protocols(
    self,
    vector: List[float],
    severity_filter: List[str],
    protocols: List[Dict],
    ttl: int = 300
):
    """Cache protocols with 5-min TTL."""
```

**Layer 3: Session History Cache**
```python
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
    Write-through: also write to Actian for persistence.
    """

async def get_session_history(
    self,
    session_id: str,
    device_id: str,
    current_vector: List[float],
    similarity_threshold: float = 0.70,
    max_results: int = 5
) -> List[Dict]:
    """
    Retrieve similar incidents from Redis cache.
    Computes cosine similarity in-memory.
    """
```

**Metrics:**
```python
def get_cache_stats(self) -> Dict:
    """
    Returns:
        {
            "embedding_cache": {"hits": X, "misses": Y, "hit_rate": Z},
            "protocol_cache": {"hits": X, "misses": Y, "hit_rate": Z},
            "session_cache": {"hits": X, "misses": Y, "hit_rate": Z}
        }
    """
```

**Optimization: Vector Quantization**
```python
def _hash_vector_query(self, vector: List[float], severity_filter: List[str]) -> str:
    """
    Quantize vector to 2 decimals for fuzzy matching.
    Similar vectors → same cache key → higher hit rate.
    """
    quantized = [round(v, 2) for v in vector[:50]]  # Use first 50 dims
    query_repr = f"{quantized}:{sorted(severity_filter)}"
    return hashlib.sha256(query_repr.encode()).hexdigest()[:16]
```

---

#### 3. `tests/agents/test_temporal_narrative.py` (~350 lines)

**Test Coverage:**

**Happy Path:**
- ✅ Single narrative (no synthesis needed)
- ✅ 2-5 narratives (temporal synthesis triggered)
- ✅ Valid Gemini response
- ✅ 200-char limit enforced

**Fire Scenarios:**
- ✅ Fire escalation (8% → 45% in 3s)
- ✅ Fire suppression (68% → 12% over 5s)
- ✅ Flashover pattern detection
- ✅ Person trapped scenario

**Error Handling:**
- ✅ Gemini API timeout → fallback
- ✅ Gemini API error → fallback
- ✅ Invalid response → fallback
- ✅ Empty buffer → safe return
- ✅ Malformed packets → skip

**Performance:**
- ✅ Latency <150ms (95th percentile)
- ✅ Fallback <5ms
- ✅ Metrics accuracy

**Fixtures:**
```python
@pytest.fixture
def escalation_sequence():
    """5 packets showing fire growth from 8% to 45%."""
    return [
        {"timestamp": t-3, "narrative": "Small fire 8%", "priority": "CAUTION"},
        {"timestamp": t-2, "narrative": "Moderate fire 22%", "priority": "CAUTION"},
        {"timestamp": t-1, "narrative": "Major fire 38%", "priority": "HIGH"},
        {"timestamp": t-0, "narrative": "Major fire 45%. Blocked.", "priority": "CRITICAL"},
    ]

@pytest.fixture
def mock_gemini_client(monkeypatch):
    """Mock Gemini API to avoid real API calls in tests."""
    async def mock_generate(prompt):
        return MockResponse("Fire escalated from 8% to 45% in 3s...")
    monkeypatch.setattr(genai.GenerativeModel, 'generate_content_async', mock_generate)
```

---

#### 4. `tests/agents/test_redis_cache.py` (~450 lines)

**Test Coverage:**

**Layer 1 - Embedding Cache:**
- ✅ Cache miss → compute → store
- ✅ Cache hit → retrieve → skip computation
- ✅ TTL expiration test
- ✅ Different narratives → different keys
- ✅ Same narrative → same key
- ✅ Hit rate tracking accuracy

**Layer 2 - Protocol Cache:**
- ✅ Vector quantization (fuzzy matching)
- ✅ Same quantized vector → cache hit
- ✅ Different severity filters → cache miss
- ✅ Protocol serialization/deserialization
- ✅ 5-min TTL test

**Layer 3 - Session History:**
- ✅ Append to sorted set
- ✅ Timestamp ordering
- ✅ Similarity search (cosine)
- ✅ Threshold filtering (>0.70)
- ✅ 30-min retention window
- ✅ Stale eviction

**Integration Tests:**
- ✅ Multi-layer cache hit scenario
- ✅ Partial cache hit (some layers hit, some miss)
- ✅ Cold cache scenario (all misses)
- ✅ Redis connection failure → graceful degradation
- ✅ Cache stats accuracy

**Fixtures:**
```python
@pytest.fixture
async def redis_client():
    """Real Redis client for integration tests."""
    client = redis.from_url("redis://localhost:6379", decode_responses=False)
    yield client
    await client.flushdb()  # Clean up after tests

@pytest.fixture
def sample_vector():
    """384-dim vector for testing."""
    return [round(random.random(), 3) for _ in range(384)]
```

---

### MODIFIED FILES (6)

#### 5. `backend/contracts/models.py` (+80 lines)

**New Models:**

```python
class TemporalSynthesisResult(BaseModel):
    """Result from temporal narrative synthesis."""
    synthesized_narrative: str = Field(..., max_length=200, description="LLM-generated temporal story")
    original_narratives: List[str] = Field(..., description="Individual frame narratives")
    time_span: float = Field(..., ge=0.0, description="Time range in seconds")
    synthesis_time_ms: float = Field(..., ge=0.0, description="Gemini API latency")
    event_count: int = Field(..., ge=0, description="Number of events synthesized")
    cache_hit: bool = Field(default=False, description="Was synthesis cached?")
    fallback_used: bool = Field(default=False, description="Did we fallback to concatenation?")

class CacheMetrics(BaseModel):
    """Cache performance metrics."""
    layer: str = Field(..., description="embedding|protocol|session")
    hits: int = Field(default=0, ge=0)
    misses: int = Field(default=0, ge=0)
    hit_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_latency_ms: float = Field(default=0.0, ge=0.0)
```

---

#### 6. `backend/orchestrator.py` (+150 lines)

**New Agent Initialization:**
```python
def __init__(self, actian_pool=None, redis_url: str = "redis://localhost:6379"):
    # Existing agents...

    # NEW: Temporal narrative synthesis
    self.temporal_narrative_agent = TemporalNarrativeAgent(
        api_key=os.getenv("GEMINI_API_KEY"),
        model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-flash-002")
    )

    # NEW: Redis caching
    self.cache_agent = RAGCacheAgent(redis_url=redis_url)
```

**Modified `stage_3_cognition()` Method:**
```python
async def stage_3_cognition(self, packet: TelemetryPacket, trend: TrendResult):
    """
    Enhanced with temporal LLM synthesis and multi-layer caching.

    Flow:
    1. Synthesize temporal narrative from buffer (Gemini Flash)
    2. Check embedding cache (Redis Layer 1)
    3. Embed if cache miss (sentence-transformers)
    4. Check protocol cache (Redis Layer 2)
    5. Query Actian if cache miss
    6. Get session history from Redis cache (Layer 3)
    7. Write-through cache incident to Redis + Actian
    8. Synthesize recommendation
    """

    # Step 1: Temporal synthesis
    buffer_packets = list(self.temporal_buffer.buffers.get(packet.device_id, []))
    temporal_synthesis = await self.temporal_narrative_agent.synthesize_temporal_narrative(
        buffer_packets,
        lookback_seconds=float(os.getenv("TEMPORAL_LOOKBACK_SECONDS", "3.0"))
    )
    synthesized_narrative = temporal_synthesis.synthesized_narrative

    # Step 2: Check embedding cache
    cached_vector = await self.cache_agent.get_cached_embedding(synthesized_narrative)

    if cached_vector:
        logger.info(f"[CACHE HIT] Embedding (saved {embedding_time:.2f}ms)")
        vector = cached_vector
        embedding_time_ms = 0.0
    else:
        # Cache miss - compute embedding
        embedding_result = await self.embedding_agent.embed_text(
            text=synthesized_narrative,
            request_id=f"{packet.device_id}_{packet.timestamp}"
        )
        vector = embedding_result.vector
        embedding_time_ms = embedding_result.embedding_time_ms

        # Cache for future use
        await self.cache_agent.cache_embedding(synthesized_narrative, vector, ttl=60)

    # Step 3: Check protocol cache
    severity_filter = self._get_severity_filter(packet.hazard_level)
    cached_protocols = await self.cache_agent.get_cached_protocols(vector, severity_filter)

    if cached_protocols:
        logger.info(f"[CACHE HIT] Protocols (saved 50-100ms)")
        protocols = [Protocol(**p) for p in cached_protocols]
    else:
        # Cache miss - query Actian
        protocols = await self.protocol_retrieval_agent.execute_vector_search(
            vector=vector,
            severity_filter=severity_filter,
            top_k=3
        )

        # Cache protocols
        await self.cache_agent.cache_protocols(
            vector, severity_filter,
            [p.dict() for p in protocols],
            ttl=300
        )

    # Step 4: Session history from Redis
    session_history = await self.cache_agent.get_session_history(
        session_id=packet.session_id,
        device_id=packet.device_id,
        current_vector=vector,
        similarity_threshold=0.70,
        max_results=5
    )

    # Fallback to DB if cache empty
    if not session_history:
        session_history = await self.history_retrieval_agent.query_session_history(...)

    # Step 5: Write-through caching
    await self.cache_agent.append_session_history(
        session_id=packet.session_id,
        device_id=packet.device_id,
        narrative=synthesized_narrative,
        vector=vector,
        timestamp=packet.timestamp,
        trend=trend.trend_tag,
        hazard_level=packet.hazard_level
    )

    # Also persist to Actian (write-through)
    await self.incident_logger.write_to_actian(vector, packet, trend)

    # Rest of synthesis pipeline unchanged...
```

---

#### 7. `backend/agents/__init__.py` (+3 lines)

```python
from .temporal_narrative import TemporalNarrativeAgent
from .redis_cache import RAGCacheAgent

__all__ = [
    # ... existing exports ...
    "TemporalNarrativeAgent",
    "RAGCacheAgent",
]
```

---

#### 8. `requirements.txt` (+2 lines)

```python
# Existing dependencies...

# Temporal LLM
google-generativeai>=0.3.0  # ~20MB (vs 2GB for PyTorch)

# Redis caching
redis>=5.0.0
```

---

#### 9. `docker-compose.yml` (+20 lines)

**Add Redis Service:**
```yaml
services:
  # ... existing services (actian, rag, ingest) ...

  redis:
    image: redis:7-alpine
    container_name: hacklytics_redis
    ports:
      - "6379:6379"
    networks:
      - rag_network
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.1'
          memory: 128M
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  # Update RAG service to depend on Redis
  rag:
    depends_on:
      actian:
        condition: service_healthy
      redis:  # NEW
        condition: service_healthy
    environment:
      # ... existing env vars ...
      REDIS_URL: redis://redis:6379
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      GEMINI_MODEL: ${GEMINI_MODEL:-gemini-1.5-flash-002}
      TEMPORAL_LOOKBACK_SECONDS: ${TEMPORAL_LOOKBACK_SECONDS:-3.0}
```

---

#### 10. `.env.example` (+10 lines)

```bash
# ... existing env vars ...

# Temporal LLM Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash-002
TEMPORAL_LOOKBACK_SECONDS=3.0

# Redis Caching Configuration
REDIS_URL=redis://localhost:6379
CACHE_EMBEDDING_TTL=60
CACHE_PROTOCOL_TTL=300
CACHE_SESSION_TTL=1800
```

---

### TEST FILES (2 New)

#### 11. `tests/test_profiles/test_08_temporal_synthesis.py` (~250 lines)

**End-to-End Integration Test**

**Purpose:** Validate full pipeline with temporal LLM + Redis caching

**Test Scenarios:**

1. **Cold Cache Scenario** (All Misses)
   ```python
   async def test_cold_cache_full_pipeline():
       """
       First run - no cache hits.
       Should use:
       - Gemini for synthesis
       - sentence-transformers for embedding
       - Actian for protocol search
       - Actian for session history

       Expected latency: 200-400ms
       """
   ```

2. **Warm Cache Scenario** (Partial Hits)
   ```python
   async def test_warm_cache_scenario():
       """
       Second run with similar fire scenario.
       Should hit:
       - Protocol cache (same quantized vector)
       - Session history cache

       Expected latency: 150-300ms
       """
   ```

3. **Hot Cache Scenario** (All Hits)
   ```python
   async def test_hot_cache_all_hits():
       """
       Repeated identical scenario.
       Should hit all caches:
       - Embedding cache
       - Protocol cache
       - Session history cache

       Expected latency: 80-180ms
       """
   ```

4. **Temporal Synthesis Quality**
   ```python
   async def test_temporal_synthesis_captures_escalation():
       """
       Verify LLM synthesis captures:
       - Fire progression (8% → 45%)
       - Timeline (3 seconds)
       - Critical events (person trapped, path blocked)
       - Pattern recognition (flashover acceleration)
       """
   ```

5. **Graceful Degradation**
   ```python
   async def test_gemini_api_failure_fallback():
       """
       Simulate Gemini API down.
       Should:
       - Fallback to concatenation (<5ms)
       - Still produce valid embedding
       - Complete RAG pipeline
       - Log warning
       """

   async def test_redis_failure_fallback():
       """
       Simulate Redis down.
       Should:
       - Skip all caches
       - Use Actian for everything
       - Complete successfully
       - Log warnings
       """
   ```

6. **Cache Effectiveness Metrics**
   ```python
   async def test_cache_hit_rate_tracking():
       """
       Run 100 packets through pipeline.
       Verify:
       - Hit rate >30% (embedding)
       - Hit rate >60% (protocols)
       - Hit rate >90% (session)
       - Cache stats accurate
       """
   ```

**Fixtures:**
```python
@pytest.fixture
async def full_system_with_redis():
    """Spin up full RAG system with Redis."""
    # Start Redis
    # Initialize orchestrator
    # Seed some protocols
    yield orchestrator
    # Cleanup

@pytest.fixture
def fire_escalation_session():
    """10 packets showing realistic fire progression."""
    return [packet1, packet2, ..., packet10]
```

---

## Implementation Phases

### Phase 1: Core Temporal LLM Agent (No Caching)

**Duration:** 3-4 hours

**Files:**
- ✅ `backend/agents/temporal_narrative.py`
- ✅ `backend/contracts/models.py` (TemporalSynthesisResult)
- ✅ `tests/agents/test_temporal_narrative.py`
- ✅ `requirements.txt` (google-generativeai)
- ✅ `.env.example` (GEMINI_*)

**Goals:**
1. Gemini Flash integration working
2. 3-second temporal synthesis
3. <150ms latency achieved
4. Fallback logic tested
5. All unit tests passing

**Validation:**
```bash
cd fastapi
pip install google-generativeai
export GEMINI_API_KEY=your_key
python -m pytest tests/agents/test_temporal_narrative.py -v
```

**Success Criteria:**
- ✅ 10/10 tests passing
- ✅ 95th percentile latency <150ms
- ✅ Fallback activates on API failure
- ✅ 200-char limit enforced

---

### Phase 2: Redis Caching Layer

**Duration:** 2-3 hours

**Files:**
- ✅ `backend/agents/redis_cache.py`
- ✅ `tests/agents/test_redis_cache.py`
- ✅ `docker-compose.yml` (redis service)
- ✅ `requirements.txt` (redis)

**Goals:**
1. 3-layer cache implemented
2. Vector quantization working
3. Session history sorted set
4. Metrics tracking
5. All cache tests passing

**Validation:**
```bash
docker compose up -d redis
python -m pytest tests/agents/test_redis_cache.py -v
```

**Success Criteria:**
- ✅ 15/15 tests passing
- ✅ Cache hit rate >30% in tests
- ✅ Graceful Redis failure handling
- ✅ Memory usage <256MB

---

### Phase 3: Orchestrator Integration

**Duration:** 2 hours

**Files:**
- ✅ `backend/orchestrator.py`
- ✅ `backend/agents/__init__.py`
- ✅ `tests/test_profiles/test_08_temporal_synthesis.py`

**Goals:**
1. Temporal agent integrated
2. Cache agent integrated
3. Full pipeline working
4. E2E tests passing

**Validation:**
```bash
docker compose up -d
make test-prompt-temporal  # New Makefile target
```

**Success Criteria:**
- ✅ Cold cache: 200-400ms total latency
- ✅ Hot cache: 80-180ms total latency
- ✅ Cache hit rate >50% overall
- ✅ Graceful degradation working

---

### Phase 4: Production Hardening

**Duration:** 1-2 hours

**Tasks:**
- ✅ Add comprehensive error logging
- ✅ Add Prometheus metrics endpoints
- ✅ Add cache invalidation endpoint
- ✅ Add docs/guides/TEMPORAL_LLM_USAGE.md
- ✅ Update main README with new architecture
- ✅ Add Makefile targets (test-temporal, cache-stats)
- ✅ Load testing (100 packets/sec)

**Validation:**
```bash
make test-all  # All tests including new ones
make cache-stats  # View cache performance
```

---

## Low-Latency Optimizations

### 1. Gemini Flash Configuration

**Optimized Generation Config:**
```python
generation_config = {
    "temperature": 0.3,           # Low temp for consistency (less creative, faster)
    "top_p": 0.8,                 # Reduced sampling space
    "top_k": 20,                  # Limit candidate tokens
    "max_output_tokens": 100,     # Strict limit (200 chars ≈ 50-70 tokens)
    "candidate_count": 1,         # Single response (no n-best)
    "stop_sequences": ["\n\n"],   # Early termination
}
```

**API Optimization:**
```python
# Streaming disabled (adds overhead for short responses)
stream=False

# Timeout enforcement
timeout=0.2  # 200ms hard limit

# Connection pooling
self.client = genai.Client(
    api_key=api_key,
    http_options={
        "pool_connections": 5,
        "pool_maxsize": 10,
        "max_retries": 0  # Fail fast
    }
)
```

**Expected Latency Breakdown:**
- Network RTT: 20-40ms
- Gemini processing: 50-100ms
- Response parsing: 5-10ms
- **Total: 75-150ms** (95th percentile)

---

### 2. Async Parallel Execution

**Run Multiple Operations Simultaneously:**
```python
# Don't do this (sequential):
synthesis = await gemini_call()        # 100ms
cached = await redis.get_embedding()   # 2ms
# Total: 102ms

# Do this (parallel):
synthesis_task = asyncio.create_task(gemini_call())
cache_task = asyncio.create_task(redis.get_embedding())

synthesis, cached = await asyncio.gather(synthesis_task, cache_task)
# Total: max(100ms, 2ms) = 100ms (saved 2ms)
```

**Orchestrator Parallel Pattern:**
```python
# Run temporal synthesis + cache checks in parallel
temporal_task = self.temporal_agent.synthesize(buffer_packets)
embedding_cache_task = self.cache_agent.get_cached_embedding(last_narrative)
protocol_cache_task = self.cache_agent.get_cached_protocols(last_vector)

temporal_result, cached_embedding, cached_protocols = await asyncio.gather(
    temporal_task,
    embedding_cache_task,
    protocol_cache_task,
    return_exceptions=True  # Don't fail entire pipeline on partial error
)
```

---

### 3. Request Batching (Future Optimization)

**Problem:** If 5 packets arrive within 100ms, we make 5 separate Gemini calls

**Solution:** Batch into single call
```python
class TemporalNarrativeAgent:
    def __init__(self):
        self.pending_requests = []
        self.batch_window_ms = 100
        self.batch_task = None

    async def synthesize_temporal_narrative(self, buffer_packets):
        # Add to batch
        future = asyncio.Future()
        self.pending_requests.append((buffer_packets, future))

        # Start batch timer if not running
        if not self.batch_task:
            self.batch_task = asyncio.create_task(self._process_batch())

        return await future

    async def _process_batch(self):
        await asyncio.sleep(self.batch_window_ms / 1000)

        # Process all pending in single Gemini call
        batch = self.pending_requests
        self.pending_requests = []

        # Combine prompts
        combined_prompt = "\n---\n".join([build_prompt(p) for p, _ in batch])
        response = await self.model.generate_content_async(combined_prompt)

        # Split response and resolve futures
        responses = response.text.split("---")
        for (packets, future), response_text in zip(batch, responses):
            future.set_result(response_text)
```

**Savings:** 5 calls × 100ms = 500ms → 1 call × 120ms = 120ms (76% reduction)

---

### 4. Connection Pooling

**Gemini HTTP Client:**
```python
import httpx

self.http_client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_keepalive_connections=5,
        max_connections=10,
        keepalive_expiry=30.0
    ),
    timeout=httpx.Timeout(0.2)  # 200ms timeout
)
```

**Redis Connection Pool:**
```python
self.redis_pool = redis.ConnectionPool(
    host='redis',
    port=6379,
    max_connections=10,
    socket_keepalive=True,
    socket_connect_timeout=0.1,
    decode_responses=False  # Binary mode for pickle
)

self.redis = redis.Redis(connection_pool=self.redis_pool)
```

**Savings:** ~10-20ms per request (no connection setup)

---

### 5. Smart Caching Strategies

**Strategy 1: Cache Synthesis Results (Not Just Vectors)**
```python
# Cache the synthesized narrative itself
synthesis_cache_key = f"synthesis:{hash_buffer_state(buffer_packets)}"
cached_synthesis = await redis.get(synthesis_cache_key)

if cached_synthesis:
    # Skip Gemini call entirely!
    return pickle.loads(cached_synthesis)
else:
    result = await self._call_gemini()
    await redis.setex(synthesis_cache_key, 60, pickle.dumps(result))
    return result
```

**Savings:** Skip 100-150ms Gemini call entirely

---

**Strategy 2: Negative Caching**
```python
# Cache "no synthesis needed" decisions
if len(buffer_packets) < 2:
    # Cache the fact that synthesis wasn't needed
    await redis.setex(f"no_synthesis:{device_id}", 5, b"1")
    return latest_narrative
```

---

**Strategy 3: Bloom Filter Pre-Check**
```python
# Quick probabilistic check before Redis
from pybloom_live import BloomFilter

self.protocol_bloom = BloomFilter(capacity=10000, error_rate=0.001)

async def get_cached_protocols(self, vector, severity):
    vector_hash = self._hash_vector_query(vector, severity)

    # Quick bloom filter check (0.1ms)
    if not self.protocol_bloom.contains(vector_hash):
        # Definitely not in cache
        return None

    # Probably in cache - check Redis (2ms)
    return await self.redis.get(f"proto:{vector_hash}")
```

**Savings:** Skip 2ms Redis call if bloom filter says "not cached"

---

### 6. Partial Response Streaming (Future)

**Problem:** Wait 150ms for complete Gemini response

**Solution:** Use streaming API, start embedding as soon as first 50 tokens arrive
```python
async for chunk in self.model.generate_content_stream(prompt):
    partial_text += chunk.text

    # Start embedding after 50 tokens (~100 chars)
    if len(partial_text) >= 100 and not embedding_started:
        embedding_task = asyncio.create_task(embed(partial_text))
        embedding_started = True

# Wait for both to complete
final_text, vector = await asyncio.gather(
    stream_complete,
    embedding_task
)
```

**Savings:** ~30-50ms overlap (parallel Gemini + embedding)

---

## Test Strategy

### Unit Tests (Fast, No External Dependencies)

**Coverage: >80% of code**

**Agents:**
- `test_temporal_narrative.py`: Mock Gemini API
- `test_redis_cache.py`: Use fakeredis for in-memory testing

**Patterns:**
```python
@pytest.fixture
def mock_gemini(monkeypatch):
    """Mock Gemini to avoid real API calls."""
    async def fake_generate(prompt):
        return MockResponse("Fire escalated from 8% to 45%...")

    monkeypatch.setattr(
        'google.generativeai.GenerativeModel.generate_content_async',
        fake_generate
    )

@pytest.mark.asyncio
async def test_synthesis_with_mock(mock_gemini, agent):
    result = await agent.synthesize_temporal_narrative(packets)
    assert result.synthesized_narrative.startswith("Fire escalated")
    assert result.synthesis_time_ms < 150
```

---

### Integration Tests (Moderate, Uses Real Redis)

**Coverage: Full pipeline with real Redis, mock Gemini**

**Test File:** `test_redis_cache.py`

**Setup:**
```python
@pytest.fixture(scope="module")
async def redis_server():
    """Start real Redis for integration tests."""
    process = subprocess.Popen(["redis-server", "--port", "6380"])
    await asyncio.sleep(1)  # Wait for startup
    yield "redis://localhost:6380"
    process.terminate()

@pytest.mark.integration
async def test_cache_integration(redis_server):
    cache = RAGCacheAgent(redis_url=redis_server)
    # Test real Redis operations
```

**Run:**
```bash
pytest tests/agents/test_redis_cache.py -m integration -v
```

---

### E2E Tests (Slow, Uses Real Services)

**Coverage: Full system with real Gemini + Redis + Actian**

**Test File:** `test_08_temporal_synthesis.py`

**Scenarios:**
1. Cold cache (first run)
2. Warm cache (second run, partial hits)
3. Hot cache (repeated scenario, all hits)
4. Gemini failure fallback
5. Redis failure fallback
6. 100-packet load test

**Fixtures:**
```python
@pytest.fixture(scope="module")
async def full_system():
    """
    Start all services:
    - Docker Compose up (Redis, Actian)
    - Initialize orchestrator
    - Seed protocols
    """
    subprocess.run(["docker", "compose", "up", "-d"])
    await asyncio.sleep(5)  # Wait for healthy

    orchestrator = RAGOrchestrator(actian_pool=get_pool(), redis_url="redis://localhost:6379")
    await orchestrator.startup()

    yield orchestrator

    subprocess.run(["docker", "compose", "down"])
```

**Run:**
```bash
# Requires Docker + Gemini API key
export GEMINI_API_KEY=your_key
make test-e2e-temporal
```

---

### Performance Tests (Latency Validation)

**Test File:** `test_08_temporal_synthesis.py`

**Metrics to Track:**
```python
@pytest.mark.asyncio
async def test_latency_budget_cold_cache(orchestrator):
    """Validate cold cache performance."""
    start = time.perf_counter()
    result = await orchestrator.stage_3_cognition(packet, trend)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 400, f"Cold cache too slow: {elapsed_ms:.1f}ms"
    assert result.temporal_synthesis.synthesis_time_ms < 150

@pytest.mark.asyncio
async def test_latency_budget_hot_cache(orchestrator, packet):
    """Validate hot cache performance."""
    # Warm up cache
    await orchestrator.stage_3_cognition(packet, trend)

    # Measure hot cache
    start = time.perf_counter()
    result = await orchestrator.stage_3_cognition(packet, trend)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 180, f"Hot cache too slow: {elapsed_ms:.1f}ms"

    # Verify cache hits
    stats = orchestrator.cache_agent.get_cache_stats()
    assert stats["embedding_cache"]["hit_rate"] > 0.8
    assert stats["protocol_cache"]["hit_rate"] > 0.8
```

---

### Load Tests (Stress Testing)

**Tool:** `locust` or custom async script

**Scenario:** 100 packets/second for 60 seconds
```python
# tests/load/test_temporal_load.py

import asyncio
import time

async def send_packet(orchestrator, packet):
    start = time.perf_counter()
    result = await orchestrator.stage_3_cognition(packet, trend)
    latency = (time.perf_counter() - start) * 1000
    return latency

async def load_test():
    orchestrator = RAGOrchestrator(...)

    # Generate 6000 packets
    packets = [generate_packet(i) for i in range(6000)]

    # Send 100/sec for 60 seconds
    latencies = []
    for i in range(0, 6000, 100):
        batch = packets[i:i+100]
        tasks = [send_packet(orchestrator, p) for p in batch]
        batch_latencies = await asyncio.gather(*tasks)
        latencies.extend(batch_latencies)
        await asyncio.sleep(1)  # 100/sec

    # Analyze
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)

    print(f"P50: {p50:.1f}ms")
    print(f"P95: {p95:.1f}ms")
    print(f"P99: {p99:.1f}ms")

    assert p95 < 400, "P95 latency too high"
```

---

## Success Criteria

### Performance Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Temporal Synthesis Latency** | <150ms (P95) | `synthesis_time_ms` field |
| **Embedding Cache Hit Rate** | >30% | After 100 packets |
| **Protocol Cache Hit Rate** | >60% | After 100 packets |
| **Session Cache Hit Rate** | >90% | During active session |
| **Total RAG Latency (Cold)** | <400ms | End-to-end timing |
| **Total RAG Latency (Warm)** | <300ms | With partial cache hits |
| **Total RAG Latency (Hot)** | <180ms | With all cache hits |
| **Gemini Failure Recovery** | <5ms | Fallback to concatenation |
| **Redis Failure Recovery** | <50ms | Fallback to direct DB |

---

### Reliability Metrics

| Metric | Target | Validation |
|--------|--------|------------|
| **API Failure Handling** | 100% graceful | Test with mock errors |
| **Cache Failure Handling** | 100% graceful | Test with Redis down |
| **Data Quality** | No truncation errors | 200-char enforcement |
| **Memory Usage** | <256MB (Redis) | Monitor in Docker |
| **Test Coverage** | >80% | pytest-cov report |

---

### Quality Metrics

| Aspect | Validation Method | Pass Criteria |
|--------|------------------|---------------|
| **Temporal Context Capture** | Manual review of 50 syntheses | Fire progression mentioned in >90% |
| **Narrative Coherence** | LLM-as-judge evaluation | >4.0/5.0 average score |
| **Protocol Matching Improvement** | Compare before/after relevance | >20% improvement |
| **False Positive Rate** | Test with non-fire scenarios | <5% false "flashover" predictions |

---

## Risk Mitigation

### Risk 1: Gemini API Latency Spikes

**Probability:** Medium
**Impact:** High (breaks <300ms budget)

**Mitigation:**
1. **Hard timeout:** 200ms max
2. **Immediate fallback:** Switch to concatenation
3. **Async retry:** Queue for retry in background (update cache later)
4. **Circuit breaker:** After 5 consecutive failures, disable LLM for 60s

**Implementation:**
```python
async def synthesize_with_circuit_breaker(self, packets):
    if self.circuit_breaker.is_open():
        logger.warning("Circuit breaker open, using fallback")
        return self._fallback_concatenation(packets)

    try:
        result = await asyncio.wait_for(
            self._call_gemini(packets),
            timeout=0.2  # 200ms
        )
        self.circuit_breaker.record_success()
        return result
    except asyncio.TimeoutError:
        self.circuit_breaker.record_failure()
        return self._fallback_concatenation(packets)
```

---

### Risk 2: Cache Stampede (Thundering Herd)

**Probability:** Medium
**Impact:** Medium (many simultaneous Gemini calls)

**Scenario:** Cache expires, 10 requests arrive simultaneously, all miss cache, all call Gemini

**Mitigation: Single-Flight Pattern**
```python
class RAGCacheAgent:
    def __init__(self):
        self.in_flight = {}  # Track ongoing requests

    async def get_cached_embedding(self, narrative):
        cache_key = self._hash_narrative(narrative)

        # Check cache
        cached = await self.redis.get(cache_key)
        if cached:
            return pickle.loads(cached)

        # Check if computation already in flight
        if cache_key in self.in_flight:
            # Wait for ongoing computation
            return await self.in_flight[cache_key]

        # Start new computation
        future = asyncio.Future()
        self.in_flight[cache_key] = future

        try:
            # Compute
            vector = await self.embedding_agent.embed_text(narrative)

            # Cache
            await self.redis.setex(cache_key, 60, pickle.dumps(vector))

            # Resolve future
            future.set_result(vector)
            return vector
        finally:
            del self.in_flight[cache_key]
```

**Result:** 10 simultaneous requests → 1 Gemini call, 9 wait for result

---

### Risk 3: Redis Memory Exhaustion

**Probability:** Low
**Impact:** High (OOM kills Redis)

**Mitigation:**
1. **maxmemory:** 256MB hard limit
2. **Eviction policy:** allkeys-lru (least recently used)
3. **Monitoring:** Alert if memory >80%
4. **TTLs:** Aggressive (60s for embeddings)

**Docker Config:**
```yaml
redis:
  command: >
    redis-server
    --maxmemory 256mb
    --maxmemory-policy allkeys-lru
    --maxmemory-samples 5
```

**Monitoring:**
```python
async def check_redis_health():
    info = await redis.info("memory")
    used_mb = info["used_memory"] / 1024 / 1024

    if used_mb > 200:  # >80% of 256MB
        logger.warning(f"Redis memory high: {used_mb:.1f}MB")
        # Trigger manual eviction
        await redis.flushdb()
```

---

### Risk 4: Stale Cached Protocols

**Probability:** Low
**Impact:** Medium (outdated safety protocols served)

**Scenario:** Protocol database updated, but cache still has old version

**Mitigation:**
1. **Short TTL:** 5 minutes (protocols rarely change)
2. **Manual invalidation endpoint:**
```python
@app.post("/admin/invalidate_protocol_cache")
async def invalidate_protocol_cache():
    """Call after updating protocols in Actian."""
    await cache_agent.redis.delete("proto:*")
    return {"invalidated": await cache_agent.redis.keys("proto:*")}
```
3. **Version tagging:**
```python
# Include protocol DB version in cache key
cache_key = f"proto:v{PROTOCOL_VERSION}:{vector_hash}"
```

---

### Risk 5: Gemini API Cost Explosion

**Probability:** Low
**Impact:** Medium ($$ cost)

**Mitigation:**
1. **Rate limiting:** Max 1000 calls/hour per device
```python
class RateLimiter:
    def __init__(self, max_per_hour=1000):
        self.calls = deque()
        self.max_per_hour = max_per_hour

    async def acquire(self):
        now = time.time()

        # Remove calls older than 1 hour
        while self.calls and self.calls[0] < now - 3600:
            self.calls.popleft()

        if len(self.calls) >= self.max_per_hour:
            raise Exception("Rate limit exceeded")

        self.calls.append(now)
```
2. **Cost monitoring:** Log daily spend
3. **Fallback to free:** Switch to concatenation if budget exceeded

**Expected Monthly Cost (100 devices, 10 FPS, 50% cache hit):**
- Packets/month: 100 devices × 10 FPS × 60s × 60m × 24h × 30d = 2.6B
- After delta filter: 2.6B × 0.1 = 260M packets
- After cache: 260M × 0.5 = 130M Gemini calls
- Cost: 130M × $0.000025 = **$3,250/month**

---

## Appendix: Detailed Code Examples

### Example 1: Temporal Synthesis Prompt

```python
def _build_timeline_prompt(self, buffer_packets: List[Dict]) -> str:
    """
    Build optimized prompt for Gemini Flash.

    Prompt Engineering Principles:
    1. Clear task definition
    2. Structured input (timeline format)
    3. Explicit constraints (200 chars)
    4. Examples (few-shot)
    5. Output format specification
    """

    current_time = time.time()
    timeline = []

    for pkt in buffer_packets[-5:]:  # Last 5 packets max
        age = current_time - pkt["timestamp"]
        narrative = pkt["packet"].visual_narrative
        priority = pkt.get("priority", "CAUTION")

        # Format: "T-2.3s [CRITICAL]: Major fire 45%. Path blocked."
        timeline.append(f"T-{age:.1f}s [{priority}]: {narrative}")

    timeline_str = "\n".join(timeline)

    prompt = f"""You are a fire safety AI analyzing temporal fire progression.

INPUT - Observations (oldest → newest):
{timeline_str}

TASK:
Synthesize these observations into ONE coherent narrative that captures:
1. What changed (progression/escalation)
2. Current state
3. Trajectory (pattern)

CONSTRAINTS:
- Maximum 200 characters (STRICT)
- Present tense for current state
- Past tense for progression
- No speculation, only observed facts
- Focus on safety-critical changes

EXAMPLES:

Input:
T-3.0s [CAUTION]: Small fire 8%
T-2.0s [CAUTION]: Moderate fire 22%
T-1.0s [HIGH]: Major fire 38%
T-0.0s [CRITICAL]: Major fire 45%. Path blocked.

Output:
Fire escalated 8%→45% in 3s. Path now blocked. Matches flashover acceleration pattern.

Input:
T-5.0s [CRITICAL]: Fire 68%
T-3.0s [HIGH]: Fire 52%
T-1.0s [CAUTION]: Fire 28%
T-0.0s [CAUTION]: Fire 12%. Suppression active.

Output:
Fire suppressed from 68%→12% over 5s. Now contained and diminishing.

YOUR OUTPUT (200 chars max):"""

    return prompt
```

---

### Example 2: Vector Quantization for Cache Fuzzy Matching

```python
def _hash_vector_query(
    self,
    vector: List[float],
    severity_filter: List[str]
) -> str:
    """
    Generate cache key with fuzzy matching via quantization.

    Strategy:
    1. Round vector components to 2 decimals (reduces uniqueness)
    2. Use only first 50 dimensions (most important for similarity)
    3. Similar fire scenarios → similar quantized vectors → cache hits

    Example:
    Vector A: [0.123, 0.456, 0.789, ...]
    Vector B: [0.127, 0.451, 0.792, ...]

    Quantized (both): [0.12, 0.46, 0.79, ...]
    → Same cache key → CACHE HIT!
    """

    # Quantize to 2 decimals, use first 50 dims
    quantized = [round(v, 2) for v in vector[:50]]

    # Include severity filter in key
    # (HIGH+CRITICAL different from ALL severities)
    filter_str = ",".join(sorted(severity_filter))

    # Create deterministic representation
    query_repr = f"{quantized}:{filter_str}"

    # Hash to fixed-length key
    return hashlib.sha256(query_repr.encode()).hexdigest()[:16]

# Usage:
key1 = _hash_vector_query([0.123, 0.456, ...], ["HIGH", "CRITICAL"])
key2 = _hash_vector_query([0.127, 0.451, ...], ["HIGH", "CRITICAL"])
# key1 == key2 → CACHE HIT despite slightly different vectors!
```

**Trade-off Analysis:**
- **Precision loss:** Vectors within ±0.005 → same key
- **Cache hit gain:** 20-30% higher hit rate
- **False positives:** ~1% (acceptable for safety protocols - better to over-alert)

---

### Example 3: Session History Similarity Search in Redis

```python
async def get_session_history(
    self,
    session_id: str,
    device_id: str,
    current_vector: List[float],
    similarity_threshold: float = 0.70,
    max_results: int = 5
) -> List[Dict]:
    """
    Retrieve similar past incidents from Redis sorted set.

    Data Structure:
    Key: "session:{session_id}:{device_id}"
    Type: Sorted Set
    Score: timestamp (for chronological order)
    Member: pickle({narrative, vector, trend, hazard, timestamp})

    Algorithm:
    1. Retrieve ALL incidents from session (Redis sorted set)
    2. Compute cosine similarity for each in-memory (NumPy)
    3. Filter by threshold (>0.70)
    4. Sort by similarity descending
    5. Return top N

    Performance:
    - Redis retrieval: ~2ms (all incidents)
    - Similarity computation: ~0.5ms per incident (NumPy vectorized)
    - Total: ~5-10ms for 10 incidents

    vs. Actian DB query: ~30-50ms
    """

    cache_key = f"session:{session_id}:{device_id}"

    try:
        # Get all incidents (sorted by timestamp)
        cached_incidents = self.redis.zrange(cache_key, 0, -1)

        if not cached_incidents:
            self.metrics["session_misses"] += 1
            return []  # Empty cache

        self.metrics["session_hits"] += 1

        # Deserialize incidents
        incidents = [pickle.loads(inc) for inc in cached_incidents]

        # Vectorized similarity computation (NumPy)
        current_vec = np.array(current_vector)
        incident_vecs = np.array([inc["vector"] for inc in incidents])

        # Batch cosine similarity
        # cos_sim = dot(A, B) / (||A|| * ||B||)
        similarities = np.dot(incident_vecs, current_vec) / (
            np.linalg.norm(incident_vecs, axis=1) * np.linalg.norm(current_vec)
        )

        # Filter by threshold and create results
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

        # Sort by similarity descending
        similar_incidents.sort(key=lambda x: x["similarity"], reverse=True)

        return similar_incidents[:max_results]

    except Exception as e:
        logger.error(f"Session history retrieval error: {e}")
        return []  # Graceful degradation
```

---

## Summary

This implementation plan provides:

1. **Temporal Intelligence:** Gemini Flash synthesis captures fire progression over 3-5 seconds
2. **Performance:** 30-50% latency reduction via 3-layer Redis caching
3. **Reliability:** Graceful degradation on API/cache failures
4. **Quality:** Richer narratives → better protocol matching
5. **Scalability:** Handles 100 devices × 10 FPS with <$4K/month cost

**Next Steps:**
1. Review and approve plan
2. Begin Phase 1 implementation (Temporal LLM agent)
3. Iterate through phases with testing
4. Deploy to production with monitoring

**Total Effort:** 8-11 hours spread over 2-3 days
