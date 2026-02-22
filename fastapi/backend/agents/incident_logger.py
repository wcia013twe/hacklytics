import time
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class IncidentLoggerAgent:
    """
    Writes incidents to PostgreSQL incident_log table using pgvector.
    (Previously used Actian VectorAI DB with Cortex gRPC SDK - now commented out)
    """

    def __init__(self, db_pool):
        """
        Args:
            db_pool: asyncpg connection pool (previously actian_client)
        """
        self.pool = db_pool

    @staticmethod
    def _generate_incident_id(session_id: str, device_id: str, timestamp: float) -> int:
        """Generate a deterministic int ID from session, device, and timestamp."""
        return abs(hash((session_id, device_id, timestamp))) % 2**63

    def format_incident_row(self, vector: List[float], narrative: str, metadata: Dict) -> Dict:
        """Format incident data for upsert."""
        return {
            "narrative_vector": vector,
            "raw_narrative": narrative,
            "session_id": metadata["session_id"],
            "device_id": metadata["device_id"],
            "timestamp": metadata["timestamp"],
            "trend_tag": metadata["trend_tag"],
            "hazard_level": metadata["hazard_level"],
            "fire_dominance": metadata["fire_dominance"],
            "smoke_opacity": metadata["smoke_opacity"],
            "proximity_alert": metadata["proximity_alert"]
        }

    async def write_to_actian(self, vector: List[float], packet, trend) -> Dict:
        """
        Write a single incident to PostgreSQL incident_log table.

        Returns:
            {"incident_id": int, "write_time_ms": float, "success": bool}
        """
        start = time.perf_counter()

        # COMMENTED OUT: Actian VectorAI DB code
        # try:
        #     incident_id = self._generate_incident_id(
        #         packet.session_id, packet.device_id, packet.timestamp
        #     )
        #     payload = {
        #         "raw_narrative": packet.visual_narrative,
        #         "session_id": packet.session_id,
        #         "device_id": packet.device_id,
        #         "timestamp": packet.timestamp,
        #         "trend_tag": trend.trend_tag,
        #         "hazard_level": packet.hazard_level,
        #         "fire_dominance": packet.scores.fire_dominance,
        #         "smoke_opacity": packet.scores.smoke_opacity,
        #         "proximity_alert": packet.scores.proximity_alert,
        #     }
        #     await self.client.upsert(
        #         collection_name="incident_log",
        #         id=incident_id,
        #         vector=vector,
        #         payload=payload,
        #     )
        #     write_time = (time.perf_counter() - start) * 1000
        #     logger.info(f"Incident logged: id={incident_id} in {write_time:.2f}ms")
        #     return {"incident_id": incident_id, "write_time_ms": write_time, "success": True}
        # except Exception as e:
        #     write_time = (time.perf_counter() - start) * 1000
        #     logger.error(f"Incident logging failed: {e}")
        #     return {"incident_id": None, "write_time_ms": write_time, "success": False}

        # NEW: pgvector-based upsert
        try:
            if not self.pool:
                logger.warning("No database pool available")
                return {"incident_id": None, "write_time_ms": 0, "success": False}

            incident_id = self._generate_incident_id(
                packet.session_id, packet.device_id, packet.timestamp
            )

            async with self.pool.acquire() as conn:
                query = """
                    INSERT INTO incident_log (
                        id, narrative_vector, raw_narrative, session_id, device_id,
                        timestamp, trend_tag, hazard_level, fire_dominance,
                        smoke_opacity, proximity_alert
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (id) DO UPDATE SET
                        narrative_vector = EXCLUDED.narrative_vector,
                        raw_narrative = EXCLUDED.raw_narrative,
                        trend_tag = EXCLUDED.trend_tag,
                        hazard_level = EXCLUDED.hazard_level,
                        fire_dominance = EXCLUDED.fire_dominance,
                        smoke_opacity = EXCLUDED.smoke_opacity,
                        proximity_alert = EXCLUDED.proximity_alert
                """

                await conn.execute(
                    query,
                    incident_id,
                    vector,
                    packet.visual_narrative,
                    packet.session_id,
                    packet.device_id,
                    packet.timestamp,
                    trend.trend_tag,
                    packet.hazard_level,
                    packet.scores.fire_dominance,
                    packet.scores.smoke_opacity,
                    packet.scores.proximity_alert,
                )

            write_time = (time.perf_counter() - start) * 1000
            logger.info(f"Incident logged (pgvector): id={incident_id} in {write_time:.2f}ms")

            return {"incident_id": incident_id, "write_time_ms": write_time, "success": True}

        except Exception as e:
            write_time = (time.perf_counter() - start) * 1000
            logger.error(f"Incident logging failed: {e}")
            return {"incident_id": None, "write_time_ms": write_time, "success": False}
