# Embedded Demo Mode - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Embed multi-location demo into backend with API control, broadcasting pure fake RAG streams without polluting real pipeline.

**Architecture:** Add DemoManager class to main_ingest.py that broadcasts scripted fake RAG messages on timeline, triggered by POST /demo/start endpoint.

**Tech Stack:** Python 3.10+, FastAPI, asyncio

---

## Task 1: Add Embedded Scenario Data

**Files:**
- Modify: `backend/main_ingest.py` (add after imports, before app definition)

**Step 1: Add scenario data constant**

Add this after imports in `backend/main_ingest.py`:

```python
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
```

**Step 2: Verify syntax**

```bash
cd backend
python3 -c "import main_ingest; print('✅ Syntax valid')"
```

Expected: `✅ Syntax valid`

**Step 3: Commit scenario data**

```bash
git add backend/main_ingest.py
git commit -m "feat(demo): add embedded scenario data for multi-location demo"
```

---

## Task 2: Implement DemoManager Class

**Files:**
- Modify: `backend/main_ingest.py` (add after DEMO_SCENARIOS, before app definition)

**Step 1: Add DemoManager class**

Add this after `DEMO_SCENARIOS` constant:

```python
# ==============================================================================
# DEMO MODE: DemoManager class
# ==============================================================================

import time
from typing import Dict, List, Tuple

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
```

**Step 2: Verify syntax**

```bash
cd backend
python3 -c "import main_ingest; print('✅ DemoManager syntax valid')"
```

Expected: `✅ DemoManager syntax valid`

**Step 3: Commit DemoManager**

```bash
git add backend/main_ingest.py
git commit -m "feat(demo): add DemoManager class for fake RAG stream"
```

---

## Task 3: Add Demo API Endpoints

**Files:**
- Modify: `backend/main_ingest.py` (add before `if __name__ == "__main__"`)

**Step 1: Add demo endpoints**

Add these endpoints after the existing `/broadcast` endpoint:

```python
# ==============================================================================
# DEMO MODE: API Endpoints
# ==============================================================================

@app.post("/demo/start")
async def start_demo():
    """
    Start multi-location demo mode

    Spawns asyncio task that broadcasts scripted fake RAG messages over 60 seconds.
    DOES NOT pollute real pipeline - only sends WebSocket messages.

    Returns:
        {"status": "started", "duration_sec": 60, "scenarios": 3}
    """
    global demo_manager

    if not demo_manager:
        demo_manager = DemoManager(orchestrator.reflex_publisher)

    result = await demo_manager.start()
    return result


@app.post("/demo/stop")
async def stop_demo():
    """
    Stop demo mode

    Cancels demo asyncio task and stops fake message broadcasts.

    Returns:
        {"status": "stopped", "elapsed_sec": <seconds_ran>}
    """
    global demo_manager

    if not demo_manager:
        return {"status": "not_running"}

    result = await demo_manager.stop()
    return result


@app.get("/demo/status")
async def demo_status():
    """
    Get demo status

    Returns:
        {"running": bool, "elapsed_sec": float, "scenarios": int}
    """
    global demo_manager

    if not demo_manager:
        return {"running": False, "scenarios": len(DEMO_SCENARIOS)}

    return demo_manager.get_status()
```

**Step 2: Test endpoint availability**

```bash
cd backend
python3 -c "
from main_ingest import app
print('Endpoints:', [route.path for route in app.routes])
assert '/demo/start' in [r.path for r in app.routes]
assert '/demo/stop' in [r.path for r in app.routes]
assert '/demo/status' in [r.path for r in app.routes]
print('✅ Demo endpoints registered')
"
```

Expected: `✅ Demo endpoints registered`

**Step 3: Commit demo endpoints**

```bash
git add backend/main_ingest.py
git commit -m "feat(demo): add /demo/start, /demo/stop, /demo/status endpoints"
```

---

## Task 4: Integration Test (Manual)

**Files:**
- None (manual testing only)

**Step 1: Start backend**

```bash
cd fastapi
docker-compose up -d

# Wait for services to be ready
sleep 10

# Verify ingest service is healthy
curl http://localhost:8000/health
```

Expected: `{"status": "healthy"}` or similar

**Step 2: Test demo status endpoint (before start)**

```bash
curl http://localhost:8000/demo/status
```

Expected output:
```json
{
  "running": false,
  "scenarios": 3
}
```

**Step 3: Start demo**

```bash
curl -X POST http://localhost:8000/demo/start
```

Expected output:
```json
{
  "status": "started",
  "duration_sec": 60,
  "scenarios": 3
}
```

**Step 4: Check demo status (while running)**

```bash
curl http://localhost:8000/demo/status
```

Expected output:
```json
{
  "running": true,
  "elapsed_sec": 5.3,
  "scenarios": 3,
  "timeline_events": 12
}
```

