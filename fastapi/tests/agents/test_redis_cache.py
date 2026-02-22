"""
Comprehensive test suite for RAGCacheAgent (Semantic Key Implementation).

Tests two-layer Redis caching strategy:
1. Layer 1 - Semantic Protocol Cache: YOLO buckets → protocols (300s TTL)
2. Layer 2 - Session History Cache: sorted set with cosine similarity (1800s TTL)

Integration tests validate:
- Semantic key generation from telemetry
- Multi-fire-scenario cache hit patterns
- Session history similarity search
- Graceful degradation on Redis failure
- Cache statistics accuracy
"""

import pytest
import sys
import os
import time
import asyncio
import pickle
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.agents.redis_cache import RAGCacheAgent
from backend.contracts.models import TelemetryPacket, TrackedObject, ScoreContext


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
async def redis_client():
    """Real Redis client for integration tests."""
    try:
        import redis.asyncio as redis
        client = redis.from_url("redis://localhost:6379", decode_responses=False)

        # Test connection
        await client.ping()

        yield client

        # Clean up after tests
        await client.flushdb()
        await client.close()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


@pytest.fixture
async def cache_agent(redis_client):
    """RAGCacheAgent instance with real Redis."""
    agent = RAGCacheAgent(redis_url="redis://localhost:6379")
    yield agent
    # Reset metrics after each test
    agent.reset_metrics()


@pytest.fixture
def sample_packet_minor():
    """Sample telemetry packet: MINOR fire."""
    return TelemetryPacket(
        device_id="jetson_test",
        session_id="test_session",
        timestamp=time.time(),
        fire_dominance=0.08,  # 8% - MINOR
        smoke_opacity=0.15,   # 15% - CLEAR
        proximity_alert=False,
        hazard_level="CAUTION",
        visual_narrative="Small fire detected 8% coverage",
        scores=ScoreContext(proximity_alert=False, obstruction=0.0, dominance=0.08),
        tracked_objects=[]
    )


@pytest.fixture
def sample_packet_moderate():
    """Sample telemetry packet: MODERATE fire."""
    return TelemetryPacket(
        device_id="jetson_test",
        session_id="test_session",
        timestamp=time.time(),
        fire_dominance=0.25,  # 25% - MODERATE
        smoke_opacity=0.45,   # 45% - HAZY
        proximity_alert=False,
        hazard_level="HIGH",
        visual_narrative="Moderate fire 25% coverage",
        scores=ScoreContext(proximity_alert=False, obstruction=0.1, dominance=0.25),
        tracked_objects=[]
    )


@pytest.fixture
def sample_packet_major():
    """Sample telemetry packet: MAJOR fire with proximity."""
    return TelemetryPacket(
        device_id="jetson_test",
        session_id="test_session",
        timestamp=time.time(),
        fire_dominance=0.45,  # 45% - MAJOR
        smoke_opacity=0.68,   # 68% - DENSE
        proximity_alert=True,
        hazard_level="CRITICAL",
        visual_narrative="Major fire 45% coverage. Person detected nearby.",
        scores=ScoreContext(proximity_alert=True, obstruction=0.3, dominance=0.45),
        tracked_objects=[]
    )


@pytest.fixture
def sample_packet_critical():
    """Sample telemetry packet: CRITICAL fire (flashover risk)."""
    return TelemetryPacket(
        device_id="jetson_test",
        session_id="test_session",
        timestamp=time.time(),
        fire_dominance=0.75,  # 75% - CRITICAL
        smoke_opacity=0.95,   # 95% - BLINDING
        proximity_alert=True,
        hazard_level="CRITICAL",
        visual_narrative="CRITICAL: Fire dominates 75% of view. Flashover risk.",
        scores=ScoreContext(proximity_alert=True, obstruction=0.8, dominance=0.75),
        tracked_objects=[]
    )


@pytest.fixture
def sample_protocols():
    """Sample protocol results."""
    return [
        {
            "id": 1,
            "protocol_text": "Use Class B extinguisher for grease fires.",
            "severity": "HIGH",
            "category": "suppression"
        },
        {
            "id": 2,
            "protocol_text": "Evacuate immediately. Establish safe perimeter.",
            "severity": "CRITICAL",
            "category": "evacuation"
        },
        {
            "id": 3,
            "protocol_text": "Cut power before using water-based suppression.",
            "severity": "HIGH",
            "category": "electrical"
        }
    ]


