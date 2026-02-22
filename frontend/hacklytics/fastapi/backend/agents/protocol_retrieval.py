import time
from typing import List, Optional
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from contracts.models import Protocol

logger = logging.getLogger(__name__)

class ProtocolRetrievalAgent:
    """
    Queries Actian for top-K safety protocols via vector similarity.
    """

    def __init__(self, actian_connection_pool):
        self.conn_pool = actian_connection_pool

    def build_query(self, vector: List[float], severity_filter: List[str], top_k: int = 3) -> tuple:
        """Task 5.1: Build parameterized query"""
        sql = """
        SELECT
            protocol_text,
            severity,
            category,
            source,
            tags,
            1 - (scenario_vector <=> %s::vector) AS similarity_score
        FROM safety_protocols
        WHERE severity = ANY(%s)
        ORDER BY scenario_vector <=> %s::vector
        LIMIT %s
        """
        return sql, (vector, severity_filter, vector, top_k)

    async def execute_vector_search(
        self,
        vector: List[float],
        severity: List[str] = ["HIGH", "CRITICAL"],
        top_k: int = 3,
        timeout: int = 200
    ) -> List[Protocol]:
        """
        Task 5.2: Execute vector search

        Returns:
            List of Protocol objects ordered by similarity
        """
        start = time.perf_counter()

        try:
            sql, params = self.build_query(vector, severity, top_k)

            async with self.conn_pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)

            protocols = []
            for row in rows:
                protocols.append(Protocol(
                    protocol_text=row['protocol_text'],
                    severity=row['severity'],
                    category=row['category'],
                    source=row['source'],
                    similarity_score=float(row['similarity_score']),
                    tags=row['tags'].split(',') if row['tags'] else []
                ))

            query_time = (time.perf_counter() - start) * 1000
            logger.info(f"Protocol retrieval: {len(protocols)} results in {query_time:.2f}ms")

            return protocols

        except Exception as e:
            logger.error(f"Protocol retrieval failed: {e}")
            return []
