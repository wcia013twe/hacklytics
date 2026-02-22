"""
Comprehensive tests for Priority Queue system in TemporalBufferAgent.

Tests cover:
1. Priority classification (auto + manual)
2. Priority-based TTL (CRITICAL=30s, CAUTION=10s, SAFE=5s)
3. Decay weight calculation
4. Narrative compression with critical info preservation
5. Latency improvements from compression
"""
import pytest
import time
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.agents.temporal_buffer import TemporalBufferAgent
from backend.contracts.models import TelemetryPacket, Scores, TrackedObject


@pytest.fixture
def agent():
    return TemporalBufferAgent(window_seconds=10.0)


def create_packet(
    device_id="jetson_alpha",
    timestamp=None,
    hazard_level="HIGH",
    fire_dominance=0.5,
    narrative="Fire detected",
    priority=None
):
    """Helper to create test packets."""
    if timestamp is None:
        timestamp = time.time()

    return TelemetryPacket(
        device_id=device_id,
        session_id="mission_001",
        timestamp=timestamp,
        hazard_level=hazard_level,
        scores=Scores(
            fire_dominance=fire_dominance,
            smoke_opacity=0.6,
            proximity_alert=True
        ),
        tracked_objects=[],
        visual_narrative=narrative,
        priority=priority
    )


# ============================================================================
# PRIORITY CLASSIFICATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_priority_classification_critical_hazard(agent):
    """Test auto-classification: CRITICAL hazard level -> CRITICAL priority."""
    packet = create_packet(hazard_level="CRITICAL", narrative="Large fire")
    priority = agent._classify_priority(packet)
    assert priority == "CRITICAL"


@pytest.mark.asyncio
async def test_priority_classification_critical_keywords(agent):
    """Test auto-classification: Keywords like 'explosion' -> CRITICAL priority."""
    packet = create_packet(hazard_level="HIGH", narrative="Explosion risk detected")
    priority = agent._classify_priority(packet)
    assert priority == "CRITICAL"

    packet2 = create_packet(hazard_level="MODERATE", narrative="Person trapped in room")
    priority2 = agent._classify_priority(packet2)
    assert priority2 == "CRITICAL"


@pytest.mark.asyncio
async def test_priority_classification_safe_keywords(agent):
    """Test auto-classification: Keywords like 'clear' -> SAFE priority."""
    packet = create_packet(hazard_level="LOW", narrative="Area is clear")
    priority = agent._classify_priority(packet)
    assert priority == "SAFE"

    packet2 = create_packet(hazard_level="MODERATE", narrative="Fire is contained")
    priority2 = agent._classify_priority(packet2)
    assert priority2 == "SAFE"


@pytest.mark.asyncio
async def test_priority_classification_caution_default(agent):
    """Test auto-classification: DEFAULT -> CAUTION priority."""
    packet = create_packet(hazard_level="MODERATE", narrative="Smoke detected")
    priority = agent._classify_priority(packet)
    assert priority == "CAUTION"


@pytest.mark.asyncio
async def test_priority_classification_manual_override(agent):
    """Test that explicit priority field overrides auto-classification."""
    packet = create_packet(
        hazard_level="LOW",
        narrative="Clear",
        priority="CRITICAL"  # Manual override
    )
    priority = agent._classify_priority(packet)
    assert priority == "CRITICAL"


# ============================================================================
# PRIORITY-BASED TTL TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_ttl_critical_events_30s(agent):
    """Test CRITICAL events stay for 30 seconds."""
    current_time = time.time()

    # Insert critical event 25 seconds ago (within 30s TTL)
    packet = create_packet(
        timestamp=current_time - 25,
        hazard_level="CRITICAL",
        narrative="Explosion risk"
    )

    result = await agent.insert_packet("jetson_alpha", packet)

    assert result["inserted"] is True
    assert result["priority"] == "CRITICAL"
    assert result["ttl"] == 30.0


