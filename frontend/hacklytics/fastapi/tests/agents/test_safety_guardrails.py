"""
Comprehensive test suite for SafetyGuardrailsAgent.

Tests critical safety scenarios to prevent dangerous recommendations:
1. Grease fire + water protocol → BLOCK
2. Electrical fire + water protocol → BLOCK
3. Gas cylinder + impact action → BLOCK
4. High temperature + approach action → BLOCK
5. Normal wood fire + water protocol → PASS
6. Edge cases: multiple hazards, ambiguous language
"""

import pytest
import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.agents.safety_guardrails import SafetyGuardrailsAgent
from backend.contracts.models import (
    TelemetryPacket,
    RAGRecommendation,
    GuardrailResult,
    Scores,
    TrackedObject
)


@pytest.fixture
def agent():
    return SafetyGuardrailsAgent()


@pytest.fixture
def sample_packet_grease():
    """Telemetry packet describing grease fire."""
    return TelemetryPacket(
        device_id="jetson_kitchen",
        session_id="mission_001",
        timestamp=time.time(),
        hazard_level="CRITICAL",
        scores=Scores(
            fire_dominance=0.85,
            smoke_opacity=0.60,
            proximity_alert=True
        ),
        tracked_objects=[
            TrackedObject(id=1, label="fire", status="active", duration_in_frame=5.2)
        ],
        visual_narrative="Deep fryer fire with visible grease flames spreading"
    )


@pytest.fixture
def sample_packet_electrical():
    """Telemetry packet describing electrical fire."""
    return TelemetryPacket(
        device_id="jetson_server",
        session_id="mission_002",
        timestamp=time.time(),
        hazard_level="HIGH",
        scores=Scores(
            fire_dominance=0.70,
            smoke_opacity=0.45,
            proximity_alert=False
        ),
        tracked_objects=[
            TrackedObject(id=2, label="smoke", status="growing", duration_in_frame=3.1)
        ],
        visual_narrative="Electrical panel sparking with visible wiring damage"
    )


@pytest.fixture
def sample_packet_gas():
    """Telemetry packet describing gas fire/leak."""
    return TelemetryPacket(
        device_id="jetson_warehouse",
        session_id="mission_003",
        timestamp=time.time(),
        hazard_level="CRITICAL",
        scores=Scores(
            fire_dominance=0.90,
            smoke_opacity=0.30,
            proximity_alert=True
        ),
        tracked_objects=[
            TrackedObject(id=3, label="fire", status="rapid", duration_in_frame=2.0)
        ],
        visual_narrative="Propane cylinder with active fire near valve"
    )


@pytest.fixture
def sample_packet_pressurized():
    """Telemetry packet describing pressurized container hazard."""
    return TelemetryPacket(
        device_id="jetson_lab",
        session_id="mission_004",
        timestamp=time.time(),
        hazard_level="HIGH",
        scores=Scores(
            fire_dominance=0.60,
            smoke_opacity=0.50,
            proximity_alert=False
        ),
        tracked_objects=[
            TrackedObject(id=4, label="container", status="heating", duration_in_frame=8.5)
        ],
        visual_narrative="Pressurized gas cylinder exposed to fire"
    )


@pytest.fixture
def sample_packet_wood():
    """Telemetry packet describing normal Class A fire (wood/paper)."""
    return TelemetryPacket(
        device_id="jetson_office",
        session_id="mission_005",
        timestamp=time.time(),
        hazard_level="MODERATE",
        scores=Scores(
            fire_dominance=0.40,
            smoke_opacity=0.35,
            proximity_alert=False
        ),
        tracked_objects=[
            TrackedObject(id=5, label="fire", status="stable", duration_in_frame=4.0)
        ],
        visual_narrative="Trash can fire with paper and cardboard burning"
    )


@pytest.fixture
def water_recommendation():
    """RAG recommendation suggesting water suppression."""
    return RAGRecommendation(
        recommendation="Apply water using fire hose. Spray directly on flames to extinguish.",
        matched_protocol="NFPA_Standard_Water",
        context_summary="Standard water suppression protocol",
        synthesis_time_ms=15.2
    )


@pytest.fixture
def approach_recommendation():
    """RAG recommendation suggesting manual approach."""
    return RAGRecommendation(
        recommendation="Approach fire with extinguisher. Manual intervention required to contain spread.",
        matched_protocol="Fire_Response_Manual",
        context_summary="Manual intervention protocol",
        synthesis_time_ms=12.8
    )


