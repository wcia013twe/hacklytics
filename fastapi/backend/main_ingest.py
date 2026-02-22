import asyncio
import json
import logging
import time
import zmq
import zmq.asyncio
from pathlib import Path
from typing import Dict, List, Tuple
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from .orchestrator import RAGOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global orchestrator instance
orchestrator: RAGOrchestrator = None
zmq_task = None

# ==============================================================================
# DEMO MODE: Embedded scenario data for multi-location demo
# ==============================================================================

DEMO_SCENARIOS = {
    "kitchen": {
        "responder_id": "DEMO_KITCHEN",
        "location": "Kitchen (Building A)",
        "events": [
            {
                "timestamp_offset": 0,
                "hazard_level": "CAUTION",
                "narrative": "Small grease fire detected on stove. Smoke detector activated.",
                "protocol_id": "205",
                "hazard_type": "Combustible Area",
                "commands": [
                    {"target": "Alpha-1", "directive": "Report fire size & trend"}
                ]
            },
            {
                "timestamp_offset": 15,
                "hazard_level": "HIGH",
                "narrative": "Fire spreading to nearby cabinets. Flames reaching 3ft height.",
                "protocol_id": "305",
                "hazard_type": "Active Fire Growth",
                "commands": [
                    {"target": "Alpha-1", "directive": "Deploy class B extinguisher"},
                    {"target": "Charlie-3", "directive": "Monitor AQI levels"}
                ]
            },
            {
                "timestamp_offset": 30,
                "hazard_level": "CRITICAL",
                "narrative": "FLASHOVER IMMINENT. Full room involvement. Evacuate immediately.",
                "protocol_id": "402",
                "hazard_type": "Flashover Risk",
                "commands": [
                    {"target": "Alpha-1", "directive": "EVACUATE NORTH - 100FT (BLEVE)"}
                ]
            },
            {
                "timestamp_offset": 45,
                "hazard_level": "CRITICAL",
                "narrative": "Post-flashover. Sustained 500F+ temperatures. Structure compromised.",
                "protocol_id": "71A",
                "hazard_type": "Structural Collapse",
                "commands": [
                    {"target": "ALL UNITS", "directive": "MINIMUM 100FT STANDOFF"}
                ]
            }
        ]
    },
    "hallway": {
        "responder_id": "DEMO_HALLWAY",
        "location": "Hallway (Building A)",
        "events": [
            {
                "timestamp_offset": 0,
                "hazard_level": "CLEAR",
                "narrative": "Routine patrol. No hazards detected. All exits clear.",
                "protocol_id": "100",
                "hazard_type": "None",
                "commands": [
                    {"target": "ALL UNITS", "directive": "Maintain patrol vectors"}
                ]
            },
            {
                "timestamp_offset": 20,
                "hazard_level": "CAUTION",
                "narrative": "Smoke entering from kitchen door. Visibility reducing to 30ft.",
                "protocol_id": "220",
                "hazard_type": "Smoke Propagation",
                "commands": [
                    {"target": "Bravo-2", "directive": "Monitor smoke density"},
                    {"target": "Charlie-3", "directive": "Prepare thermal imaging"}
                ]
            },
            {
                "timestamp_offset": 35,
                "hazard_level": "HIGH",
                "narrative": "Heavy smoke. Visibility <10ft. Emergency lighting activated.",
                "protocol_id": "330",
                "hazard_type": "Zero Visibility Environment",
                "commands": [
                    {"target": "Bravo-2", "directive": "Activate SCBA"},
                    {"target": "Charlie-3", "directive": "Establish rope guideline"}
                ]
            },
            {
                "timestamp_offset": 50,
                "hazard_level": "HIGH",
                "narrative": "Near-zero visibility. Thermal imaging required. Exit routes compromised.",
                "protocol_id": "330",
                "hazard_type": "Zero Visibility Environment",
                "commands": [
                    {"target": "Bravo-2", "directive": "Mark egress path with chem lights"}
                ]
            }
        ]
    },
    "living_room": {
        "responder_id": "DEMO_LIVING_ROOM",
        "location": "Living Room (Building A)",
        "events": [
            {
                "timestamp_offset": 0,
                "hazard_level": "CLEAR",
                "narrative": "Normal conditions. Structural integrity nominal.",
                "protocol_id": "100",
                "hazard_type": "None",
                "commands": [
                    {"target": "ALL UNITS", "directive": "Continue monitoring"}
                ]
            },
            {
                "timestamp_offset": 40,
                "hazard_level": "CAUTION",
                "narrative": "Elevated ambient temperature. Minor structural stress indicators detected.",
                "protocol_id": "240",
                "hazard_type": "Structural Monitoring",
                "commands": [
                    {"target": "Delta-4", "directive": "Inspect load-bearing walls"},
                    {"target": "Echo-5", "directive": "Monitor ceiling integrity"}
                ]
            },
            {
                "timestamp_offset": 50,
                "hazard_level": "HIGH",
                "narrative": "Ceiling integrity compromised. Visible cracks. Load-bearing wall stressed.",
                "protocol_id": "71A",
                "hazard_type": "Structural Collapse Risk",
                "commands": [
                    {"target": "Delta-4", "directive": "EVACUATE - Collapse imminent"},
                    {"target": "Echo-5", "directive": "Establish collapse zone perimeter"}
                ]
            }
        ]
    }
}