@pytest.mark.asyncio
async def test_ttl_safe_events_5s(agent):
    """Test SAFE events expire after 5 seconds."""
    current_time = time.time()

    # Insert safe event 8 seconds ago (outside 5s TTL)
    packet = create_packet(
        timestamp=current_time - 8,
        hazard_level="CLEAR",
        narrative="Area is clear"
    )

    result = await agent.insert_packet("jetson_alpha", packet)

    assert result["inserted"] is False
    assert result["reason"] == "too_old"
    assert result["priority"] == "SAFE"
    assert result["ttl"] == 5.0


@pytest.mark.asyncio
async def test_ttl_caution_events_10s(agent):
    """Test CAUTION events stay for 10 seconds (default)."""
    current_time = time.time()

    # Insert caution event 7 seconds ago (within 10s TTL)
    packet = create_packet(
        timestamp=current_time - 7,
        hazard_level="MODERATE",
        narrative="Smoke detected"
    )

    result = await agent.insert_packet("jetson_alpha", packet)

    assert result["inserted"] is True
    assert result["priority"] == "CAUTION"
    assert result["ttl"] == 10.0


@pytest.mark.asyncio
async def test_eviction_respects_priority_ttl(agent):
    """
    Scenario: Safe event at t=-3s, critical event at t=-2s.
    At t=+7s (simulated), safe event should be evicted (expired after 5s TTL).
    Critical event should remain (within 30s TTL).
    """
    current_time = time.time()

    # Insert SAFE event 3 seconds ago (within 5s TTL, so it gets inserted)
    safe_packet = create_packet(
        timestamp=current_time - 3,
        hazard_level="CLEAR",
        narrative="Area clear"
    )
    result1 = await agent.insert_packet("jetson_alpha", safe_packet)
    assert result1["inserted"] is True  # Should be inserted (3s < 5s TTL)

    # Insert CRITICAL event 2 seconds ago (within 30s TTL)
    critical_packet = create_packet(
        timestamp=current_time - 2,
        hazard_level="CRITICAL",
        narrative="Explosion imminent"
    )
    result2 = await agent.insert_packet("jetson_alpha", critical_packet)
    assert result2["inserted"] is True

    # Simulate time passing: 7 seconds from when SAFE event was created
    # SAFE event is now 10s old (current_time - 3 + 7 = 10s)
    # SAFE TTL is 5s, so it should be expired
    simulated_future_time = current_time + 7

    # Manually evict at simulated future time
    eviction_result = await agent.evict_stale("jetson_alpha", simulated_future_time)

    # SAFE event should be evicted (10s old, TTL=5s → expired at 8s)
    # CRITICAL event should remain (9s old, TTL=30s → still valid)
    assert eviction_result["evicted_count"] >= 1
    assert len(agent.buffers["jetson_alpha"]) >= 1

    # Verify only critical remains
    remaining = list(agent.buffers["jetson_alpha"])
    assert all(p.get("priority") in ["CRITICAL", "CAUTION"] for p in remaining)


# ============================================================================
# DECAY WEIGHT TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_decay_weight_recent_events(agent):
    """Test recent events (<=3s) get weight=1.0."""
    weight = agent._calculate_decay_weight(packet_age=2.0, priority="CAUTION")
    assert weight == 1.0


@pytest.mark.asyncio
async def test_decay_weight_mid_age_events(agent):
    """Test mid-age events (3-10s) get weight=0.5."""
    weight = agent._calculate_decay_weight(packet_age=5.0, priority="CAUTION")
    assert weight == 0.5


@pytest.mark.asyncio
async def test_decay_weight_old_critical_events(agent):
    """Test old critical events (>10s) get weight=0.3."""
    weight = agent._calculate_decay_weight(packet_age=15.0, priority="CRITICAL")
    assert weight == 0.3


@pytest.mark.asyncio
async def test_decay_weight_old_noncritical_events(agent):
    """Test old non-critical events (>10s) get weight=0.1."""
    weight = agent._calculate_decay_weight(packet_age=15.0, priority="SAFE")
    assert weight == 0.1


