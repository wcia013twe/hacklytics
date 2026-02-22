# Backend Full-Payload Demo Mode - Design

**Date:** 2026-02-22
**Status:** Approved
**Decision:** Option B - Backend produces full scripted sequence

---

## Problem Statement

Current architecture has split mock data responsibilities:
- **Frontend:** 177 lines of `MOCK_STATES` cycling through 3 scenarios every 5 seconds
- **Backend:** Partial demo mode broadcasting only `rag_data` (intelligence layer)

This creates confusion:
- Frontend mock blocks real WebSocket data when enabled
- Backend demo incomplete (missing responders, telemetry, entities, etc.)
- Two separate demo systems that don't integrate
- No realistic showcase of backend RAG pipeline with temporal progression

## Solution: Backend-Driven Full-Payload Demo

Consolidate ALL demo/mock data in backend. Backend produces complete `WebSocketPayload` objects with realistic time-series data showing fire growth, responder movement, vitals changes, and intelligence updates.

**Pros:**
- Realistic, credible demo showing motion of responders, fire growth, telemetry changes
- Frontend becomes stateless (no mock logic)
- Same code path for demo and production data
- Properly showcases backend RAG pipeline capabilities
- Temporal progression (60-second scripted narrative)

**Cons:**
- More backend implementation work (expand existing DemoManager)
- Requires careful payload structure matching TypeScript types

---

## Architecture

### Backend Demo System

**Location:** `backend/main_ingest.py` (expand existing `DemoManager` class)

**Demo Scenario:** Multi-location fire emergency over 60 seconds
- **Kitchen:** Fire growth (CAUTION → HIGH → CRITICAL → Flashover)
- **Hallway:** Smoke propagation (CLEAR → CAUTION → HIGH)
- **Living Room:** Structural stress (CLEAR → CAUTION → HIGH)

**Responder Assignment:**
- R-01 (Alpha-1 - Olsen) → Kitchen location (experiences fire directly)
- R-02 (Bravo-2 - Chen) → Hallway location (smoke exposure)
- R-03 (Charlie-3 - Dixon) → Kitchen support
- R-04 (Delta-4 - Vasquez) → Living room (structural monitoring)
- R-05 (Echo-5 - Hudson) → Living room support
- R-06 (Foxtrot-6 - Hicks) → External perimeter (remains nominal)

**Timeline Strategy:**
- Broadcast continuous updates **every 2 seconds** (30 total broadcasts over 60s)
- Interpolate values between keyframe events for smooth progression
- Each broadcast contains complete `WebSocketPayload` structure

---

## Data Structure

### Complete WebSocketPayload (matches TypeScript types)

```python
{
    "timestamp": time.time(),
    "system_status": "nominal" | "warning" | "critical",
    "action_command": str,
    "action_reason": str,
    "rag_data": {
        "protocol_id": str,
        "hazard_type": str,
        "source_text": str,
        "actionable_commands": [
            {"target": str, "directive": str}
        ]
    },
    "scene_context": {
        "entities": [
            {"name": str, "duration_sec": int, "trend": str}
        ],
        "telemetry": {
            "temp_f": int,
            "trend": "rising" | "falling" | "stable"
        },
        "responders": [
            {
                "id": str,              # e.g., "R-01"
                "name": str,            # e.g., "Alpha-1 (Olsen)"
                "status": str,          # nominal/warning/critical
                "vitals": {
                    "heart_rate": int,
                    "o2_level": int,
                    "aqi": int
                },
                "body_cam_url": str,
                "thermal_cam_url": str
            }
        ],
        "synthesized_insights": {
            "threat_vector": str,
            "evacuation_radius_ft": int | None,
            "resource_bottleneck": str | None,
            "max_temp_f": int,
            "max_aqi": int
        },
        "detections": []  # Optional, empty for demo
    }
}
```

### Keyframe Events

Each location has 4-5 keyframes storing complete state snapshots:
- Temperature (`temp_f`)
- Air quality (`aqi`)
- Responder vitals per person (`heart_rate`, `o2_level`, `aqi`)
- Hazard level (`status`: nominal/warning/critical)
- Intelligence narratives and commands
- Entity states (fire, gas_tank, structural_stress)
- Synthesized insights

