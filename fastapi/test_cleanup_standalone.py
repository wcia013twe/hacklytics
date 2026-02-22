"""
Standalone test for incident cleanup - can run outside Docker.

Tests the cleanup logic without requiring Google Gemini dependencies.
"""
import asyncio
import time


class MockConnection:
    """Mock database connection"""

    def __init__(self):
        self.queries_executed = []

    async def execute(self, query, *args):
        """Simulate DELETE and TRUNCATE queries"""
        self.queries_executed.append((query, args))

        if "DELETE FROM incident_log" in query:
            # Simulate deleting 5 old rows
            return "DELETE 5"
        elif "TRUNCATE TABLE incident_log" in query:
            return "TRUNCATE TABLE"
        return "OK"


class MockPool:
    """Mock connection pool"""

    def __init__(self):
        self.conn = MockConnection()

    async def acquire(self):
        return self.conn

    async def release(self, conn):
        pass


class MockActianClient:
    """Mock Actian client"""

    def __init__(self):
        self.pool = MockPool()

    async def list_collections(self):
        return []


class SimplifiedOrchestrator:
    """Simplified orchestrator with just cleanup logic"""

    def __init__(self, actian_client):
        self.actian_client = actian_client
        self.cleanup_count = 0

    async def cleanup_once(self):
        """Single cleanup execution (no loop)"""
        if not self.actian_client:
            return

        cutoff_time = time.time() - (2 * 3600)

        conn = await self.actian_client.pool.acquire()
        try:
            result = await conn.execute(
                "DELETE FROM incident_log WHERE timestamp < $1",
                cutoff_time
            )

            if result and result != "DELETE 0":
                deleted_count = result.split()[-1]
                self.cleanup_count = int(deleted_count)
                print(f"🧹 Auto-cleanup: Deleted {deleted_count} old incidents (>2h)")

        finally:
            await self.actian_client.pool.release(conn)

    async def reset_demo(self):
        """Demo reset logic"""
        if not self.actian_client:
            return {"status": "error", "message": "No database connection"}

        conn = await self.actian_client.pool.acquire()
        try:
            await conn.execute("TRUNCATE TABLE incident_log")
            print("🔄 Demo reset: incident_log truncated")

            return {
                "status": "success",
                "message": "Demo reset complete"
            }
        finally:
            await self.actian_client.pool.release(conn)


async def test_cleanup_deletes_old_incidents():
    """Test cleanup deletes incidents older than 2 hours"""
    print("\n[TEST 1] Cleanup deletes old incidents")

    mock_actian = MockActianClient()
    orchestrator = SimplifiedOrchestrator(mock_actian)

    await orchestrator.cleanup_once()

    # Verify
    assert orchestrator.cleanup_count == 5, f"Expected 5, got {orchestrator.cleanup_count}"
    assert len(mock_actian.pool.conn.queries_executed) == 1
    query, args = mock_actian.pool.conn.queries_executed[0]
    assert "DELETE FROM incident_log" in query
    assert args[0] < time.time()  # Cutoff time is in the past

    print("✅ PASS: Cleanup deleted 5 old incidents")


async def test_reset_truncates_table():
    """Test reset truncates incident_log"""
    print("\n[TEST 2] Reset truncates incident_log")

    mock_actian = MockActianClient()
    orchestrator = SimplifiedOrchestrator(mock_actian)

    result = await orchestrator.reset_demo()

    # Verify
    assert result["status"] == "success"
    assert len(mock_actian.pool.conn.queries_executed) == 1
    query, _ = mock_actian.pool.conn.queries_executed[0]
    assert "TRUNCATE TABLE incident_log" in query

    print("✅ PASS: Reset truncated incident_log")


async def test_cleanup_with_no_database():
    """Test cleanup handles missing database gracefully"""
    print("\n[TEST 3] Cleanup with no database")

    orchestrator = SimplifiedOrchestrator(actian_client=None)

    # Should not crash
    await orchestrator.cleanup_once()

    print("✅ PASS: Cleanup handles missing database gracefully")


async def test_reset_with_no_database():
    """Test reset returns error when no database"""
    print("\n[TEST 4] Reset with no database")

    orchestrator = SimplifiedOrchestrator(actian_client=None)

    result = await orchestrator.reset_demo()

    assert result["status"] == "error"
    assert "No database connection" in result["message"]

    print("✅ PASS: Reset returns error with no database")


async def run_all_tests():
    """Run all tests"""
    print("="*60)
    print("INCIDENT CLEANUP TESTS - Standalone")
    print("="*60)

    tests = [
        test_cleanup_deletes_old_incidents(),
        test_reset_truncates_table(),
        test_cleanup_with_no_database(),
        test_reset_with_no_database(),
    ]

    for test in tests:
        try:
            await test
        except AssertionError as e:
            print(f"❌ FAIL: {e}")
            return False
        except Exception as e:
            print(f"❌ ERROR: {e}")
            return False

    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED (4/4)")
    print("="*60)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
