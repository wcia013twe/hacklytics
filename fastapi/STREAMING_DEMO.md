# Fire Detection Streaming Demo

## Overview

This demo provides a complete end-to-end visualization of your fire detection RAG pipeline. It consists of:

1. **Mock Streaming Service** - Simulates Jetson camera telemetry
2. **HTML Dashboard** - Real-time visualization with 4 processing checkpoints
3. **FastAPI Backend** - Processes packets through dual-path RAG system

## Quick Start

### Option 1: Automated Test (Recommended)

```bash
cd /Users/wes/Desktop/Project/hacklytics/hacklytics/fastapi
./scripts/quick_test.sh
```

This script will:
- Start the FastAPI backend
- Open the dashboard in your browser
- Begin streaming fire scenarios automatically

### Option 2: Manual Step-by-Step

**Terminal 1 - Start FastAPI:**
```bash
cd /Users/wes/Desktop/Project/hacklytics/hacklytics/fastapi
uvicorn backend.main_ingest:app --reload --port 8000
```

**Terminal 2 - Open Dashboard:**
```bash
open http://localhost:8000/
# Or manually navigate to: http://localhost:8000/
```

**Terminal 3 - Run Mock Streamer:**
```bash
cd /Users/wes/Desktop/Project/hacklytics/hacklytics/fastapi
python scripts/mock_stream_service.py
```

## What You'll See

### Dashboard (http://localhost:8000/)

The dashboard shows 4 processing checkpoints:

**Checkpoint 1: TELEMETRY INGEST**
- Device ID (jetson_cam_001)
- Fire Dominance Score (0.0 - 1.0)
- Person Detection Status
- Timestamp

**Checkpoint 2: TEMPORAL BUFFER**
- Buffer Size (10-second sliding window)
- Trend Direction (growing/stable/diminishing)
- Average Fire Score
- RAG Trigger Status

**Checkpoint 3: RAG PIPELINE**
- Retrieved Safety Protocol
- Severity Level (CRITICAL/HIGH/MEDIUM/LOW)
- Similarity Score
- Cache Hit/Miss

**Checkpoint 4: REFLEX OUTPUT**
- Action Required
- Alert Level
- Published Status
- Processing Latency

**Metrics Panel:**
- Total Packets Processed
- RAG Invocations
- Average Latency (target: <50ms)
- Cache Hit Rate

**Event Logs:**
- Real-time scrolling log of all events
- Last 50 events displayed

### Mock Streamer Output

The terminal running the mock service will show:

```
============================================================
Streaming Scenario: growing_fire_with_victim
Description: Fire grows from small to large, person trapped
Duration: 30s | Packets: 60 | Rate: 2 Hz
============================================================

✓ [ 1/60] LOW      | Fire: 0.148   | Latency: 12.3ms
✓ [ 2/60] LOW      | Fire: 0.163   | Latency: 8.7ms
✓ [ 3/60] MODERATE | Fire: 0.387 👤 | Latency: 15.2ms
✓ [ 4/60] MODERATE | Fire: 0.421 👤 | Latency: 9.1ms
...
✓ [58/60] CRITICAL | Fire: 0.851 👤 | Latency: 18.5ms
✓ [59/60] CRITICAL | Fire: 0.863 👤 | Latency: 11.2ms
✓ [60/60] CRITICAL | Fire: 0.879 👤 | Latency: 14.7ms

✓ Scenario 'growing_fire_with_victim' completed
```

## Test Scenarios

The mock service cycles through 4 scenarios:

### 1. Growing Fire with Victim
- **Duration:** 30 seconds
- **Fire Evolution:** 15% → 85%
- **Person:** Trapped throughout
- **Exit:** Blocked
- **Expected Behavior:** RAG should trigger, CRITICAL alerts

### 2. Rapid Flashover
- **Duration:** 15 seconds
- **Fire Evolution:** 20% → 98% (rapid growth)
- **Person:** Present initially, then flees
- **Exit:** Clear
- **Expected Behavior:** CRITICAL alerts, high growth rate detection

### 3. Contained Small Fire
- **Duration:** 20 seconds
- **Fire Evolution:** 8% → 2% (diminishing)
- **Person:** None
- **Exit:** Clear
- **Expected Behavior:** LOW alerts, trend should show diminishing

### 4. Multiple Victims Crisis
- **Duration:** 25 seconds
- **Fire Evolution:** 30% → 75%
- **Person:** Multiple people trapped
- **Exit:** Blocked
- **Expected Behavior:** HIGH/CRITICAL alerts, mass casualty protocols

## Architecture Flow

