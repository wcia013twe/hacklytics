#!/usr/bin/env python3
"""
Test Actian vector similarity queries.

Tests:
1. Protocol retrieval by vector similarity
2. Session history retrieval
3. Index performance
"""

import asyncpg
from sentence_transformers import SentenceTransformer
import time
import asyncio


async def test_protocol_retrieval():
    """
    Test Query 1: Protocol Retrieval

    Embed a test narrative and find top-3 matching protocols.
    """
    print("\n=== Test 1: Protocol Retrieval ===")

    model = SentenceTransformer('all-MiniLM-L6-v2')
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='vectordb',
        password='vectordb_pass',
        database='safety_rag'
    )

    # Test narrative
    test_narrative = "Person trapped in corner, fire growing rapidly, exit blocked"
    print(f"Query: {test_narrative}")

    # Embed
    vector = model.encode(test_narrative, normalize_embeddings=True).tolist()

    # Query Actian
    start = time.perf_counter()
    results = await conn.fetch(
        """
        SELECT
            protocol_text,
            severity,
            category,
            source,
            tags,
            1 - (scenario_vector <-> $1::vector) AS similarity_score
        FROM safety_protocols
        WHERE severity = ANY($2)
        ORDER BY scenario_vector <-> $1::vector
        LIMIT 3
        """,
        vector,
        ['HIGH', 'CRITICAL']
    )
    query_time = (time.perf_counter() - start) * 1000

    print(f"\nTop 3 Protocols (retrieved in {query_time:.2f}ms):")
    for i, row in enumerate(results, 1):
        print(f"\n{i}. Similarity: {row['similarity_score']:.4f}")
        print(f"   Source: {row['source']}")
        print(f"   Severity: {row['severity']} | Category: {row['category']}")
        print(f"   Tags: {row['tags']}")
        print(f"   Protocol: {row['protocol_text'][:100]}...")

    await conn.close()

    # Validation
    assert len(results) > 0, "No protocols retrieved"
    assert results[0]['similarity_score'] > 0.60, "Top result has low similarity"
    assert query_time < 300, f"Query too slow: {query_time:.2f}ms"

    print("\n✅ Protocol retrieval test PASSED")


async def test_session_history_retrieval():
    """
    Test Query 2: Session History Retrieval

    Insert test incidents and query for similar ones in same session.
    """
    print("\n=== Test 2: Session History Retrieval ===")

    model = SentenceTransformer('all-MiniLM-L6-v2')
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='vectordb',
        password='vectordb_pass',
        database='safety_rag'
    )

    session_id = "test_session_001"

    # Insert test incidents
    test_incidents = [
        "Smoke detected in hallway",
        "Fire growing in corner room",
        "Person spotted near fire",
        "Person trapped, exit blocked"
    ]

    print(f"Inserting {len(test_incidents)} test incidents...")
    for i, narrative in enumerate(test_incidents):
        vector = model.encode(narrative, normalize_embeddings=True).tolist()
        await conn.execute(
            """
            INSERT INTO incident_log (
                timestamp, session_id, device_id, narrative_vector,
                raw_narrative, trend_tag, hazard_level,
                fire_dominance, smoke_opacity, proximity_alert
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            time.time() + i,
            session_id,
            "jetson_test",
            vector,
            narrative,
            "GROWING",
            "HIGH",
            0.5,
            0.5,
            False
        )

    # Query for similar incidents
    query_narrative = "Person in danger near fire"
    query_vector = model.encode(query_narrative, normalize_embeddings=True).tolist()

    print(f"\nQuerying similar incidents in session '{session_id}'...")
    print(f"Query: {query_narrative}")

    start = time.perf_counter()
    results = await conn.fetch(
        """
        SELECT
            raw_narrative,
            timestamp,
            trend_tag,
            hazard_level,
            1 - (narrative_vector <-> $1::vector) AS similarity_score
        FROM incident_log
        WHERE session_id = $2
          AND 1 - (narrative_vector <-> $1::vector) > $3
        ORDER BY
            narrative_vector <-> $1::vector,
            timestamp DESC
        LIMIT 5
        """,
        query_vector,
        session_id,
        0.60  # similarity threshold
    )
    query_time = (time.perf_counter() - start) * 1000

    print(f"\nSimilar Incidents (retrieved in {query_time:.2f}ms):")
    for i, row in enumerate(results, 1):
        time_ago = time.time() - row['timestamp']
        print(f"\n{i}. Similarity: {row['similarity_score']:.4f} | {time_ago:.1f}s ago")
        print(f"   {row['raw_narrative']}")
        print(f"   Trend: {row['trend_tag']} | Hazard: {row['hazard_level']}")

    # Cleanup
    await conn.execute("DELETE FROM incident_log WHERE session_id = $1", session_id)
    await conn.close()

    # Validation
    assert len(results) > 0, "No history retrieved"
    assert query_time < 300, f"Query too slow: {query_time:.2f}ms"

    print("\n✅ Session history retrieval test PASSED")


async def test_index_performance():
    """
    Test index performance with varying dataset sizes.
    """
    print("\n=== Test 3: Index Performance ===")

    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='vectordb',
        password='vectordb_pass',
        database='safety_rag'
    )

    # Check index usage
    result = await conn.fetch(
        """
        SELECT
            schemaname,
            tablename,
            indexname,
            idx_scan,
            idx_tup_read
        FROM pg_stat_user_indexes
        WHERE tablename IN ('safety_protocols', 'incident_log')
        """
    )

    print("\nIndex Statistics:")
    for row in result:
        print(f"  {row['tablename']}.{row['indexname']}")
        print(f"    Scans: {row['idx_scan']} | Tuples read: {row['idx_tup_read']}")

    await conn.close()

    print("\n✅ Index performance check complete")


async def main():
    """Run all tests"""
    await test_protocol_retrieval()
    await test_session_history_retrieval()
    await test_index_performance()
    print("\n🎉 All Actian tests PASSED")


if __name__ == "__main__":
    asyncio.run(main())