@pytest.fixture
def sample_vector():
    """384-dim vector for testing."""
    np.random.seed(42)
    return np.random.rand(384).tolist()


# ============================================================================
# LAYER 1: SEMANTIC PROTOCOL CACHE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_semantic_key_generation(cache_agent, sample_packet_moderate):
    """Test semantic cache key generation from YOLO fire buckets."""
    key = cache_agent.get_semantic_cache_key(sample_packet_moderate)

    assert key == "FIRE_MODERATE|SMOKE_HAZY|PROX_FAR|HIGH"
    assert "FIRE_" in key
    assert "SMOKE_" in key
    assert "PROX_" in key


@pytest.mark.asyncio
async def test_semantic_cache_hit_same_bucket(cache_agent, sample_protocols):
    """Test cache hit when fire stays in same semantic bucket."""
    # First packet: 25% fire
    packet1 = TelemetryPacket(
        device_id="test", session_id="test", timestamp=time.time(),
        fire_dominance=0.25, smoke_opacity=0.45, proximity_alert=False,
        hazard_level="HIGH", visual_narrative="Fire 25%",
        scores=ScoreContext(proximity_alert=False, obstruction=0, dominance=0.25),
        tracked_objects=[]
    )

    # Cache protocols
    await cache_agent.cache_protocols_by_semantic_key(packet1, sample_protocols, ttl=300)

    # Second packet: 28% fire (still MODERATE bucket)
    packet2 = TelemetryPacket(
        device_id="test", session_id="test", timestamp=time.time(),
        fire_dominance=0.28, smoke_opacity=0.48, proximity_alert=False,
        hazard_level="HIGH", visual_narrative="Fire 28%",
        scores=ScoreContext(proximity_alert=False, obstruction=0, dominance=0.28),
        tracked_objects=[]
    )

    # Should get cache hit (same bucket)
    cached = await cache_agent.get_protocols_by_semantic_key(packet2)

    assert cached is not None
    assert len(cached) == 3
    assert cached[0]["protocol_text"] == sample_protocols[0]["protocol_text"]
    assert cache_agent.metrics["semantic_hits"] == 1


@pytest.mark.asyncio
async def test_semantic_cache_miss_different_bucket(cache_agent, sample_protocols):
    """Test cache miss when fire crosses into different bucket."""
    # Packet 1: 25% fire (MODERATE)
    packet1 = TelemetryPacket(
        device_id="test", session_id="test", timestamp=time.time(),
        fire_dominance=0.25, smoke_opacity=0.45, proximity_alert=False,
        hazard_level="HIGH", visual_narrative="Fire 25%",
        scores=ScoreContext(proximity_alert=False, obstruction=0, dominance=0.25),
        tracked_objects=[]
    )

    await cache_agent.cache_protocols_by_semantic_key(packet1, sample_protocols, ttl=300)

    # Packet 2: 45% fire (MAJOR - different bucket)
    packet2 = TelemetryPacket(
        device_id="test", session_id="test", timestamp=time.time(),
        fire_dominance=0.45, smoke_opacity=0.68, proximity_alert=False,
        hazard_level="CRITICAL", visual_narrative="Fire 45%",
        scores=ScoreContext(proximity_alert=False, obstruction=0, dominance=0.45),
        tracked_objects=[]
    )

    # Should be cache miss (different bucket)
    cached = await cache_agent.get_protocols_by_semantic_key(packet2)

    assert cached is None
    assert cache_agent.metrics["semantic_misses"] == 1


@pytest.mark.asyncio
async def test_semantic_cache_proximity_change(cache_agent, sample_protocols):
    """Test cache miss when proximity alert changes."""
    # Packet 1: No proximity
    packet1 = TelemetryPacket(
        device_id="test", session_id="test", timestamp=time.time(),
        fire_dominance=0.45, smoke_opacity=0.68, proximity_alert=False,
        hazard_level="HIGH", visual_narrative="Fire 45%",
        scores=ScoreContext(proximity_alert=False, obstruction=0, dominance=0.45),
        tracked_objects=[]
    )

    await cache_agent.cache_protocols_by_semantic_key(packet1, sample_protocols, ttl=300)

    # Packet 2: Proximity alert (person detected)
    packet2 = TelemetryPacket(
        device_id="test", session_id="test", timestamp=time.time(),
        fire_dominance=0.45, smoke_opacity=0.68, proximity_alert=True,
        hazard_level="CRITICAL", visual_narrative="Fire 45%. Person nearby.",
        scores=ScoreContext(proximity_alert=True, obstruction=0, dominance=0.45),
        tracked_objects=[]
    )

    # Should be cache miss (proximity changed)
    cached = await cache_agent.get_protocols_by_semantic_key(packet2)

    assert cached is None


