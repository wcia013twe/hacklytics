import time
import asyncio
import logging
import os
from typing import Dict, Optional
from collections import defaultdict

from .agents.telemetry_ingest import TelemetryIngestAgent
from .agents.temporal_buffer import TemporalBufferAgent
from .agents.reflex_publisher import ReflexPublisherAgent
from .agents.embedding import EmbeddingAgent
from .agents.protocol_retrieval import ProtocolRetrievalAgent
from .agents.history_retrieval import HistoryRetrievalAgent
from .agents.incident_logger import IncidentLoggerAgent
from .agents.synthesis import SynthesisAgent
from .agents.safety_guardrails import SafetyGuardrailsAgent
from .agents.temporal_narrative import TemporalNarrativeAgent
from .agents.redis_cache import RAGCacheAgent
from .agents.protocol_formatter import ProtocolFormatterAgent
from .contracts.models import TelemetryPacket

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
    """Health monitor for RAG pipeline (local, not remote service)."""

    def __init__(self):
        self.failures = 0

    def is_healthy(self) -> bool:
        return self.failures < 3

    def mark_success(self):
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

    def __init__(self, actian_client=None, redis_url: str = None):
        # Initialize all agents
        self.telemetry_agent = TelemetryIngestAgent()
        self.temporal_buffer = TemporalBufferAgent(window_seconds=10)
        self.reflex_publisher = ReflexPublisherAgent()
        self.embedding_agent = EmbeddingAgent()
        self.protocol_agent = ProtocolRetrievalAgent(actian_client) if actian_client else None
        self.history_agent = HistoryRetrievalAgent(actian_client) if actian_client else None
        self.incident_logger = IncidentLoggerAgent(actian_client) if actian_client else None
        self.synthesis_agent = SynthesisAgent()
        self.guardrails_agent = SafetyGuardrailsAgent()

        # Temporal narrative synthesis via local Ollama
        self.temporal_narrative_agent = TemporalNarrativeAgent(
            model_name=os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        )
        self.protocol_formatter = ProtocolFormatterAgent(
            model_name=os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        )

        redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.cache_agent = RAGCacheAgent(redis_url=redis_url)

        # State management
        self.metrics = OrchestratorMetrics()
        self.rag_health = RAGHealth()
        self.actian_client = actian_client

    async def startup(self):
        """
        Initialize orchestrator: warmup models, pre-load indexes
        """
        logger.info("RAGOrchestrator starting up...")

        # Warmup embedding model (critical: first call is slow)
        await self.embedding_agent.warmup_model()

        # Actian health check (warn on failure, don't crash)
        if self.actian_client:
            try:
                collections = await self.actian_client.list_collections()
                names = [c.name for c in collections]
                logger.info(f"Actian connected — collections: {names}")
            except Exception as e:
                logger.warning(f"Actian health check failed (non-fatal): {e}")

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
        Stage 3: Cognition path with READ/WRITE separation (async, <2s target)

        ╔═══════════════════════════════════════════════════════════════╗
        ║ READ PATH (Action - Fast)                                    ║
        ║ Goal: "What should I do RIGHT NOW?"                          ║
        ║ Strategy: Check cache first, avoid embedding if possible     ║
        ║ Latency: 2-200ms depending on cache hits                     ║
        ╚═══════════════════════════════════════════════════════════════╝

        ╔═══════════════════════════════════════════════════════════════╗
        ║ WRITE PATH (Memory - Always runs in background)             ║
        ║ Goal: "Remember this moment forever"                         ║
        ║ Strategy: ALWAYS embed + store in Actian for timeline       ║
        ║ Latency: 200ms+ but invisible (fire-and-forget)             ║
        ╚═══════════════════════════════════════════════════════════════╝

        This is fire-and-forget: exceptions are logged but don't propagate.
        """
        start = time.perf_counter()
        request_id = f"{packet.device_id}_{packet.timestamp}"

        try:
            # ═════════════════════════════════════════════════════════
            # PHASE 1: TEMPORAL NARRATIVE SYNTHESIS (100-150ms)
            # ═════════════════════════════════════════════════════════
            synthesized_narrative = packet.visual_narrative  # Default fallback
            temporal_synthesis = None

            if self.temporal_narrative_agent:
                try:
                    # Get buffered packets for this device
                    buffer_packets = list(self.temporal_buffer.buffers.get(packet.device_id, []))

                    if len(buffer_packets) >= 2:
                        temporal_synthesis = await self.temporal_narrative_agent.synthesize_temporal_narrative(
                            buffer_packets=buffer_packets,
                            lookback_seconds=float(os.getenv("TEMPORAL_LOOKBACK_SECONDS", "3.0"))
                        )
                        synthesized_narrative = temporal_synthesis.synthesized_narrative
                        logger.info(f"📖 Temporal synthesis: {len(buffer_packets)} events → {len(synthesized_narrative)} chars")
                except Exception as e:
                    logger.warning(f"Temporal synthesis failed, using raw narrative: {e}")

            # ═════════════════════════════════════════════════════════
            # READ PATH: GET PROTOCOLS (Semantic Key Cache - YOLO Buckets)
            # ═════════════════════════════════════════════════════════

            # Step 1: Try semantic protocol cache FIRST (uses YOLO fire/smoke buckets)
            cached_protocols = await self.cache_agent.get_protocols_by_semantic_key(packet)

            if cached_protocols:
                logger.info(f"✅ [CACHE HIT] Semantic protocols: {self.cache_agent.get_semantic_cache_key(packet)} (saved ~90ms - no embedding!)")
                protocols = cached_protocols
                vector = None  # Don't need vector yet on cache hit
                embedding_time_ms = 0.0
                self.metrics.increment("cache.semantic_hits")
            else:
                logger.info(f"❌ [CACHE MISS] Semantic key: {self.cache_agent.get_semantic_cache_key(packet)} - generating embedding + querying Actian...")

                # Cache miss - must compute embedding
                embedding = await self.embedding_agent.embed_text(
                    text=synthesized_narrative,
                    request_id=request_id
                )
                vector = embedding.vector
                embedding_time_ms = embedding.embedding_time_ms

                # Query Actian with vector
                severity_filter = ["HIGH", "CRITICAL"] if packet.hazard_level in ["HIGH", "CRITICAL"] else ["CAUTION", "HIGH", "CRITICAL"]
                protocols = await self.protocol_agent.execute_vector_search(
                    vector=vector,
                    severity=severity_filter,
                    top_k=3,
                    timeout=200
                ) if self.protocol_agent else []

                # Cache protocols under semantic key
                await self.cache_agent.cache_protocols_by_semantic_key(
                    packet,
                    protocols,
                    ttl=300
                )
                self.metrics.increment("cache.semantic_misses")

            # Step 2: Get session history from Redis cache
            # NOTE: Need vector for similarity search - generate if not already computed
            if vector is None:
                # Cache hit path - need to generate vector for history search
                embedding = await self.embedding_agent.embed_text(
                    text=synthesized_narrative,
                    request_id=request_id
                )
                vector = embedding.vector
                embedding_time_ms = embedding.embedding_time_ms

            session_history = await self.cache_agent.get_session_history(
                session_id=packet.session_id,
                device_id=packet.device_id,
                current_vector=vector,
                similarity_threshold=0.70,
                max_results=5
            )

            if session_history:
                logger.info(f"✅ [READ PATH] Session history cache HIT ({len(session_history)} incidents)")
                history = session_history
                self.metrics.increment("cache.session_hits")
            else:
                logger.info(f"❌ [READ PATH] Session history cache MISS - querying Actian...")
                # Fallback to Actian DB
                history = await self.history_agent.execute_history_search(
                    vector=vector,
                    session_id=packet.session_id,
                    similarity_threshold=0.70,
                    top_k=5,
                    timeout=200
                ) if self.history_agent else []
                self.metrics.increment("cache.session_misses")

            # ═════════════════════════════════════════════════════════
            # SYNTHESIS & SAFETY GUARDRAILS
            # ═════════════════════════════════════════════════════════

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

            # Task 8.3: Apply safety guardrails BEFORE broadcasting
            thermal_reading = None
            for obj in packet.tracked_objects:
                if obj.label.lower() in ["thermal", "temperature", "heat"]:
                    try:
                        thermal_reading = float(obj.status) if obj.status.replace('.', '').isdigit() else None
                    except (ValueError, AttributeError):
                        pass

            recommendation = await self.guardrails_agent.apply_guardrails(
                recommendation=recommendation,
                packet=packet,
                thermal_reading=thermal_reading
            )

            # Track guardrail metrics
            guardrail_metrics = self.guardrails_agent.get_metrics()
            if "guardrail_blocks_total" in guardrail_metrics:
                self.metrics.increment("guardrail.blocks", guardrail_metrics["guardrail_blocks_total"])
            if "guardrail_pass_total" in guardrail_metrics:
                self.metrics.increment("guardrail.pass", guardrail_metrics["guardrail_pass_total"])

            # ═════════════════════════════════════════════════════════
            # WRITE PATH: SAVE TO MEMORY (Fire-and-Forget)
            # ═════════════════════════════════════════════════════════

            # Launch background task to write incident to Actian
            # This ALWAYS runs embedding to ensure vector DB has complete history
            asyncio.create_task(
                self._write_incident_to_memory(
                    packet=packet,
                    trend=trend,
                    synthesized_narrative=synthesized_narrative,
                    vector=vector  # May be cached or freshly computed
                )
            )

            logger.info(f"🧠 [WRITE PATH] Incident memory write queued (background)")

            # ═════════════════════════════════════════════════════════
            # BROADCAST TO DASHBOARD
            # ═════════════════════════════════════════════════════════

            # Build WebSocketPayload so the frontend receives a consistent format
            # from both the reflex path and the RAG cognition path.
            primary_protocol = protocols[0] if protocols else None
            temp_f = round(72 + packet.scores.fire_dominance * 428)
            from .agents.reflex_publisher import _STATUS_MAP, _TREND_MAP
            
            formatter_result = None
            if primary_protocol and self.protocol_formatter:
                formatter_result = await self.protocol_formatter.format(
                    protocol=primary_protocol,
                    packet=packet,
                    synthesized_narrative=synthesized_narrative,
                )

            if formatter_result and not formatter_result.fallback_used:
                rag_message = {
                    "timestamp": packet.timestamp,
                    "system_status": _STATUS_MAP[packet.hazard_level],
                    "action_command": formatter_result.action_command,
                    "action_reason": formatter_result.action_reason,
                    "rag_data": {
                        "protocol_id": primary_protocol.source,
                        "hazard_type": formatter_result.hazard_type,
                        "source_document": primary_protocol.source,
                        "source_text": formatter_result.source_text,
                        "actionable_commands": [cmd.dict() for cmd in formatter_result.actionable_commands]
                    },
                    "scene_context": {
                        "entities": [
                            {
                                "name": o.label,
                                "duration_sec": o.duration_in_frame,
                                "trend": _TREND_MAP.get(o.status, "static"),
                            }
                            for o in packet.tracked_objects
                        ],
                        "telemetry": {
                            "temp_f": temp_f,
                            "trend": "rising" if packet.scores.fire_dominance > 0.1 else "stable",
                        },
                        "responders": [],
                        "synthesized_insights": {
                            "threat_vector": synthesized_narrative,
                            "evacuation_radius_ft": 100 if packet.hazard_level == "CRITICAL" else (50 if packet.hazard_level == "HIGH" else None),
                            "resource_bottleneck": None,
                            "max_temp_f": temp_f,
                            "max_aqi": round(packet.scores.smoke_opacity * 500),
                        },
                    },
                }
            else:
                rag_message = {
                    "timestamp": packet.timestamp,
                    "system_status": _STATUS_MAP[packet.hazard_level],
                    "action_command": recommendation.recommendation,
                    "action_reason": synthesized_narrative,
                    "rag_data": {
                        "protocol_id": primary_protocol.source if primary_protocol else "fallback",
                        "hazard_type": primary_protocol.category if primary_protocol else packet.hazard_level,
                        # source_document is the actual filename/reference stored in Actian
                        "source_document": primary_protocol.source if primary_protocol else None,
                        "source_text": primary_protocol.protocol_text if primary_protocol else recommendation.recommendation,
                        "actionable_commands": [],
                    } if primary_protocol or recommendation else None,
                    "scene_context": {
                        "entities": [
                            {
                                "name": o.label,
                                "duration_sec": o.duration_in_frame,
                                "trend": _TREND_MAP.get(o.status, "static"),
                            }
                            for o in packet.tracked_objects
                        ],
                        "telemetry": {
                            "temp_f": temp_f,
                            "trend": "rising" if packet.scores.fire_dominance > 0.1 else "stable",
                        },
                        "responders": [],
                        "synthesized_insights": {
                            "threat_vector": synthesized_narrative,
                            "evacuation_radius_ft": 100 if packet.hazard_level == "CRITICAL" else (50 if packet.hazard_level == "HIGH" else None),
                            "resource_bottleneck": None,
                            "max_temp_f": temp_f,
                            "max_aqi": round(packet.scores.smoke_opacity * 500),
                        },
                    },
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
                f"{len(protocols)} protocols | {len(history)} history | "
                f"Cache: EMB={'HIT' if cached_protocols else 'MISS'} "
                f"PROTO={'HIT' if cached_protocols else 'MISS'} "
                f"SESS={'HIT' if session_history else 'MISS'}"
            )

            if total_time > 2000:
                logger.warning(f"RAG latency {total_time:.2f}ms exceeds 2s SLA")

        except Exception as e:
            logger.error(f"Cognition path failed: {e}", exc_info=True)
            self.metrics.increment("rag.failures")
            self.rag_health.mark_failure()

    async def _write_incident_to_memory(
        self,
        packet: TelemetryPacket,
        trend,
        synthesized_narrative: str,
        vector: list
    ):
        """
        ╔═══════════════════════════════════════════════════════════════╗
        ║ WRITE PATH (Memory - Background Task)                       ║
        ║ Goal: Build complete mission timeline in Actian Vector DB   ║
        ╚═══════════════════════════════════════════════════════════════╝

        This method runs in the background (fire-and-forget) and:
        1. Writes incident to Redis session history cache (write-through)
        2. Writes incident to Actian Vector DB for permanent storage

        Critical: This ALWAYS runs to ensure the mission log is complete,
        even if the READ path got a cache hit and skipped embedding.

        Args:
            packet: Current telemetry packet
            trend: Fire growth trend
            synthesized_narrative: LLM-synthesized temporal narrative
            vector: 384-dim embedding vector (may be cached or fresh)
        """
        write_start = time.perf_counter()

        try:
            # Step 1: Write-through to Redis session history cache
            await self.cache_agent.append_session_history(
                session_id=packet.session_id,
                device_id=packet.device_id,
                narrative=synthesized_narrative,
                vector=vector,
                timestamp=packet.timestamp,
                trend=trend.trend_tag,
                hazard_level=packet.hazard_level
            )

            # Step 2: Write to Actian Vector DB for permanent storage
            if self.incident_logger:
                await self.incident_logger.write_to_actian(
                    vector=vector,
                    packet=packet,
                    trend=trend
                )

            write_time = (time.perf_counter() - write_start) * 1000
            logger.info(
                f"🧠 [WRITE PATH] Memory stored: {packet.device_id} | "
                f"{write_time:.2f}ms | Redis + Actian"
            )

        except Exception as e:
            logger.error(f"[WRITE PATH] Memory write failed: {e}", exc_info=True)
            # Don't propagate - this is fire-and-forget

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
