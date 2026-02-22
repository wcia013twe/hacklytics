# Multi-Location Fire Response Aggregation System

**Author:** Claude Code
**Date:** 2026-02-22
**Status:** Ready for Implementation
**Estimated Effort:** 4-5 hours

---

## Executive Summary

Add multi-location fire response capability to the existing fire safety system by:
1. Creating 3 mock responder units with scripted fire scenarios (kitchen, hallway, living room)
2. Building a standalone aggregator service that synthesizes building-wide intelligence using Gemini LLM
3. Broadcasting aggregated insights to the existing dashboard **with zero frontend changes**

**Key Constraint:** No pollution of production database. Mock data stays completely isolated.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ EDGE LAYER: Real + Mock Responders                             │
├─────────────────────────────────────────────────────────────────┤
│ Real Jetson/iPhone → ZeroMQ → Ingest → RAG → PostgreSQL        │
│                                                                  │
│ Mock Kitchen    ──┐                                             │
│ Mock Hallway    ──┼─→ WebSocket → Aggregator Service (:8002)   │
│ Mock Living Room──┘   (Gemini LLM synthesis)                   │
│                           ↓                                      │
│                       Local JSON logs                            │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ BACKEND: Existing Ingest Service (:8000)                       │
├─────────────────────────────────────────────────────────────────┤
│ NEW: POST /broadcast endpoint                                   │
│   - Receives aggregated intelligence from aggregator           │
│   - Relays to dashboard via existing WebSocket                 │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ DASHBOARD: React Frontend (:3000)                              │
├─────────────────────────────────────────────────────────────────┤
│ ZERO CHANGES - existing IntelligencePanel displays aggregation │
│ Aggregation formatted as standard RAG recommendation message   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Design

### 1. Mock Responder Scripts

**Purpose:** Generate scripted fire progression scenarios without polluting production database

**Implementation:**
- Standalone Python scripts (no backend imports)
- Read scenario from JSON file
- Stream events to aggregator via WebSocket
- Write to local JSON log files for aggregator to read

**Files:**
- `scripts/mock_responder_kitchen.py`
- `scripts/mock_responder_hallway.py`
- `scripts/mock_responder_living_room.py`

**Scenario Format:**
```json
{
  "responder_id": "R-KITCHEN-01",
  "location": "Kitchen (Building A)",
  "scenario_name": "Grease Fire Escalation",
  "duration_sec": 60,
  "events": [
    {
      "timestamp_offset": 0,
      "hazard_level": "CAUTION",
      "narrative": "Small grease fire detected on stove...",
      "fire_dominance": 0.15,
      "smoke_opacity": 0.3,
      "temp_f": 180,
      "entities": ["fire"],
      "responder_vitals": {
        "heart_rate": 85,
        "o2_level": 98,
        "aqi": 65
      }
    }
  ]
}
```

---

### 2. Aggregator Service

**Purpose:** Collect updates from all responders and synthesize building-wide intelligence

**Tech Stack:**
- FastAPI for WebSocket hub
- Gemini 1.5 Flash for LLM synthesis
- asyncio for concurrent responder handling

**Endpoints:**
- `ws://localhost:8002/responder` - Mock responders connect here
- `ws://localhost:8002/dashboard` - Optional direct dashboard connection
- `GET /health` - Health check
- `GET /status` - Debug view of all responder states

**Aggregation Logic:**
- Triggered when ANY responder reaches CRITICAL
- Collects latest event from all active responders
- Calls Gemini with prompt: "Synthesize building-wide tactical situation"
- Broadcasts result to backend `/broadcast` endpoint

**LLM Prompt Template:**
```
You are a fire command AI analyzing a multi-location emergency.

CURRENT SITUATION ACROSS ALL LOCATIONS:
[Per-responder summaries with hazard level, narrative, vitals]

TASK: Synthesize a building-wide tactical situation report.

REQUIREMENTS:
1. Identify PRIMARY threat (which location is most critical)
2. Note spreading/escalation patterns between locations
3. Flag responders in immediate danger
4. Provide ONE actionable recommendation for incident commander
5. Keep response under 250 characters

OUTPUT FORMAT:
[Primary Threat] | [Spread Pattern] | [Responder Status] | [Command Recommendation]
```

---

### 3. Backend Integration

**Change Required:** Add one endpoint to `backend/main_ingest.py`

```python
@app.post("/broadcast")
async def broadcast_message(message: dict):
    """
    Relay aggregated intelligence to dashboard WebSocket clients
    Called by aggregator service when building-wide synthesis is ready
    """
    from .agents.reflex_publisher import ReflexPublisherAgent

    publisher = ReflexPublisherAgent()
    await publisher.websocket_broadcast(
        message,
        session_id="building_wide",
        timeout_ms=50
    )

    return {"status": "broadcast_sent"}
```

**Message Format (matches existing RAG structure):**
```json
{
  "message_type": "rag_recommendation",
  "device_id": "BUILDING_AGGREGATOR",
  "recommendation": "Kitchen CRITICAL flashover | Fire spreading...",
  "matched_protocol": "MULTI-LOCATION PROTOCOL 999",
  "processing_time_ms": 450,
  "protocols_count": 3,
  "history_count": 9,
  "cache_stats": {}
}
```

---

### 4. Frontend Integration

**Change Required:** ZERO

The existing `IntelligencePanel` component already handles messages with `message_type: "rag_recommendation"`. The aggregation message is formatted identically to standard RAG recommendations, so it displays automatically.