# ==============================================================================
# DEMO MODE: DemoManager class
# ==============================================================================

class DemoManager:
    """
    Manages demo mode: broadcasts scripted fake RAG results on timeline

    ZERO PIPELINE POLLUTION:
    - Does NOT call orchestrator.process_packet()
    - Does NOT write to database
    - Only broadcasts fake WebSocket messages
    """

    def __init__(self, reflex_publisher):
        self.reflex_publisher = reflex_publisher
        self.demo_task = None
        self.running = False
        self.start_time = None

    async def start(self) -> Dict:
        """Start demo: spawn asyncio task broadcasting fake RAG messages"""
        if self.running:
            return {"status": "already_running", "elapsed_sec": time.time() - self.start_time}

        self.start_time = time.time()
        self.demo_task = asyncio.create_task(self._run_demo())
        self.running = True

        logger.info("🎬 Demo mode started")
        return {
            "status": "started",
            "duration_sec": 60,
            "scenarios": len(DEMO_SCENARIOS)
        }

    async def stop(self) -> Dict:
        """Stop demo: cancel asyncio task"""
        if not self.running:
            return {"status": "not_running"}

        if self.demo_task:
            self.demo_task.cancel()
            try:
                await self.demo_task
            except asyncio.CancelledError:
                pass

        elapsed = time.time() - self.start_time if self.start_time else 0
        self.running = False
        self.demo_task = None

        logger.info(f"🛑 Demo mode stopped (ran for {elapsed:.1f}s)")
        return {"status": "stopped", "elapsed_sec": elapsed}

    def get_status(self) -> Dict:
        """Get demo status"""
        if not self.running:
            return {"running": False, "scenarios": len(DEMO_SCENARIOS)}

        elapsed = time.time() - self.start_time if self.start_time else 0
        return {
            "running": True,
            "elapsed_sec": elapsed,
            "scenarios": len(DEMO_SCENARIOS),
            "timeline_events": len(self._build_timeline())
        }

    async def _run_demo(self):
        """
        Main demo loop: broadcasts fake RAG messages according to timeline
        Runs for 60 seconds total
        """
        try:
            timeline = self._build_timeline()
            logger.info(f"📋 Demo timeline: {len(timeline)} events over 60s")

            for timestamp, event in timeline:
                # Wait until event time
                elapsed = time.time() - self.start_time
                wait = timestamp - elapsed

                if wait > 0:
                    await asyncio.sleep(wait)

                # Broadcast fake RAG message
                fake_rag = self._build_fake_rag(event)
                await self.reflex_publisher.websocket_broadcast(
                    fake_rag,
                    session_id="demo_mode",
                    timeout_ms=50
                )

                logger.info(
                    f"📡 T+{int(time.time() - self.start_time):2d}s | "
                    f"{event['location']:20s} | {event['hazard_level']:8s} | "
                    f"{event['narrative'][:40]}..."
                )

                # If CRITICAL event, also trigger aggregation
                if event['hazard_level'] == 'CRITICAL' and not hasattr(self, '_aggregation_sent'):
                    self._aggregation_sent = True
                    fake_aggregation = self._build_fake_aggregation()
                    await self.reflex_publisher.websocket_broadcast(
                        fake_aggregation,
                        session_id="demo_mode",
                        timeout_ms=50
                    )
                    logger.info("🚨 AGGREGATION TRIGGERED - Building-wide emergency")

            logger.info("✅ Demo completed (60s)")
            self.running = False

        except asyncio.CancelledError:
            logger.info("🛑 Demo cancelled")
            raise
        except Exception as e:
            logger.error(f"❌ Demo error: {e}", exc_info=True)
            self.running = False

    def _build_timeline(self) -> List[Tuple[float, Dict]]:
        """
        Build timeline: merge all scenarios into single sorted timeline

        Returns:
            List of (timestamp, event) tuples sorted by timestamp
        """
        timeline = []

        for location_key, scenario in DEMO_SCENARIOS.items():
            location = scenario['location']
            responder_id = scenario['responder_id']

            for event in scenario['events']:
                timeline_event = {
                    'location': location,
                    'responder_id': responder_id,
                    **event  # timestamp_offset, hazard_level, narrative, etc.
                }
                timeline.append((event['timestamp_offset'], timeline_event))

        # Sort by timestamp
        timeline.sort(key=lambda x: x[0])
        return timeline

    def _build_fake_rag(self, event: Dict) -> Dict:
        """Build fake RAG recommendation message for one location"""
        return {
            "message_type": "rag_recommendation",
            "device_id": event['responder_id'],
            "timestamp": time.time(),
            "recommendation": event['narrative'],
            "matched_protocol": f"Protocol {event['protocol_id']}",
            "processing_time_ms": 120,  # Fake timing
            "protocols_count": 1,
            "history_count": 0,
            "cache_stats": {},
            "rag_data": {
                "protocol_id": event['protocol_id'],
                "hazard_type": event['hazard_type'],
                "source_text": event['narrative'],
                "actionable_commands": event.get('commands', [])
            }
        }

    def _build_fake_aggregation(self) -> Dict:
        """Build fake building-wide aggregation (triggered on first CRITICAL)"""
        return {
            "message_type": "rag_recommendation",
            "device_id": "BUILDING_AGGREGATOR",
            "timestamp": time.time(),
            "recommendation": (
                "Kitchen CRITICAL flashover imminent | Fire spreading to hallway "
                "(smoke detected) | Living room structural integrity compromised | "
                "EVACUATE Kitchen unit, establish defensive perimeter at hallway, "
                "monitor collapse zones"
            ),
            "matched_protocol": "Multi-Location Protocol 999",
            "processing_time_ms": 450,
            "protocols_count": 3,
            "history_count": 12,
            "cache_stats": {},
            "rag_data": {
                "protocol_id": "999",
                "hazard_type": "MULTI-LOCATION EMERGENCY",
                "source_text": (
                    "Kitchen CRITICAL flashover imminent | Fire spreading to hallway "
                    "(smoke detected) | Living room structural integrity compromised"
                ),
                "actionable_commands": [
                    {"target": "Alpha-1 (Kitchen)", "directive": "EVACUATE NORTH - 100FT (BLEVE)"},
                    {"target": "Bravo-2 (Hallway)", "directive": "ESTABLISH DEFENSIVE PERIMETER - Smoke spreading"},
                    {"target": "Delta-4 (Living Room)", "directive": "EVACUATE - Collapse imminent"}
                ]
            }
        }

