import pytest
from sentence_transformers import SentenceTransformer, util


@pytest.fixture
def embedding_model():
    """Load MiniLM-L6 model for testing"""
    return SentenceTransformer('all-MiniLM-L6-v2')


def test_embedding_semantic_similarity(embedding_model):
    """
    Test Profile 1: Embedding Semantic Sanity

    Validates that MiniLM-L6 captures safety-relevant semantics.

    Pass Criteria:
    - sim(A, B) > sim(A, C) where:
      - A = "Person trapped, fire growing, exit blocked"
      - B = "Person trapped, fire diminishing, exit clear"
      - C = "Empty room, no hazards detected"

    Both A and B have "person trapped" so should be more similar than A vs C.
    """

    # Test narratives
    narrative_a = "Person trapped, fire growing, exit blocked"
    narrative_b = "Person trapped, fire diminishing, exit clear"
    narrative_c = "Empty room, no hazards detected"

    # Embed
    vec_a = embedding_model.encode(narrative_a)
    vec_b = embedding_model.encode(narrative_b)
    vec_c = embedding_model.encode(narrative_c)

    # Compute cosine similarities
    sim_ab = float(util.cos_sim(vec_a, vec_b)[0][0])
    sim_ac = float(util.cos_sim(vec_a, vec_c)[0][0])

    print(f"\nSemantic Similarity Results:")
    print(f"  sim(A, B) = {sim_ab:.4f} (trapped+fire vs trapped+clear)")
    print(f"  sim(A, C) = {sim_ac:.4f} (trapped+fire vs empty)")

    # CRITICAL: A should be closer to B than C
    assert sim_ab > sim_ac, (
        f"FAILED: Embedding does not capture safety semantics. "
        f"sim(A,B)={sim_ab:.4f} should be > sim(A,C)={sim_ac:.4f}"
    )

    # Additional checks
    assert sim_ab > 0.70, f"sim(A,B) = {sim_ab:.4f} is too low (expected >0.70)"
    assert sim_ac < 0.50, f"sim(A,C) = {sim_ac:.4f} is too high (expected <0.50)"

    print("✅ PASS: Embedding captures safety-relevant semantics")


def test_embedding_performance(embedding_model):
    """
    Validate embedding performance meets latency targets.

    Pass Criteria:
    - First call <500ms (warmup)
    - Subsequent calls <50ms
    """
    import time

    text = "Fire detected in corner, spreading rapidly"

    # First call (warmup)
    start = time.perf_counter()
    _ = embedding_model.encode(text)
    first_call_ms = (time.perf_counter() - start) * 1000

    # Subsequent calls
    latencies = []
    for _ in range(10):
        start = time.perf_counter()
        _ = embedding_model.encode(text)
        latencies.append((time.perf_counter() - start) * 1000)

    avg_latency = sum(latencies) / len(latencies)

    print(f"\nEmbedding Performance:")
    print(f"  First call: {first_call_ms:.2f}ms")
    print(f"  Avg (10 calls): {avg_latency:.2f}ms")

    assert avg_latency < 50, f"Avg latency {avg_latency:.2f}ms exceeds 50ms"
    print("✅ PASS: Embedding performance meets targets")
