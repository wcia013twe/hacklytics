# Mock Streaming Service & Dashboard

This directory contains tools for testing and visualizing the fire detection RAG pipeline in real-time.

## Components

### 1. Mock Streaming Service (`mock_stream_service.py`)

Simulates Jetson camera telemetry by generating realistic fire scenario data and streaming it to the FastAPI backend.

**Features:**
- 4 pre-configured fire scenarios (growing fire, flashover, contained fire, mass casualty)
- Realistic temporal evolution of fire dominance scores
- Person detection simulation
- Configurable streaming rate (default: 2 Hz)

**Scenarios:**
1. **Growing Fire with Victim**: Fire grows from 15% to 85% dominance, person trapped, exit blocked
2. **Rapid Flashover**: Sudden fire growth from 20% to 98%, simulates flashover conditions
3. **Contained Small Fire**: Controlled fire that diminishes over time (8% → 2%)
4. **Multiple Victims Crisis**: Large fire (30% → 75%) with multiple trapped people

### 2. HTML Dashboard (`static/dashboard.html`)

Real-time visualization dashboard showing the RAG pipeline's 4 processing stages:

**Checkpoint 1: Telemetry Ingest**
- Device ID
- Fire dominance score
- Person detection status
- Timestamp

**Checkpoint 2: Temporal Buffer**
- Buffer size (10-second sliding window)
- Trend direction (growing/stable/diminishing)
- Average fire score
- RAG trigger status

**Checkpoint 3: RAG Pipeline**
- Retrieved safety protocol
- Severity level (CRITICAL/HIGH/MEDIUM/LOW)
- Similarity score
- Cache hit/miss status

**Checkpoint 4: Reflex Output**
- Action required
- Alert level
- Publish status
- Processing latency

**Additional Features:**
- Real-time metrics (total packets, RAG invocations, avg latency, cache hit rate)
- Live event logs (last 50 events)
- WebSocket connection status indicator
- Auto-reconnect on disconnect

## Usage

### Step 1: Start the FastAPI Backend

```bash
cd /Users/wes/Desktop/Project/hacklytics/hacklytics/fastapi

# Install dependencies (if not already installed)
pip install fastapi uvicorn websockets httpx

# Start the ingest service
uvicorn backend.main_ingest:app --reload --port 8000
```

The backend will:
- Start the RAG orchestrator
- Mount the static dashboard at `http://localhost:8000/`
- Expose WebSocket endpoint at `ws://localhost:8000/ws/{session_id}`
- Listen for test packets at `POST /test/inject`

### Step 2: Open the Dashboard

Open your browser to:
```
http://localhost:8000/
```

You should see:
- 4 checkpoint boxes (dark theme, monospace font)
- Connection status showing "DISCONNECTED" initially
- Once FastAPI is running, it should show "CONNECTED" (green)

### Step 3: Start the Mock Streaming Service

In a new terminal:

```bash
cd /Users/wes/Desktop/Project/hacklytics/hacklytics/fastapi

# Run the mock streamer
python scripts/mock_stream_service.py
```

The streamer will:
1. Check FastAPI health endpoint
2. Start streaming scenario 1 (growing fire with victim)
3. Display progress in terminal with fire scores and processing status
4. Cycle through all 4 scenarios continuously
5. Send packets at 2 Hz (configurable)

### Step 4: Watch the Dashboard

As packets stream in, you'll see:
- **Checkpoint boxes light up** in sequence as data flows through the pipeline
- **Fire dominance scores** color-coded (green=safe, yellow=warning, red=critical)
- **Person detection** indicators (👤 icon when detected)
- **RAG triggers** when fire trends meet thresholds
- **Protocol retrievals** from the safety database
- **Real-time metrics** updating (total packets, latency, cache hit rate)
- **Event logs** scrolling at the bottom

### Step 5: Monitor Pipeline Performance