@pytest.fixture
def impact_recommendation():
    """RAG recommendation suggesting impact action."""
    return RAGRecommendation(
        recommendation="Strike cylinder to break seal. Force open valve to release pressure.",
        matched_protocol="Pressure_Release_Protocol",
        context_summary="Emergency pressure release",
        synthesis_time_ms=10.5
    )


@pytest.fixture
def safe_recommendation():
    """Safe recommendation for Class A fire."""
    return RAGRecommendation(
        recommendation="Evacuate area. Call fire department. Use ABC extinguisher from safe distance.",
        matched_protocol="Standard_Evacuation",
        context_summary="Safe evacuation protocol",
        synthesis_time_ms=11.0
    )


# ============================================================================
# CRITICAL SAFETY TESTS: Dangerous Combinations That Must Be Blocked
# ============================================================================

@pytest.mark.asyncio
async def test_grease_fire_water_blocked(agent, sample_packet_grease, water_recommendation):
    """CRITICAL: Water on grease fire must be blocked (causes explosive splatter)."""
    result = await agent.validate_recommendation(
        water_recommendation,
        sample_packet_grease
    )

    assert result.blocked is True, "Water on grease fire MUST be blocked"
    assert result.hazard_detected == "grease"
    assert result.dangerous_action == "water"
    assert "grease" in result.reason.lower() or "oil" in result.reason.lower()
    assert len(result.safe_alternative) > 0
    assert "Class B" in result.safe_alternative or "CO2" in result.safe_alternative
    assert result.latency_ms < 5.0, "Guardrail latency must be <5ms"


@pytest.mark.asyncio
async def test_electrical_fire_water_blocked(agent, sample_packet_electrical, water_recommendation):
    """CRITICAL: Water on electrical fire must be blocked (electrocution risk)."""
    result = await agent.validate_recommendation(
        water_recommendation,
        sample_packet_electrical
    )

    assert result.blocked is True, "Water on electrical fire MUST be blocked"
    assert result.hazard_detected == "electrical"
    assert result.dangerous_action == "water"
    assert "electrical" in result.reason.lower() or "electrocution" in result.reason.lower()
    assert len(result.safe_alternative) > 0
    assert "Class C" in result.safe_alternative or "de-energize" in result.safe_alternative.lower()


@pytest.mark.asyncio
async def test_gas_fire_water_blocked(agent, sample_packet_gas, water_recommendation):
    """CRITICAL: Water on gas fire must be blocked (ineffective, dangerous)."""
    result = await agent.validate_recommendation(
        water_recommendation,
        sample_packet_gas
    )

    assert result.blocked is True, "Water on gas fire MUST be blocked"
    assert result.hazard_detected == "gas"
    assert result.dangerous_action == "water"
    assert "gas" in result.reason.lower() or "chemical" in result.reason.lower()
    assert len(result.safe_alternative) > 0


@pytest.mark.asyncio
async def test_high_temperature_approach_blocked(agent, sample_packet_grease, approach_recommendation):
    """CRITICAL: Approaching >400C fire must be blocked (flashover risk)."""
    thermal_reading = 450.0  # Above 400C threshold

    result = await agent.validate_recommendation(
        approach_recommendation,
        sample_packet_grease,
        thermal_reading
    )

    assert result.blocked is True, "Approach at >400C MUST be blocked"
    assert result.hazard_detected == "high_temp"
    assert result.dangerous_action == "approach"
    assert "400" in result.reason or "thermal" in result.reason.lower()
    assert "remote" in result.safe_alternative.lower() or "distance" in result.safe_alternative.lower()


@pytest.mark.asyncio
async def test_pressurized_container_impact_blocked(agent, sample_packet_pressurized, impact_recommendation):
    """CRITICAL: Impact on pressurized container must be blocked (explosion risk)."""
    result = await agent.validate_recommendation(
        impact_recommendation,
        sample_packet_pressurized
    )

    assert result.blocked is True, "Impact on pressurized container MUST be blocked"
    assert result.hazard_detected == "pressurized"
    assert result.dangerous_action == "impact"
    assert "pressurized" in result.reason.lower() or "explosion" in result.reason.lower()
    assert "evacuate" in result.safe_alternative.lower() or "distance" in result.safe_alternative.lower()


# ============================================================================
# SAFE SCENARIO TESTS: Valid Recommendations That Should Pass
# ============================================================================

