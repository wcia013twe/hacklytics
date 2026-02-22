# Hybrid Demo Mode - Implementation Addendum

**Date:** 2026-02-22
**Extends:** `2026-02-22-backend-full-payload-demo-implementation.md`

---

## Key Design Changes

### 1. Slower Story Progression

**Problem:** Original plan had 60-second demo with 5 keyframes → drastic changes every 15 seconds

**Solution:** Extend timeline and add intermediate keyframes for gradual progression

**New Timeline: 120 seconds (2 minutes)**

| Time    | Phase | Key Changes |
|---------|-------|-------------|
| T+0s    | Nominal | Routine patrol, all clear |
| T+20s   | Early Warning | Kitchen temp rising slowly (72°F → 120°F) |
| T+40s   | Fire Detected | Small fire confirmed, temp 180°F, Alpha-1/Charlie-3 WARNING |
| T+60s   | Fire Growing | Temp 280°F, smoke spreading to hallway, Bravo-2 affected |
| T+80s   | Critical Escalation | Temp 400°F, flashover imminent, CRITICAL status |
| T+100s  | Post-Flashover | Temp 520°F, evacuation orders, structural risk |
| T+120s  | Containment | Temp降 to 380°F, fire contained, monitoring phase |

**Benefits:**
- Broadcast every 2 seconds = **60 total broadcasts** over 120s
- Keyframe every 20 seconds = **more gradual interpolation**
- Values change smoothly: ~1-2°F per broadcast, ~1 BPM per broadcast
- Story feels realistic, not rushed

---

### 2. Hybrid Mode: Live RAG Override

**Architecture:** Demo provides baseline story, but live RAG data overrides specific responders when available.

#### Device ID Mapping

```python
# Add to DEMO_SCENARIOS
DEMO_SCENARIOS = {
    "device_mapping": {
        # Maps real hardware device IDs to demo responder IDs
        "NANO_KITCHEN_001": "R-01",      # Alpha-1 (Olsen) - Kitchen
        "JETSON_HALLWAY_02": "R-02",     # Bravo-2 (Chen) - Hallway
        "NANO_KITCHEN_002": "R-03",      # Charlie-3 (Dixon) - Kitchen support
        "JETSON_LIVING_01": "R-04",      # Delta-4 (Vasquez) - Living room
        "JETSON_LIVING_02": "R-05",      # Echo-5 (Hudson) - Living room support
        "NANO_PERIMETER_01": "R-06"      # Foxtrot-6 (Hicks) - Perimeter
    },
    # ... keyframes, responder_names, etc.
}
```

#### Live Data Override Logic

**Backend Changes** (add to `DemoManager` class):

```python
class DemoManager:
    def __init__(self, reflex_publisher):
        self.reflex_publisher = reflex_publisher
        self.demo_task = None
        self.running = False
        self.start_time = None
        self.live_overrides = {}  # Stores live RAG data by responder_id

    def register_live_data(self, device_id: str, rag_result: dict):
        """
        Register live RAG data to override demo for specific responder

        Args:
            device_id: Real hardware device ID (e.g., "NANO_KITCHEN_001")
            rag_result: Live RAG recommendation result from orchestrator
        """
        # Map device_id to responder_id
        device_mapping = DEMO_SCENARIOS.get("device_mapping", {})
        responder_id = device_mapping.get(device_id)

        if responder_id:
            self.live_overrides[responder_id] = {
                "timestamp": time.time(),
                "rag_result": rag_result,
                "device_id": device_id
            }
            logger.info(f"🔴 LIVE DATA: {device_id} → {responder_id} (overriding demo)")

    def _build_full_payload(self, elapsed: float) -> dict:
        """
        Build complete WebSocketPayload with live data overrides

        MODIFIED: Merge live RAG data for specific responders
        """
        # ... existing interpolation logic ...

        # Build responders with interpolated vitals
        responders = self._interpolate_responders(elapsed)

        # OVERRIDE: Replace responders with live data if available
        for i, responder in enumerate(responders):
            responder_id = responder["id"]

            if responder_id in self.live_overrides:
                live = self.live_overrides[responder_id]

                # Check if live data is fresh (< 10 seconds old)
                age = time.time() - live["timestamp"]
                if age < 10:
                    # Extract vitals from live RAG result (if available)
                    rag = live["rag_result"]

                    # Override with live data
                    responders[i] = {
                        **responder,  # Keep demo baseline (name, id, cam URLs)
                        "status": rag.get("hazard_level", responder["status"]),
                        "vitals": {
                            # Use live vitals if available, fallback to demo
                            "heart_rate": rag.get("vitals", {}).get("heart_rate", responder["vitals"]["heart_rate"]),
                            "o2_level": rag.get("vitals", {}).get("o2_level", responder["vitals"]["o2_level"]),
                            "aqi": rag.get("vitals", {}).get("aqi", responder["vitals"]["aqi"])
                        }
                    }
                    logger.debug(f"✅ Using live data for {responder_id} (age: {age:.1f}s)")
                else:
                    # Stale data, remove override
                    logger.warning(f"⚠️ Stale live data for {responder_id} (age: {age:.1f}s), using demo")
                    del self.live_overrides[responder_id]

        # ... rest of payload building ...
```

