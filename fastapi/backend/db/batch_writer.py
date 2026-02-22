import asyncio
import time
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class IncidentBatchWriter:
    """
    Accumulates incident_log writes and flushes to Actian periodically.

    Design (from RAG.MD 3.4.5):
    - Time-based trigger: flushes every flush_interval_seconds
    - Background asyncio task runs flush loop
    - Thread-safe for concurrent add_incident() calls
    - Graceful shutdown: flushes remaining incidents on cleanup
    """

    def __init__(self, db_connection_pool, flush_interval_seconds: float = 2.0):
        self.db_pool = db_connection_pool
        self.flush_interval = flush_interval_seconds
        self.buffer: List[Dict] = []
        self.buffer_lock = asyncio.Lock()
        self.flush_task = None
        self.running = False

    async def start(self):
        """Start the background flush task."""
        self.running = True
        self.flush_task = asyncio.create_task(self._flush_loop())
        logger.info(f"IncidentBatchWriter started (flush every {self.flush_interval}s)")

    async def stop(self):
        """Stop the background task and flush remaining incidents."""
        self.running = False
        if self.flush_task:
            await self.flush_task
        await self._flush()  # Final flush
        logger.info("IncidentBatchWriter stopped")

    async def add_incident(self, incident: Dict):
        """
        Add an incident to the batch buffer.

        Args:
            incident: Dict with keys matching incident_log schema:
                - timestamp, session_id, device_id
                - narrative_vector, raw_narrative
                - trend_tag, hazard_level
                - fire_dominance, smoke_opacity, proximity_alert
        """
        async with self.buffer_lock:
            self.buffer.append(incident)

            # Safety: if buffer grows too large (>100 incidents), flush immediately
            if len(self.buffer) >= 100:
                logger.warning(f"Buffer overflow at {len(self.buffer)} incidents, flushing early")
                await self._flush()

    async def _flush_loop(self):
        """Background task that flushes buffer every flush_interval seconds."""
        while self.running:
            await asyncio.sleep(self.flush_interval)
            await self._flush()

    async def _flush(self):
        """Write all buffered incidents to Actian in a single transaction."""
        async with self.buffer_lock:
            if not self.buffer:
                return  # Nothing to flush

            incidents = self.buffer.copy()
            self.buffer.clear()

        # Execute batch insert in a transaction
        start = time.perf_counter()
        try:
            await self._batch_insert(incidents)
            flush_time = (time.perf_counter() - start) * 1000
            logger.info(f"✓ Flushed {len(incidents)} incidents to Actian in {flush_time:.2f}ms")
        except Exception as e:
            logger.error(f"✗ Batch write failed: {e}")
            # For safety-critical systems, log failure and continue (don't retry to avoid blocking)

    async def _batch_insert(self, incidents: List[Dict]):
        """
        Insert multiple incidents using parameterized batch query.

        Uses Actian's executemany() for efficient batch inserts.
        """
        query = """
        INSERT INTO incident_log (
            timestamp, session_id, device_id,
            narrative_vector, raw_narrative,
            trend_tag, hazard_level,
            fire_dominance, smoke_opacity, proximity_alert
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """

        async with self.db_pool.acquire() as conn:
            await conn.executemany(query, [
                (
                    inc['timestamp'],
                    inc['session_id'],
                    inc['device_id'],
                    inc['narrative_vector'],
                    inc['raw_narrative'],
                    inc['trend_tag'],
                    inc['hazard_level'],
                    inc['fire_dominance'],
                    inc['smoke_opacity'],
                    inc['proximity_alert']
                )
                for inc in incidents
            ])