# Global demo manager instance
demo_manager: DemoManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan: startup and shutdown hooks
    """
    global orchestrator, zmq_task

    logger.info("Starting ingest service...")

    # Initialize orchestrator
    # NOTE: Ingest service doesn't directly access the database
    # It forwards packets to the RAG service which handles DB operations
    orchestrator = RAGOrchestrator(actian_client=None)  # No direct DB access needed
    await orchestrator.startup()

    # Start ZMQ listener as background task
    zmq_task = asyncio.create_task(zmq_listener())

    logger.info("Ingest service ready")

    yield

    # Shutdown
    logger.info("Shutting down ingest service...")
    if zmq_task:
        zmq_task.cancel()


app = FastAPI(lifespan=lifespan)

# Mount static files (dashboard)
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"Static files mounted from {static_dir}")


@app.get("/")
async def root():
    """Serve the dashboard HTML"""
    dashboard_path = static_dir / "dashboard.html"
    if dashboard_path.exists():
        return FileResponse(dashboard_path)
    return {"message": "Dashboard not found. Check /health for API status."}


async def zmq_listener():
    """
    Background task: Listen to ZMQ PUB socket from Jetson.

    Continuously receives packets and passes them to orchestrator.
    """
    ctx = zmq.asyncio.Context()
    socket = ctx.socket(zmq.SUB)

    # TODO: Get from env var
    zmq_endpoint = "tcp://localhost:5555"  # Jetson publishes here
    socket.connect(zmq_endpoint)
    socket.subscribe(b"")  # Subscribe to all topics

    logger.info(f"ZMQ listener connected to {zmq_endpoint}")

    try:
        while True:
            raw_message = await socket.recv_string()
            logger.debug(f"Received ZMQ packet: {raw_message[:100]}...")

            # Process packet through orchestrator
            try:
                result = await orchestrator.process_packet(raw_message)
                if not result.get("success"):
                    logger.warning(f"Packet processing failed: {result}")
            except Exception as e:
                logger.error(f"Orchestrator error: {e}", exc_info=True)

    except asyncio.CancelledError:
        logger.info("ZMQ listener cancelled")
    finally:
        socket.close()
        ctx.term()


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "rag_healthy": orchestrator.rag_health.is_healthy() if orchestrator else False,
        "metrics": orchestrator.metrics.summary() if orchestrator else {}
    }


@app.get("/buffer/{device_id}")
async def get_buffer(device_id: str):
    """Debug endpoint: Inspect buffer state"""
    if not orchestrator or device_id not in orchestrator.temporal_buffer.buffers:
        return {"error": "Buffer not found"}

    buffer = orchestrator.temporal_buffer.buffers[device_id]
    return {
        "device_id": device_id,
        "buffer_size": len(buffer),
        "packets": [
            {
                "timestamp": entry["timestamp"],
                "fire_dominance": entry["scores"]["fire_dominance"]
            }
            for entry in buffer
        ]
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for dashboard connections.

    Clients connect to receive reflex_update and rag_recommendation messages.
    """
    await websocket.accept()
    logger.info(f"WebSocket client connected: session={session_id}")

    # Register client in reflex publisher
    orchestrator.reflex_publisher.register_client(session_id, websocket)

    try:
        # Keep connection alive (receive pings from client)
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received from client: {data}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: session={session_id}")
    finally:
        # Unregister client
        orchestrator.reflex_publisher.unregister_client(session_id, websocket)


