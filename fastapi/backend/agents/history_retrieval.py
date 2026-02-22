import time
from typing import List
import logging

from ..contracts.models import HistoryEntry

logger = logging.getLogger(__name__)


class HistoryRetrievalAgent:
    """
    Queries PostgreSQL with pgvector for similar past incidents in current session.
    (Previously used Actian VectorAI DB with Cortex gRPC SDK - now commented out)
    """

    def __init__(self, db_pool):
        """
        Args:
            db_pool: asyncpg connection pool (previously actian_client)
        """
        self.pool = db_pool

    async def execute_history_search(
        self,
        vector: List[float],
        session_id: str,
        similarity_threshold: float = 0.70,
        top_k: int = 5,
        timeout: int = 200
    ) -> List[HistoryEntry]:
        """
        Execute history search with session filter using pgvector.

        Returns:
            List of HistoryEntry objects from same session
        """
        start = time.perf_counter()
        current_time = time.time()

        # COMMENTED OUT: Actian VectorAI DB code
        # try:
        #     from cortex import Filter, Field
        #     results = await self.client.search(
        #         collection_name="incident_log",
        #         query=vector,
        #         top_k=top_k * 2,
        #         filter=Filter().must(Field("session_id").eq(session_id)),
        #         with_payload=True,
        #     )
        #     history = []
        #     for r in results:
        #         score = float(r.score)
        #         if score < similarity_threshold:
        #             continue
        #         payload = r.payload
        #         ts = payload.get("timestamp", 0.0)
        #         time_ago = current_time - ts
        #         history.append(HistoryEntry(
        #             raw_narrative=payload.get("raw_narrative", ""),
        #             timestamp=ts,
        #             trend_tag=payload.get("trend_tag", "UNKNOWN"),
        #             hazard_level=payload.get("hazard_level", ""),
        #             similarity_score=score,
        #             time_ago_seconds=time_ago,
        #         ))
        #         if len(history) >= top_k:
        #             break
        #     query_time = (time.perf_counter() - start) * 1000
        #     logger.info(f"History retrieval: {len(history)} results in {query_time:.2f}ms")
        #     return history
        # except Exception as e:
        #     logger.error(f"History retrieval failed: {e}")
        #     return []

        # NEW: pgvector-based search
        try:
            if not self.pool:
                logger.warning("No database pool available")
                return []

            async with self.pool.acquire() as conn:
                query = """
                    SELECT
                        raw_narrative,
                        timestamp,
                        trend_tag,
                        hazard_level,
                        1 - (narrative_vector <=> $1::vector) as similarity_score
                    FROM incident_log
                    WHERE session_id = $2
                    ORDER BY narrative_vector <=> $1::vector
                    LIMIT $3
                """

                rows = await conn.fetch(query, vector, session_id, top_k * 2)

                history = []
                for row in rows:
                    score = float(row["similarity_score"])
                    if score < similarity_threshold:
                        continue

                    ts = row["timestamp"]
                    time_ago = current_time - ts

                    history.append(HistoryEntry(
                        raw_narrative=row["raw_narrative"],
                        timestamp=ts,
                        trend_tag=row["trend_tag"] or "UNKNOWN",
                        hazard_level=row["hazard_level"],
                        similarity_score=score,
                        time_ago_seconds=time_ago,
                    ))

                    if len(history) >= top_k:
                        break

                query_time = (time.perf_counter() - start) * 1000
                logger.info(f"History retrieval (pgvector): {len(history)} results in {query_time:.2f}ms")

                return history

        except Exception as e:
            logger.error(f"History retrieval failed: {e}")
            return []
