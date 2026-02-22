import time
from typing import List
import logging

from ..contracts.models import HistoryEntry

logger = logging.getLogger(__name__)


class HistoryRetrievalAgent:
    """
    Queries Actian VectorAI DB for similar past incidents in current session.
    Uses Cortex gRPC SDK (AsyncCortexClient).
    """

    def __init__(self, actian_client):
        self.client = actian_client

    async def execute_history_search(
        self,
        vector: List[float],
        session_id: str,
        similarity_threshold: float = 0.70,
        top_k: int = 5,
        timeout: int = 200
    ) -> List[HistoryEntry]:
        """
        Execute history search with session filter.

        The Cortex SDK does not support a score_threshold parameter, so we
        fetch top_k * 2 results and filter client-side by similarity_threshold.

        Returns:
            List of HistoryEntry objects from same session
        """
        start = time.perf_counter()
        current_time = time.time()

        try:
            from cortex import Filter, Field

            results = await self.client.search(
                collection_name="incident_log",
                query=vector,
                top_k=top_k * 2,
                filter=Filter().must(Field("session_id").eq(session_id)),
                with_payload=True,
            )

            history = []
            for r in results:
                score = float(r.score)
                if score < similarity_threshold:
                    continue

                payload = r.payload
                ts = payload.get("timestamp", 0.0)
                time_ago = current_time - ts

                history.append(HistoryEntry(
                    raw_narrative=payload.get("raw_narrative", ""),
                    timestamp=ts,
                    trend_tag=payload.get("trend_tag", "UNKNOWN"),
                    hazard_level=payload.get("hazard_level", ""),
                    similarity_score=score,
                    time_ago_seconds=time_ago,
                ))

                if len(history) >= top_k:
                    break

            query_time = (time.perf_counter() - start) * 1000
            logger.info(f"History retrieval: {len(history)} results in {query_time:.2f}ms")

            return history

        except Exception as e:
            logger.error(f"History retrieval failed: {e}")
            return []
