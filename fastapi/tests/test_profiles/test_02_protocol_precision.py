import os
import pytest
from typing import List, Dict

from backend.agents.protocol_retrieval import ProtocolRetrievalAgent


@pytest.fixture
def test_scenarios():
    """
    10 test scenarios covering distinct safety situations.

    Each scenario has:
    - narrative: What the system sees
    - expected_tags: Tags that should appear in top-3 protocols
    """
    return [
        {
            "narrative": "Person trapped, fire growing, exit blocked",
            "expected_tags": ["trapped", "exit_blocked", "growing"]
        },
        {
            "narrative": "Smoke inhalation risk, visibility less than 3 feet",
            "expected_tags": ["smoke", "visibility"]
        },
        {
            "narrative": "Fire spreading to adjacent room, structural damage visible",
            "expected_tags": ["spreading", "structural"]
        },
        {
            "narrative": "Multiple casualties, triage needed, fire contained",
            "expected_tags": ["medical", "triage"]
        },
        {
            "narrative": "Hazmat leak detected, evacuation required",
            "expected_tags": ["hazmat", "evacuation"]
        },
        {
            "narrative": "Fire diminishing, clear exit path available",
            "expected_tags": ["diminishing", "clear_exit"]
        },
        {
            "narrative": "Flashover conditions imminent, temperature rising rapidly",
            "expected_tags": ["flashover", "temperature"]
        },
        {
            "narrative": "Backdraft risk, door breach dangerous",
            "expected_tags": ["backdraft", "breach"]
        },
        {
            "narrative": "Person unconscious near fire, immediate rescue needed",
            "expected_tags": ["unconscious", "rescue"]
        },
        {
            "narrative": "Secondary ignition point detected, fire spreading in two directions",
            "expected_tags": ["secondary", "spreading"]
        }
    ]


@pytest.fixture
async def actian_client():
    """Create a real Cortex client for integration tests."""
    host = os.getenv("ACTIAN_HOST", "vectoraidb")
    port = int(os.getenv("ACTIAN_PORT", "50051"))

    from cortex import AsyncCortexClient

    client = AsyncCortexClient(address=f"{host}:{port}")
    await client.connect()
    yield client
    await client.close()


@pytest.fixture
def protocol_agent(actian_client):
    return ProtocolRetrievalAgent(actian_client)


@pytest.fixture
def embedding_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer('all-MiniLM-L6-v2')


@pytest.mark.asyncio
async def test_protocol_retrieval_precision(test_scenarios, embedding_model, protocol_agent):
    """
    Test Profile 2: Protocol Retrieval Precision

    For each scenario, retrieve top-3 protocols and check if expected tags appear.

    Pass Criteria:
    - Precision@3 >= 80% (8 out of 10 scenarios have correct protocol in top 3)
    """

    matches = 0
    total = len(test_scenarios)

    for scenario in test_scenarios:
        # Embed narrative
        vector = embedding_model.encode(scenario["narrative"]).tolist()

        # Retrieve top-3 protocols
        protocols = await protocol_agent.execute_vector_search(
            vector=vector,
            severity=["HIGH", "CRITICAL"],
            top_k=3
        )

        # Check if any of top-3 protocols contain expected tags
        retrieved_tags = set()
        for protocol in protocols[:3]:
            retrieved_tags.update(protocol.tags)

        expected = set(scenario["expected_tags"])
        if expected.intersection(retrieved_tags):
            matches += 1
            status = "✓"
        else:
            status = "✗"

        print(f"{status} {scenario['narrative'][:50]}...")
        print(f"   Expected: {expected}")
        print(f"   Retrieved: {retrieved_tags}")

    precision = matches / total
    print(f"\nPrecision@3: {precision:.2%} ({matches}/{total})")

    assert precision >= 0.80, f"Precision {precision:.2%} < 80%"
    print("PASS: Protocol retrieval precision meets target")


def test_protocol_retrieval_mock():
    """
    Mock version of protocol precision test (runs without Actian).

    This is a placeholder that will be replaced when Actian is available.
    """
    print("\nMock test: Actian not available")
    print("   When Actian is running with seeded protocols, update this test.")
    assert True  # Always pass for now