#### Integration with Orchestrator

**Modify `backend/orchestrator.py`** (add after successful RAG processing):

```python
class RAGOrchestrator:
    async def process_packet(self, raw_json: str) -> dict:
        # ... existing packet processing ...

        # After successful RAG recommendation
        if rag_result.get("success"):
            # Notify demo manager of live data (if demo is running)
            if demo_manager and demo_manager.running:
                device_id = packet.get("device_id")
                demo_manager.register_live_data(device_id, rag_result)

        # ... continue with existing flow ...
```

---

### 3. Gentler Value Changes

**Interpolation Strategy:**

With 120-second timeline and 7 keyframes (every 20s), interpolation creates smooth progression:

**Example: Kitchen Temperature**

| Time  | Keyframe Temp | Broadcasts Between | Temp Change per Broadcast |
|-------|---------------|--------------------|-----------------------------|
| T+0s  | 72°F          | -                  | -                           |
| T+20s | 120°F         | 10 broadcasts      | +4.8°F per broadcast        |
| T+40s | 180°F         | 10 broadcasts      | +6.0°F per broadcast        |
| T+60s | 280°F         | 10 broadcasts      | +10.0°F per broadcast       |
| T+80s | 400°F         | 10 broadcasts      | +12.0°F per broadcast       |
| T+100s| 520°F         | 10 broadcasts      | +12.0°F per broadcast       |
| T+120s| 380°F         | 10 broadcasts      | -14.0°F per broadcast       |

**Example: Alpha-1 Heart Rate (Kitchen)**

| Time  | Keyframe HR | Broadcasts Between | HR Change per Broadcast |
|-------|-------------|--------------------|-----------------------------|
| T+0s  | 82 BPM      | -                  | -                           |
| T+20s | 88 BPM      | 10 broadcasts      | +0.6 BPM per broadcast      |
| T+40s | 115 BPM     | 10 broadcasts      | +2.7 BPM per broadcast      |
| T+60s | 135 BPM     | 10 broadcasts      | +2.0 BPM per broadcast      |
| T+80s | 165 BPM     | 10 broadcasts      | +3.0 BPM per broadcast      |
| T+100s| 170 BPM     | 10 broadcasts      | +0.5 BPM per broadcast      |
| T+120s| 140 BPM     | 10 broadcasts      | -3.0 BPM per broadcast      |

**Perceptual Result:**
- Temperature rises visibly but not jarringly (~5-12°F every 2 seconds)
- Heart rate climbs gradually (~0.5-3 BPM every 2 seconds)
- User can observe progression without feeling rushed

---

## Implementation Changes

### Modified Task 1: Expand Keyframes to 7 (120-second timeline)

**Replace Step 1** in Task 1 with 7 keyframes at: 0s, 20s, 40s, 60s, 80s, 100s, 120s

**Key Additions:**

