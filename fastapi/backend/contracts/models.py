"""
Data models for Temporal RAG System telemetry and processing.

IMPORTANT - Timestamp Convention:
All timestamps in this system use Unix epoch time (seconds since Jan 1, 1970 UTC).
- Format: float (e.g., 1708541234.567)
- Timezone: Always UTC (no local time conversions)
- Precision: Sub-second resolution supported
- Sources: Jetson devices must sync clocks via NTP

This ensures consistent temporal reasoning across distributed devices and services.
"""

from pydantic import BaseModel, Field, validator
from typing import Literal, List, Dict, Optional, Any
from datetime import datetime
import os

class ActionCommand(BaseModel):
    target: str = Field(..., description="Who receives the command ('Rescue Team', 'IC', 'All Units')")
    directive: str = Field(..., description="What they must do — imperative, specific, ≤12 words")

class FormatterResult(BaseModel):
    action_command: str = Field(..., description="Single primary directive (≤15 words, imperative)")
    action_reason: str = Field(..., description="Why — grounds the command in ERG + scene facts (≤25 words)")
    hazard_type: str = Field(..., description="Hazard classification, e.g. 'Adsorbed Gases - Flammable'")
    source_text: str = Field(..., description="Key excerpt from the ERG guide (≤3 sentences)")
    actionable_commands: List[ActionCommand] = Field(..., description="2–4 scene-grounded commands")
    fallback_used: bool = Field(default=False, description="True if LLM failed and fallback was used")
from typing import Literal, List, Dict, Optional
from datetime import datetime
import os

class TrackedObject(BaseModel):
    id: int
    label: str
    status: str
    duration_in_frame: float
    growth_rate: Optional[float] = None  # Present on fire objects (e.g., 0.1 = 10% growth over 5s)

class Scores(BaseModel):
    fire_dominance: float = Field(..., ge=0.0, le=1.0)
    smoke_opacity: float = Field(..., ge=0.0, le=1.0)
    proximity_alert: bool

class TelemetryPacket(BaseModel):
    device_id: str = Field(..., pattern=r"jetson_\w+")
    session_id: str = Field(..., pattern=r"mission_\w+")
    timestamp: float = Field(
        ...,
        description="Unix epoch timestamp (UTC) in seconds. Must be within configured tolerance of server time."
    )
    hazard_level: Literal["CLEAR", "LOW", "MODERATE", "HIGH", "CRITICAL"]
    scores: Scores
    tracked_objects: List[TrackedObject]
    visual_narrative: str = Field(..., max_length=200, min_length=1)
    priority: Optional[Literal["CRITICAL", "CAUTION", "SAFE"]] = Field(
        None,
        description="Event priority for temporal buffer retention. Auto-classified if not provided."
    )

    @validator('timestamp')
    def validate_timestamp(cls, v):
        """
        Validate timestamp is within acceptable range of server time.

        Allows past timestamps to handle:
        - Network latency and retries
        - Batch uploads from Jetson devices
        - Processing delays during connectivity loss
        - Clock skew between devices and server

        Configurable via TIMESTAMP_TOLERANCE_SECONDS (default: 300s = 5 minutes)
        Rejects future timestamps beyond 10 seconds (protects against clock drift)
        """
        import time
        current_time = time.time()

        # Get tolerance from environment (default 300 seconds = 5 minutes)
        tolerance_past = int(os.getenv('TIMESTAMP_TOLERANCE_SECONDS', '300'))
        tolerance_future = 10  # Only allow 10s into future (clock skew protection)

        time_diff = v - current_time

        # Reject timestamps too far in the past
        if time_diff < -tolerance_past:
            raise ValueError(
                f"Timestamp {v} is {abs(time_diff):.1f}s in the past "
                f"(max allowed: {tolerance_past}s). Check device clock sync."
            )

        # Reject timestamps too far in the future
        if time_diff > tolerance_future:
            raise ValueError(
                f"Timestamp {v} is {time_diff:.1f}s in the future "
                f"(max allowed: {tolerance_future}s). Check device clock sync."
            )

        return v