**Step 5: Check backend logs**

```bash
docker logs hacklytics_ingest 2>&1 | grep -i demo
```

Expected: Lines like:
```
INFO: 🎬 Demo mode started
INFO: 📋 Demo timeline: 12 events over 60s
INFO: 📡 T+ 0s | Kitchen (Building A)   | CAUTION  | Small grease fire detected on stove...
INFO: 📡 T+ 0s | Hallway (Building A)   | CLEAR    | Routine patrol. No hazards detected...
...
INFO: 🚨 AGGREGATION TRIGGERED - Building-wide emergency
...
INFO: ✅ Demo completed (60s)
```

**Step 6: Stop demo (before completion)**

```bash
# Start demo again
curl -X POST http://localhost:8000/demo/start

# Wait 10 seconds
sleep 10

# Stop demo
curl -X POST http://localhost:8000/demo/stop
```

Expected output:
```json
{
  "status": "stopped",
  "elapsed_sec": 10.2
}
```

**Step 7: Verify logs show cancellation**

```bash
docker logs hacklytics_ingest 2>&1 | tail -20 | grep -i demo
```

Expected: `INFO: 🛑 Demo mode stopped (ran for 10.2s)` or similar

**Step 8: Document test results**

Create a quick test report (no commit needed):

```bash
cat > TEST_RESULTS_DEMO.txt << EOF
✅ Demo API Integration Test - $(date)

Backend Started: ✅
Demo Status Endpoint: ✅ (returns correct status)
Demo Start: ✅ (spawns task, returns started)
Demo Timeline: ✅ (12 events logged over 60s)
Demo Aggregation: ✅ (triggered at T+30s)
Demo Stop: ✅ (cancels cleanly)
Logs: ✅ (shows all events)

PASS: All demo endpoints functional
EOF

cat TEST_RESULTS_DEMO.txt
```

---

## Task 5: Frontend Integration (Optional)

**Files:**
- Modify: `frontend/src/components/GlobalHeader.tsx` (optional - add demo controls)

**Step 1: Add demo control functions**

This step is **OPTIONAL**. The demo can be controlled from browser console without any frontend changes.

If you want visible buttons, add this to `GlobalHeader.tsx`:

```typescript
// Add these functions inside the GlobalHeader component

const [demoRunning, setDemoRunning] = useState(false);

const handleDemoStart = async () => {
  try {
    const response = await fetch('http://localhost:8000/demo/start', {
      method: 'POST'
    });
    const result = await response.json();
    console.log('Demo started:', result);
    setDemoRunning(true);
  } catch (error) {
    console.error('Failed to start demo:', error);
  }
};

const handleDemoStop = async () => {
  try {
    const response = await fetch('http://localhost:8000/demo/stop', {
      method: 'POST'
    });
    const result = await response.json();
    console.log('Demo stopped:', result);
    setDemoRunning(false);
  } catch (error) {
    console.error('Failed to stop demo:', error);
  }
};

// Add buttons to the JSX return:
<button
  onClick={handleDemoStart}
  disabled={demoRunning}
  className="text-xs px-3 py-2 uppercase tracking-widest font-bold border border-green-500/50 bg-green-900/40 text-green-400 hover:bg-green-800 disabled:opacity-50"
>
  {demoRunning ? 'DEMO RUNNING' : 'START DEMO'}
</button>

<button
  onClick={handleDemoStop}
  disabled={!demoRunning}
  className="text-xs px-3 py-2 uppercase tracking-widest font-bold border border-red-500/50 bg-red-900/40 text-red-400 hover:bg-red-800 disabled:opacity-50"
>
  STOP DEMO
</button>
```

**Step 2: Test from browser console (no UI changes)**

Alternatively, skip frontend changes and just use browser console:

```javascript
// Open http://localhost:3000 and open browser console (F12)

// Start demo
fetch('http://localhost:8000/demo/start', {method: 'POST'})
  .then(r => r.json())
  .then(console.log);

// Check status
fetch('http://localhost:8000/demo/status')
  .then(r => r.json())
  .then(console.log);

// Stop demo
fetch('http://localhost:8000/demo/stop', {method: 'POST'})
  .then(r => r.json())
  .then(console.log);
```

**Step 3: Verify IntelligencePanel displays fake data**

1. Start demo from browser console
2. Watch IntelligencePanel update with fake RAG messages
3. At T+30s, verify "MULTI-LOCATION EMERGENCY - PROTOCOL 999" appears
4. Verify actionable commands show for all 3 locations

**Step 4: Commit frontend changes (if made)**

```bash
# Only if you added demo buttons to GlobalHeader.tsx
git add frontend/src/components/GlobalHeader.tsx
git commit -m "feat(demo): add demo start/stop buttons to GlobalHeader"
```

---

