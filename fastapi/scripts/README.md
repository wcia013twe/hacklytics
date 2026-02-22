# Multi-Location Aggregation Demo

Standalone demo layer for multi-location fire response aggregation.

## Quick Start

```bash
# 1. Start backend + frontend (existing)
cd fastapi && docker-compose up -d
cd frontend && npm run dev

# 2. Start demo layer
cd fastapi/scripts
export GEMINI_API_KEY=your-key-here  # Optional
./demo_launcher.sh
```

## Components

### Mock Responders
- `mock_responder.py` - Generic scenario playback script
- `scenarios/` - JSON scenario files (kitchen, hallway, living room)

### Aggregator Service
- `aggregator_service.py` - FastAPI WebSocket hub + Gemini LLM synthesis
- Listens on `:8002`
- Relays aggregations to backend `/broadcast` endpoint

### Demo Launcher
- `demo_launcher.sh` - One-command start script
- Starts aggregator + 3 mock responders in parallel

## Scenario Format

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
      "narrative": "...",
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

## Aggregation Logic

1. Mock responders stream events to aggregator via WebSocket
2. When ANY responder reaches CRITICAL:
   - Aggregator collects latest from all responders
   - Gemini synthesizes building-wide tactical report
   - Sends to backend `/broadcast` endpoint
   - Backend relays to dashboard WebSocket clients
3. Dashboard IntelligencePanel displays aggregation (zero frontend changes)

## Environment Variables

- `GEMINI_API_KEY` - Optional. If not set, uses fallback synthesis
- `BACKEND_URL` - Default: `http://localhost:8000`

## Debugging

View logs:
```bash
tail -f /tmp/aggregator.log
tail -f /tmp/kitchen.log
tail -f /tmp/hallway.log
tail -f /tmp/living_room.log
```

Check aggregator status:
```bash
curl http://localhost:8002/status | python3 -m json.tool
```

## File Structure

```
scripts/
├── aggregator_service.py          # Aggregator FastAPI app
├── mock_responder.py               # Generic mock responder
├── demo_launcher.sh                # One-command start
├── requirements_aggregator.txt     # Python dependencies
├── scenarios/                      # Scenario JSON files
│   ├── kitchen_fire_progression.json
│   ├── hallway_smoke_spread.json
│   └── living_room_structural.json
└── README.md                       # This file
```

## Cleanup

```bash
# Stop demo (Ctrl+C in launcher terminal)
# Or kill processes:
pkill -f aggregator_service.py
pkill -f mock_responder.py
```

No database cleanup needed - mock data never touches PostgreSQL.
