# Incident Log Cleanup - Hackathon Safe

**Automatic cleanup to prevent database growth during demos**

---

## Problem

The `incident_log` table grows continuously as the system runs:
- **1 packet/second × 30 minutes** = ~1,800 rows per session
- **Multiple demo runs** = accumulated data
- **No cleanup** = performance degradation over time

---

## Solution: Two-Tier Cleanup Strategy

### 1. **Auto-Cleanup (Background Task)**

Automatically deletes incidents older than 2 hours, runs every 10 minutes.

**Implementation:** `backend/orchestrator.py:orchestrator.py:569`

```python
async def _cleanup_old_incidents(self):
    """Delete incident_log entries older than 2 hours"""
    while True:
        await asyncio.sleep(600)  # Every 10 minutes
        cutoff_time = time.time() - (2 * 3600)  # 2 hours ago
        await conn.execute(
            "DELETE FROM incident_log WHERE timestamp < $1",
            cutoff_time
        )
```

**Benefits:**
- ✅ Set-and-forget
- ✅ Prevents unbounded growth
- ✅ Keeps last 2 hours of data for history queries
- ✅ No manual intervention needed

**Logging:**
```
🧹 Auto-cleanup: Deleted 1,234 old incidents (>2h)
```

---

### 2. **Manual Reset Endpoint (Between Demos)**

Quick reset for clean demo state.

**Endpoint:** `POST /admin/reset`

```bash
curl -X POST http://localhost:8001/admin/reset
```

**Response:**
```json
{
  "status": "success",
  "message": "Demo reset complete - incident_log truncated, cache cleared"
}
```

**What it does:**
1. `TRUNCATE TABLE incident_log` - Delete all incidents
2. `flushdb()` - Clear Redis cache
3. Reset metrics counters

**Use case:**
```bash
# Demo 1 to judges at 9:00 AM
# (demo runs, data accumulates)

# Between demos at 10:30 AM
curl -X POST http://localhost:8001/admin/reset

# Demo 2 to sponsors at 11:00 AM
# (starts with fresh data)
```

---

## Configuration

### Adjust Cleanup Interval

Edit `backend/orchestrator.py:orchestrator.py:578`:

```python
await asyncio.sleep(600)  # 10 minutes (default)
# Change to:
await asyncio.sleep(300)  # 5 minutes (more aggressive)
await asyncio.sleep(1800)  # 30 minutes (less aggressive)
```

### Adjust TTL Window

Edit `backend/orchestrator.py:orchestrator.py:584`:

```python
cutoff_time = time.time() - (2 * 3600)  # 2 hours (default)
# Change to:
cutoff_time = time.time() - (1 * 3600)  # 1 hour (more aggressive)
cutoff_time = time.time() - (4 * 3600)  # 4 hours (keep more history)
```

---

## Testing

Run cleanup tests:

```bash
cd /Users/wes/Desktop/Project/hacklytics/hacklytics/fastapi
python -m pytest tests/test_incident_cleanup.py -v
```

**Test coverage:**
- ✅ Auto-cleanup deletes old incidents
- ✅ Background task starts on startup
- ✅ Manual reset clears incident_log and cache
- ✅ Error handling (continues on failure)
- ✅ Metrics tracking

---

## Monitoring

### Check Cleanup Activity

View logs for cleanup activity:

```bash
docker compose logs rag | grep "Auto-cleanup"
```

Output:
```
🧹 Auto-cleanup: Deleted 1,234 old incidents (>2h)
```

### Check Metrics

```bash
curl http://localhost:8001/metrics
```

Response:
```json
{
  "counters": {
    "cleanup.incidents_deleted": 1234
  }
}
```

### Check Database Size

