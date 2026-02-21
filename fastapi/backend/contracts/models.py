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
from typing import Literal, List, Dict, Optional
from datetime import datetime
import os

class TrackedObject(BaseModel):
    id: int
    label: str
    status: str
    duration_in_frame: float

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
