import time
from typing import List
import logging

from ..contracts.models import Protocol

logger = logging.getLogger(__name__)


class ProtocolRetrievalAgent:
    """
    Queries PostgreSQL with pgvector for top-K safety protocols via vector similarity.
    (Previously used Actian VectorAI DB with Cortex gRPC SDK - now commented out)
    """

    def __init__(self, db_pool):
        """
        Args:
            db_pool: asyncpg connection pool (previously actian_client)
        """
        self.pool = db_pool

    async def execute_vector_search(
        self,
        vector: List[float],
        severity: List[str] = ["HIGH", "CRITICAL"],
        top_k: int = 3,
        timeout: int = 200
    ) -> List[Protocol]:
        """
        Execute vector similarity search against safety_protocols table using pgvector.

        Returns:
            List of Protocol objects ordered by similarity
        """
        start = time.perf_counter()

        # COMMENTED OUT: Actian VectorAI DB code
        # try:
        #     from cortex import Filter, Field
        #     results = await self.client.search(
        #         collection_name="safety_protocols",
        #         query=vector,
        #         top_k=top_k,
        #         filter=Filter().must(Field("severity").is_in(severity)),
        #         with_payload=True,
        #     )
        #     protocols = []
        #     for r in results:
        #         payload = r.payload
        #         tags_raw = payload.get("tags", "")
        #         tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if isinstance(tags_raw, str) else tags_raw
        #         protocols.append(Protocol(
        #             protocol_text=payload.get("protocol_text", ""),
        #             severity=payload.get("severity", ""),
        #             category=payload.get("category", ""),
        #             source=payload.get("source", ""),
        #             similarity_score=float(r.score),
        #             tags=tags,
        #         ))
        #     query_time = (time.perf_counter() - start) * 1000
        #     logger.info(f"Protocol retrieval: {len(protocols)} results in {query_time:.2f}ms")
        #     return protocols
        # except Exception as e:
        #     logger.error(f"Protocol retrieval failed: {e}")
        #     return []

        # NEW: pgvector-based search
        try:
            if not self.pool:
                logger.warning("No database pool available")
                return []

            async with self.pool.acquire() as conn:
                # Convert severity list to PostgreSQL array format
                severity_clause = "ANY($2::text[])" if severity else "TRUE"

                query = f"""
                    SELECT
                        protocol_text,
                        severity,
                        category,
                        source,
                        tags,
                        1 - (embedding <=> $1::vector) as similarity_score
                    FROM safety_protocols
                    WHERE severity = {severity_clause}
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                """

                rows = await conn.fetch(query, vector, severity, top_k)

                protocols = []
                for row in rows:
                    tags_raw = row["tags"]
                    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if isinstance(tags_raw, str) else tags_raw

                    protocols.append(Protocol(
                        protocol_text=row["protocol_text"],
                        severity=row["severity"],
                        category=row["category"],
                        source=row["source"],
                        similarity_score=float(row["similarity_score"]),
                        tags=tags,
                    ))

                query_time = (time.perf_counter() - start) * 1000
                logger.info(f"Protocol retrieval (pgvector): {len(protocols)} results in {query_time:.2f}ms")

                return protocols

        except Exception as e:
            logger.error(f"Protocol retrieval failed: {e}")
            return []
