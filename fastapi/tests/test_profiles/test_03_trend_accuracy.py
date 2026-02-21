import pytest
import sys
import os
import time

# Add backend to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.agents.temporal_buffer import TemporalBufferAgent
from backend.contracts.models import TelemetryPacket, Scores, TrackedObject


@pytest.fixture
def buffer_agent():
    return TemporalBufferAgent(window_seconds=10)


def create_packet(device_id: str, timestamp: float, fire_dominance: float):
    """Helper to create test packets"""
    return TelemetryPacket(
        device_id=device_id,
        session_id="test_session",
        timestamp=timestamp,
        hazard_level="MODERATE",
        scores=Scores(
            fire_dominance=fire_dominance,
            smoke_opacity=0.3,
            proximity_alert=False
        ),
        tracked_objects=[],
        visual_narrative="Test narrative"
    )


@pytest.mark.asyncio
async def test_trend_rapid_growth(buffer_agent):
    """
    Test Profile 3A: RAPID_GROWTH detection

    Sequence: fire_dominance increases from 0.1 to 1.0 over 9 seconds
    Expected: growth_rate ≈ 0.11/s, trend_tag = RAPID_GROWTH

    THRESHOLD (from RAG.MD 3.4.2): growth_rate > 0.10/s = RAPID_GROWTH
    """
    device_id = "test_device_growth"
    base_time = time.time()

    # Insert 10 packets with steep linear growth
    # 0.1 → 1.0 over 9s = ~0.11/s growth rate (exceeds RAPID_GROWTH threshold)
    for i in range(10):
        packet = create_packet(
            device_id=device_id,
            timestamp=base_time + i,
            fire_dominance=0.1 + i * 0.10  # 0.1 → 1.0 over 9s = ~0.11/s
        )
        await buffer_agent.insert_packet(device_id, packet)

    # Compute trend
    trend = await buffer_agent.compute_trend(device_id)

    print(f"\nRAPID_GROWTH Test:")
    print(f"  Trend: {trend.trend_tag}")
    print(f"  Growth rate: {trend.growth_rate:.4f}/s")
    print(f"  Sample count: {trend.sample_count}")
    print(f"  Time span: {trend.time_span:.2f}s")

    # Validate trend tag (CRITICAL: must match RAG.MD 3.4.2 threshold)
    assert trend.trend_tag == "RAPID_GROWTH", f"Expected RAPID_GROWTH, got {trend.trend_tag}"

    # Validate growth rate is >0.10/s (RAPID_GROWTH threshold from RAG.MD 3.4.2)
    assert trend.growth_rate > 0.10, f"Growth rate {trend.growth_rate:.4f} should be >0.10/s"

    # Validate output fields match new spec (sample_count, time_span, not confidence)
    assert trend.sample_count == 10, f"Expected 10 samples, got {trend.sample_count}"
    assert 8.5 <= trend.time_span <= 9.5, f"Time span {trend.time_span:.2f}s should be ~9s"

    print("✅ PASS: RAPID_GROWTH detected correctly")


@pytest.mark.asyncio
async def test_trend_stable(buffer_agent):
    """
    Test Profile 3B: STABLE detection

    Sequence: fire_dominance constant at 0.3
    Expected: growth_rate ≈ 0.0, trend_tag = STABLE
    """
    device_id = "test_device_stable"
    base_time = time.time()

    for i in range(10):
        packet = create_packet(
            device_id=device_id,
            timestamp=base_time + i,
            fire_dominance=0.3  # Constant
        )
        await buffer_agent.insert_packet(device_id, packet)

    trend = await buffer_agent.compute_trend(device_id)

    print(f"\nSTABLE Test:")
    print(f"  Trend: {trend.trend_tag}")
    print(f"  Growth rate: {trend.growth_rate:.4f}/s")

    assert trend.trend_tag == "STABLE", f"Expected STABLE, got {trend.trend_tag}"
    assert abs(trend.growth_rate) < 0.005, f"Growth rate {trend.growth_rate:.4f} should be ~0"

    print("✅ PASS: STABLE detected correctly")


@pytest.mark.asyncio
async def test_trend_diminishing(buffer_agent):
    """
    Test Profile 3C: DIMINISHING detection

    Sequence: fire_dominance decreases from 0.5 to 0.2 over 10 seconds
    Expected: growth_rate ≈ -0.03/s, trend_tag = DIMINISHING
    """
    device_id = "test_device_diminishing"
    base_time = time.time()

    for i in range(10):
        packet = create_packet(
            device_id=device_id,
            timestamp=base_time + i,
            fire_dominance=0.5 - i * 0.03  # 0.5 → 0.2
        )
        await buffer_agent.insert_packet(device_id, packet)

    trend = await buffer_agent.compute_trend(device_id)

    print(f"\nDIMINISHING Test:")
    print(f"  Trend: {trend.trend_tag}")
    print(f"  Growth rate: {trend.growth_rate:.4f}/s")

    assert trend.trend_tag == "DIMINISHING", f"Expected DIMINISHING, got {trend.trend_tag}"
    assert abs(trend.growth_rate - (-0.03)) < 0.01, f"Growth rate {trend.growth_rate:.4f} != -0.03 (±0.01)"

    print("✅ PASS: DIMINISHING detected correctly")


@pytest.mark.asyncio
async def test_trend_insufficient_data(buffer_agent):
    """
    Test edge case: <2 packets should return UNKNOWN
    """
    device_id = "test_device_unknown"
    base_time = time.time()

    # Insert only 1 packet
    packet = create_packet(device_id, base_time, 0.3)
    await buffer_agent.insert_packet(device_id, packet)

    trend = await buffer_agent.compute_trend(device_id)

    print(f"\nUNKNOWN Test:")
    print(f"  Trend: {trend.trend_tag}")
    print(f"  Sample count: {trend.sample_count}")

    assert trend.trend_tag == "UNKNOWN", f"Expected UNKNOWN with <2 packets, got {trend.trend_tag}"
    assert trend.sample_count == 1

    print("✅ PASS: UNKNOWN returned for insufficient data")


@pytest.mark.asyncio
async def test_trend_growing(buffer_agent):
    """
    Test Profile 3D: GROWING detection

    Sequence: fire_dominance increases moderately
    Expected: 0.02 < growth_rate ≤ 0.10, trend_tag = GROWING
    """
    device_id = "test_device_growing"
    base_time = time.time()

    # Create growth of 0.05/s (between GROWING thresholds 0.02 and 0.10)
    for i in range(10):
        packet = create_packet(
            device_id=device_id,
            timestamp=base_time + i,
            fire_dominance=0.3 + i * 0.05  # 0.3 → 0.75 over 9s = ~0.05/s
        )
        await buffer_agent.insert_packet(device_id, packet)

    trend = await buffer_agent.compute_trend(device_id)

    print(f"\nGROWING Test:")
    print(f"  Trend: {trend.trend_tag}")
    print(f"  Growth rate: {trend.growth_rate:.4f}/s")

    assert trend.trend_tag == "GROWING", f"Expected GROWING, got {trend.trend_tag}"
    assert 0.02 < trend.growth_rate <= 0.10, f"Growth rate {trend.growth_rate:.4f} not in GROWING range (0.02, 0.10]"

    print("✅ PASS: GROWING detected correctly")