@pytest.mark.asyncio
async def test_wood_fire_water_allowed(agent, sample_packet_wood, water_recommendation):
    """Class A fire (wood/paper) + water should be ALLOWED."""
    result = await agent.validate_recommendation(
        water_recommendation,
        sample_packet_wood
    )

    assert result.blocked is False, "Water on Class A fire should be allowed"
    assert result.hazard_detected is None
    assert result.dangerous_action is None
    assert "passed" in result.reason.lower()
    assert result.safe_alternative == ""


@pytest.mark.asyncio
async def test_safe_evacuation_protocol_allowed(agent, sample_packet_grease, safe_recommendation):
    """Safe evacuation protocols should always pass."""
    result = await agent.validate_recommendation(
        safe_recommendation,
        sample_packet_grease
    )

    assert result.blocked is False
    assert result.safe_alternative == ""


@pytest.mark.asyncio
async def test_low_temperature_approach_allowed(agent, sample_packet_wood, approach_recommendation):
    """Approaching fire at normal temperatures (<400C) should be allowed."""
    thermal_reading = 150.0  # Below 400C threshold

    result = await agent.validate_recommendation(
        approach_recommendation,
        sample_packet_wood,
        thermal_reading
    )

    assert result.blocked is False, "Approach at <400C should be allowed"


# ============================================================================
# EDGE CASE TESTS: Complex Scenarios
# ============================================================================

@pytest.mark.asyncio
async def test_multiple_hazards_grease_and_electrical(agent, water_recommendation):
    """Test packet with both grease AND electrical hazards (should block water)."""
    packet = TelemetryPacket(
        device_id="jetson_kitchen",
        session_id="mission_multi",
        timestamp=time.time(),
        hazard_level="CRITICAL",
        scores=Scores(fire_dominance=0.90, smoke_opacity=0.70, proximity_alert=True),
        tracked_objects=[],
        visual_narrative="Deep fryer fire near electrical panel with sparking wires"
    )

    result = await agent.validate_recommendation(water_recommendation, packet)

    assert result.blocked is True, "Multiple hazards should trigger block"
    assert result.dangerous_action == "water"


@pytest.mark.asyncio
async def test_ambiguous_language_grease_variants(agent, water_recommendation):
    """Test detection of grease fire using various wordings."""
    packets = [
        ("cooking oil fire in pan", "grease"),
        ("petroleum-based fuel burning", "grease"),
        ("diesel spill ignited", "grease"),
        ("gasoline fire spreading", "grease"),
    ]

    for narrative, expected_hazard in packets:
        packet = TelemetryPacket(
            device_id="jetson_test",
            session_id="mission_test",
            timestamp=time.time(),
            hazard_level="HIGH",
            scores=Scores(fire_dominance=0.70, smoke_opacity=0.50, proximity_alert=False),
            tracked_objects=[],
            visual_narrative=narrative
        )

        result = await agent.validate_recommendation(water_recommendation, packet)
        assert result.blocked is True, f"Failed to detect hazard in: {narrative}"


@pytest.mark.asyncio
async def test_ambiguous_language_electrical_variants(agent, water_recommendation):
    """Test detection of electrical fire using various wordings."""
    narratives = [
        "power panel on fire",
        "circuit breaker sparking",
        "lithium battery thermal runaway",
        "transformer explosion with flames"
    ]

    for narrative in narratives:
        packet = TelemetryPacket(
            device_id="jetson_test",
            session_id="mission_test",
            timestamp=time.time(),
            hazard_level="HIGH",
            scores=Scores(fire_dominance=0.70, smoke_opacity=0.50, proximity_alert=False),
            tracked_objects=[],
            visual_narrative=narrative
        )

        result = await agent.validate_recommendation(water_recommendation, packet)
        assert result.blocked is True, f"Failed to detect electrical hazard in: {narrative}"


@pytest.mark.asyncio
async def test_case_insensitive_detection(agent, water_recommendation):
    """Test that hazard detection is case-insensitive."""
    packet = TelemetryPacket(
        device_id="jetson_test",
        session_id="mission_test",
        timestamp=time.time(),
        hazard_level="HIGH",
        scores=Scores(fire_dominance=0.70, smoke_opacity=0.50, proximity_alert=False),
        tracked_objects=[],
        visual_narrative="GREASE FIRE IN KITCHEN"  # All caps
    )

    result = await agent.validate_recommendation(water_recommendation, packet)
    assert result.blocked is True, "Case-insensitive detection failed"


