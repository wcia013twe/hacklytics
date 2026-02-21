# Docker Setup - Quick Reference

## 🚀 First Time Setup (5 minutes)

```bash
# 1. Navigate to fastapi directory
cd /Users/wes/Desktop/Project/hacklytics/hacklytics/fastapi

# 2. Initialize environment
make init

# 3. Build and start services
make setup

# 4. Seed safety protocols
docker-compose exec rag python scripts/seed_protocols.py

# 5. Verify everything is running
make health
```

## 📦 What Gets Created

**Docker Containers:**
- `hacklytics_actian` - Vector database on port 5432
- `hacklytics_rag` - RAG service on port 8001
- `hacklytics_ingest` - Ingest service on ports 8000 (API/WS) and 5555 (ZMQ)

**Docker Volumes:**
- `hacklytics_actian_data` - Persistent storage for protocols and incidents
- `hacklytics_model_cache` - Cached sentence-transformers models

**Docker Network:**
- `hacklytics_rag_network` - Bridge network for inter-container communication

## 🔧 Common Commands

```bash
# Start everything
make up

# Stop everything
make down

# View logs
make logs

# Run tests
make test

# Connect to database
make db-shell

# Check service health
make health

# Rebuild after code changes
make build && make restart
```

## 🔌 Connecting the Jetson

Your Jetson should publish to ZeroMQ:

```python
import zmq
import json

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.connect("tcp://<LAPTOP_IP>:5555")  # Replace with your laptop's IP

packet = {
    "device_id": "jetson_alpha_01",
    "session_id": "mission_2026_02_21",
    "timestamp": time.time(),
    "hazard_level": "MODERATE",
    "scores": {
        "fire_dominance": 0.3,
        "smoke_opacity": 0.4,
        "proximity_alert": False
    },
    "tracked_objects": [...],
    "visual_narrative": "Fire detected near corner..."
}

socket.send_string(json.dumps(packet))
```

## 📊 Dashboard WebSocket Connection

```javascript
const ws = new WebSocket('ws://<LAPTOP_IP>:8000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'reflex_update') {
    // Update hazard indicators immediately (< 50ms latency)
    updateHazardLevel(data.hazard_level);
    updateScores(data.scores);
    updateTrend(data.trend);
  }

  if (data.type === 'rag_recommendation') {
    // Update protocol panel (0.5-2s latency)
    updateRecommendation(data.recommendation);
    updateProtocols(data.protocols);
    updateHistory(data.session_history);
  }
};
```

## 🗄️ Database Queries

```bash
# Connect to database
make db-shell

# Inside psql shell:
\dt                              # List tables
SELECT COUNT(*) FROM safety_protocols;
SELECT COUNT(*) FROM incident_log;
SELECT * FROM recent_incidents LIMIT 10;
SELECT * FROM protocol_coverage;
```

## 🐛 Troubleshooting

**Services won't start:**
```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

**Can't connect from Jetson:**
```bash
# Check if port 5555 is exposed
netstat -an | grep 5555

# Check firewall
sudo ufw allow 5555

# Find your laptop IP
ifconfig | grep "inet "
```

**Database schema missing:**
```bash
docker-compose exec -T actian psql -U vectoruser -d safety_db < init.sql
```

**No protocols seeded:**
```bash
docker-compose exec rag python scripts/seed_protocols.py
```

## 📁 File Structure Reference

```
fastapi/
├── backend/                    # Python source code
│   ├── agents/                 # Core processing logic
│   ├── contracts/              # Pydantic models
│   ├── main_ingest.py          # Ingest FastAPI app
│   └── main_rag.py             # RAG FastAPI app
├── scripts/                    # Utility scripts
│   └── seed_protocols.py       # Database seeding
├── tests/                      # Test suite
├── docker-compose.yml          # Service orchestration
├── Dockerfile.ingest           # Ingest container build
├── Dockerfile.rag              # RAG container build
├── init.sql                    # Database schema
├── requirements.txt            # Python dependencies
├── Makefile                    # Helper commands
├── .env.example                # Environment template
└── README.md                   # Full documentation
```

## ⚡ Performance Metrics

**Target Latencies (from RAG.MD):**
- Reflex path: < 50ms
- RAG p50: < 500ms
- RAG p95: < 1500ms
- RAG p99: < 2000ms

**Monitor latency:**
```bash
# Watch RAG processing time
curl -X POST http://localhost:8001/retrieve \
  -H "Content-Type: application/json" \
  -d @test_packet.json | jq '.processing_time_ms'

# Watch ingest logs
docker-compose logs -f ingest | grep "processing_time"
```

## 🔒 Security Notes

- Default credentials are in `.env` - change for production
- No TLS enabled - add nginx reverse proxy for HTTPS
- Database port 5432 is exposed - restrict in production
- No authentication on API endpoints - add JWT for production

## 📝 Next Steps

1. **Expand Protocol Database**: Add more protocols to `scripts/seed_protocols.py` (target: 30-50)
2. **Create Dashboard**: Build frontend that connects to WebSocket on port 8000
3. **Implement Main Services**: Create `main_ingest.py` and `main_rag.py` FastAPI apps
4. **Add Monitoring**: Instrument with Prometheus/Grafana for latency tracking
5. **Load Testing**: Simulate 10 FPS for 30 minutes to verify buffer and RAG handle sustained throughput

## 📖 Full Documentation

See [README.md](./README.md) for complete documentation and [RAG.MD](./RAG.MD) for architecture details.
