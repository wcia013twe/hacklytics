# Embedded Demo Mode - Pure Fake Stream Design

**Author:** Claude Code
**Date:** 2026-02-22
**Status:** Ready for Implementation
**Estimated Effort:** 2-3 hours

---

## Executive Summary

Refactor the multi-location demo layer to be **embedded in the backend** with API control from the frontend. No separate processes, no WebSockets, no data pollution - just a pure fake stream of RAG results broadcasted on a timeline.

**Key Changes:**
1. Add `DemoManager` class to `main_ingest.py` that generates fake RAG messages
2. Add `/demo/start`, `/demo/stop`, `/demo/status` API endpoints
3. Frontend calls API to start/stop demo (no separate terminal needed)
4. **Zero pollution** - no real orchestrator calls, no database writes, no pipeline involvement

---

## Architecture

```
Frontend Dashboard
    │
    ├─ User clicks "Start Demo"
    ↓
POST /demo/start → main_ingest.py
    │
    ├─ DemoManager spawns asyncio task
    ↓
Demo Task Loop (60 seconds):
    ├─ T+0s:  Broadcast fake RAG (Kitchen CAUTION)
    ├─ T+0s:  Broadcast fake RAG (Hallway CLEAR)
    ├─ T+0s:  Broadcast fake RAG (Living Room CLEAR)
    ├─ T+15s: Broadcast fake RAG (Kitchen HIGH)
    ├─ T+20s: Broadcast fake RAG (Hallway CAUTION)
    ├─ T+30s: Broadcast fake RAG (Kitchen CRITICAL)
    ├─ T+30s: ⚡ Broadcast fake AGGREGATION (Building-wide)
    ├─ T+35s: Broadcast fake RAG (Hallway HIGH)
    └─ T+40s: Broadcast fake RAG (Living Room CAUTION)
    │
    ↓ Direct WebSocket broadcast
Dashboard IntelligencePanel
    └─ Displays fake RAG messages (no code changes)

[REAL PIPELINE COMPLETELY UNTOUCHED]
```

---

## Design Principles

### 1. **Zero Pollution**
- No calls to `orchestrator.process_packet()`
- No writes to PostgreSQL `incident_log`
- No entries in temporal buffer
- Demo data completely isolated from production data

### 2. **Pure Fake Stream**
- Scripted timeline of fake RAG messages
- Broadcasts directly to WebSocket clients
- Looks identical to real RAG results
- Frontend can't tell the difference (and doesn't need to)

### 3. **API-Controlled**
- Frontend starts/stops demo with HTTP endpoints
- No separate terminals or scripts
- No docker-compose changes
- No environment variables

### 4. **Self-Contained**
- All scenario data embedded in Python code
- No external JSON files
- No separate services
- Single asyncio task

---

## Component Design

### DemoManager Class

**Location:** `backend/main_ingest.py`

**Responsibilities:**
- Load embedded scenario data (3 locations × 4-5 events each)
- Build timeline from all scenarios (merge by timestamp)
- Run asyncio task that broadcasts fake RAG messages
- Trigger fake aggregation when any location reaches CRITICAL

**Interface:**
```python
class DemoManager:
    def __init__(self, reflex_publisher: ReflexPublisherAgent)
    async def start() -> Dict[str, str]
    async def stop() -> Dict[str, str]
    def get_status() -> Dict[str, Any]
```

**Key Methods:**

1. `_build_timeline()` - Merge 3 scenarios into single timeline sorted by timestamp
2. `_run_demo()` - Main asyncio loop that broadcasts messages on schedule
3. `_build_fake_rag()` - Generate fake RAG recommendation message
4. `_build_fake_aggregation()` - Generate fake building-wide aggregation

---

## Scenario Data Structure

**Embedded in Python (no external files):**

```python
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
                "narrative": "Fire spreading to cabinets. Flames reaching 3ft height.",
                "protocol_id": "305",
                "hazard_type": "Active Fire Growth",
                "commands": [
                    {"target": "Alpha-1", "directive": "Deploy class B extinguisher"}
                ]
            },
            {
                "timestamp_offset": 30,
                "hazard_level": "CRITICAL",
                "narrative": "FLASHOVER IMMINENT. Full room involvement. Evacuate immediately.",
                "protocol_id": "402",
                "hazard_type": "Flashover Risk",
                "commands": [
                    {"target": "Alpha-1", "directive": "EVACUATE NORTH - 100FT"}
                ]
            }
        ]
    },
    "hallway": { /* similar structure */ },
    "living_room": { /* similar structure */ }
}
```

---

## API Endpoints

### POST /demo/start

**Request:** None

**Response:**
```json
{
  "status": "started",
  "duration_sec": 60,
  "scenarios": 3
}
```

**Behavior:**
- Spawns asyncio task running `DemoManager._run_demo()`
- Returns immediately (non-blocking)
- If already running, returns `{"status": "already_running"}`

---

### POST /demo/stop

**Request:** None