@pytest.mark.asyncio
async def test_semantic_cache_ttl_expiration(cache_agent, sample_protocols, sample_packet_moderate):
    """Test cache expiration after TTL."""
    # Cache with 1-second TTL
    await cache_agent.cache_protocols_by_semantic_key(sample_packet_moderate, sample_protocols, ttl=1)

    # Immediate hit
    cached = await cache_agent.get_protocols_by_semantic_key(sample_packet_moderate)
    assert cached is not None

    # Wait for expiration
    await asyncio.sleep(1.5)

    # Should be expired
    cached = await cache_agent.get_protocols_by_semantic_key(sample_packet_moderate)
    assert cached is None


@pytest.mark.asyncio
async def test_all_fire_buckets(cache_agent, sample_protocols):
    """Test all four fire severity buckets."""
    fire_levels = [
        (0.05, "MINOR"),
        (0.15, "MODERATE"),
        (0.45, "MAJOR"),
        (0.75, "CRITICAL")
    ]

    for fire_pct, expected_bucket in fire_levels:
        packet = TelemetryPacket(
            device_id="test", session_id="test", timestamp=time.time(),
            fire_dominance=fire_pct, smoke_opacity=0.3, proximity_alert=False,
            hazard_level="HIGH", visual_narrative=f"Fire {fire_pct*100}%",
            scores=ScoreContext(proximity_alert=False, obstruction=0, dominance=fire_pct),
            tracked_objects=[]
        )

        key = cache_agent.get_semantic_cache_key(packet)
        assert expected_bucket in key


# ============================================================================
# LAYER 2: SESSION HISTORY CACHE TESTS (Unchanged)
# ============================================================================

@pytest.mark.asyncio
async def test_session_history_append(cache_agent, sample_vector):
    """Test appending incidents to session history."""
    await cache_agent.append_session_history(
        session_id="test_session",
        device_id="jetson_test",
        narrative="Small fire detected",
        vector=sample_vector,
        timestamp=time.time(),
        trend="STABLE",
        hazard_level="CAUTION"
    )

    # Verify stored in Redis
    history = await cache_agent.get_session_history(
        session_id="test_session",
        device_id="jetson_test",
        current_vector=sample_vector,
        similarity_threshold=0.50
    )

    assert len(history) == 1
    assert history[0]["narrative"] == "Small fire detected"
    assert history[0]["similarity"] >= 0.99  # Should be nearly identical


@pytest.mark.asyncio
async def test_session_history_similarity_search(cache_agent):
    """Test cosine similarity search in session history."""
    # Add 3 incidents with different vectors
    vectors = [
        [0.1, 0.2, 0.3] + [0.0] * 381,  # Incident 1
        [0.5, 0.6, 0.7] + [0.0] * 381,  # Incident 2
        [0.1, 0.2, 0.3] + [0.0] * 381,  # Incident 3 (similar to 1)
    ]

    for i, vec in enumerate(vectors):
        await cache_agent.append_session_history(
            session_id="test",
            device_id="jetson",
            narrative=f"Incident {i}",
            vector=vec,
            timestamp=time.time() + i,
            trend="STABLE",
            hazard_level="CAUTION"
        )

    # Query with vector similar to incident 1 and 3
    query_vector = [0.1, 0.2, 0.3] + [0.0] * 381

    results = await cache_agent.get_session_history(
        session_id="test",
        device_id="jetson",
        current_vector=query_vector,
        similarity_threshold=0.95,  # High threshold
        max_results=5
    )

    # Should return incidents 1 and 3 (similar), not 2
    assert len(results) >= 2
    assert all(r["similarity"] >= 0.95 for r in results)


