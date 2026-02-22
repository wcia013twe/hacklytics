import time
import asyncio
from typing import List, Dict
from collections import deque
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logger = logging.getLogger(__name__)

class IncidentLoggerAgent:
    """
    Writes incidents to Actian incident_log table (batched every 2s).
    """

    def __init__(self, actian_connection_pool, batch_interval: int = 2):
        self.conn_pool = actian_connection_pool
        self.batch_interval = batch_interval
        self.write_buffer = deque()
        self.batch_task = None

    def format_incident_row(self, vector: List[float], narrative: str, metadata: Dict) -> Dict:
        """Task 7.1: Format incident row"""
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
        Task 7.2: Write incident (buffered, batched)

        Returns:
            {"incident_id": Optional[int], "write_time_ms": float, "success": bool}
        """
        row = self.format_incident_row(
            vector=vector,
            narrative=packet.visual_narrative,
            metadata={
                "session_id": packet.session_id,
                "device_id": packet.device_id,
                "timestamp": packet.timestamp,
                "trend_tag": trend.trend_tag,
                "hazard_level": packet.hazard_level,
                "fire_dominance": packet.scores.fire_dominance,
                "smoke_opacity": packet.scores.smoke_opacity,
                "proximity_alert": packet.scores.proximity_alert
            }
        )

        self.write_buffer.append(row)

        # Start batch flusher if not running
        if not self.batch_task or self.batch_task.done():
            self.batch_task = asyncio.create_task(self._batch_flush_loop())

        return {"incident_id": None, "write_time_ms": 0.0, "success": True}  # Queued

    async def _batch_flush_loop(self):
        """Background task: Flush buffer every 2s"""
        while True:
            await asyncio.sleep(self.batch_interval)
            if self.write_buffer:
                await self._flush_batch()

    async def _flush_batch(self) -> Dict:
        """Task 7.3: Batch flush to Actian"""
        if not self.write_buffer:
            return {"inserted_count": 0, "failed_count": 0, "flush_time_ms": 0}

        start = time.perf_counter()
        batch = list(self.write_buffer)
        self.write_buffer.clear()

        inserted = 0
        failed = 0

        try:
            async with self.conn_pool.acquire() as conn:
                for row in batch:
                    try:
                        await conn.execute("""
                            INSERT INTO incident_log (
                                narrative_vector, raw_narrative, session_id, device_id,
                                timestamp, trend_tag, hazard_level, fire_dominance,
                                smoke_opacity, proximity_alert
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """, row["narrative_vector"], row["raw_narrative"], row["session_id"],
                            row["device_id"], row["timestamp"], row["trend_tag"],
                            row["hazard_level"], row["fire_dominance"], row["smoke_opacity"],
                            row["proximity_alert"])
                        inserted += 1
                    except Exception as e:
                        logger.error(f"Failed to insert incident: {e}")
                        failed += 1
        except Exception as e:
            logger.error(f"Batch flush failed: {e}")
            failed = len(batch)

        flush_time = (time.perf_counter() - start) * 1000
        logger.info(f"Flushed {inserted} incidents in {flush_time:.2f}ms ({failed} failed)")

        return {"inserted_count": inserted, "failed_count": failed, "flush_time_ms": flush_time}
