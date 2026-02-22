import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock
from backend.agents.protocol_formatter import ProtocolFormatterAgent
from backend.contracts.models import Protocol, TelemetryPacket, TrackedObject, Scores, FormatterResult

@pytest.fixture
def sample_packet():
    return TelemetryPacket(
        device_id="jetson_001",
        session_id="mission_001",
        timestamp=time.time(),
        hazard_level="CRITICAL",
        scores=Scores(fire_dominance=0.8, smoke_opacity=0.5, proximity_alert=True),
        tracked_objects=[
            TrackedObject(id=42, label="person", status="stationary", duration_in_frame=28.0),
            TrackedObject(id=7, label="fire", status="growing", duration_in_frame=15.0, growth_rate=0.14)
        ],
        visual_narrative="Person stationary near growing fire"
    )

@pytest.fixture
def sample_protocol():
    return Protocol(
        protocol_text="Containers may explode when heated. Do not approach containers engulfed in fire. Cool with water from maximum distance.",
        severity="CRITICAL",
        category="Adsorbed Gases - Flammable",
        source="ERG_2024_Guide_174",
        similarity_score=0.95,
        tags=["fire", "gas"]
    )

@pytest.mark.asyncio
async def test_format_success(sample_protocol, sample_packet):
    agent = ProtocolFormatterAgent(timeout_seconds=1.0)
    
    # Mock the Ollama API call
    mock_json_response = '''
    {
      "action_command": "Evacuate all personnel",
      "action_reason": "ERG 174: adsorbed gas containers may explode in fire.",
      "hazard_type": "Adsorbed Gases - Flammable",
      "source_text": "Containers may explode when heated.",
      "actionable_commands": [
        {"target": "Rescue Team", "directive": "Extract Person #42 now"},
        {"target": "All Units", "directive": "Maintain 300ft standoff"}
      ]
    }
    '''
    
    with patch.object(agent, '_call_ollama', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_json_response
        
        result = await agent.format(
            protocol=sample_protocol,
            packet=sample_packet,
            synthesized_narrative="Person stationary 28s, Fire growing 14%/s"
        )
        
        assert isinstance(result, FormatterResult)
        assert result.action_command == "Evacuate all personnel"
        assert len(result.actionable_commands) == 2
        assert result.actionable_commands[0].target == "Rescue Team"
        assert result.actionable_commands[0].directive == "Extract Person #42 now"
        assert result.fallback_used is False
        assert agent.metrics["successful_formats"] == 1

@pytest.mark.asyncio
async def test_format_timeout_fallback(sample_protocol, sample_packet):
    agent = ProtocolFormatterAgent(timeout_seconds=0.1)
    
    with patch.object(agent, '_call_ollama', new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = asyncio.TimeoutError("Timeout")
        
        result = await agent.format(
            protocol=sample_protocol,
            packet=sample_packet,
            synthesized_narrative="Fallback reason"
        )
        
        assert isinstance(result, FormatterResult)
        assert result.fallback_used is True
        assert result.action_reason == "Fallback reason"
        assert result.hazard_type == sample_protocol.category
        assert len(result.actionable_commands) == 0
        assert agent.metrics["timeouts"] == 1

@pytest.mark.asyncio
async def test_format_json_decode_error_fallback(sample_protocol, sample_packet):
    agent = ProtocolFormatterAgent(timeout_seconds=1.0)
    
    # Mock the Ollama API call giving invalid JSON
    mock_json_response = "I am a helpful assistant! Here is your output: ```json Oops missing brace"
    
    with patch.object(agent, '_call_ollama', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_json_response
        
        result = await agent.format(
            protocol=sample_protocol,
            packet=sample_packet,
            synthesized_narrative="Narrative text"
        )
        
        assert result.fallback_used is True
        assert result.action_reason == "Narrative text"
        assert len(result.actionable_commands) == 0

@pytest.mark.asyncio
async def test_format_markdown_wrapped_json(sample_protocol, sample_packet):
    agent = ProtocolFormatterAgent(timeout_seconds=1.0)
    
    # Mock Ollama giving markdown block
    mock_json_response = '''```json
    {
      "action_command": "Cmd",
      "action_reason": "Reason",
      "hazard_type": "Haz",
      "source_text": "Src",
      "actionable_commands": []
    }
    ```'''
    
    with patch.object(agent, '_call_ollama', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_json_response
        
        result = await agent.format(
            protocol=sample_protocol,
            packet=sample_packet,
            synthesized_narrative="Narrative text"
        )
        
        assert result.fallback_used is False
        assert result.action_command == "Cmd"