```
Mock Service (Python)
    ↓ HTTP POST /test/inject
FastAPI Backend (main_ingest.py)
    ↓
RAGOrchestrator.process_packet()
    ↓
    ├─→ Stage 1: Telemetry Ingest (validate schema)
    ├─→ Stage 2: Reflex Path (<50ms target)
    │       ├─→ Temporal Buffer (10s window)
    │       ├─→ Trend Analysis (growing/stable/diminishing)
    │       └─→ WebSocket Broadcast
    │               ↓
    │           Dashboard (checkpoint 1, 2, 4)
    │
    └─→ Stage 3: Cognition Path (async, best-effort)
            ├─→ Semantic Cache Check (YOLO buckets)
            ├─→ Vector Embedding (if cache miss)
            ├─→ Protocol Retrieval (Actian VectorAI)
            ├─→ LLM Synthesis (Gemini)
            └─→ WebSocket Broadcast
                    ↓
                Dashboard (checkpoint 3)
```

## Key Features Demonstrated

### 1. Dual-Path Processing
- **Reflex Path:** Always executes, <50ms, synchronous
- **Cognition Path:** Conditional, async, fire-and-forget

### 2. Temporal Buffer
- 10-second sliding window
- Automatic eviction of stale packets
- Trend analysis (growth rate calculation)

### 3. Real-Time WebSocket Updates
- Auto-reconnect on disconnect
- Connection status indicator
- Live metric updates

### 4. Visual Feedback
- Checkpoint boxes light up as data flows
- Color-coded severity levels (green/yellow/red)
- Animated pulses on active checkpoints

## Customization

### Change Streaming Rate
Edit `mock_stream_service.py`:
```python
packets_per_second = 5  # Change from 2 to 5 Hz
```

### Add New Scenario
Edit `mock_stream_service.py` SCENARIOS list:
```python
{
    "name": "my_scenario",
    "description": "Description here",
    "duration_seconds": 30,
    "fire_trajectory": [0.1, 0.3, 0.6, 0.9],
    "person_trajectory": [True, True, False, False],
    "exit_blocked": True,
}
```

### Modify Dashboard Theme
Edit `static/dashboard.html` CSS:
```css
#checkpoint1 { --accent-color: #your-color; }
```

## Troubleshooting

### Dashboard shows "DISCONNECTED"
- Ensure FastAPI is running: `curl http://localhost:8000/health`
- Check browser console for errors
- Verify WebSocket endpoint is accessible

### No packets appearing
- Check mock service is sending: look for HTTP POST logs in FastAPI terminal
- Verify packet schema matches `TelemetryPacket` model
- Check for validation errors in FastAPI logs

### RAG not triggering (Checkpoint 3 empty)
This is **expected behavior** if:
- Fire dominance is too low (< threshold)
- No significant trend detected
- Actian VectorAI DB not running

To force RAG triggers:
- Run scenarios with HIGH/CRITICAL fire levels
- Ensure temporal buffer has enough samples (>2 packets)

### High Latency (>50ms)
- Check system resources (CPU/memory)
- Disable LLM synthesis if not needed
- Verify Redis is running for caching

## Next Steps

1. **Seed Safety Protocols:**
   ```bash
   python scripts/seed_protocols.py
   ```

2. **Enable Redis Caching:**
   ```bash
   docker run -d -p 6379:6379 redis:7-alpine
   export REDIS_URL=redis://localhost:6379
   ```

3. **Configure LLM Synthesis:**
   ```bash
   export GEMINI_API_KEY=your-api-key-here
   ```

4. **Deploy Full Stack:**
   ```bash
   docker-compose up -d
   ```

## File Locations

```
fastapi/
├── backend/
│   ├── main_ingest.py          # FastAPI app with WebSocket
│   └── orchestrator.py         # RAG pipeline orchestrator
├── static/
│   └── dashboard.html          # Real-time visualization dashboard
├── scripts/
│   ├── mock_stream_service.py  # Telemetry simulator
│   ├── quick_test.sh           # Automated demo launcher
│   └── README_MOCK_STREAMING.md # Detailed documentation
└── STREAMING_DEMO.md           # This file
```

## Performance Targets

- **Reflex Path Latency:** <50ms (p95)
- **RAG Path Latency:** <2000ms (best-effort)
- **WebSocket Broadcast:** <10ms
- **Temporal Buffer:** 10-second window, auto-eviction
- **Throughput:** 1-5 Hz sustained (matches camera frame rate)

## Dependencies

```bash
pip install fastapi uvicorn websockets httpx sentence-transformers
```

Optional (for full features):
```bash
pip install redis google-generativeai actiancortex
```

---

**Built with:** FastAPI, WebSocket, HTML5, vanilla JavaScript
**Author:** Fire Detection RAG System Team
**Version:** 1.0.0
