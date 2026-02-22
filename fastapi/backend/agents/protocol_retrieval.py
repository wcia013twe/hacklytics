import time
from typing import List
import logging

from ..contracts.models import Protocol

logger = logging.getLogger(__name__)


class ProtocolRetrievalAgent:
    """
    Queries Actian VectorAI DB for top-K safety protocols via vector similarity.
    Uses Cortex gRPC SDK (AsyncCortexClient).
    """

    def __init__(self, actian_client):
        self.client = actian_client

    async def execute_vector_search(
        self,
        vector: List[float],
        severity: List[str] = ["HIGH", "CRITICAL"],
        top_k: int = 3,
        timeout: int = 200
    ) -> List[Protocol]:
        """
        Execute vector similarity search against safety_protocols collection.

        Returns:
            List of Protocol objects ordered by similarity
        """
        start = time.perf_counter()

        try:
            from cortex import Filter, Field

            results = await self.client.search(
                collection_name="safety_protocols",
                query=vector,
                top_k=top_k,
                filter=Filter().must(Field("severity").is_in(severity)),
                with_payload=True,
            )

            protocols = []
            for r in results:
                payload = r.payload
                tags_raw = payload.get("tags", "")
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if isinstance(tags_raw, str) else tags_raw

                protocols.append(Protocol(
                    protocol_text=payload.get("protocol_text", ""),
                    severity=payload.get("severity", ""),
                    category=payload.get("category", ""),
                    source=payload.get("source", ""),
                    similarity_score=float(r.score),
                    tags=tags,
                ))

            query_time = (time.perf_counter() - start) * 1000
            logger.info(f"Protocol retrieval: {len(protocols)} results in {query_time:.2f}ms")

            return protocols

        except Exception as e:
            logger.error(f"Protocol retrieval failed: {e}")
            return []
