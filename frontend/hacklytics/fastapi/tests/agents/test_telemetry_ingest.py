"""Unit tests for TelemetryIngestAgent."""
import pytest
import json
import time
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.agents.telemetry_ingest import TelemetryIngestAgent


@pytest.fixture
def agent():
    return TelemetryIngestAgent()


@pytest.fixture
def valid_packet_json():
    return json.dumps({
        "device_id": "jetson_alpha",
        "session_id": "mission_001",
        "timestamp": time.time(),
        "hazard_level": "HIGH",
        "scores": {
            "fire_dominance": 0.7,
            "smoke_opacity": 0.6,
            "proximity_alert": True
        },
        "tracked_objects": [
            {"id": 1, "label": "fire", "status": "tracked", "duration_in_frame": 2.5}
        ],
        "visual_narrative": "Fire detected in corridor"
    })


@pytest.mark.asyncio
async def test_validate_valid_packet(agent, valid_packet_json):
    """Test validation of valid packet."""
    valid, result = await agent.validate_schema(valid_packet_json)

    assert valid is True
    assert result["parsed_packet"] is not None
    assert result["errors"] == []
    assert agent.valid_count == 1
    assert agent.malformed_count == 0


@pytest.mark.asyncio
async def test_validate_invalid_json(agent):
    """Test validation of malformed JSON."""
    invalid_json = "{ invalid json }"

    valid, result = await agent.validate_schema(invalid_json)

    assert valid is False
    assert result["parsed_packet"] is None
    assert len(result["errors"]) > 0
    assert agent.malformed_count == 1
    assert agent.valid_count == 0


@pytest.mark.asyncio
async def test_validate_missing_field(agent):
    """Test validation with missing required field."""
    missing_field = json.dumps({
        "device_id": "jetson_alpha",
        # Missing session_id
        "timestamp": time.time(),
        "hazard_level": "HIGH",
        "scores": {
            "fire_dominance": 0.7,
            "smoke_opacity": 0.6,
            "proximity_alert": True
        },
        "tracked_objects": [],
        "visual_narrative": "Test"
    })

    valid, result = await agent.validate_schema(missing_field)

    assert valid is False
    assert result["parsed_packet"] is None
    assert agent.malformed_count == 1


@pytest.mark.asyncio
async def test_route_to_buffer(agent, valid_packet_json):
    """Test routing to correct device buffer."""
    valid, result = await agent.validate_schema(valid_packet_json)
    packet = result["parsed_packet"]

    buffer_key = await agent.route_to_buffer(packet)

    assert buffer_key == "jetson_alpha"


def test_get_stats(agent):
    """Test statistics tracking."""
    stats = agent.get_stats()

    assert "valid_count" in stats
    assert "malformed_count" in stats
    assert "error_rate" in stats
    assert stats["error_rate"] == 0.0  # No errors yet


@pytest.mark.asyncio
async def test_error_rate_calculation(agent, valid_packet_json):
    """Test error rate calculation with mixed valid/invalid packets."""
    # Add 1 valid packet
    await agent.validate_schema(valid_packet_json)

    # Add 1 invalid packet
    await agent.validate_schema("invalid json")

    stats = agent.get_stats()
    assert stats["valid_count"] == 1
    assert stats["malformed_count"] == 1
    assert stats["error_rate"] == 0.5  # 50% error rate
