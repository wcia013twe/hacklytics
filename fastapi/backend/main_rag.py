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

# Global database connection pool (for shutdown)
_db_pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan: startup and shutdown hooks
    """
    global orchestrator, _db_pool

    logger.info("Starting RAG service...")

    # Get PostgreSQL connection details from environment
    postgres_host = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_user = os.getenv("POSTGRES_USER", "hacklytics")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "hacklytics_dev")
    postgres_db = os.getenv("POSTGRES_DB", "hacklytics_rag")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    # COMMENTED OUT: Actian VectorAI DB initialization
    # actian_host = os.getenv("ACTIAN_HOST", "vectoraidb")
    # actian_port = int(os.getenv("ACTIAN_PORT", "50051"))
    # actian_client = None
    # try:
    #     from cortex import AsyncCortexClient
    #     address = f"{actian_host}:{actian_port}"
    #     actian_client = AsyncCortexClient(
    #         address=address,
    #         pool_size=3,
    #         enable_smart_batching=True,
    #     )
    #     await actian_client.connect()
    #     logger.info(f"Actian client connected at {address}")
    #     for col_name in ("safety_protocols", "incident_log"):
    #         try:
    #             await actian_client.get_or_create_collection(
    #                 name=col_name,
    #                 dimension=384,
    #                 distance_metric="COSINE",
    #             )
    #             logger.info(f"Collection ready: {col_name}")
    #         except Exception as e:
    #             logger.warning(f"Collection {col_name} setup failed (non-fatal): {e}")
    #     _actian_client = actian_client
    # except Exception as e:
    #     logger.error(f"Actian client init failed (graceful degradation): {e}")
    #     actian_client = None

    # Initialize PostgreSQL connection pool with asyncpg
    db_pool = None
    try:
        import asyncpg

        db_pool = await asyncpg.create_pool(
            host=postgres_host,
            port=postgres_port,
            user=postgres_user,
            password=postgres_password,
            database=postgres_db,
            min_size=2,
            max_size=10,
        )
        logger.info(f"PostgreSQL pool connected at {postgres_host}:{postgres_port}")

        # Test connection
        async with db_pool.acquire() as conn:
            await conn.execute("SELECT 1")
            logger.info("PostgreSQL connection verified")

        _db_pool = db_pool

    except Exception as e:
        logger.error(f"PostgreSQL pool init failed (graceful degradation): {e}")
        db_pool = None

    # Initialize orchestrator (using pgvector pool instead of actian_client)
    orchestrator = RAGOrchestrator(actian_client=db_pool, redis_url=redis_url)
    await orchestrator.startup()

    logger.info(f"RAG service ready (PostgreSQL: {postgres_host}:{postgres_port}, connected={db_pool is not None})")

    yield

    # Shutdown
    logger.info("Shutting down RAG service...")
    if _db_pool:
        try:
            await _db_pool.close()
            logger.info("PostgreSQL pool closed")
        except Exception as e:
            logger.warning(f"PostgreSQL pool close error: {e}")

    # COMMENTED OUT: Actian shutdown
    # if _actian_client:
    #     try:
    #         await _actian_client.close()
    #         logger.info("Actian client closed")
    #     except Exception as e:
    #         logger.warning(f"Actian client close error: {e}")


app = FastAPI(lifespan=lifespan, title="RAG Service API", version="1.0")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "rag",
        "postgres_connected": _db_pool is not None,
        # "actian_connected": _actian_client is not None,  # COMMENTED OUT
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
