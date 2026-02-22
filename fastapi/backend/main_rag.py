import asyncio
import logging
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from typing import Dict, Optional
import os

from backend.orchestrator import RAGOrchestrator
from backend.contracts.models import TelemetryPacket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global orchestrator instance
orchestrator: RAGOrchestrator = None

# Global Actian client (for shutdown)
_actian_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan: startup and shutdown hooks
    """
    global orchestrator, _actian_client

    logger.info("Starting RAG service...")

    # Get Actian connection details from environment
    actian_host = os.getenv("ACTIAN_HOST", "vectoraidb")
    actian_port = int(os.getenv("ACTIAN_PORT", "50051"))
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Initialize Actian client via Cortex gRPC SDK
    actian_client = None
    try:
        from cortex import AsyncCortexClient

        address = f"{actian_host}:{actian_port}"
        actian_client = AsyncCortexClient(
            address=address,
            pool_size=3,
            enable_smart_batching=True,
        )
        await actian_client.connect()
        logger.info(f"Actian client connected at {address}")

        # Ensure collections exist (idempotent)
        for col_name in ("safety_protocols", "incident_log"):
            try:
                await actian_client.get_or_create_collection(
                    name=col_name,
                    vector_size=384,
                    distance="COSINE",
                )
                logger.info(f"Collection ready: {col_name}")
            except Exception as e:
                logger.warning(f"Collection {col_name} setup failed (non-fatal): {e}")

        _actian_client = actian_client

    except Exception as e:
        logger.error(f"Actian client init failed (graceful degradation): {e}")
        actian_client = None

    # Initialize orchestrator
    orchestrator = RAGOrchestrator(actian_client=actian_client, redis_url=redis_url)
    await orchestrator.startup()

    logger.info(f"RAG service ready (Actian: {actian_host}:{actian_port}, connected={actian_client is not None})")

    yield

    # Shutdown
    logger.info("Shutting down RAG service...")
    if _actian_client:
        try:
            await _actian_client.close()
            logger.info("Actian client closed")
        except Exception as e:
            logger.warning(f"Actian client close error: {e}")


app = FastAPI(lifespan=lifespan, title="RAG Service API", version="1.0")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "rag",
        "actian_connected": _actian_client is not None,
        "rag_healthy": orchestrator.rag_health.is_healthy() if orchestrator else False,
        "metrics": orchestrator.metrics.summary() if orchestrator else {}
    }


@app.get("/metrics")
async def get_metrics():
    """Get orchestrator metrics"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    return orchestrator.metrics.summary()


@app.post("/process")
async def process_packet(packet: Dict):
    """
    Process a telemetry packet through the RAG pipeline.

    This endpoint is for testing and can be called directly without ZMQ.
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    try:
        import json
        raw_message = json.dumps(packet)
        result = await orchestrator.process_packet(raw_message)
        return result
    except Exception as e:
        logger.error(f"Error processing packet: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/buffer/{device_id}")
async def get_buffer(device_id: str):
    """Debug endpoint: Inspect buffer state"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    if device_id not in orchestrator.temporal_buffer.buffers:
        raise HTTPException(status_code=404, detail="Buffer not found")

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


@app.get("/cache/stats")
async def get_cache_stats():
    """Get Redis cache statistics"""
    if not orchestrator or not orchestrator.cache_agent:
        raise HTTPException(status_code=503, detail="Cache agent not initialized")

    # Return basic cache info
    return {
        "cache_agent": "initialized",
        "metrics": {
            "semantic_hits": orchestrator.metrics.counters.get("cache.semantic_hits", 0),
            "semantic_misses": orchestrator.metrics.counters.get("cache.semantic_misses", 0),
            "session_hits": orchestrator.metrics.counters.get("cache.session_hits", 0),
            "session_misses": orchestrator.metrics.counters.get("cache.session_misses", 0)
        }
    }


@app.get("/guardrails/metrics")
async def get_guardrails_metrics():
    """Get safety guardrails metrics"""
    if not orchestrator or not orchestrator.guardrails_agent:
        raise HTTPException(status_code=503, detail="Guardrails agent not initialized")

    return orchestrator.guardrails_agent.get_metrics()


@app.post("/admin/reset")
async def reset_demo():
    """
    Reset system for new demo: Clear incident_log and cache.

    WARNING: Hackathon-only endpoint! Remove before production.
    Use between demos to ensure clean state.
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    result = await orchestrator.reset_demo()

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