# ============================================================================
# NARRATIVE COMPRESSION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_compress_narrative_under_limit(agent):
    """Test compression when total narrative is under 500 chars."""
    current_time = time.time()

    packets = [
        {
            "timestamp": current_time - 1,
            "packet": create_packet(narrative="Fire small", timestamp=current_time - 1),
            "priority": "CAUTION"
        },
        {
            "timestamp": current_time - 2,
            "packet": create_packet(narrative="Smoke detected", timestamp=current_time - 2),
            "priority": "CAUTION"
        }
    ]

    result = await agent.compress_narrative(packets, max_chars=500)

    assert result["compressed_length"] <= 500
    assert result["events_included"] == 2
    assert result["events_excluded"] == 0
    assert "Fire small" in result["narrative"]
    assert "Smoke detected" in result["narrative"]


@pytest.mark.asyncio
async def test_compress_narrative_over_limit(agent):
    """
    Test compression when total narrative exceeds 500 chars.
    Verify critical events are preserved.
    """
    current_time = time.time()

    # Create mix of critical and safe events with long narratives
    packets = []
    for i in range(10):
        priority = "CRITICAL" if i % 3 == 0 else "SAFE"
        narrative = f"Event {i}: " + "x" * 50  # ~60 chars each
        packets.append({
            "timestamp": current_time - i,
            "packet": create_packet(
                narrative=narrative,
                timestamp=current_time - i,
                hazard_level="CRITICAL" if priority == "CRITICAL" else "LOW"
            ),
            "priority": priority
        })

    result = await agent.compress_narrative(packets, max_chars=500)

    assert result["compressed_length"] <= 500
    assert result["events_excluded"] > 0
    assert result["critical_events_retained"] > 0
    # Critical events should dominate the compressed narrative
    assert "Event 0" in result["narrative"]  # Most recent critical


@pytest.mark.asyncio
async def test_compress_narrative_preserves_critical_info(agent):
    """
    Scenario: Mix of critical + safe events.
    Verify critical events dominate the narrative.
    """
    current_time = time.time()

    packets = [
        {
            "timestamp": current_time - 1,
            "packet": create_packet(
                narrative="Explosion risk detected near fuel tanks",
                timestamp=current_time - 1,
                hazard_level="CRITICAL"
            ),
            "priority": "CRITICAL"
        },
        {
            "timestamp": current_time - 2,
            "packet": create_packet(
                narrative="Area on west side is clear and stable",
                timestamp=current_time - 2,
                hazard_level="LOW"
            ),
            "priority": "SAFE"
        },
        {
            "timestamp": current_time - 3,
            "packet": create_packet(
                narrative="Person trapped on second floor",
                timestamp=current_time - 3,
                hazard_level="CRITICAL"
            ),
            "priority": "CRITICAL"
        }
    ]

    result = await agent.compress_narrative(packets, max_chars=200)

    # Critical events should be included
    assert "Explosion risk" in result["narrative"] or "trapped" in result["narrative"]
    assert result["critical_events_retained"] >= 1


@pytest.mark.asyncio
async def test_compress_narrative_1000_chars_to_500(agent):
    """
    Scenario: 1000-char narrative compresses to 500 chars.
    Verify compression preserves critical info.
    """
    current_time = time.time()

    # Create 1000+ char narrative
    packets = []
    critical_narrative = "CRITICAL: Explosion imminent in Building A, evacuate immediately"
    safe_narrative = "Safe zone established in parking lot, all personnel accounted for"

    # Add 1 critical event
    packets.append({
        "timestamp": current_time - 1,
        "packet": create_packet(
            narrative=critical_narrative,
            timestamp=current_time - 1,
            hazard_level="CRITICAL"
        ),
        "priority": "CRITICAL"
    })

    # Add many safe events to exceed 1000 chars
    for i in range(20):
        packets.append({
            "timestamp": current_time - (i + 2),
            "packet": create_packet(
                narrative=safe_narrative + f" zone {i}",
                timestamp=current_time - (i + 2),
                hazard_level="LOW"
            ),
            "priority": "SAFE"
        })

    result = await agent.compress_narrative(packets, max_chars=500)

    assert result["original_length"] > 1000
    assert result["compressed_length"] <= 500
    assert result["compression_ratio"] < 0.5
    # Critical event should be preserved
    assert "CRITICAL" in result["narrative"]
    assert result["critical_events_retained"] == 1