@app.post("/test/inject")
async def test_inject(packet: dict):
    """
    Test endpoint: Inject synthetic packet for testing without Jetson.
    """
    raw_json = json.dumps(packet)
    result = await orchestrator.process_packet(raw_json)
    return result


@app.get("/api/metrics")
async def get_api_metrics():
    """
    REST API alternative to WebSocket: Get current metrics and state.

    Returns the latest telemetry data for dashboard polling.
    """
    if not orchestrator:
        return {"error": "Orchestrator not initialized"}

    # Get latest buffer state
    latest_data = {}
    for device_id, buffer in orchestrator.temporal_buffer.buffers.items():
        if buffer:
            latest_packet = buffer[-1]  # Most recent packet
            latest_data[device_id] = {
                "timestamp": latest_packet.get("timestamp"),
                "fire_dominance": latest_packet.get("scores", {}).get("fire_dominance"),
                "smoke_opacity": latest_packet.get("scores", {}).get("smoke_opacity"),
                "proximity_alert": latest_packet.get("scores", {}).get("proximity_alert"),
                "hazard_level": latest_packet.get("hazard_level"),
                "buffer_size": len(buffer)
            }

    return {
        "status": "ok",
        "metrics": orchestrator.metrics.summary(),
        "rag_healthy": orchestrator.rag_health.is_healthy(),
        "latest_data": latest_data
    }


@app.post("/broadcast")
async def broadcast_message(message: dict):
    """
    Relay aggregated intelligence to all dashboard WebSocket clients

    Called by aggregator service when building-wide synthesis is ready.
    Broadcasts message to all connected dashboard clients via WebSocket.

    Args:
        message: Aggregation payload (formatted as RAG recommendation)

    Returns:
        Status confirmation
    """
    try:
        if not orchestrator:
            return {"status": "error", "error": "Orchestrator not initialized"}

        # Broadcast to all connected WebSocket clients via orchestrator's reflex publisher
        # Try all registered sessions by iterating through all connected clients
        total_clients_reached = 0
        for session_id in orchestrator.reflex_publisher.ws_clients.keys():
            result = await orchestrator.reflex_publisher.websocket_broadcast(
                message,
                session_id=session_id,
                timeout_ms=50
            )
            total_clients_reached += result.get("clients_reached", 0)

        logger.info(f"📡 Broadcast aggregation: {message.get('recommendation', '')[:50]}...")

        return {
            "status": "broadcast_sent",
            "message_type": message.get('message_type'),
            "responder_count": message.get('protocols_count', 0),
            "clients_reached": total_clients_reached
        }

    except Exception as e:
        logger.error(f"❌ Broadcast failed: {e}")
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