```python
# T+20s: Early warning - temperature rising
{
    "timestamp_offset": 20,
    "system_status": "nominal",  # Still nominal, but trends changing
    "action_command": "Temperature Anomaly Detected",
    "action_reason": "Kitchen sensors showing elevated readings. Monitoring.",
    "temp_f": 120,
    "global_aqi": 50,
    "rag_data": {
        "protocol_id": "100",
        "hazard_type": "Temperature Monitoring",
        "source_text": "Elevated temperature detected. Investigate potential ignition sources.",
        "actionable_commands": [
            {"target": "Alpha-1", "directive": "Investigate kitchen heat source"}
        ]
    },
    "entities": [],
    "responders": {
        "R-01": {"heart_rate": 88, "o2_level": 98, "aqi": 50, "status": "nominal", "location": "Kitchen"},
        "R-02": {"heart_rate": 77, "o2_level": 99, "aqi": 43, "status": "nominal", "location": "Hallway"},
        # ... others with minimal change
    },
    "synthesized_insights": {
        "threat_vector": "Temperature anomaly in Kitchen sector. Cause under investigation.",
        "evacuation_radius_ft": None,
        "resource_bottleneck": None
    }
},

# T+60s: Fire growing (intermediate between detection and critical)
{
    "timestamp_offset": 60,
    "system_status": "warning",
    "action_command": "Fire Expanding",
    "action_reason": "Flames reaching 4-5ft height. Class B extinguisher deployment ongoing.",
    "temp_f": 280,
    "global_aqi": 200,
    "rag_data": {
        "protocol_id": "305",
        "hazard_type": "Active Fire Growth",
        "source_text": "Fire spreading beyond initial containment zone. Monitor for flashover indicators.",
        "actionable_commands": [
            {"target": "Alpha-1", "directive": "Deploy class B extinguisher"},
            {"target": "Charlie-3", "directive": "Monitor smoke density"},
            {"target": "Bravo-2", "directive": "Prepare SCBA - smoke entering hallway"}
        ]
    },
    "entities": [
        {"name": "fire", "duration_sec": 45, "trend": "expanding"},
        {"name": "smoke", "duration_sec": 30, "trend": "expanding"}
    ],
    "responders": {
        "R-01": {"heart_rate": 135, "o2_level": 95, "aqi": 200, "status": "warning", "location": "Kitchen"},
        "R-02": {"heart_rate": 95, "o2_level": 97, "aqi": 120, "status": "nominal", "location": "Hallway"},
        "R-03": {"heart_rate": 125, "o2_level": 93, "aqi": 250, "status": "warning", "location": "Kitchen"},
        "R-04": {"heart_rate": 92, "o2_level": 97, "aqi": 80, "status": "nominal", "location": "Living Room"},
        "R-05": {"heart_rate": 91, "o2_level": 98, "aqi": 75, "status": "nominal", "location": "Living Room"},
        "R-06": {"heart_rate": 89, "o2_level": 99, "aqi": 70, "status": "nominal", "location": "Perimeter"}
    },
    "synthesized_insights": {
        "threat_vector": "Fire growth exceeding containment capacity. Smoke migrating to adjacent zones.",
        "evacuation_radius_ft": 60,
        "resource_bottleneck": "Alpha-1 and Charlie-3 engaging fire directly in high-AQI environment."
    }
}

# ... (continue with T+80s, T+100s keyframes)
```

### Modified Task 4: Update Broadcast Loop for 120s Duration

**Replace Step 1** in Task 4:

```python
async def _run_demo(self):
    """
    Main demo loop: broadcasts full WebSocketPayload every 2 seconds
    Runs for 120 seconds total with smooth interpolation
    """
    try:
        logger.info(f"📋 Demo starting: 120s timeline with broadcasts every 2s")

        broadcast_interval = 2.0   # seconds
        total_duration = 120.0     # seconds (2 minutes)

        while True:
            elapsed = time.time() - self.start_time

            # Check if demo complete
            if elapsed >= total_duration:
                logger.info("✅ Demo completed (120s)")
                self.running = False
                break

            # Build full payload at current time (with live overrides)
            full_payload = self._build_full_payload(elapsed)

            # Broadcast to ALL connected sessions
            total_clients = 0
            for session_id in list(self.reflex_publisher.ws_clients.keys()):
                result = await self.reflex_publisher.websocket_broadcast(
                    full_payload,
                    session_id=session_id,
                    timeout_ms=50
                )
                total_clients += result.get("clients_reached", 0)

            # Log with live override indicator
            live_count = len(self.live_overrides)
            live_indicator = f" | LIVE: {live_count}" if live_count > 0 else ""

            logger.info(
                f"📡 T+{int(elapsed):3d}s | "
                f"Status: {full_payload['system_status']:8s} | "
                f"Temp: {full_payload['scene_context']['telemetry']['temp_f']:3d}°F | "
                f"Clients: {total_clients}{live_indicator}"
            )

            # Wait for next broadcast interval
            await asyncio.sleep(broadcast_interval)

    except asyncio.CancelledError:
        logger.info("🛑 Demo cancelled")
        raise
    except Exception as e:
        logger.error(f"❌ Demo error: {e}", exc_info=True)
        self.running = False
```

---

## Updated Story Progression Timeline

**120-second Multi-Location Fire Emergency**

### Phase 1: Nominal Operations (T+0-20s)
- **Situation:** Routine patrol, all zones clear
- **Temperature:** 72°F → 120°F (gradual rise)
- **Responders:** All nominal, heart rates 68-90 BPM
- **AQI:** 40-50 (normal air quality)
- **Intelligence:** "Temperature anomaly detected. Investigate."

