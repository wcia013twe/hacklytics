import time
from typing import List
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from contracts.models import HistoryEntry

logger = logging.getLogger(__name__)

class HistoryRetrievalAgent:
    """
    Queries Actian for similar past incidents in current session.
    """

    def __init__(self, actian_connection_pool):
        self.conn_pool = actian_connection_pool

    def build_history_query(
        self,
        vector: List[float],
        session_id: str,
        threshold: float = 0.70,
        top_k: int = 5
    ) -> tuple:
        """Task 6.1: Build history query with session filter"""
        sql = """
        SELECT
            raw_narrative,
            timestamp,
            trend_tag,
            hazard_level,
            1 - (narrative_vector <=> %s::vector) AS similarity_score
        FROM incident_log
        WHERE session_id = %s
          AND 1 - (narrative_vector <=> %s::vector) > %s
        ORDER BY
            narrative_vector <=> %s::vector,
            timestamp DESC
        LIMIT %s
        """
        return sql, (vector, session_id, vector, threshold, vector, top_k)

    async def execute_history_search(
        self,
        vector: List[float],
        session_id: str,
        similarity_threshold: float = 0.70,
        top_k: int = 5,
        timeout: int = 200
    ) -> List[HistoryEntry]:
        """
        Task 6.2: Execute history search

        Returns:
            List of HistoryEntry objects from same session
        """
        start = time.perf_counter()
        current_time = time.time()

        try:
            sql, params = self.build_history_query(vector, session_id, similarity_threshold, top_k)

            async with self.conn_pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)

            history = []
            for row in rows:
                time_ago = current_time - row['timestamp']
                history.append(HistoryEntry(
                    raw_narrative=row['raw_narrative'],
                    timestamp=row['timestamp'],
                    trend_tag=row['trend_tag'],
                    hazard_level=row['hazard_level'],
                    similarity_score=float(row['similarity_score']),
                    time_ago_seconds=time_ago
                ))

            query_time = (time.perf_counter() - start) * 1000
            logger.info(f"History retrieval: {len(history)} results in {query_time:.2f}ms")

            return history

        except Exception as e:
            logger.error(f"History retrieval failed: {e}")
            return []
