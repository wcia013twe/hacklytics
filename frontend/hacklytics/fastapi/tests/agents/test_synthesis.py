"""Unit tests for SynthesisAgent."""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.agents.synthesis import SynthesisAgent
from backend.contracts.models import Protocol, HistoryEntry


@pytest.fixture
def agent():
    return SynthesisAgent()


@pytest.fixture
def sample_protocols():
    return [
        Protocol(
            protocol_text="Evacuate building immediately via nearest exit",
            severity="CRITICAL",
            category="fire_response",
            source="NFPA_72",
            similarity_score=0.95,
            tags=["evacuation", "fire"]
        ),
        Protocol(
            protocol_text="Activate fire suppression system",
            severity="HIGH",
            category="fire_response",
            source="NFPA_13",
            similarity_score=0.85,
            tags=["suppression", "fire"]
        )
    ]


@pytest.fixture
def sample_history():
    import time
    return [
        HistoryEntry(
            raw_narrative="Fire in corridor",
            timestamp=time.time() - 120,
            trend_tag="GROWING",
            hazard_level="HIGH",
            similarity_score=0.88,
            time_ago_seconds=120.0
        ),
        HistoryEntry(
            raw_narrative="Smoke detected",
            timestamp=time.time() - 60,
            trend_tag="STABLE",
            hazard_level="MODERATE",
            similarity_score=0.75,
            time_ago_seconds=60.0
        )
    ]


@pytest.mark.asyncio
async def test_select_primary_protocol(agent, sample_protocols):
    """Test selection of primary protocol (highest similarity)."""
    primary = await agent.select_primary_protocol(sample_protocols, {})

    assert primary is not None
    assert primary.similarity_score == 0.95
    assert primary.source == "NFPA_72"


@pytest.mark.asyncio
async def test_select_primary_protocol_empty_list(agent):
    """Test selection with no protocols returns None."""
    primary = await agent.select_primary_protocol([], {})

    assert primary is None


@pytest.mark.asyncio
async def test_render_template_with_protocols(agent, sample_protocols, sample_history):
    """Test rendering recommendation with protocols."""
    context = {
        "hazard_level": "CRITICAL",
        "trend_tag": "RAPID_GROWTH",
        "growth_rate": 0.15,
        "proximity_alert": True
    }

    rec = await agent.render_template(sample_protocols, sample_history, context)

    assert rec.recommendation is not None
    assert len(rec.recommendation) <= 300
    assert rec.matched_protocol == "NFPA_72"
    assert "RAPID_GROWTH" in rec.recommendation or "Current trend" in rec.recommendation
    assert rec.synthesis_time_ms >= 0


@pytest.mark.asyncio
async def test_render_template_fallback(agent, sample_history):
    """Test rendering with fallback template when no protocols."""
    context = {
        "hazard_level": "CRITICAL",
        "trend_tag": "RAPID_GROWTH",
        "growth_rate": 0.15,
        "proximity_alert": False
    }

    rec = await agent.render_template([], sample_history, context)

    assert rec.recommendation is not None
    assert rec.matched_protocol == "fallback"
    assert "CRITICAL" in rec.recommendation
    assert "RAPID_GROWTH" in rec.recommendation


@pytest.mark.asyncio
async def test_render_template_truncation(agent):
    """Test that recommendations are truncated to 300 chars."""
    # Create a protocol with very long text
    long_protocol = Protocol(
        protocol_text="x" * 500,  # Very long text
        severity="CRITICAL",
        category="test",
        source="test",
        similarity_score=0.95,
        tags=[]
    )

    context = {
        "hazard_level": "CRITICAL",
        "trend_tag": "RAPID_GROWTH",
        "growth_rate": 0.15,
        "proximity_alert": True
    }

    rec = await agent.render_template([long_protocol], [], context)

    assert len(rec.recommendation) <= 300
    if len(rec.recommendation) == 300:
        assert rec.recommendation.endswith("...")


@pytest.mark.asyncio
async def test_context_summary_format(agent, sample_protocols, sample_history):
    """Test context summary formatting."""
    context = {
        "hazard_level": "HIGH",
        "trend_tag": "GROWING",
        "growth_rate": 0.05,
        "proximity_alert": False
    }

    rec = await agent.render_template(sample_protocols, sample_history, context)

    assert "HIGH" in rec.context_summary
    assert "GROWING" in rec.context_summary
    assert "2 protocols" in rec.context_summary
    assert "2 history" in rec.context_summary


@pytest.mark.asyncio
async def test_proximity_alert_included(agent, sample_protocols):
    """Test that proximity alert is included in recommendation."""
    context = {
        "hazard_level": "CRITICAL",
        "trend_tag": "RAPID_GROWTH",
        "growth_rate": 0.15,
        "proximity_alert": True
    }

    rec = await agent.render_template(sample_protocols, [], context)

    assert "proximity" in rec.recommendation.lower() or "⚠️" in rec.recommendation


@pytest.mark.asyncio
async def test_history_count_included(agent, sample_protocols, sample_history):
    """Test that history count is included when history exists."""
    context = {
        "hazard_level": "HIGH",
        "trend_tag": "GROWING",
        "growth_rate": 0.05,
        "proximity_alert": False
    }

    rec = await agent.render_template(sample_protocols, sample_history, context)

    assert "2 recent incident" in rec.recommendation or "Similar to" in rec.recommendation