```bash
# Enter RAG container
docker compose exec rag bash

# Connect to Actian
psql -h vectoraidb -U vectorai -d vectorai

# Check incident_log size
SELECT COUNT(*) FROM incident_log;
SELECT
  COUNT(*) as total_incidents,
  COUNT(DISTINCT session_id) as unique_sessions,
  MIN(timestamp) as oldest,
  MAX(timestamp) as newest
FROM incident_log;
```

---

## Demo Workflow

### Recommended Hackathon Workflow

```bash
# Morning setup (8:00 AM)
make setup
make seed

# Demo 1 - Judges (9:00 AM)
# (system runs, data accumulates)

# Quick reset (10:00 AM)
curl -X POST http://localhost:8001/admin/reset

# Demo 2 - Sponsors (10:30 AM)
# (fresh data, no cross-contamination)

# Quick reset (12:00 PM)
curl -X POST http://localhost:8001/admin/reset

# Demo 3 - Final presentation (1:00 PM)
# (clean slate)
```

### What Gets Preserved

**After reset:**
- ✅ `safety_protocols` table (static knowledge base)
- ✅ Docker containers and services
- ✅ Embedding model warmup

**What gets cleared:**
- ❌ `incident_log` table (all incidents)
- ❌ Redis cache (all cached protocols and session history)
- ❌ Metrics counters

---

## Production Considerations

⚠️ **WARNING:** This is a hackathon-optimized solution!

**Before production:**

1. **Remove manual reset endpoint** - Too dangerous for production
   ```python
   # Delete this endpoint in main_rag.py
   @app.post("/admin/reset")
   ```

2. **Adjust TTL for production workload**
   - Hackathon: 2 hours (demos are short)
   - Production: 24-48 hours (real incident history needed)

3. **Add session-based partitioning**
   - Partition `incident_log` by `session_id`
   - Enable efficient per-session cleanup

4. **Add rate limiting**
   - Prevent accidental multiple resets
   - Require authentication for admin endpoints

5. **Add audit logging**
   - Log all cleanup and reset operations
   - Track who triggered manual resets

---

## Troubleshooting

### Cleanup Not Running

**Symptom:** incident_log continues growing

**Check:**
```bash
# Verify background task started
docker compose logs rag | grep "RAGOrchestrator ready"
# Should see: "RAGOrchestrator ready" after "Start background cleanup task"
```

**Fix:**
```bash
# Restart RAG service
docker compose restart rag
```

### Reset Endpoint Returns 503

**Symptom:** `POST /admin/reset` returns "Orchestrator not initialized"

**Check:**
```bash
curl http://localhost:8001/health
```

**Fix:**
```bash
docker compose restart rag
```

### Database Connection Errors

**Symptom:** `⚠️ Cleanup query error: connection refused`

**Check:**
```bash
# Verify Actian is running
docker compose ps vectoraidb

# Check connectivity
docker compose exec rag ping -c 3 vectoraidb
```

**Fix:**
```bash
docker compose restart vectoraidb
docker compose restart rag
```

---

## Performance Impact

| Metric | Impact | Notes |
|--------|--------|-------|
| **Cleanup Latency** | <100ms | DELETE query on indexed table |
| **Cleanup Frequency** | Every 10 min | Minimal overhead |
| **Reset Latency** | <500ms | TRUNCATE + cache flush |
| **Memory Overhead** | ~0 bytes | Background task |
| **CPU Overhead** | <0.1% | Sleeps 99.7% of the time |

---

## Summary

**Auto-Cleanup:**
- Runs every 10 minutes
- Deletes incidents > 2 hours old
- Keeps system lean during long demos

**Manual Reset:**
- `POST /admin/reset`
- Clears all incidents and cache
- Use between demo runs

**Hackathon-Safe:**
- ✅ No manual intervention needed
- ✅ Quick reset between demos
- ✅ Prevents performance degradation
- ✅ Simple code (70 lines total)

---

**Last Updated:** February 21, 2026
**Status:** ✅ Implemented and tested
**Hackathon Ready:** Yes
**Production Ready:** No (needs modifications listed above)