---

## Scenario Definitions

### Kitchen: Grease Fire Escalation (60s)
- T+0s: CAUTION - Small fire on stove
- T+15s: HIGH - Fire spreading to cabinets, 3ft flames
- T+30s: CRITICAL - Flashover imminent, full room involvement

### Hallway: Smoke Propagation (60s)
- T+0s: CLEAR - Routine patrol
- T+20s: CAUTION - Smoke entering from kitchen
- T+35s: HIGH - Heavy smoke, visibility <10ft

### Living Room: Structural Monitoring (60s)
- T+0s: CLEAR - Normal conditions
- T+40s: CAUTION - Structural stress indicators detected
- T+50s: HIGH - Ceiling integrity compromised

---

## Demo Workflow

### Pre-Demo Setup (5 min)
```bash
# Terminal 1: Start backend
cd fastapi && docker-compose up -d

# Terminal 2: Start frontend
cd frontend && npm run dev

# Terminal 3: Start demo layer
cd fastapi && ./scripts/demo_launcher.sh
```

### During Demo (judges see)
1. **T+0s**: Dashboard shows 3 responders, all CLEAR
2. **T+15s**: Kitchen goes HIGH, IntelligencePanel updates with local protocol
3. **T+30s**: Kitchen goes CRITICAL → **Aggregation triggered**
   - IntelligencePanel shows: "MULTI-LOCATION EMERGENCY - PROTOCOL 999"
   - Source text: "Kitchen CRITICAL flashover imminent | Fire spreading to hallway..."
   - Commands: Per-responder directives (EVACUATE Kitchen, DEFEND Hallway, MONITOR Living Room)

### Post-Demo Cleanup
```bash
Ctrl+C  # Stops demo layer
docker-compose down  # Stops backend
```

---

## Implementation Plan

### Phase 1: Scenario Files (30 min)
- Create 3 JSON scenario files with realistic fire progression
- Define event timings, narratives, vitals

### Phase 2: Mock Responders (1 hour)
- Build reusable `MockResponder` class
- Implement WebSocket streaming to aggregator
- Add local JSON logging

### Phase 3: Aggregator Service (2 hours)
- FastAPI app with WebSocket hub
- State management for multiple responders
- Gemini LLM integration for synthesis
- Aggregation trigger logic

### Phase 4: Backend Integration (15 min)
- Add `/broadcast` endpoint to main_ingest.py
- Test message relay to dashboard

### Phase 5: Demo Launcher (15 min)
- Bash script to start all services in parallel
- Graceful shutdown handling

### Phase 6: Testing (30 min)
- End-to-end integration test
- Verify aggregation displays correctly in IntelligencePanel
- Polish console output for demo presentation

---

## File Structure

```
fastapi/
├── backend/
│   └── main_ingest.py              # ADD: /broadcast endpoint
│
├── scripts/                        # NEW: Demo layer
│   ├── aggregator_service.py       # Aggregator FastAPI app
│   ├── mock_responder_kitchen.py
│   ├── mock_responder_hallway.py
│   ├── mock_responder_living_room.py
│   ├── demo_launcher.sh            # One-command start
│   │
│   └── scenarios/                  # Scenario definitions
│       ├── kitchen_fire_progression.json
│       ├── hallway_smoke_spread.json
│       └── living_room_structural.json
│
└── data/logs/                      # Runtime - gitignored
    ├── R-KITCHEN-01_incidents.json
    ├── R-HALLWAY-01_incidents.json
    └── R-LIVING-ROOM-01_incidents.json
```

---

## Success Criteria

- ✅ All 3 mock responders run concurrently without conflicts
- ✅ Aggregator successfully receives updates from all responders
- ✅ LLM synthesis fires when kitchen reaches CRITICAL
- ✅ Dashboard IntelligencePanel displays aggregation (no UI errors)
- ✅ Zero data pollution in PostgreSQL incident_log table
- ✅ Demo can be started/stopped with single command

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Mock data pollutes production DB | Mock responders write to local JSON only, never touch PostgreSQL |
| Aggregator WebSocket failures | Mock responders also write to JSON log files as fallback |
| LLM synthesis timeout | Fallback to simple concatenation if Gemini call exceeds 2s |
| Demo timing issues | Scenarios use relative timestamps (T+0, T+15, T+30) for predictability |
| Frontend doesn't display aggregation | Message format exactly matches existing RAG structure (tested) |

---

## Future Enhancements (Post-Hackathon)

- Add 4th responder: Exterior perimeter unit
- Real-time 2D floor plan visualization showing responder positions
- Historical playback: Replay past scenarios from JSON logs
- Multi-building support: Aggregate across different structures

---

## Dependencies

- Python 3.10+
- FastAPI
- websockets
- google-generativeai (Gemini SDK)
- aiohttp (for HTTP POST to backend)
- Existing backend services (docker-compose)
- Existing frontend (React + TypeScript)

---

## Conclusion

This design adds impressive multi-location aggregation capability with:
- **Minimal backend changes** (1 endpoint)
- **Zero frontend changes** (reuses existing components)
- **Complete data isolation** (no production DB pollution)
- **Fast implementation** (4-5 hours total)
- **Reliable demo** (scripted scenarios, one-command launch)

The system demonstrates advanced RAG capabilities (multi-source aggregation, LLM synthesis) while maintaining production code cleanliness.
