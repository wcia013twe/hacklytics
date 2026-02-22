#!/usr/bin/env python3
"""
Test Redis cache layer for RAG pipeline.

Tests:
1. Semantic protocol cache (YOLO fire buckets)
2. Session history cache (sorted sets)
3. Cache hit rate under realistic scenarios
4. Cache metrics and monitoring
"""

import os
import asyncio
import pytest
import time
from backend.agents.redis_cache import RAGCacheAgent

# Environment variables
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


class MockPacket:
    """Mock telemetry packet for testing."""
    def __init__(self, fire_dominance, smoke_opacity, proximity_alert, hazard_level):
        self.fire_dominance = fire_dominance
        self.smoke_opacity = smoke_opacity
        self.proximity_alert = proximity_alert
        self.hazard_level = hazard_level


@pytest.fixture
def cache():
    """Fixture to provide Redis cache agent."""
    cache_agent = RAGCacheAgent(redis_url=REDIS_URL)
    cache_agent.reset_metrics()
    yield cache_agent
    # Cleanup
    cache_agent.redis.flushdb()


@pytest.mark.asyncio
async def test_redis_connection(cache):
    """
    Test 1: Verify Redis connection is healthy.
    """
    print("\n=== Test 1: Redis Connection ===")

    is_healthy = await cache.health_check()
    assert is_healthy is True, "Redis connection not healthy"
    print("  ✓ Redis connection is healthy")


@pytest.mark.asyncio
async def test_semantic_cache_key_generation(cache):
    """
    Test 2: Verify semantic cache keys are deterministic and cover 128 states.
    """
    print("\n=== Test 2: Semantic Cache Key Generation ===")

    # Test boundary conditions for fire buckets
    test_cases = [
        (0.05, 0.1, False, "LOW", "FIRE_MINOR|SMOKE_CLEAR|PROX_FAR|LOW"),
        (0.15, 0.3, False, "MODERATE", "FIRE_MODERATE|SMOKE_HAZY|PROX_FAR|MODERATE"),
        (0.45, 0.6, True, "HIGH", "FIRE_MAJOR|SMOKE_DENSE|PROX_NEAR|HIGH"),
        (0.75, 0.9, True, "CRITICAL", "FIRE_CRITICAL|SMOKE_BLINDING|PROX_NEAR|CRITICAL"),
    ]

    print("\n  Testing semantic bucket boundaries:")
    for fire, smoke, prox, hazard, expected_key in test_cases:
        packet = MockPacket(fire, smoke, prox, hazard)
        key = cache.get_semantic_cache_key(packet)
        assert key == expected_key, f"Expected {expected_key}, got {key}"
        print(f"    ✓ {expected_key}")

    print("\n  ✓ Semantic cache key generation test PASSED")


@pytest.mark.asyncio
async def test_protocol_caching(cache):
    """
    Test 3: Verify protocol caching and retrieval.
    """
    print("\n=== Test 3: Protocol Caching & Retrieval ===")

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

    print("\n  ✓ Protocol caching test PASSED")


@pytest.mark.asyncio
async def test_session_history_cache(cache):
    """
    Test 4: Verify session history caching and vectorized similarity search.
    """
    print("\n=== Test 4: Session History Cache ===")

    session_id = "test_session_001"
    device_id = "jetson_test"

    # Append 3 incidents to session history
    incidents = [
        ("Smoke detected in hallway", [0.1] * 384, 1.0, "STABLE", "LOW"),
        ("Fire growing in corner", [0.5] * 384, 2.0, "GROWING", "MODERATE"),
        ("Person spotted near fire", [0.8] * 384, 3.0, "RAPID_GROWTH", "HIGH"),
    ]

    print(f"  Appending {len(incidents)} incidents to session history...")
    for narrative, vector, timestamp, trend, hazard in incidents:
        await cache.append_session_history(
            session_id=session_id,
            device_id=device_id,
            narrative=narrative,
            vector=vector,
            timestamp=time.time() - (4.0 - timestamp),
            trend=trend,
            hazard_level=hazard
        )

    print(f"  ✓ Appended {len(incidents)} incidents")

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
    print("\n  Similar incidents:")
    for i, incident in enumerate(results):
        print(f"    {i+1}. {incident['narrative']} (sim={incident['similarity']:.3f}, {incident['time_ago']:.1f}s ago)")

    print("\n  ✓ Session history cache test PASSED")


