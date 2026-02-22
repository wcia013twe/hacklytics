import asyncio
import json
import logging
import zmq
import zmq.asyncio
from pathlib import Path
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan: startup and shutdown hooks
    """
    global orchestrator, zmq_task

    logger.info("Starting ingest service...")

    # Initialize orchestrator
    orchestrator = RAGOrchestrator(actian_pool=None)  # TODO: Add Actian pool
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
