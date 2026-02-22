#!/usr/bin/env python3
"""
Test Actian Vector DB setup and functionality.

Tests:
1. Database connection and schema verification
2. Protocol retrieval by vector similarity
3. Session history insertion and retrieval
4. Index performance validation
"""

import os
import asyncio
import pytest
import asyncpg
from sentence_transformers import SentenceTransformer
import time

# Environment variables
ACTIAN_HOST = os.getenv("ACTIAN_HOST", "localhost")
ACTIAN_PORT = int(os.getenv("ACTIAN_PORT", "5432"))
ACTIAN_USER = os.getenv("ACTIAN_USER", "vectordb")
ACTIAN_PASSWORD = os.getenv("ACTIAN_PASSWORD", "vectordb_pass")
ACTIAN_DATABASE = os.getenv("ACTIAN_DATABASE", "safety_rag")


@pytest.fixture
async def db_connection():
    """Fixture to provide database connection."""
    conn = await asyncpg.connect(
        host=ACTIAN_HOST,
        port=ACTIAN_PORT,
        user=ACTIAN_USER,
        password=ACTIAN_PASSWORD,
        database=ACTIAN_DATABASE
    )
    yield conn
    await conn.close()


@pytest.fixture
def embedding_model():
    """Fixture to provide embedding model."""
    return SentenceTransformer('all-MiniLM-L6-v2')


@pytest.mark.asyncio
async def test_database_connection(db_connection):
    """
    Test 1: Verify database connection and pgvector extension.
    """
    print("\n=== Test 1: Database Connection ===")

    # Check if vector extension is installed
    result = await db_connection.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM pg_extension WHERE extname = 'vector'
        )
    """)

    assert result is True, "pgvector extension not installed"
    print("  ✓ pgvector extension installed")


@pytest.mark.asyncio
async def test_schema_tables(db_connection):
    """
    Test 2: Verify safety_protocols and incident_log tables exist.
    """
    print("\n=== Test 2: Schema Validation ===")

    # Check safety_protocols table
    protocols_exists = await db_connection.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'safety_protocols'
        )
    """)
    assert protocols_exists is True, "safety_protocols table not found"
    print("  ✓ safety_protocols table exists")

    # Check incident_log table
    incidents_exists = await db_connection.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'incident_log'
        )
    """)
    assert incidents_exists is True, "incident_log table not found"
    print("  ✓ incident_log table exists")

    # Check protocol count
    protocol_count = await db_connection.fetchval("SELECT COUNT(*) FROM safety_protocols")
    print(f"  ✓ {protocol_count} protocols loaded")
    assert protocol_count > 0, "No protocols seeded"


@pytest.mark.asyncio
async def test_vector_indexes(db_connection):
    """
    Test 3: Verify vector indexes exist.
    """
    print("\n=== Test 3: Vector Index Validation ===")

    # Check for protocol vector index
    protocol_index = await db_connection.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'safety_protocols'
            AND indexname = 'idx_protocol_vector'
        )
    """)
    assert protocol_index is True, "Protocol vector index not found"
    print("  ✓ idx_protocol_vector exists")

    # Check for incident vector index
    incident_index = await db_connection.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'incident_log'
            AND indexname = 'idx_incident_vector'
        )
    """)
    assert incident_index is True, "Incident vector index not found"
    print("  ✓ idx_incident_vector exists")


@pytest.mark.asyncio
async def test_protocol_retrieval(db_connection, embedding_model):
    """
    Test 4: Test protocol retrieval by vector similarity.
    """
    print("\n=== Test 4: Protocol Retrieval ===")

    # Test query
    test_narrative = "Person trapped in corner, fire growing rapidly, exit blocked"
    print(f"  Query: {test_narrative}")

    # Embed query
    vector = embedding_model.encode(test_narrative, normalize_embeddings=True).tolist()

    # Query database
    start = time.perf_counter()
    results = await db_connection.fetch("""
        SELECT
            protocol_text,
            severity,
            category,
            source,
            tags,
            (1 - (scenario_vector <-> $1::vector)) AS similarity_score
        FROM safety_protocols
        WHERE severity IN ('HIGH', 'CRITICAL')
        ORDER BY scenario_vector <-> $1::vector ASC
        LIMIT 3
    """, vector)
    query_time = (time.perf_counter() - start) * 1000

    print(f"\n  Retrieved {len(results)} protocols in {query_time:.2f}ms")

    # Validation
    assert len(results) > 0, "No protocols retrieved"
    assert results[0]['similarity_score'] > 0.50, "Top result has low similarity"
    assert query_time < 500, f"Query too slow: {query_time:.2f}ms"

    # Display results
    for i, row in enumerate(results, 1):
        print(f"\n  {i}. Similarity: {row['similarity_score']:.3f}")
        print(f"     Source: {row['source']} | Severity: {row['severity']}")
        print(f"     Tags: {row['tags']}")
        print(f"     Protocol: {row['protocol_text'][:80]}...")

    print("\n  ✓ Protocol retrieval test PASSED")


@pytest.mark.asyncio
async def test_session_history_insertion(db_connection, embedding_model):
    """
    Test 5: Test incident log insertion and session history retrieval.
    """
    print("\n=== Test 5: Session History ===")

    session_id = "test_session_001"
    device_id = "jetson_test"

    # Test incidents to insert
    test_incidents = [
        "Smoke detected in hallway",
        "Fire growing in corner room",
        "Person spotted near fire",
        "Person trapped, exit blocked"
    ]

    print(f"  Inserting {len(test_incidents)} test incidents...")

    # Insert incidents
    for i, narrative in enumerate(test_incidents):
        vector = embedding_model.encode(narrative, normalize_embeddings=True).tolist()
        await db_connection.execute("""
            INSERT INTO incident_log (
                timestamp, session_id, device_id, narrative_vector,
                raw_narrative, trend_tag, hazard_level,
                fire_dominance, smoke_opacity, proximity_alert
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
            time.time() + i,
            session_id,
            device_id,
            vector,
            narrative,
            "GROWING",
            "HIGH",
            0.5,
            0.5,
            False
        )

    print(f"  ✓ Inserted {len(test_incidents)} incidents")

    # Query for similar incidents
    query_narrative = "Person in danger near fire"
    query_vector = embedding_model.encode(query_narrative, normalize_embeddings=True).tolist()

    print(f"\n  Querying similar incidents...")
    print(f"  Query: {query_narrative}")

    start = time.perf_counter()
    results = await db_connection.fetch("""
        WITH scored_incidents AS (
            SELECT
                raw_narrative,
                timestamp,
                trend_tag,
                hazard_level,
                (1 - (narrative_vector <-> $1::vector)) AS similarity_score
            FROM incident_log
            WHERE session_id = $2
            ORDER BY narrative_vector <-> $1::vector ASC
            LIMIT 20
        )
        SELECT *
        FROM scored_incidents
        WHERE similarity_score > 0.60
        ORDER BY timestamp DESC
        LIMIT 5
    """, query_vector, session_id)
    query_time = (time.perf_counter() - start) * 1000

    print(f"\n  Retrieved {len(results)} similar incidents in {query_time:.2f}ms")

    # Display results
    for i, row in enumerate(results, 1):
        time_ago = time.time() - row['timestamp']
        print(f"\n  {i}. Similarity: {row['similarity_score']:.3f} | {time_ago:.1f}s ago")
        print(f"     {row['raw_narrative']}")
        print(f"     Trend: {row['trend_tag']} | Hazard: {row['hazard_level']}")

    # Cleanup
    await db_connection.execute("DELETE FROM incident_log WHERE session_id = $1", session_id)
    print(f"\n  ✓ Cleaned up test data")

    # Validation
    assert len(results) > 0, "No similar incidents retrieved"
    assert query_time < 500, f"Query too slow: {query_time:.2f}ms"

    print("\n  ✓ Session history test PASSED")