**Example Keyframes (Kitchen - Alpha-1):**

| Time  | Temp | Alpha-1 HR | Alpha-1 O2 | Alpha-1 AQI | Status   | Narrative                          |
|-------|------|------------|------------|-------------|----------|------------------------------------|
| T+0s  | 72°F | 82 BPM     | 98%        | 45          | nominal  | Routine patrol                     |
| T+15s | 180°F| 115 BPM    | 96%        | 105         | warning  | Small grease fire detected         |
| T+30s | 400°F| 165 BPM    | 92%        | 350         | critical | FLASHOVER IMMINENT                 |
| T+45s | 520°F| 140 BPM    | 94%        | 280         | critical | Post-flashover, evacuated to safe zone |

### Interpolation Logic

**Numeric values:** Linear interpolation between keyframes
```python
def interpolate_value(t, t1, t2, v1, v2):
    """Linear interpolation for smooth transitions"""
    if t <= t1: return v1
    if t >= t2: return v2
    ratio = (t - t1) / (t2 - t1)
    return int(v1 + (v2 - v1) * ratio)
```

**Discrete values:** Use keyframe value until next transition (status, commands, narratives)

---

## Backend Implementation

### Changes to `DemoManager` class

**1. Expand `DEMO_SCENARIOS` data structure:**

Add to each location scenario:
```python
{
    "location": str,
    "responder_assignments": ["R-01", "R-03"],  # Which responders are here
    "keyframes": [
        {
            "timestamp_offset": int,
            "temp_f": int,
            "aqi": int,
            "hazard_level": str,
            "narrative": str,
            "protocol_id": str,
            "hazard_type": str,
            "commands": [...],
            "responder_vitals": {
                "R-01": {"heart_rate": int, "o2_level": int, "aqi": int, "status": str},
                ...
            },
            "entities": [...],
            "synthesized_insights": {...}
        }
    ]
}
```

**2. Replace `_build_fake_rag()` with `_build_full_payload(elapsed_time)`:**
- Takes current elapsed time
- Interpolates all numeric values between keyframes
- Builds complete `WebSocketPayload` structure
- Returns single coherent state snapshot

**3. Update `_run_demo()` broadcast loop:**
- Change from event-based to **time-based** (every 2 seconds)
- Call `_build_full_payload(elapsed_time)` each iteration
- Broadcast to ALL connected WebSocket sessions
- Remove separate aggregation trigger (now part of normal progression)

**4. Add interpolation helper methods:**
- `_interpolate_responders(elapsed)` - calculates vitals at time T for all 6 responders
- `_interpolate_telemetry(elapsed)` - calculates temp/AQI at time T
- `_derive_system_status(responders)` - determines overall status from max responder hazard
- `_build_entities(elapsed)` - constructs entities list based on elapsed time
- `_find_active_keyframes(elapsed)` - returns (prev_keyframe, next_keyframe) for interpolation

**5. Keep existing API endpoints:**
- `POST /demo/start` - starts 60-second scripted sequence
- `POST /demo/stop` - cancels demo
- `GET /demo/status` - shows running state and elapsed time

---

## Frontend Changes

### Remove Mock Data (App.tsx)

**Delete:**
- Lines 13-189: entire `MOCK_STATES` array (177 lines)
- Line 193: `useMockData` state
- Line 194: `mockIndex` state
- Lines 198-204: mock cycling `useEffect`
- Line 207: ternary logic `useMockData ? MOCK_STATES[mockIndex] : payload`
- Lines 239-244: "MOCK ON/OFF" toggle button

**Simplify to:**
```typescript
function App() {
  const { payload, latencyMs, isConnected } = useDashboardSocket();
  const [selectedResponderId, setSelectedResponderId] = useState<string | null>(null);

  // Use real payload directly
  const activeData = payload;

  if (!activeData) {
    return <div>Waiting for data...</div>;
  }

  const ragData = activeData.rag_data;
  const sceneData = activeData.scene_context;

  // ... rest of component unchanged
}
```

### Optional: Add Demo Controls (GlobalHeader.tsx)