@pytest.mark.asyncio
async def test_session_history_ttl(cache_agent, sample_vector):
    """Test session history expiration (30 minutes)."""
    await cache_agent.append_session_history(
        session_id="test",
        device_id="jetson",
        narrative="Test",
        vector=sample_vector,
        timestamp=time.time(),
        trend="STABLE",
        hazard_level="CAUTION"
    )

    # Check TTL is set (should be 1800 seconds = 30 minutes)
    # Note: This test just verifies the append worked; full TTL test would take 30 min
    history = await cache_agent.get_session_history(
        session_id="test",
        device_id="jetson",
        current_vector=sample_vector,
        similarity_threshold=0.50
    )

    assert len(history) == 1


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_full_cache_workflow(cache_agent, sample_packet_moderate, sample_protocols, sample_vector):
    """Test complete cache workflow: protocol cache + session history."""
    # Step 1: Cache protocols
    await cache_agent.cache_protocols_by_semantic_key(sample_packet_moderate, sample_protocols, ttl=300)

    # Step 2: Verify protocol cache hit
    cached_protocols = await cache_agent.get_protocols_by_semantic_key(sample_packet_moderate)
    assert cached_protocols is not None
    assert len(cached_protocols) == 3

    # Step 3: Write to session history
    await cache_agent.append_session_history(
        session_id=sample_packet_moderate.session_id,
        device_id=sample_packet_moderate.device_id,
        narrative=sample_packet_moderate.visual_narrative,
        vector=sample_vector,
        timestamp=sample_packet_moderate.timestamp,
        trend="RAPID_GROWTH",
        hazard_level=sample_packet_moderate.hazard_level
    )

    # Step 4: Verify session history retrieval
    history = await cache_agent.get_session_history(
        session_id=sample_packet_moderate.session_id,
        device_id=sample_packet_moderate.device_id,
        current_vector=sample_vector,
        similarity_threshold=0.70
    )

    assert len(history) >= 1
    assert cache_agent.metrics["session_hits"] == 1


@pytest.mark.asyncio
async def test_cache_stats_accuracy(cache_agent, sample_packet_moderate, sample_protocols):
    """Test cache statistics tracking."""
    # Generate some cache hits and misses
    await cache_agent.get_protocols_by_semantic_key(sample_packet_moderate)  # miss
    await cache_agent.cache_protocols_by_semantic_key(sample_packet_moderate, sample_protocols, ttl=300)
    await cache_agent.get_protocols_by_semantic_key(sample_packet_moderate)  # hit
    await cache_agent.get_protocols_by_semantic_key(sample_packet_moderate)  # hit

    stats = cache_agent.get_cache_stats()

    assert stats["semantic_protocol_cache"]["hits"] == 2
    assert stats["semantic_protocol_cache"]["misses"] == 1
    assert stats["semantic_protocol_cache"]["hit_rate"] == 2/3


@pytest.mark.asyncio
async def test_graceful_degradation_redis_unavailable():
    """Test graceful degradation when Redis is unavailable."""
    # Connect to non-existent Redis
    agent = RAGCacheAgent(redis_url="redis://localhost:9999")

    packet = TelemetryPacket(
        device_id="test", session_id="test", timestamp=time.time(),
        fire_dominance=0.45, smoke_opacity=0.68, proximity_alert=False,
        hazard_level="HIGH", visual_narrative="Test",
        scores=ScoreContext(proximity_alert=False, obstruction=0, dominance=0.45),
        tracked_objects=[]
    )

    # Should return None gracefully (not crash)
    cached = await agent.get_protocols_by_semantic_key(packet)
    assert cached is None


@pytest.mark.asyncio
async def test_metrics_reset(cache_agent, sample_packet_moderate, sample_protocols):
    """Test metrics reset functionality."""
    # Generate some activity
    await cache_agent.cache_protocols_by_semantic_key(sample_packet_moderate, sample_protocols, ttl=300)
    await cache_agent.get_protocols_by_semantic_key(sample_packet_moderate)

    # Reset metrics
    cache_agent.reset_metrics()

    stats = cache_agent.get_cache_stats()
    assert stats["semantic_protocol_cache"]["hits"] == 0
    assert stats["semantic_protocol_cache"]["misses"] == 0


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_semantic_cache_latency(cache_agent, sample_packet_moderate, sample_protocols):
    """Test semantic cache lookup latency."""
    await cache_agent.cache_protocols_by_semantic_key(sample_packet_moderate, sample_protocols, ttl=300)

    start = time.perf_counter()
    await cache_agent.get_protocols_by_semantic_key(sample_packet_moderate)
    latency_ms = (time.perf_counter() - start) * 1000

    # Should be very fast (<10ms)
    assert latency_ms < 10


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