@pytest.mark.asyncio
async def test_no_false_positives_wood_mentioned(agent, water_recommendation):
    """Test that mentioning 'wood' doesn't trigger false positives."""
    packet = TelemetryPacket(
        device_id="jetson_test",
        session_id="mission_test",
        timestamp=time.time(),
        hazard_level="MODERATE",
        scores=Scores(fire_dominance=0.40, smoke_opacity=0.30, proximity_alert=False),
        tracked_objects=[],
        visual_narrative="Wooden structure fire with paper debris"
    )

    result = await agent.validate_recommendation(water_recommendation, packet)
    assert result.blocked is False, "False positive: wood fire should allow water"


@pytest.mark.asyncio
async def test_boundary_temperature_exactly_400(agent, sample_packet_wood, approach_recommendation):
    """Test boundary condition: exactly 400C."""
    thermal_reading = 400.0

    result = await agent.validate_recommendation(
        approach_recommendation,
        sample_packet_wood,
        thermal_reading
    )

    # At exactly 400C, should NOT block (>400 is the threshold)
    assert result.blocked is False, "400C exactly should not block"


@pytest.mark.asyncio
async def test_boundary_temperature_401(agent, sample_packet_wood, approach_recommendation):
    """Test boundary condition: 401C (just above threshold)."""
    thermal_reading = 401.0

    result = await agent.validate_recommendation(
        approach_recommendation,
        sample_packet_wood,
        thermal_reading
    )

    assert result.blocked is True, "401C should block approach"


# ============================================================================
# INTEGRATION TESTS: apply_guardrails() method
# ============================================================================

@pytest.mark.asyncio
async def test_apply_guardrails_blocks_and_replaces(agent, sample_packet_grease, water_recommendation):
    """Test that apply_guardrails() replaces dangerous recommendations."""
    modified = await agent.apply_guardrails(
        water_recommendation,
        sample_packet_grease
    )

    # Should return a NEW recommendation object
    assert modified.recommendation != water_recommendation.recommendation
    assert modified.matched_protocol.startswith("GUARDRAIL_OVERRIDE")
    assert "BLOCKED" in modified.context_summary
    assert "Class B" in modified.recommendation or "CO2" in modified.recommendation


@pytest.mark.asyncio
async def test_apply_guardrails_passes_through_safe(agent, sample_packet_wood, safe_recommendation):
    """Test that apply_guardrails() passes through safe recommendations unchanged."""
    modified = await agent.apply_guardrails(
        safe_recommendation,
        sample_packet_wood
    )

    # Should return the SAME recommendation
    assert modified.recommendation == safe_recommendation.recommendation
    assert modified.matched_protocol == safe_recommendation.matched_protocol
    assert modified.context_summary == safe_recommendation.context_summary


@pytest.mark.asyncio
async def test_apply_guardrails_respects_max_length(agent, sample_packet_grease):
    """Test that replaced recommendations respect 300 char limit."""
    # Create a recommendation that would generate long safe alternative
    rec = RAGRecommendation(
        recommendation="Apply water spray with high pressure hose to extinguish grease fire",
        matched_protocol="dangerous",
        context_summary="test",
        synthesis_time_ms=10.0
    )

    modified = await agent.apply_guardrails(rec, sample_packet_grease)

    assert len(modified.recommendation) <= 300, "Safe alternative must respect max length"


# ============================================================================
# METRICS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_metrics_tracking_blocks(agent, sample_packet_grease, water_recommendation):
    """Test that blocked recommendations increment metrics."""
    agent.reset_metrics()

    await agent.validate_recommendation(water_recommendation, sample_packet_grease)
    metrics = agent.get_metrics()

    assert metrics["guardrail_blocks_total"] == 1
    assert "guardrail_pass_total" not in metrics or metrics["guardrail_pass_total"] == 0


@pytest.mark.asyncio
async def test_metrics_tracking_passes(agent, sample_packet_wood, safe_recommendation):
    """Test that passed recommendations increment metrics."""
    agent.reset_metrics()

    await agent.validate_recommendation(safe_recommendation, sample_packet_wood)
    metrics = agent.get_metrics()

    assert metrics["guardrail_pass_total"] == 1
    assert "guardrail_blocks_total" not in metrics or metrics["guardrail_blocks_total"] == 0