class TrendResult(BaseModel):
    """Fire growth trend result from TemporalBuffer analysis.

    Based on RAG.MD Section 3.4.2:
    - Uses linear regression over buffered fire_dominance values
    - Thresholds: RAPID_GROWTH >0.10/s, GROWING >0.02/s, STABLE -0.05 to +0.02, DIMINISHING <-0.05
    """
    trend_tag: Literal["RAPID_GROWTH", "GROWING", "STABLE", "DIMINISHING", "UNKNOWN"]
    growth_rate: float = Field(..., description="Change in fire_dominance per second")
    sample_count: int = Field(..., description="Number of packets in analysis")
    time_span: float = Field(..., description="Time range of buffer in seconds")

class EmbeddingResult(BaseModel):
    request_id: str
    vector: List[float]
    embedding_time_ms: float
    model: str = "all-MiniLM-L6-v2"

    @validator('vector')
    def validate_vector_dimension(cls, v):
        if len(v) != 384:
            raise ValueError(f"Vector must be 384-dim, got {len(v)}")
        return v

class Protocol(BaseModel):
    protocol_text: str
    severity: str
    category: str
    source: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    tags: List[str]

class HistoryEntry(BaseModel):
    raw_narrative: str
    timestamp: float = Field(..., description="Unix epoch timestamp (UTC) when incident occurred")
    trend_tag: str
    hazard_level: str
    similarity_score: float
    time_ago_seconds: float = Field(..., description="Seconds elapsed since this incident (calculated from current time)")

class RAGRecommendation(BaseModel):
    recommendation: str = Field(..., max_length=300)
    matched_protocol: Optional[str]
    context_summary: str
    synthesis_time_ms: float

class GuardrailResult(BaseModel):
    """Result from safety guardrail validation.

    Safety guardrails enforce physics-based hard constraints to prevent
    dangerous recommendations (e.g., water on grease fires).
    """
    blocked: bool = Field(..., description="True if recommendation contains dangerous advice")
    reason: str = Field(..., description="Human-readable explanation of why it was blocked")
    safe_alternative: str = Field(..., description="Safe alternative recommendation if blocked, empty if passed")
    hazard_detected: Optional[str] = Field(None, description="Type of hazard detected (grease, electrical, gas, high_temp, pressurized)")
    dangerous_action: Optional[str] = Field(None, description="Dangerous action that was blocked (water, approach, impact)")
    latency_ms: float = Field(..., description="Time taken to evaluate guardrails")

class TemporalSynthesisResult(BaseModel):
    """Result from temporal narrative synthesis.

    The TemporalNarrativeAgent uses Gemini Flash to synthesize 3-5 seconds
    of buffered frame narratives into coherent temporal stories that capture
    fire progression patterns and safety-critical trajectories.
    """
    synthesized_narrative: str = Field(..., max_length=200, description="LLM-generated temporal story (200 char max)")
    original_narratives: List[str] = Field(..., description="Individual frame narratives that were synthesized")
    time_span: float = Field(..., ge=0.0, description="Time range in seconds covered by synthesis")
    synthesis_time_ms: float = Field(..., ge=0.0, description="Gemini API latency in milliseconds")
    event_count: int = Field(..., ge=0, description="Number of events synthesized")
    cache_hit: bool = Field(default=False, description="Was synthesis cached? (future optimization)")
    fallback_used: bool = Field(default=False, description="Did we fallback to concatenation due to API failure?")

class CacheMetrics(BaseModel):
    """Cache performance metrics for Redis multi-layer caching.

    Tracks hit/miss rates and latency for the 3-layer cache system:
    - Layer 1: Embedding cache (narrative → vector)
    - Layer 2: Protocol cache (vector → protocols)
    - Layer 3: Session history cache (similarity search)
    """
    layer: Literal["embedding", "protocol", "session"] = Field(..., description="Cache layer identifier")
    hits: int = Field(default=0, ge=0, description="Number of cache hits")
    misses: int = Field(default=0, ge=0, description="Number of cache misses")
    hit_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Cache hit rate (hits / total)")
    avg_latency_ms: float = Field(default=0.0, ge=0.0, description="Average cache operation latency in milliseconds")