The dashboard tracks:
- **Total Packets**: Count of telemetry packets processed
- **RAG Invocations**: How many times the cognition path triggered
- **Avg Latency**: Mean processing time in milliseconds
- **Cache Hit Rate**: Percentage of RAG queries served from Redis cache

## Architecture Flow

```
Mock Service → FastAPI /test/inject → RAGOrchestrator
                                          ↓
                        ┌─────────────────┴─────────────────┐
                        ↓                                   ↓
                  Reflex Path                         Cognition Path
              (Synchronous, <50ms)                  (Async, Best Effort)
                        ↓                                   ↓
              Temporal Buffer → Trend Analysis → RAG Pipeline
                        ↓                                   ↓
              Reflex Publisher ← Safety Guardrails ← Synthesis
                        ↓
              WebSocket Broadcast → Dashboard
```

## Customization

### Adding New Scenarios

Edit `mock_stream_service.py` and add to `SCENARIOS`:

```python
{
    "name": "your_scenario",
    "description": "Scenario description",
    "duration_seconds": 30,
    "fire_trajectory": [0.1, 0.2, 0.4, 0.7, 0.9],  # Fire growth
    "person_trajectory": [True, True, False, False, False],
    "exit_blocked": True,
}
```

### Adjusting Stream Rate

In `mock_stream_service.py`, modify `packets_per_second`:

```python
packets_per_second = 5  # Increase to 5 Hz for faster streaming
```

### Changing Dashboard Theme

Edit `static/dashboard.html` CSS variables:

```css
:root {
    --bg-color: #0a0e27;           /* Background */
    --accent-1: #4a9eff;           /* Checkpoint 1 */
    --accent-2: #ffa84a;           /* Checkpoint 2 */
    --accent-3: #ff4a9e;           /* Checkpoint 3 */
    --accent-4: #4aff9e;           /* Checkpoint 4 */
}
```

## Troubleshooting

### Dashboard shows "DISCONNECTED"
- Ensure FastAPI is running on port 8000
- Check browser console for WebSocket errors
- Verify firewall isn't blocking WebSocket connections

### Mock service can't reach FastAPI
- Verify FastAPI is running: `curl http://localhost:8000/health`
- Check that port 8000 is not in use by another process
- Look for error messages in FastAPI terminal

### No data appearing in dashboard
- Verify WebSocket connection is established (green status)
- Check that mock service is sending packets (terminal output)
- Open browser DevTools → Network → WS tab to see WebSocket messages
- Check FastAPI logs for errors in `orchestrator.process_packet()`

### RAG not triggering
- RAG triggers when fire trends are detected in temporal buffer
- Ensure Actian VectorAI DB is running and seeded with protocols
- Check `orchestrator.temporal_buffer` configuration (default: 10s window)

## Integration with Real Jetson

To use with real Jetson camera (instead of mock service):

1. Update `main_ingest.py` ZMQ endpoint:
   ```python
   zmq_endpoint = "tcp://<jetson-ip>:5555"
   ```

2. Configure Jetson to publish telemetry to ZMQ
3. Ensure packet format matches `TelemetryPacket` schema
4. Remove or disable the mock service

## Performance Notes

- **Reflex path latency**: Target <50ms (synchronous)
- **RAG cognition latency**: 200-500ms (asynchronous, best-effort)
- **WebSocket broadcast**: Near-instant (<10ms)
- **Buffer window**: 10 seconds (configurable in `TemporalBufferAgent`)
- **Recommended packet rate**: 1-5 Hz (matches camera frame rate)

## Dependencies

```
fastapi>=0.104.0
uvicorn>=0.24.0
websockets>=12.0
httpx>=0.25.0
sentence-transformers>=2.2.0
```

## Next Steps

1. **Seed Safety Protocols**: Run `python scripts/seed_protocols.py` to populate Actian VectorAI DB
2. **Enable Redis Caching**: Set `REDIS_URL` environment variable for semantic caching
3. **Configure LLM**: Set `GEMINI_API_KEY` for temporal narrative synthesis
4. **Deploy to Production**: Use `docker-compose.yml` for full stack deployment