@pytest.mark.asyncio
async def test_metrics_accumulate(agent, sample_packet_grease, sample_packet_wood,
                                   water_recommendation, safe_recommendation):
    """Test that metrics accumulate across multiple validations."""
    agent.reset_metrics()

    await agent.validate_recommendation(water_recommendation, sample_packet_grease)  # Block
    await agent.validate_recommendation(safe_recommendation, sample_packet_wood)     # Pass
    await agent.validate_recommendation(water_recommendation, sample_packet_grease)  # Block

    metrics = agent.get_metrics()
    assert metrics["guardrail_blocks_total"] == 2
    assert metrics["guardrail_pass_total"] == 1


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_latency_budget_under_5ms(agent, sample_packet_grease, water_recommendation):
    """Test that guardrail evaluation meets <5ms latency budget."""
    results = []

    for _ in range(10):
        result = await agent.validate_recommendation(
            water_recommendation,
            sample_packet_grease
        )
        results.append(result.latency_ms)

    avg_latency = sum(results) / len(results)
    max_latency = max(results)

    assert avg_latency < 5.0, f"Average latency {avg_latency}ms exceeds 5ms budget"
    assert max_latency < 10.0, f"Max latency {max_latency}ms is too high"


@pytest.mark.asyncio
async def test_hazard_detection_performance(agent):
    """Test that hazard detection is fast (pure regex, no LLM)."""
    narrative = "Deep fryer grease fire with electrical panel sparking near propane cylinder"

    start = time.perf_counter()
    for _ in range(100):
        agent.detect_hazards(narrative, thermal_reading=450.0)
    elapsed = (time.perf_counter() - start) * 1000

    # 100 iterations should take <10ms total
    assert elapsed < 10.0, f"Hazard detection too slow: {elapsed}ms for 100 iterations"


# ============================================================================
# UNIT TESTS: Internal Methods
# ============================================================================

def test_detect_hazards_grease(agent):
    """Test hazard detection for grease/oil."""
    hazards = agent.detect_hazards("Deep fryer oil fire")
    assert hazards["grease"] is True
    assert hazards["electrical"] is False


def test_detect_hazards_electrical(agent):
    """Test hazard detection for electrical."""
    hazards = agent.detect_hazards("Electrical panel fire")
    assert hazards["electrical"] is True
    assert hazards["grease"] is False


def test_detect_hazards_gas(agent):
    """Test hazard detection for gas."""
    hazards = agent.detect_hazards("Propane leak with fire")
    assert hazards["gas"] is True
    assert hazards["electrical"] is False


def test_detect_hazards_pressurized(agent):
    """Test hazard detection for pressurized containers."""
    hazards = agent.detect_hazards("Pressurized cylinder heating")
    assert hazards["pressurized"] is True


def test_detect_hazards_high_temp(agent):
    """Test thermal hazard detection."""
    hazards = agent.detect_hazards("Fire", thermal_reading=450.0)
    assert hazards["high_temp"] is True

    hazards = agent.detect_hazards("Fire", thermal_reading=300.0)
    assert hazards["high_temp"] is False


def test_detect_dangerous_actions_water(agent):
    """Test water action detection."""
    actions = agent.detect_dangerous_actions("Apply water spray to extinguish")
    assert actions["water"] is True


def test_detect_dangerous_actions_approach(agent):
    """Test approach action detection."""
    actions = agent.detect_dangerous_actions("Approach fire and manually extinguish")
    assert actions["approach"] is True


def test_detect_dangerous_actions_impact(agent):
    """Test impact action detection."""
    actions = agent.detect_dangerous_actions("Strike valve to break seal")
    assert actions["impact"] is True


def test_get_safe_alternative_grease_water(agent):
    """Test safe alternative for grease + water."""
    alt = agent.get_safe_alternative("grease", "water")
    assert "Class B" in alt or "CO2" in alt
    assert "Never use water" in alt or "never use water" in alt


def test_get_safe_alternative_electrical_water(agent):
    """Test safe alternative for electrical + water."""
    alt = agent.get_safe_alternative("electrical", "water")
    assert "Class C" in alt or "de-energize" in alt.lower()


def test_get_safe_alternative_high_temp_approach(agent):
    """Test safe alternative for high temp + approach."""
    alt = agent.get_safe_alternative("high_temp", "approach")
    assert "evacuate" in alt.lower() or "distance" in alt.lower()