@pytest.mark.asyncio
async def test_cache_hit_rate_simulation(cache):
    """
    Test 5: Simulate realistic fire growth and measure cache hit rate.
    """
    print("\n=== Test 5: Cache Hit Rate Simulation ===")

    # Simulate fire growing from 5% → 70% over 20 packets
    # Fire buckets: MINOR (5-9%), MODERATE (10-29%), MAJOR (30-59%), CRITICAL (60-70%)
    # Expected: 3-5 packets per bucket before transition = high hit rate

    print("  Simulating fire growth from 5% to 70% over 20 packets...")

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

    # Expect 70%+ hit rate (some buckets have 3-5 consecutive packets)
    assert hit_rate >= 0.70, f"Expected hit rate ≥70%, got {hit_rate*100:.1f}%"

    print("\n  ✓ Cache hit rate simulation PASSED")


@pytest.mark.asyncio
async def test_cache_metrics(cache):
    """
    Test 6: Verify cache metrics tracking.
    """
    print("\n=== Test 6: Cache Metrics ===")

    # Perform some cache operations
    packet = MockPacket(0.25, 0.45, False, "MODERATE")

    # First call - miss
    await cache.get_protocols_by_semantic_key(packet)

    # Cache data
    await cache.cache_protocols_by_semantic_key(packet, [{"test": "data"}], ttl=300)

    # Second call - hit
    await cache.get_protocols_by_semantic_key(packet)

    # Get stats
    stats = cache.get_cache_stats()

    print("\n  Semantic Protocol Cache:")
    print(f"    Hits: {stats['semantic_protocol_cache']['hits']}")
    print(f"    Misses: {stats['semantic_protocol_cache']['misses']}")
    print(f"    Hit Rate: {stats['semantic_protocol_cache']['hit_rate']*100:.1f}%")
    print(f"    Avg Latency: {stats['semantic_protocol_cache']['avg_latency_ms']:.2f}ms")

    assert stats['semantic_protocol_cache']['hits'] == 1
    assert stats['semantic_protocol_cache']['misses'] == 1
    assert stats['semantic_protocol_cache']['hit_rate'] == 0.5

    print("\n  ✓ Cache metrics test PASSED")


@pytest.mark.asyncio
async def test_cache_ttl_expiration(cache):
    """
    Test 7: Verify cache entries expire after TTL.
    """
    print("\n=== Test 7: Cache TTL Expiration ===")

    packet = MockPacket(0.35, 0.55, True, "HIGH")

    # Cache with 2 second TTL
    print("  Caching protocols with 2s TTL...")
    await cache.cache_protocols_by_semantic_key(packet, [{"test": "data"}], ttl=2)

    # Immediate retrieval should hit
    result = await cache.get_protocols_by_semantic_key(packet)
    assert result is not None, "Expected cache hit immediately after caching"
    print("  ✓ Cache hit immediately after caching")

    # Wait for expiration
    print("  Waiting 3 seconds for TTL expiration...")
    await asyncio.sleep(3)

    # Should be expired
    result = await cache.get_protocols_by_semantic_key(packet)
    assert result is None, "Expected cache miss after TTL expiration"
    print("  ✓ Cache miss after TTL expiration")

    print("\n  ✓ Cache TTL expiration test PASSED")


@pytest.mark.asyncio
async def test_cache_graceful_degradation(cache):
    """
    Test 8: Verify cache handles errors gracefully.
    """
    print("\n=== Test 8: Graceful Degradation ===")

    # Close Redis connection to simulate failure
    await cache.close()
    print("  Simulated Redis connection failure")

    # Operations should not raise exceptions
    packet = MockPacket(0.35, 0.55, True, "HIGH")

    try:
        result = await cache.get_protocols_by_semantic_key(packet)
        assert result is None, "Expected None on Redis failure"
        print("  ✓ get_protocols_by_semantic_key handles failure gracefully")

        await cache.cache_protocols_by_semantic_key(packet, [{"test": "data"}], ttl=300)
        print("  ✓ cache_protocols_by_semantic_key handles failure gracefully")

        print("\n  ✓ Graceful degradation test PASSED")

    except Exception as e:
        pytest.fail(f"Cache should handle Redis failures gracefully, but raised: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
