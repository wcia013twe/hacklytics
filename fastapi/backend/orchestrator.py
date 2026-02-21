import time
import asyncio
import logging
from typing import Dict, Optional
from collections import defaultdict

from agents.telemetry_ingest import TelemetryIngestAgent
from agents.temporal_buffer import TemporalBufferAgent
from agents.reflex_publisher import ReflexPublisherAgent
from agents.embedding import EmbeddingAgent
from agents.protocol_retrieval import ProtocolRetrievalAgent
from agents.history_retrieval import HistoryRetrievalAgent
from agents.incident_logger import IncidentLoggerAgent
from agents.synthesis import SynthesisAgent
from contracts.models import TelemetryPacket

logger = logging.getLogger(__name__)


class OrchestratorMetrics:
    """Metrics collector for observability"""

    def __init__(self):
        self.counters = defaultdict(int)
        self.histograms = defaultdict(list)

    def increment(self, metric: str, value: int = 1):
        self.counters[metric] += value

    def record(self, metric: str, value: float):
        self.histograms[metric].append(value)

    def get_percentile(self, metric: str, p: int) -> float:
        """Calculate percentile (p50, p95, p99)"""
        import numpy as np
        if metric not in self.histograms or not self.histograms[metric]:
            return 0.0
        return np.percentile(self.histograms[metric], p)

    def summary(self) -> Dict:
        return {
            "counters": dict(self.counters),
            "latency_p50": self.get_percentile("reflex.latency_ms", 50),
            "latency_p95": self.get_percentile("reflex.latency_ms", 95),
            "rag_p50": self.get_percentile("rag.latency_ms", 50),
            "rag_p95": self.get_percentile("rag.latency_ms", 95)
        }


class RAGHealth:
    """Health monitor for RAG service"""

    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.last_heartbeat = time.time()
        self.failures = 0

    def is_healthy(self) -> bool:
        age = time.time() - self.last_heartbeat
        return age < self.timeout and self.failures < 3

    def mark_success(self):
        self.last_heartbeat = time.time()
        self.failures = 0

    def mark_failure(self):
        self.failures += 1


