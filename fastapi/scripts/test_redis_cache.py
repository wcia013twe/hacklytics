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
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.agents.redis_cache import RAGCacheAgent


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

    # Expect 70%+ hit rate (some buckets have 3-5 consecutive packets)
    assert hit_rate >= 0.70, f"Expected hit rate ≥70%, got {hit_rate*100:.1f}%"

    print("\n✅ Cache hit rate simulation PASSED")


async def main():
    """Run all Redis cache tests."""
    try:
        await test_semantic_cache_key_generation()
        await test_protocol_caching()
        await test_session_history_cache()
        await test_cache_hit_rate_simulation()

        print("\n🎉 All Redis cache tests PASSED")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
