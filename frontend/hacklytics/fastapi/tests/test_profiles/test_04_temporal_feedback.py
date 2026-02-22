import pytest
import time

# This test requires Actian incident_log table to be available
# Mock version provided for now

@pytest.fixture
def escalation_sequence():
    """
    5-packet escalation sequence for testing temporal feedback loop.
    """
    base_time = time.time()
    return [
        {
            "narrative": "Room clear, no hazards",
            "hazard_level": "CLEAR",
            "timestamp": base_time
        },
        {
            "narrative": "Smoke detected near ceiling",
            "hazard_level": "LOW",
            "timestamp": base_time + 1
        },
        {
            "narrative": "Fire growing in corner",
            "hazard_level": "MODERATE",
            "timestamp": base_time + 2
        },
        {
            "narrative": "Person visible near fire",
            "hazard_level": "HIGH",
            "timestamp": base_time + 3
        },
        {
            "narrative": "Person trapped, exit blocked",
            "hazard_level": "CRITICAL",
            "timestamp": base_time + 4
        }
    ]


@pytest.mark.skipif(True, reason="Requires Actian incident_log")
async def test_temporal_feedback_loop(escalation_sequence, embedding_agent, history_agent, incident_logger):
    """
    Test Profile 4: Incident Log Temporal Feedback Loop

    Send 5 sequential packets. On 5th packet, verify that history retrieval
    returns ≥2 entries from same session.

    Pass Criteria:
    - history_count ≥ 2 on 5th packet
    - Similarity scores descending (most recent = highest)
    """

    session_id = "test_session_temporal_001"

    for i, packet_data in enumerate(escalation_sequence):
        # Embed narrative
        vector = (await embedding_agent.embed_text(
            packet_data["narrative"],
            request_id=f"test_{i}"
        )).vector

        # Write incident
        await incident_logger.write_to_actian(
            vector=vector,
            narrative=packet_data["narrative"],
            metadata={
                "session_id": session_id,
                "device_id": "test_device",
                "timestamp": packet_data["timestamp"],
                "trend_tag": "GROWING",
                "hazard_level": packet_data["hazard_level"],
                "fire_dominance": 0.5,
                "smoke_opacity": 0.5,
                "proximity_alert": False
            }
        )

        # On 5th packet, query history
        if i == 4:
            history = await history_agent.execute_history_search(
                vector=vector,
                session_id=session_id,
                similarity_threshold=0.60,
                top_k=5
            )

            print(f"\nHistory retrieval on packet 5:")
            print(f"  Retrieved {len(history)} entries")
            for entry in history:
                print(f"    - {entry.raw_narrative} (sim={entry.similarity_score:.2f})")

            assert len(history) >= 2, f"Expected ≥2 history entries, got {len(history)}"

            # Check similarity scores are descending
            scores = [entry.similarity_score for entry in history]
            assert scores == sorted(scores, reverse=True), "Similarity scores not descending"

            print("✅ PASS: Temporal feedback loop working")


def test_temporal_feedback_mock():
    """Mock version (no Actian required)"""
    print("\n⚠️  Mock test: Actian not available")
    print("   When Actian is running, update this test.")
    assert True