### Phase 2: Fire Detection (T+20-40s)
- **Situation:** Small grease fire confirmed in kitchen
- **Temperature:** 120°F → 180°F
- **Responders:** Alpha-1, Charlie-3 → WARNING status
- **AQI:** Kitchen rises to 105-180
- **Intelligence:** "Small localized fire. Monitor expansion. Prepare class B extinguisher."

### Phase 3: Fire Growth (T+40-60s)
- **Situation:** Flames reaching 4-5ft, smoke spreading
- **Temperature:** 180°F → 280°F
- **Responders:** Bravo-2 (hallway) starts experiencing smoke
- **AQI:** Kitchen 200-250, Hallway 100-120
- **Intelligence:** "Fire growth exceeding containment. Smoke migrating to adjacent zones."

### Phase 4: Critical Escalation (T+60-80s)
- **Situation:** Flashover imminent, BLEVE risk identified
- **Temperature:** 280°F → 400°F
- **Responders:** Alpha-1, Charlie-3 → CRITICAL status
- **AQI:** Kitchen 300-350, Hallway 150-200
- **Intelligence:** "CRITICAL MULTI-HAZARD: Propane blast risk. Evacuate immediately."

### Phase 5: Post-Flashover (T+80-100s)
- **Situation:** Flashover occurred, structural collapse risk
- **Temperature:** 400°F → 520°F (peak)
- **Responders:** Alpha-1, Charlie-3 evacuated to safe zone, recovering
- **AQI:** Peak at 420, hallway critical (280)
- **Intelligence:** "Post-flashover sustained 500F+. Minimum 100ft standoff."

### Phase 6: Containment (T+100-120s)
- **Situation:** Fire contained, defensive perimeter established
- **Temperature:** 520°F → 380°F (cooling)
- **Responders:** Gradual recovery, HR降, O2 improving
- **AQI:** Decreasing to 180-220
- **Intelligence:** "Fire contained. Monitoring for flare-ups and structural shifts."

---

## Testing Strategy

### Test 1: Pure Demo Mode (No Live Data)
```bash
curl -X POST http://localhost:8000/demo/start
# Watch 120 seconds of gradual progression
# Verify smooth interpolation (no jumps)
```

### Test 2: Hybrid Mode (Demo + Live Override)
```bash
# Start demo
curl -X POST http://localhost:8000/demo/start

# Wait 30 seconds (fire detection phase)

# Inject live RAG data for kitchen responder
curl -X POST http://localhost:8000/test/inject -H "Content-Type: application/json" -d '{
  "device_id": "NANO_KITCHEN_001",
  "scores": {"fire_dominance": 0.95},
  "vitals": {"heart_rate": 180, "o2_level": 88, "aqi": 450}
}'

# Verify: Kitchen responder (R-01/Alpha-1) shows LIVE data (HR 180, AQI 450)
# Verify: Other responders continue demo progression
# Check logs for: "🔴 LIVE DATA: NANO_KITCHEN_001 → R-01 (overriding demo)"
```

### Test 3: Live Data Staleness
```bash
# Start demo + inject live data (as above)
# Wait 15 seconds
# Verify: Live data expires after 10s, reverts to demo
# Check logs for: "⚠️ Stale live data for R-01 (age: 12.3s), using demo"
```

---

## Success Criteria (Updated)

- ✅ Demo duration: 120 seconds (2 minutes)
- ✅ Broadcast interval: 2 seconds (60 total broadcasts)
- ✅ Story progression: 7 keyframes every 20 seconds
- ✅ Smooth interpolation: No jarring value jumps
- ✅ Temperature change: ~5-12°F per broadcast (perceptually smooth)
- ✅ Heart rate change: ~0.5-3 BPM per broadcast (realistic)
- ✅ Live data override: Real RAG replaces specific responders
- ✅ Device mapping: Hardware IDs map to demo responders
- ✅ Staleness check: Live data expires after 10 seconds
- ✅ Frontend unaware: Same rendering for demo/live/hybrid data

---

## Summary of Changes

**From Original Plan:**
- ❌ 60-second demo → ✅ 120-second demo
- ❌ 5 keyframes (15s apart) → ✅ 7 keyframes (20s apart)
- ❌ Demo-only mode → ✅ Hybrid mode with live override
- ✅ 2-second broadcast interval (unchanged)

**New Features:**
- ✅ Device ID mapping for live hardware
- ✅ `register_live_data()` method in DemoManager
- ✅ Live data staleness check (10-second TTL)
- ✅ Gentler progression (fewer drastic changes)
- ✅ Logging shows live override count

**Story Pacing:**
- 20-second phases feel realistic (not rushed)
- Users can observe each escalation stage
- Smooth enough for UI animations
- Fast enough to stay engaging