class RAGOrchestrator:
    """
    Master coordinator for dual-path RAG system.

    Manages execution flow:
    1. Stage 1: Intake & validation
    2. Stage 2: Reflex path (synchronous, critical)
    3. Stage 3: Cognition path (asynchronous, best-effort)
    4. Stage 4: Validation
    5. Stage 5: Error recovery
    6. Stage 6: Logging
    """

    def __init__(self, actian_pool=None):
        # Initialize all agents
        self.telemetry_agent = TelemetryIngestAgent()
        self.temporal_buffer = TemporalBufferAgent(window_seconds=10)
        self.reflex_publisher = ReflexPublisherAgent()
        self.embedding_agent = EmbeddingAgent()
        self.protocol_agent = ProtocolRetrievalAgent(actian_pool) if actian_pool else None
        self.history_agent = HistoryRetrievalAgent(actian_pool) if actian_pool else None
        self.incident_logger = IncidentLoggerAgent(actian_pool) if actian_pool else None
        self.synthesis_agent = SynthesisAgent()

        # State management
        self.metrics = OrchestratorMetrics()
        self.rag_health = RAGHealth(timeout=5)
        self.actian_pool = actian_pool

    async def startup(self):
        """
        Initialize orchestrator: warmup models, pre-load indexes
        """
        logger.info("RAGOrchestrator starting up...")

        # Warmup embedding model (critical: first call is slow)
        await self.embedding_agent.warmup_model()

        # TODO: Warmup Actian indexes with dummy query
        # if self.protocol_agent:
        #     await self.protocol_agent.warmup_query()

        logger.info("RAGOrchestrator ready")

    async def process_packet(self, raw_message: str) -> Dict:
        """
        Main entry point: Process one telemetry packet through dual-path pipeline.

        Returns:
            {
                "reflex_result": {...},
                "rag_result": {...} or None,
                "total_time_ms": float
            }
        """
        pipeline_start = time.perf_counter()

        # STAGE 1: Intake & Validation
        intake_result = await self.stage_1_intake(raw_message)
        if not intake_result["success"]:
            self.metrics.increment("packets.invalid")
            return {"error": "intake_failed", "details": intake_result["errors"]}

        packet = intake_result["packet"]
        self.metrics.increment("packets.valid")

        # STAGE 2: Reflex Path (CRITICAL - must always execute)
        try:
            reflex_result = await self.stage_2_reflex(packet)
            self.metrics.record("reflex.latency_ms", reflex_result["latency_ms"])

            if reflex_result["latency_ms"] > 50:
                logger.warning(f"Reflex path slow: {reflex_result['latency_ms']:.2f}ms > 50ms")

        except Exception as e:
            logger.error(f"CRITICAL: Reflex path failed: {e}", exc_info=True)
            self.metrics.increment("reflex.failures")
            return {"error": "reflex_failed", "exception": str(e)}

        # STAGE 3: Cognition Path (async, fire-and-forget)
        if self.should_invoke_rag(packet, reflex_result):
            asyncio.create_task(
                self.stage_3_cognition(packet, reflex_result["trend"])
            )
        else:
            logger.debug(f"Skipping RAG: hazard={packet.hazard_level}, rag_healthy={self.rag_health.is_healthy()}")

        total_time = (time.perf_counter() - pipeline_start) * 1000

        return {
            "success": True,
            "reflex_result": reflex_result,
            "total_time_ms": total_time
        }

    async def stage_1_intake(self, raw_message: str) -> Dict:
        """
        Stage 1: Validate schema and route to buffer

        Returns:
            {"success": bool, "packet": TelemetryPacket or None, "errors": list}
        """
        start = time.perf_counter()

        # Task 1.2: Validate schema
        valid, result = await self.telemetry_agent.validate_schema(raw_message)

        if not valid:
            return {
                "success": False,
                "packet": None,
                "errors": result["errors"],
                "stage_time_ms": (time.perf_counter() - start) * 1000
            }

        packet = result["parsed_packet"]

        # Task 1.3: Route to buffer
        buffer_key = await self.telemetry_agent.route_to_buffer(packet)

        stage_time = (time.perf_counter() - start) * 1000
        logger.debug(f"Stage 1 intake: {stage_time:.2f}ms")

        return {
            "success": True,
            "packet": packet,
            "buffer_key": buffer_key,
            "errors": [],
            "stage_time_ms": stage_time
        }

    async def stage_2_reflex(self, packet: TelemetryPacket) -> Dict:
        """
        Stage 2: Reflex path execution (CRITICAL - <50ms target)

        Steps:
        1. Insert packet into temporal buffer
        2. Evict stale packets (>10s old)
        3. Compute fire growth trend
        4. Format reflex message
        5. Broadcast to WebSocket clients

        Returns:
            {"success": bool, "trend": TrendResult, "latency_ms": float}
        """
        start = time.perf_counter()

        device_id = packet.device_id

        # Task 2.1: Insert packet
        await self.temporal_buffer.insert_packet(device_id, packet)

        # Task 2.2: Evict stale
        await self.temporal_buffer.evict_stale(device_id, packet.timestamp)

        # Task 2.3: Compute trend
        trend = await self.temporal_buffer.compute_trend(device_id)

        # Task 3.1: Format reflex message
        reflex_message = await self.reflex_publisher.format_reflex_message(packet, trend)

        # Task 3.2: WebSocket broadcast
        broadcast_result = await self.reflex_publisher.websocket_broadcast(
            reflex_message,
            session_id=packet.session_id,
            timeout_ms=10
        )

        latency = (time.perf_counter() - start) * 1000

        logger.info(
            f"Reflex: {packet.device_id} | {packet.hazard_level} | {trend.trend_tag} | "
            f"{latency:.2f}ms | {broadcast_result['clients_reached']} clients"
        )

        return {
            "success": True,
            "trend": trend,
            "clients_reached": broadcast_result["clients_reached"],
            "latency_ms": latency
        }

    async def stage_3_cognition(self, packet: TelemetryPacket, trend):
        """
        Stage 3: Cognition path execution (async, <2s target)

        Steps:
        1. Embed visual narrative
        2. Retrieve protocols + history (parallel)
        3. Log incident (fire-and-forget)
        4. Synthesize recommendation
        5. Broadcast to WebSocket

        This is fire-and-forget: exceptions are logged but don't propagate.
        """
        start = time.perf_counter()
        request_id = f"{packet.device_id}_{packet.timestamp}"

        try:
            # Task 4.1: Embed narrative
            embedding = await self.embedding_agent.embed_text(
                text=packet.visual_narrative,
                request_id=request_id
            )

            # Tasks 5.2 & 6.2: Parallel retrieval (total ~200ms, not 400ms)
            protocol_task = self.protocol_agent.execute_vector_search(
                vector=embedding.vector,
                severity=["HIGH", "CRITICAL"],
                top_k=3,
                timeout=200
            ) if self.protocol_agent else self._mock_protocols()

            history_task = self.history_agent.execute_history_search(
                vector=embedding.vector,
                session_id=packet.session_id,
                similarity_threshold=0.70,
                top_k=5,
                timeout=200
            ) if self.history_agent else self._mock_history()

            protocols, history = await asyncio.gather(
                protocol_task,
                history_task,
                return_exceptions=True
            )

            # Handle partial failures
            if isinstance(protocols, Exception):
                logger.error(f"Protocol retrieval failed: {protocols}")
                protocols = []
                self.metrics.increment("rag.protocol_failures")

            if isinstance(history, Exception):
                logger.error(f"History retrieval failed: {history}")
                history = []
                self.metrics.increment("rag.history_failures")

            # Task 7.2: Log incident (fire-and-forget, batched)
            if self.incident_logger:
                asyncio.create_task(
                    self.incident_logger.write_to_actian(
                        vector=embedding.vector,
                        packet=packet,
                        trend=trend
                    )
                )

            # Task 8.2: Synthesize recommendation
            recommendation = await self.synthesis_agent.render_template(
                protocols=protocols,
                history=history,
                current_context={
                    "hazard_level": packet.hazard_level,
                    "trend_tag": trend.trend_tag,
                    "growth_rate": trend.growth_rate,
                    "proximity_alert": packet.scores.proximity_alert
                }
            )

            # Broadcast RAG recommendation to dashboard
            rag_message = {
                "message_type": "rag_recommendation",
                "device_id": packet.device_id,
                "recommendation": recommendation.recommendation,
                "matched_protocol": recommendation.matched_protocol,
                "processing_time_ms": (time.perf_counter() - start) * 1000,
                "protocols_count": len(protocols),
                "history_count": len(history)
            }

            await self.reflex_publisher.websocket_broadcast(
                rag_message,
                session_id=packet.session_id,
                timeout_ms=10
            )

            total_time = (time.perf_counter() - start) * 1000
            self.metrics.record("rag.latency_ms", total_time)
            self.rag_health.mark_success()

            logger.info(
                f"RAG: {packet.device_id} | {total_time:.2f}ms | "
                f"{len(protocols)} protocols | {len(history)} history"
            )

            if total_time > 2000:
                logger.warning(f"RAG latency {total_time:.2f}ms exceeds 2s SLA")

        except Exception as e:
            logger.error(f"Cognition path failed: {e}", exc_info=True)
            self.metrics.increment("rag.failures")
            self.rag_health.mark_failure()

    def should_invoke_rag(self, packet: TelemetryPacket, reflex_result: Dict) -> bool:
        """
        Decide whether to invoke RAG cognition path.

        Criteria:
        1. Hazard level is HIGH or CRITICAL
        2. RAG service is healthy (last success <5s ago, <3 consecutive failures)
        3. Visual narrative is non-empty
        """
        return (
            packet.hazard_level in ["HIGH", "CRITICAL"] and
            self.rag_health.is_healthy() and
            len(packet.visual_narrative) > 10
        )

    async def _mock_protocols(self):
        """Mock protocol retrieval for testing without Actian"""
        return []

    async def _mock_history(self):
        """Mock history retrieval for testing without Actian"""
        return []


class LatencyTracker:
    """Track latency breakdown for debugging"""

    def __init__(self):
        self.stages = {}
        self.start_time = None

    def start(self):
        self.start_time = time.perf_counter()

    def mark(self, stage: str):
        if not self.start_time:
            self.start()
        elapsed = (time.perf_counter() - self.start_time) * 1000
        self.stages[stage] = elapsed

    def summary(self) -> Dict:
        return {
            "stages": self.stages,
            "total_ms": max(self.stages.values()) if self.stages else 0
        }