**Response:**
```json
{
  "status": "stopped"
}
```

**Behavior:**
- Cancels demo asyncio task
- Stops all fake message broadcasts
- Safe to call even if not running

---

### GET /demo/status

**Request:** None

**Response:**
```json
{
  "running": true,
  "elapsed_sec": 23.5,
  "scenarios": 3,
  "next_event": "Kitchen CRITICAL at T+30s"
}
```

**Behavior:**
- Returns current demo state
- Useful for debugging and monitoring

---

## Message Format

### Fake RAG Recommendation (per-location)

```json
{
  "message_type": "rag_recommendation",
  "device_id": "DEMO_KITCHEN",
  "timestamp": 1708532455.123,
  "recommendation": "Fire spreading to cabinets. Flames reaching 3ft height.",
  "matched_protocol": "Protocol 305",
  "processing_time_ms": 120,
  "protocols_count": 1,
  "history_count": 0,
  "cache_stats": {},
  "rag_data": {
    "protocol_id": "305",
    "hazard_type": "Active Fire Growth",
    "source_text": "Fire spreading to cabinets. Flames reaching 3ft height.",
    "actionable_commands": [
      {
        "target": "Alpha-1",
        "directive": "Deploy class B extinguisher"
      }
    ]
  }
}
```

**This matches the exact structure frontend expects** - no changes needed to IntelligencePanel.

---

### Fake Building Aggregation (triggered at T+30s)

```json
{
  "message_type": "rag_recommendation",
  "device_id": "BUILDING_AGGREGATOR",
  "timestamp": 1708532485.456,
  "recommendation": "Kitchen CRITICAL flashover imminent | Fire spreading to hallway (smoke detected) | R-KITCHEN-01 in danger zone (HR 165, AQI 380) | EVACUATE Kitchen unit, establish defensive perimeter at hallway",
  "matched_protocol": "Multi-Location Protocol 999",
  "processing_time_ms": 450,
  "rag_data": {
    "protocol_id": "999",
    "hazard_type": "MULTI-LOCATION EMERGENCY",
    "source_text": "Kitchen CRITICAL flashover imminent | Fire spreading to hallway...",
    "actionable_commands": [
      {"target": "R-KITCHEN-01", "directive": "EVACUATE - Kitchen compromised"},
      {"target": "R-HALLWAY-01", "directive": "ESTABLISH DEFENSIVE PERIMETER - Monitor hallway"},
      {"target": "R-LIVING-ROOM-01", "directive": "HOLD POSITION - Monitor structural integrity"}
    ]
  }
}
```

**This triggers when Kitchen reaches CRITICAL at T+30s** - shows building-wide synthesis in IntelligencePanel.

---

## Frontend Integration

### No IntelligencePanel Changes

The existing component already handles `message_type: "rag_recommendation"` - it displays:
- Protocol ID
- Hazard type
- Source text (narrative/synthesis)
- Actionable commands

**Fake messages look identical to real RAG results.**

---

### Optional: Add Demo Control Button

If you want a visible "Start Demo" button:

```typescript
// In frontend/src/components/GlobalHeader.tsx or similar

async function handleDemoStart() {
  const response = await fetch('http://localhost:8000/demo/start', {
    method: 'POST'
  });
  const result = await response.json();
  console.log('Demo started:', result);
}

async function handleDemoStop() {
  await fetch('http://localhost:8000/demo/stop', { method: 'POST' });
}

// Add buttons to UI
<button onClick={handleDemoStart}>Start Demo</button>
<button onClick={handleDemoStop}>Stop Demo</button>
```

**But this is optional** - you can also just call the API from browser console:
```javascript
fetch('http://localhost:8000/demo/start', {method: 'POST'})
```

---

## Implementation Changes

### Files Modified
1. **`backend/main_ingest.py`**
   - Add `DemoManager` class (~200 lines)
   - Add `DEMO_SCENARIOS` constant (~150 lines)
   - Add 3 endpoints: `/demo/start`, `/demo/stop`, `/demo/status` (~30 lines)
   - Total: ~380 lines added

### Files Created
- None (everything embedded in existing file)

### Files Deleted
- `scripts/aggregator_service.py` (no longer needed)
- `scripts/mock_responder.py` (no longer needed)
- `scripts/demo_launcher.sh` (no longer needed)
- `scripts/scenarios/*.json` (no longer needed)

**Net result: Simpler codebase, fewer moving parts.**

---

## Demo Workflow

### Before Judges Arrive
```bash
# 1. Start backend (as usual)
cd fastapi && docker-compose up -d

# 2. Start frontend (as usual)
cd frontend && npm run dev

# 3. Open dashboard
open http://localhost:3000
```

**That's it! No third terminal for demo layer.**

---

### During Demo

**Option A: Browser console**
```javascript
// Start demo
fetch('http://localhost:8000/demo/start', {method: 'POST'})

// Watch dashboard IntelligencePanel update over 60 seconds
// T+30s: See "MULTI-LOCATION EMERGENCY" appear

// Stop demo (optional)
fetch('http://localhost:8000/demo/stop', {method: 'POST'})
```

