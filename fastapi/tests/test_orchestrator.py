import pytest
import json
import time
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.orchestrator import RAGOrchestrator

@pytest.fixture
def sample_packet():
    return {
        "device_id": "jetson_test_01",
        "session_id": "mission_test_001",
        "timestamp": time.time(),
        "hazard_level": "CRITICAL",
        "scores": {
            "fire_dominance": 0.85,
            "smoke_opacity": 0.70,
            "proximity_alert": True
        },
        "tracked_objects": [
            {"id": 42, "label": "person", "status": "stationary", "duration_in_frame": 10.0},
            {"id": 7, "label": "fire", "status": "growing", "duration_in_frame": 5.0}
        ],
        "visual_narrative": "CRITICAL: Person trapped, fire growing rapidly"
    }


@pytest.mark.asyncio
async def test_orchestrator_reflex_path(sample_packet):
    """Test that reflex path always executes"""
    orchestrator = RAGOrchestrator(actian_client=None)
    await orchestrator.startup()

    raw_message = json.dumps(sample_packet)
    result = await orchestrator.process_packet(raw_message)

    assert result["success"] == True
    assert "reflex_result" in result
    assert result["reflex_result"]["success"] == True
    assert result["total_time_ms"] < 100  # Should be fast without Actian


@pytest.mark.asyncio
async def test_orchestrator_invalid_packet():
    """Test that invalid packets are rejected at intake"""
    orchestrator = RAGOrchestrator(actian_client=None)
    await orchestrator.startup()

    invalid_packet = {"invalid": "data"}
    raw_message = json.dumps(invalid_packet)

    result = await orchestrator.process_packet(raw_message)

    assert "error" in result
    assert result["error"] == "intake_failed"
    assert orchestrator.metrics.counters["packets.invalid"] == 1


@pytest.mark.asyncio
async def test_orchestrator_trend_computation(sample_packet):
    """Test that trend is computed from buffer"""
    orchestrator = RAGOrchestrator(actian_client=None)
    await orchestrator.startup()

    # Send 5 packets with increasing fire_dominance
    for i in range(5):
        packet = sample_packet.copy()
        packet["timestamp"] = time.time() + i
        packet["scores"] = {
            "fire_dominance": 0.2 + i * 0.1,  # 0.2 → 0.6
            "smoke_opacity": 0.5,
            "proximity_alert": False
        }

        raw_message = json.dumps(packet)
        result = await orchestrator.process_packet(raw_message)

    # Last packet should show RAPID_GROWTH or GROWING
    trend = result["reflex_result"]["trend"]
    assert trend.trend_tag in ["RAPID_GROWTH", "GROWING"]
    assert trend.growth_rate > 0.01


@pytest.mark.asyncio
async def test_orchestrator_rag_skipped_for_low_hazard():
    """Test that RAG is not invoked for LOW hazard"""
    orchestrator = RAGOrchestrator(actian_client=None)
    await orchestrator.startup()

    packet = {
        "device_id": "jetson_test_01",
        "session_id": "mission_test_001",
        "timestamp": time.time(),
        "hazard_level": "LOW",  # Below threshold
        "scores": {"fire_dominance": 0.1, "smoke_opacity": 0.1, "proximity_alert": False},
        "tracked_objects": [],
        "visual_narrative": "Minor smoke detected"
    }

    raw_message = json.dumps(packet)
    result = await orchestrator.process_packet(raw_message)

    # Reflex should succeed, but RAG should be skipped
    assert result["success"] == True
    # Check that should_invoke_rag would return False
    from backend.contracts.models import TelemetryPacket
    packet_obj = TelemetryPacket(**packet)
    assert orchestrator.should_invoke_rag(packet_obj, result["reflex_result"]) == False