@pytest.mark.asyncio
async def test_cosine_similarity_function(db_connection, embedding_model):
    """
    Test 6: Test the cosine_similarity helper function.
    """
    print("\n=== Test 6: Cosine Similarity Function ===")

    # Create two similar vectors
    vec1 = embedding_model.encode("Fire growing rapidly", normalize_embeddings=True).tolist()
    vec2 = embedding_model.encode("Fire spreading quickly", normalize_embeddings=True).tolist()

    # Test cosine_similarity function
    similarity = await db_connection.fetchval("""
        SELECT cosine_similarity($1::vector, $2::vector)
    """, vec1, vec2)

    print(f"  Similarity between 'Fire growing rapidly' and 'Fire spreading quickly': {similarity:.3f}")

    assert similarity > 0.70, "Similarity too low for semantically similar phrases"
    print("  ✓ Cosine similarity function working correctly")


@pytest.mark.asyncio
async def test_performance_benchmarks(db_connection, embedding_model):
    """
    Test 7: Performance benchmarks for vector searches.
    """
    print("\n=== Test 7: Performance Benchmarks ===")

    # Benchmark protocol retrieval (10 iterations)
    print("\n  Benchmarking protocol retrieval (10 iterations)...")

    test_query = "Fire blocking exit with person trapped"
    vector = embedding_model.encode(test_query, normalize_embeddings=True).tolist()

    latencies = []
    for i in range(10):
        start = time.perf_counter()
        await db_connection.fetch("""
            SELECT protocol_text, severity, source,
                   (1 - (scenario_vector <-> $1::vector)) AS similarity_score
            FROM safety_protocols
            WHERE severity IN ('HIGH', 'CRITICAL')
            ORDER BY scenario_vector <-> $1::vector ASC
            LIMIT 3
        """, vector)
        latencies.append((time.perf_counter() - start) * 1000)

    avg_latency = sum(latencies) / len(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

    print(f"  Average latency: {avg_latency:.2f}ms")
    print(f"  P95 latency: {p95_latency:.2f}ms")

    assert avg_latency < 200, f"Average latency too high: {avg_latency:.2f}ms"
    assert p95_latency < 300, f"P95 latency too high: {p95_latency:.2f}ms"

    print("  ✓ Performance benchmarks PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
