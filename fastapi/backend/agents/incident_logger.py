import time
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class IncidentLoggerAgent:
    """
    Writes incidents to Actian VectorAI DB incident_log collection.
    Relies on Cortex SmartBatcher (100ms auto-flush) instead of manual batching.
    """

    def __init__(self, actian_client):
        self.client = actian_client

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
        Write a single incident to Actian VectorAI DB.

        SmartBatcher on the client handles automatic batching (100ms flush).

        Returns:
            {"incident_id": int, "write_time_ms": float, "success": bool}
        """
        start = time.perf_counter()

        try:
            incident_id = self._generate_incident_id(
                packet.session_id, packet.device_id, packet.timestamp
            )

            payload = {
                "raw_narrative": packet.visual_narrative,
                "session_id": packet.session_id,
                "device_id": packet.device_id,
                "timestamp": packet.timestamp,
                "trend_tag": trend.trend_tag,
                "hazard_level": packet.hazard_level,
                "fire_dominance": packet.scores.fire_dominance,
                "smoke_opacity": packet.scores.smoke_opacity,
                "proximity_alert": packet.scores.proximity_alert,
            }

            await self.client.upsert(
                collection_name="incident_log",
                id=incident_id,
                vector=vector,
                payload=payload,
            )

            write_time = (time.perf_counter() - start) * 1000
            logger.info(f"Incident logged: id={incident_id} in {write_time:.2f}ms")

            return {"incident_id": incident_id, "write_time_ms": write_time, "success": True}

        except Exception as e:
            write_time = (time.perf_counter() - start) * 1000
            logger.error(f"Incident logging failed: {e}")
            return {"incident_id": None, "write_time_ms": write_time, "success": False}
