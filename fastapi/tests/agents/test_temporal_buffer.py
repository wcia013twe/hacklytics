"""Unit tests for TemporalBufferAgent."""
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


@pytest.fixture
def sample_packet():
    """Create a sample telemetry packet."""
    return TelemetryPacket(
        device_id="jetson_alpha",
        session_id="mission_001",
        timestamp=time.time(),
        hazard_level="HIGH",
        scores=Scores(fire_dominance=0.5, smoke_opacity=0.6, proximity_alert=True),
        tracked_objects=[
            TrackedObject(id=1, label="fire", status="tracked", duration_in_frame=2.5)
        ],
        visual_narrative="Fire detected"
    )


@pytest.mark.asyncio
async def test_insert_first_packet(agent, sample_packet):
    """Test inserting first packet creates buffer."""
    result = await agent.insert_packet("jetson_alpha", sample_packet)

    assert result["inserted"] is True
    assert result["buffer_size"] == 1
    assert "jetson_alpha" in agent.buffers


@pytest.mark.asyncio
async def test_insert_multiple_packets(agent):
    """Test inserting multiple packets in order."""
    current_time = time.time()

    for i in range(5):
        packet = TelemetryPacket(
            device_id="jetson_alpha",
            session_id="mission_001",
            timestamp=current_time + i,
            hazard_level="HIGH",
            scores=Scores(fire_dominance=0.5 + i * 0.1, smoke_opacity=0.6, proximity_alert=True),
            tracked_objects=[],
            visual_narrative="Fire detected"
        )
        result = await agent.insert_packet("jetson_alpha", packet)
        assert result["inserted"] is True

    assert len(agent.buffers["jetson_alpha"]) == 5


@pytest.mark.asyncio
async def test_out_of_order_insertion(agent):
    """Test handling of out-of-order packets."""
    current_time = time.time()

    # Insert packets out of order
    packets = [
        (current_time + 0, 0.1),
        (current_time + 2, 0.3),
        (current_time + 1, 0.2),  # Out of order
    ]

    for ts, fire_val in packets:
        packet = TelemetryPacket(
            device_id="jetson_alpha",
            session_id="mission_001",
            timestamp=ts,
            hazard_level="HIGH",
            scores=Scores(fire_dominance=fire_val, smoke_opacity=0.6, proximity_alert=True),
            tracked_objects=[],
            visual_narrative="Fire"
        )
        await agent.insert_packet("jetson_alpha", packet)

    # Verify packets are in chronological order
    buffer = list(agent.buffers["jetson_alpha"])
    timestamps = [p["timestamp"] for p in buffer]
    assert timestamps == sorted(timestamps)


@pytest.mark.asyncio
async def test_evict_stale_packets(agent):
    """Test eviction of packets older than window."""
    current_time = time.time()

    # Insert old packet (15 seconds ago, outside 10s window)
    old_packet = TelemetryPacket(
        device_id="jetson_alpha",
        session_id="mission_001",
        timestamp=current_time - 15,
        hazard_level="HIGH",
        scores=Scores(fire_dominance=0.3, smoke_opacity=0.6, proximity_alert=True),
        tracked_objects=[],
        visual_narrative="Old fire"
    )

    result = await agent.insert_packet("jetson_alpha", old_packet)
    assert result["inserted"] is False
    assert result["reason"] == "too_old"


@pytest.mark.asyncio
async def test_compute_trend_rapid_growth(agent):
    """Test trend computation for rapid fire growth."""
    current_time = time.time()

    # Simulate linear increase from 0.1 to 0.6 over 4 seconds (0.125/s growth)
    for i in range(10):
        packet = TelemetryPacket(
            device_id="jetson_alpha",
            session_id="mission_001",
            timestamp=current_time + i * 0.5,
            hazard_level="HIGH",
            scores=Scores(
                fire_dominance=0.1 + i * 0.055,  # Creates >0.10/s growth rate
                smoke_opacity=0.6,
                proximity_alert=True
            ),
            tracked_objects=[],
            visual_narrative="Fire"
        )
        await agent.insert_packet("jetson_alpha", packet)

    trend = await agent.compute_trend("jetson_alpha")

    assert trend.trend_tag == "RAPID_GROWTH"
    assert trend.growth_rate > 0.10
    assert trend.sample_count == 10


@pytest.mark.asyncio
async def test_compute_trend_stable(agent):
    """Test trend computation for stable fire."""
    current_time = time.time()

    # Hold at 0.3 over 10 packets
    for i in range(10):
        packet = TelemetryPacket(
            device_id="jetson_alpha",
            session_id="mission_001",
            timestamp=current_time + i * 0.5,
            hazard_level="MODERATE",
            scores=Scores(fire_dominance=0.3, smoke_opacity=0.6, proximity_alert=True),
            tracked_objects=[],
            visual_narrative="Fire"
        )
        await agent.insert_packet("jetson_alpha", packet)

    trend = await agent.compute_trend("jetson_alpha")

    assert trend.trend_tag == "STABLE"
    assert -0.05 <= trend.growth_rate <= 0.02


@pytest.mark.asyncio
async def test_compute_trend_diminishing(agent):
    """Test trend computation for diminishing fire."""
    current_time = time.time()

    # Decrease from 0.5 to 0.2 over 4 seconds
    for i in range(10):
        packet = TelemetryPacket(
            device_id="jetson_alpha",
            session_id="mission_001",
            timestamp=current_time + i * 0.5,
            hazard_level="MODERATE",
            scores=Scores(
                fire_dominance=0.5 - i * 0.035,  # Creates <-0.05/s growth rate
                smoke_opacity=0.6,
                proximity_alert=True
            ),
            tracked_objects=[],
            visual_narrative="Fire"
        )
        await agent.insert_packet("jetson_alpha", packet)

    trend = await agent.compute_trend("jetson_alpha")

    assert trend.trend_tag == "DIMINISHING"
    assert trend.growth_rate < -0.05


@pytest.mark.asyncio
async def test_compute_trend_unknown_insufficient_data(agent):
    """Test trend returns UNKNOWN with insufficient data."""
    trend = await agent.compute_trend("nonexistent_device")

    assert trend.trend_tag == "UNKNOWN"
    assert trend.growth_rate == 0.0
    assert trend.sample_count == 0


@pytest.mark.asyncio
async def test_linear_regression_slope(agent):
    """Test linear regression slope calculation."""
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [2.0, 4.0, 6.0, 8.0, 10.0]  # Perfect linear: y = 2x

    slope = agent._linear_regression_slope(x, y)

    assert abs(slope - 2.0) < 0.01  # Should be very close to 2.0