**Simple UI buttons:**
```typescript
const handleDemoStart = async () => {
  await fetch('http://localhost:8000/demo/start', { method: 'POST' });
};

const handleDemoStop = async () => {
  await fetch('http://localhost:8000/demo/stop', { method: 'POST' });
};

// Add buttons to JSX:
<button onClick={handleDemoStart}>START DEMO</button>
<button onClick={handleDemoStop}>STOP DEMO</button>
```

**Benefits:**
- Frontend becomes stateless (no mock logic)
- Same code path for demo and production
- Demo controlled entirely via backend API
- No complex toggle logic

---

## Migration Strategy

**Phase 1: Expand Backend (Keep Frontend Mock Intact)**
1. Expand `DEMO_SCENARIOS` with full keyframe data
2. Implement `_build_full_payload()` and interpolation helpers
3. Update `_run_demo()` to broadcast every 2 seconds
4. Test backend broadcasts with curl/Postman

**Phase 2: Test Integration**
1. Start demo via API
2. Verify frontend receives full payloads (check browser console)
3. Toggle frontend mock OFF temporarily to test
4. Verify all UI components render correctly

**Phase 3: Remove Frontend Mock**
1. Delete `MOCK_STATES` from App.tsx
2. Remove mock toggle logic
3. Add optional demo control buttons
4. Test full flow: start demo → UI updates → stop demo

**Phase 4: Cleanup**
1. Remove old partial demo implementation if needed
2. Update README with new demo instructions
3. Commit all changes

---

## Testing Plan

**Backend Tests:**
- Start demo → verify 30 broadcasts over 60 seconds
- Check interpolation: values smoothly transition between keyframes
- Verify payload structure matches TypeScript types exactly
- Test stop endpoint: demo cancels cleanly mid-run

**Frontend Tests:**
- Connect to demo WebSocket → verify all UI components render
- RespondersList: shows 6 responders with changing vitals
- IntelligencePanel: shows intelligence updates
- OpsMap: reflects system_status (nominal → warning → critical)
- SceneContext: shows entities, telemetry, insights

**Integration Tests:**
- Start demo → watch 60-second progression
- Verify smooth transitions (no jumps in vitals/temp)
- Check critical events trigger proper UI alerts
- Stop demo mid-run → verify clean cancellation

---

## Success Criteria

- ✅ Backend broadcasts complete `WebSocketPayload` every 2 seconds
- ✅ Frontend removes all mock data (177 lines deleted from App.tsx)
- ✅ Frontend works identically with demo and production data
- ✅ Responder vitals/status change smoothly over 60 seconds
- ✅ Fire growth, smoke propagation, structural stress visible in UI
- ✅ Intelligence recommendations update with actionable commands
- ✅ Demo controllable via simple API endpoints
- ✅ Zero code duplication between demo and production paths

---

## Strategic Notes

**Keep payloads consistent with TypeScript types:**
- No mismatched fields
- Exact structure match between backend and frontend types
- Use `WebSocketPayload` interface as single source of truth

**Only fake the values, structure stays identical to production:**
- Same keys, same nesting, same data types
- Demo data indistinguishable from real data at the type level
- Frontend code doesn't know/care if data is demo or real

**This way, frontend code doesn't need any mock states, only a toggle:**
- No conditional rendering based on mock mode
- No separate data transformations
- Single rendering path for all data sources

---

## Future Enhancements

**Multi-scenario support:**
- Add multiple demo scenarios (building fire, hazmat, rescue)
- API parameter: `POST /demo/start?scenario=building_fire`

**Interactive demo:**
- Allow real-time control: `/demo/jump_to?time=30` (skip to T+30s)
- Speed control: `/demo/speed?multiplier=2` (2x playback)

**Demo recording:**
- Save demo payloads to file for regression testing
- Replay recorded real incidents as demo data

---

## References

- Frontend Types: `frontend/src/types/websocket.ts`
- Current Frontend Mock: `frontend/src/App.tsx` (lines 13-189)
- Existing Backend Demo: `backend/main_ingest.py` (DemoManager class)
- Original Partial Demo Plan: `docs/plans/2026-02-22-embedded-demo-mode-implementation.md`