# ============================================================================
# LATENCY IMPROVEMENT TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_compression_reduces_narrative_length(agent):
    """
    Latency test: Verify compression reduces narrative length,
    which would reduce embedding time.
    """
    current_time = time.time()

    # Create many packets with long narratives
    packets = []
    for i in range(50):
        narrative = f"Sensor {i}: Fire detected with smoke levels rising, temperature at 500F, visibility low"
        packets.append({
            "timestamp": current_time - i,
            "packet": create_packet(
                narrative=narrative,
                timestamp=current_time - i
            ),
            "priority": "CAUTION"
        })

    result = await agent.compress_narrative(packets, max_chars=500)

    # Verify significant compression
    assert result["original_length"] > 2000  # ~100 chars * 50 = 5000+ chars
    assert result["compressed_length"] <= 500
    assert result["compression_ratio"] < 0.25

    # In production, this would translate to:
    # - Shorter embedding time (fewer tokens)
    # - Faster vector search (more focused query)
    # - Less noise in retrieval results


# ============================================================================
# METRICS TRACKING TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_metrics_tracking(agent):
    """Test that metrics are properly tracked."""
    current_time = time.time()

    # Insert some packets
    for i in range(5):
        packet = create_packet(
            timestamp=current_time - i,
            hazard_level="CRITICAL" if i % 2 == 0 else "LOW"
        )
        await agent.insert_packet("jetson_alpha", packet)

    # Compress narrative to populate metrics
    packets = list(agent.buffers["jetson_alpha"])
    await agent.compress_narrative(packets, max_chars=500)

    # Get metrics summary
    summary = agent.get_metrics_summary()

    assert summary["total_events_processed"] == 5
    assert summary["critical_events_retained"] == 3  # 0, 2, 4
    assert summary["avg_narrative_length"] > 0
    assert 0.0 <= summary["avg_compression_ratio"] <= 1.0


# ============================================================================
# BACKWARD COMPATIBILITY TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_backward_compatibility_no_priority_field(agent):
    """Test that packets without priority field still work (auto-classification)."""
    packet = create_packet(hazard_level="HIGH", narrative="Fire detected")
    # Don't set priority field (None by default)

    result = await agent.insert_packet("jetson_alpha", packet)

    assert result["inserted"] is True
    assert result["priority"] in ["CRITICAL", "CAUTION", "SAFE"]


@pytest.mark.asyncio
async def test_backward_compatibility_existing_tests(agent):
    """
    Ensure existing temporal_buffer tests still pass.
    This test mimics the existing test_insert_first_packet.
    """
    current_time = time.time()
    packet = create_packet(timestamp=current_time)

    result = await agent.insert_packet("jetson_alpha", packet)

    assert result["inserted"] is True
    assert result["buffer_size"] == 1
    assert "jetson_alpha" in agent.buffers


@pytest.mark.asyncio
async def test_edge_case_empty_narrative_compression(agent):
    """Test compression with empty packets list."""
    result = await agent.compress_narrative([], max_chars=500)

    assert result["narrative"] == ""
    assert result["original_length"] == 0
    assert result["compressed_length"] == 0
    assert result["compression_ratio"] == 1.0


@pytest.mark.asyncio
async def test_integration_full_pipeline(agent):
    """
    Integration test: Full pipeline with priority queue, eviction, and compression.
    """
    current_time = time.time()

    # Scenario: Safe event at t=0, critical at t=8, safe at t=9
    events = [
        ("SAFE", current_time - 10, "Area is clear"),
        ("CRITICAL", current_time - 2, "Explosion imminent"),
        ("SAFE", current_time - 1, "North wing stable")
    ]

    for priority_hint, ts, narrative in events:
        packet = create_packet(
            timestamp=ts,
            hazard_level=priority_hint if priority_hint != "SAFE" else "LOW",
            narrative=narrative
        )
        await agent.insert_packet("jetson_alpha", packet)

    # Evict stale events
    await agent.evict_stale("jetson_alpha", current_time)

    # Only recent events should remain (SAFE from t=0 should be evicted)
    buffer = list(agent.buffers["jetson_alpha"])
    assert len(buffer) >= 1

    # Compress narrative
    result = await agent.compress_narrative(buffer, max_chars=500)

    # Critical event should dominate
    assert "Explosion" in result["narrative"]
    assert result["critical_events_retained"] >= 1
