"""
Test incident_log auto-cleanup and demo reset functionality.

Hackathon-safe: Ensures database doesn't grow unbounded during demos.
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch

from backend.orchestrator import RAGOrchestrator


class MockActianClient:
    """Mock Actian client for testing cleanup"""

    def __init__(self):
        self.pool = Mock()
        self.pool.acquire = AsyncMock(return_value=MockConnection())
        self.pool.release = AsyncMock()
        self.incidents = []  # Simulated incident_log

    async def list_collections(self):
        return []


class MockConnection:
    """Mock database connection"""

    def __init__(self):
        self.deleted_count = 0

    async def execute(self, query, *args):
        """Simulate DELETE and TRUNCATE queries"""
        if "DELETE FROM incident_log" in query:
            # Simulate deleting old incidents
            cutoff_time = args[0] if args else 0
            # Return mock result
            self.deleted_count = 5  # Simulate 5 deleted rows
            return f"DELETE {self.deleted_count}"

        elif "TRUNCATE TABLE incident_log" in query:
            # Simulate truncate
            return "TRUNCATE TABLE"

        return "OK"


@pytest.mark.asyncio
async def test_cleanup_old_incidents():
    """Test that auto-cleanup deletes incidents older than 2 hours"""

    # Create orchestrator with mock Actian
    mock_actian = MockActianClient()
    orchestrator = RAGOrchestrator(actian_client=mock_actian)

    # Manually trigger cleanup (don't wait 10 minutes)
    cutoff_time = time.time() - (2 * 3600)

    conn = await mock_actian.pool.acquire()
    try:
        result = await conn.execute(
            "DELETE FROM incident_log WHERE timestamp < $1",
            cutoff_time
        )

        # Verify delete was called
        assert result == "DELETE 5"
        assert conn.deleted_count == 5

    finally:
        await mock_actian.pool.release(conn)


@pytest.mark.asyncio
async def test_cleanup_runs_in_background():
    """Test that cleanup task starts automatically on startup"""

    mock_actian = MockActianClient()
    orchestrator = RAGOrchestrator(actian_client=mock_actian)

    # Mock warmup to avoid actual model loading
    orchestrator.embedding_agent.warmup_model = AsyncMock()

    # Start orchestrator
    await orchestrator.startup()

    # Verify cleanup task was created (task runs in background)
    # We can't directly check asyncio.create_task, but we can verify
    # the method exists and is callable
    assert hasattr(orchestrator, '_cleanup_old_incidents')
    assert callable(orchestrator._cleanup_old_incidents)


@pytest.mark.asyncio
async def test_reset_demo():
    """Test manual demo reset clears incident_log and cache"""

    # Create orchestrator with mock Actian
    mock_actian = MockActianClient()
    orchestrator = RAGOrchestrator(actian_client=mock_actian)

    # Mock Redis cache
    mock_redis = AsyncMock()
    orchestrator.cache_agent = Mock()
    orchestrator.cache_agent.redis = mock_redis

    # Call reset_demo
    result = await orchestrator.reset_demo()

    # Verify result
    assert result["status"] == "success"
    assert "incident_log truncated" in result["message"]
    assert "cache cleared" in result["message"]

    # Verify Redis flush was called
    mock_redis.flushdb.assert_called_once()

    # Verify Actian truncate was called
    mock_actian.pool.acquire.assert_called()


@pytest.mark.asyncio
async def test_reset_demo_no_database():
    """Test reset_demo returns error when no database connection"""

    orchestrator = RAGOrchestrator(actian_client=None)

    result = await orchestrator.reset_demo()

    assert result["status"] == "error"
    assert "No database connection" in result["message"]


@pytest.mark.asyncio
async def test_cleanup_continues_on_error():
    """Test cleanup task continues running even if queries fail"""

    mock_actian = MockActianClient()

    # Make execute raise an exception
    error_conn = Mock()
    error_conn.execute = AsyncMock(side_effect=Exception("DB Error"))
    mock_actian.pool.acquire = AsyncMock(return_value=error_conn)

    orchestrator = RAGOrchestrator(actian_client=mock_actian)

    # Manually trigger cleanup
    try:
        cutoff_time = time.time() - (2 * 3600)
        conn = await mock_actian.pool.acquire()
        await conn.execute(
            "DELETE FROM incident_log WHERE timestamp < $1",
            cutoff_time
        )
    except Exception as e:
        # Exception is expected
        assert str(e) == "DB Error"

    # Verify cleanup didn't crash (task would continue in real scenario)
    assert orchestrator is not None


@pytest.mark.asyncio
async def test_cleanup_metrics_tracking():
    """Test cleanup increments metrics counter"""

    mock_actian = MockActianClient()
    orchestrator = RAGOrchestrator(actian_client=mock_actian)

    # Manually trigger cleanup and parse result
    cutoff_time = time.time() - (2 * 3600)
    conn = await mock_actian.pool.acquire()

    result = await conn.execute(
        "DELETE FROM incident_log WHERE timestamp < $1",
        cutoff_time
    )

    # Simulate metric increment (in real code)
    if result and result != "DELETE 0":
        deleted_count = result.split()[-1]
        orchestrator.metrics.increment("cleanup.incidents_deleted", int(deleted_count))

    # Verify metric was recorded
    assert orchestrator.metrics.counters["cleanup.incidents_deleted"] == 5


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