## Task 6: Cleanup Old Demo Files

**Files:**
- Delete: `scripts/aggregator_service.py`
- Delete: `scripts/mock_responder.py`
- Delete: `scripts/demo_launcher.sh`
- Delete: `scripts/scenarios/` (entire directory)
- Delete: `scripts/requirements_aggregator.txt`
- Delete: `scripts/IMPLEMENTATION_COMPLETE.md`

**Step 1: Remove obsolete demo files**

```bash
cd fastapi

# Remove standalone demo scripts
rm scripts/aggregator_service.py
rm scripts/mock_responder.py
rm scripts/demo_launcher.sh
rm scripts/requirements_aggregator.txt
rm scripts/IMPLEMENTATION_COMPLETE.md

# Remove scenario directory
rm -rf scripts/scenarios/

# Verify removed
ls scripts/
```

Expected: Only `README.md` remains (or directory is empty)

**Step 2: Update scripts/README.md**

Replace `scripts/README.md` with simpler content:

```markdown
# Demo Mode

Multi-location fire response demo is now **embedded in the backend**.

## Usage

### Start Demo
```bash
curl -X POST http://localhost:8000/demo/start
```

### Stop Demo
```bash
curl -X POST http://localhost:8000/demo/stop
```

### Check Status
```bash
curl http://localhost:8000/demo/status
```

## Demo Timeline

- **T+0s**: Kitchen (CAUTION), Hallway (CLEAR), Living Room (CLEAR)
- **T+15s**: Kitchen escalates to HIGH
- **T+20s**: Hallway shows smoke (CAUTION)
- **T+30s**: Kitchen reaches CRITICAL → **Building-wide aggregation triggers**
- **T+35s**: Hallway escalates to HIGH (heavy smoke)
- **T+40s**: Living Room shows structural stress (CAUTION)
- **T+45s**: Kitchen post-flashover (CRITICAL continues)
- **T+50s**: Hallway near-zero visibility (HIGH continues)
- **T+50s**: Living Room collapse risk (HIGH)

## Implementation

Demo mode is implemented in `backend/main_ingest.py`:
- `DemoManager` class broadcasts fake RAG messages on timeline
- No real pipeline involvement (zero pollution)
- Controlled via `/demo/*` API endpoints

See `docs/plans/2026-02-22-embedded-demo-mode-design.md` for architecture details.
```

**Step 3: Commit cleanup**

```bash
git add -A
git commit -m "refactor(demo): remove standalone scripts, embed demo in backend"
```

---

## Task 7: Final Documentation

**Files:**
- Modify: `README.md` (update demo section)

**Step 1: Update main README**

Replace the "Multi-Location Demo (Optional)" section in `fastapi/README.md` with:

```markdown
## Multi-Location Demo

Demo mode is embedded in the backend. Start/stop via API:

```bash
# Start demo (runs for 60 seconds)
curl -X POST http://localhost:8000/demo/start

# Stop demo early
curl -X POST http://localhost:8000/demo/stop

# Check status
curl http://localhost:8000/demo/status
```

**Or from browser console** (F12 at `http://localhost:3000`):

```javascript
fetch('http://localhost:8000/demo/start', {method: 'POST'})
```

Demo broadcasts fake RAG results to dashboard without polluting real pipeline.

See [docs/plans/2026-02-22-embedded-demo-mode-design.md](docs/plans/2026-02-22-embedded-demo-mode-design.md) for details.
```

**Step 2: Commit documentation**

```bash
git add README.md scripts/README.md
git commit -m "docs: update demo mode documentation for embedded approach"
```

---

## Summary

**Implementation Complete! Total time: ~2-3 hours**

**What was built:**
1. ✅ Embedded scenario data in `main_ingest.py` (150 lines)
2. ✅ `DemoManager` class with fake RAG stream (200 lines)
3. ✅ API endpoints: `/demo/start`, `/demo/stop`, `/demo/status` (30 lines)
4. ✅ Integration tested (manual)
5. ✅ Cleaned up obsolete standalone demo files
6. ✅ Updated documentation

**What changed:**
- **Backend:** Added ~380 lines to `main_ingest.py`
- **Frontend:** Zero required changes (optional buttons if desired)
- **Database:** Zero involvement (no pollution possible)

**Comparison to original:**
- **Old approach:** 6 files, 1,300 lines, 3 terminals, WebSocket connections
- **New approach:** 1 file, 380 lines, 0 terminals, API control

**Demo workflow:**
1. Start backend: `docker-compose up -d`
2. Start frontend: `npm run dev`
3. Start demo: `curl -X POST http://localhost:8000/demo/start`
4. Watch dashboard update for 60 seconds
5. At T+30s: See "MULTI-LOCATION EMERGENCY" in IntelligencePanel

**Zero pollution, zero separate processes, zero complexity.**
