"""Unit tests for Pydantic data contracts."""
import pytest
import time
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.contracts.models import (
    TrackedObject,
    Scores,
    TelemetryPacket,
    TrendResult,
    EmbeddingResult,
    Protocol,
    HistoryEntry,
    RAGRecommendation
)


class TestScores:
    def test_valid_scores(self):
        """Test valid score values within range."""
        scores = Scores(
            fire_dominance=0.5,
            smoke_opacity=0.8,
            proximity_alert=True
        )
        assert scores.fire_dominance == 0.5
        assert scores.smoke_opacity == 0.8
        assert scores.proximity_alert is True

    def test_fire_dominance_out_of_range(self):
        """Test fire_dominance validation rejects values outside [0.0, 1.0]."""
        with pytest.raises(Exception):
            Scores(fire_dominance=1.5, smoke_opacity=0.5, proximity_alert=False)

        with pytest.raises(Exception):
            Scores(fire_dominance=-0.1, smoke_opacity=0.5, proximity_alert=False)


class TestTelemetryPacket:
    def test_valid_packet(self):
        """Test valid telemetry packet."""
        current_time = time.time()
        packet = TelemetryPacket(
            device_id="jetson_alpha",
            session_id="mission_001",
            timestamp=current_time,
            hazard_level="HIGH",
            scores=Scores(fire_dominance=0.7, smoke_opacity=0.6, proximity_alert=True),
            tracked_objects=[
                TrackedObject(id=1, label="fire", status="tracked", duration_in_frame=2.5)
            ],
            visual_narrative="Fire detected in east corridor"
        )
        assert packet.device_id == "jetson_alpha"
        assert packet.hazard_level == "HIGH"

    def test_invalid_device_id_pattern(self):
        """Test device_id pattern validation."""
        current_time = time.time()
        with pytest.raises(Exception):
            TelemetryPacket(
                device_id="invalid_device",  # Should be "jetson_*"
                session_id="mission_001",
                timestamp=current_time,
                hazard_level="HIGH",
                scores=Scores(fire_dominance=0.7, smoke_opacity=0.6, proximity_alert=True),
                tracked_objects=[],
                visual_narrative="Test"
            )

    def test_invalid_hazard_level(self):
        """Test hazard_level enum validation."""
        current_time = time.time()
        with pytest.raises(Exception):
            TelemetryPacket(
                device_id="jetson_alpha",
                session_id="mission_001",
                timestamp=current_time,
                hazard_level="INVALID",  # Not a valid hazard level
                scores=Scores(fire_dominance=0.7, smoke_opacity=0.6, proximity_alert=True),
                tracked_objects=[],
                visual_narrative="Test"
            )

    def test_visual_narrative_length_validation(self):
        """Test visual_narrative max length."""
        current_time = time.time()
        with pytest.raises(Exception):
            TelemetryPacket(
                device_id="jetson_alpha",
                session_id="mission_001",
                timestamp=current_time,
                hazard_level="HIGH",
                scores=Scores(fire_dominance=0.7, smoke_opacity=0.6, proximity_alert=True),
                tracked_objects=[],
                visual_narrative="x" * 201  # Exceeds 200 char limit
            )


class TestTrendResult:
    def test_valid_trend(self):
        """Test valid trend result."""
        trend = TrendResult(
            trend_tag="RAPID_GROWTH",
            growth_rate=0.15,
            sample_count=10,
            time_span=5.0
        )
        assert trend.trend_tag == "RAPID_GROWTH"
        assert trend.growth_rate == 0.15

    def test_invalid_trend_tag(self):
        """Test trend_tag enum validation."""
        with pytest.raises(Exception):
            TrendResult(
                trend_tag="INVALID_TAG",
                growth_rate=0.15,
                sample_count=10,
                time_span=5.0
            )


class TestEmbeddingResult:
    def test_valid_embedding(self):
        """Test valid embedding with 384-dim vector."""
        result = EmbeddingResult(
            request_id="test_001",
            vector=[0.1] * 384,
            embedding_time_ms=25.5,
            model="all-MiniLM-L6-v2"
        )
        assert len(result.vector) == 384
        assert result.embedding_time_ms == 25.5

    def test_invalid_vector_dimension(self):
        """Test vector dimension validation."""
        with pytest.raises(Exception):
            EmbeddingResult(
                request_id="test_001",
                vector=[0.1] * 128,  # Wrong dimension
                embedding_time_ms=25.5
            )


class TestProtocol:
    def test_valid_protocol(self):
        """Test valid protocol."""
        protocol = Protocol(
            protocol_text="Evacuate immediately",
            severity="CRITICAL",
            category="fire_response",
            source="NFPA_72",
            similarity_score=0.95,
            tags=["evacuation", "fire"]
        )
        assert protocol.similarity_score == 0.95
        assert len(protocol.tags) == 2

    def test_similarity_score_out_of_range(self):
        """Test similarity_score validation."""
        with pytest.raises(Exception):
            Protocol(
                protocol_text="Test",
                severity="HIGH",
                category="test",
                source="test",
                similarity_score=1.5,  # Outside [0.0, 1.0]
                tags=[]
            )


class TestHistoryEntry:
    def test_valid_history_entry(self):
        """Test valid history entry."""
        entry = HistoryEntry(
            raw_narrative="Fire in corridor",
            timestamp=time.time(),
            trend_tag="GROWING",
            hazard_level="HIGH",
            similarity_score=0.85,
            time_ago_seconds=120.0
        )
        assert entry.similarity_score == 0.85
        assert entry.time_ago_seconds == 120.0


class TestRAGRecommendation:
    def test_valid_recommendation(self):
        """Test valid RAG recommendation."""
        rec = RAGRecommendation(
            recommendation="Evacuate building immediately",
            matched_protocol="NFPA_72",
            context_summary="HIGH | GROWING | 3 protocols | 2 history",
            synthesis_time_ms=0.5
        )
        assert rec.matched_protocol == "NFPA_72"

    def test_recommendation_max_length(self):
        """Test recommendation max length validation."""
        with pytest.raises(Exception):
            RAGRecommendation(
                recommendation="x" * 301,  # Exceeds 300 char limit
                matched_protocol="test",
                context_summary="test",
                synthesis_time_ms=0.5
            )