**Option B: Demo control button (if you add it to frontend)**
- Click "Start Demo" button
- Watch progression
- Click "Stop Demo" when done

---

### Timeline (What Judges See)

```
T+0s:  Dashboard shows 3 locations, all CLEAR/CAUTION
T+15s: Kitchen escalates to HIGH
T+20s: Hallway shows smoke spreading (CAUTION)
T+30s: 🚨 Kitchen reaches CRITICAL
       → IntelligencePanel shows "MULTI-LOCATION EMERGENCY - PROTOCOL 999"
       → Displays building-wide synthesis
       → Shows per-location commands
T+35s: Hallway escalates to HIGH
T+40s: Living room shows structural stress
T+60s: Demo completes (can restart or stop)
```

---

## Advantages Over Original Design

| Aspect | Original (Standalone Scripts) | New (Embedded) |
|--------|------------------------------|----------------|
| **Terminals needed** | 3 (backend, frontend, demo) | 2 (backend, frontend) |
| **Separate processes** | 4 (aggregator + 3 responders) | 0 (all asyncio tasks) |
| **WebSocket connections** | 3 (responders → aggregator) | 0 (direct function calls) |
| **External files** | 7 (scripts + scenarios) | 0 (embedded in code) |
| **Docker changes** | None | None |
| **Frontend changes** | None | None (or optional button) |
| **Data pollution** | None (JSON logs) | None (no persistence) |
| **Startup complexity** | `./demo_launcher.sh` | `POST /demo/start` |
| **Code complexity** | ~1,300 lines (6 files) | ~380 lines (1 file) |

**Winner: Embedded approach is simpler in every dimension.**

---

## Testing Plan

### Unit Test: Timeline Builder
```python
def test_build_timeline():
    dm = DemoManager(mock_publisher)
    timeline = dm._build_timeline()

    # Verify timeline is sorted by timestamp
    assert timeline[0][0] == 0  # First event at T+0
    assert timeline[-1][0] == 60  # Last event at T+60

    # Verify all scenarios included
    locations = {event['location'] for _, event in timeline}
    assert locations == {'Kitchen', 'Hallway', 'Living Room'}
```

### Integration Test: Fake Broadcast
```python
async def test_demo_start_stop():
    # Start demo
    response = await client.post("/demo/start")
    assert response.json()['status'] == 'started'

    # Wait for first message
    await asyncio.sleep(1)

    # Stop demo
    response = await client.post("/demo/stop")
    assert response.json()['status'] == 'stopped'
```

### Manual Test: Full Demo
1. Start backend + frontend
2. Call `POST /demo/start` from browser console
3. Watch IntelligencePanel update over 60 seconds
4. Verify "MULTI-LOCATION EMERGENCY" appears at T+30s
5. Call `POST /demo/stop`

---

## Cleanup (Post-Hackathon)

**Remove demo code:**
```python
# In main_ingest.py:
# 1. Delete DemoManager class
# 2. Delete DEMO_SCENARIOS constant
# 3. Delete /demo/* endpoints (3 functions)
# Total: ~380 lines removed
```

**Delete obsolete files:**
```bash
rm -rf scripts/aggregator_service.py
rm -rf scripts/mock_responder.py
rm -rf scripts/demo_launcher.sh
rm -rf scripts/scenarios/
rm -rf scripts/requirements_aggregator.txt
```

**No git history pollution** - demo code is clearly isolated in one section of one file.

---

## Success Criteria

- ✅ `POST /demo/start` spawns demo task
- ✅ Dashboard receives fake RAG messages on timeline
- ✅ At T+30s, "MULTI-LOCATION EMERGENCY" appears in IntelligencePanel
- ✅ `POST /demo/stop` cancels demo cleanly
- ✅ Zero real data in temporal buffer or PostgreSQL
- ✅ Works with existing frontend (zero IntelligencePanel changes)
- ✅ No separate terminals or processes needed

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Demo task doesn't start | Add logging to `DemoManager.start()` |
| Messages don't reach dashboard | Verify `reflex_publisher` WebSocket clients connected |
| Timeline out of sync | Use `time.time()` for accurate waiting, not cumulative sleep |
| Demo won't stop | Use `asyncio.create_task()` and proper `.cancel()` |
| Pollutes real data | DemoManager has ZERO orchestrator calls - architecturally impossible |

---

## Conclusion

This design achieves the goal: **multi-location demo embedded in backend, triggered by API, zero separate processes.**

- **Simpler**: 1 file vs 6 files, 380 lines vs 1,300 lines
- **Cleaner**: No WebSockets, no subprocesses, no external files
- **Safer**: Zero possibility of data pollution
- **Faster**: Single API call to start vs launching shell script
- **Better UX**: Frontend controls demo, no terminal juggling

**Ready to implement!**
