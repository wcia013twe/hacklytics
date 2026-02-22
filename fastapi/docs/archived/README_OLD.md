# Temporal RAG Backend - Docker Setup

Safety-critical fire detection backend implementing the Reflex-Cognition Split architecture. See [RAG.MD](./RAG.MD) for complete architecture documentation.

## Quick Start

```bash
# 1. Copy environment configuration
cp .env.example .env

# 2. Build and start all services
docker-compose up --build -d

# 3. Check service health
docker-compose ps

# 4. View logs
docker-compose logs -f
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Jetson Nano (Edge)                       │
│  YOLOv8 → BoT-SORT → Narrative Gen → ZMQ PUB :5555         │
└────────────────────────────┬────────────────────────────────┘
                             │ ZeroMQ
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              Ingest Container (:8000, :5555)                │
│  ZMQ SUB → TemporalBuffer → Trend → WebSocket Dashboard    │
│                        │                                     │
│                        └──→ Async HTTP POST                 │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                RAG Container (:8001)                        │
│  Embed → Retrieve Protocols → Retrieve History → Synthesize│
│         ↓ writes incidents                                  │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              Actian Vector DB (:5432)                       │
│  safety_protocols (static) + incident_log (dynamic)         │
└─────────────────────────────────────────────────────────────┘
```

## Service Endpoints

| Service | Port | Endpoints |
|---------|------|-----------|
| **Ingest** | 8000 | `/health`, `/buffer/{device_id}`, `/ws` (WebSocket) |
| **Ingest** | 5555 | ZeroMQ SUB socket (bind for Jetson) |
| **RAG** | 8001 | `/health`, `/retrieve`, `/protocols` |
| **Actian** | 5432 | PostgreSQL wire protocol |

## Directory Structure

```
fastapi/
├── backend/
│   ├── agents/              # Core processing agents
│   │   ├── embedding.py     # MiniLM-L6 embedding
│   │   ├── temporal_buffer.py  # Sliding window + trend
│   │   ├── synthesis.py     # Template-based recommendations
│   │   └── ...
│   ├── contracts/
│   │   └── models.py        # Pydantic data models
│   ├── main_ingest.py       # Ingest service FastAPI app
│   └── main_rag.py          # RAG service FastAPI app
├── tests/                   # Unit and integration tests
├── docker-compose.yml       # 3-container orchestration
├── Dockerfile.ingest        # Ingest container image
├── Dockerfile.rag           # RAG container image
├── init.sql                 # Actian schema initialization
├── requirements.txt         # Python dependencies
└── .env.example             # Environment template
```

## Development Commands

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs for specific service
docker-compose logs -f rag
docker-compose logs -f ingest
docker-compose logs -f actian

# Restart a service
docker-compose restart rag

# Execute command in running container
docker-compose exec rag python -m pytest
docker-compose exec actian psql -U vectoruser -d safety_db

# Scale down (stop all services, keep volumes)
docker-compose down

# Nuclear option (remove volumes - deletes all data)
docker-compose down -v
```

## Database Access

```bash
# Connect to Actian Vector DB
docker-compose exec actian psql -U vectoruser -d safety_db

# Useful SQL queries
SELECT COUNT(*) FROM safety_protocols;
SELECT COUNT(*) FROM incident_log;
SELECT * FROM recent_incidents LIMIT 10;
SELECT * FROM protocol_coverage;
```

## Testing

```bash
# Run all tests inside RAG container
docker-compose exec rag python -m pytest tests/

# Run specific test file
docker-compose exec rag python -m pytest tests/agents/test_embedding.py -v

# Run with coverage
docker-compose exec rag python -m pytest --cov=backend tests/
```

## Seeding Safety Protocols

The `safety_protocols` table needs to be seeded with NFPA/OSHA protocols before deployment. Create a seeding script:

```python
# scripts/seed_protocols.py
from sentence_transformers import SentenceTransformer
import asyncpg

model = SentenceTransformer('all-MiniLM-L6-v2')

protocols = [
    {
        "scenario": "Person trapped, fire blocking exit",
        "text": "NFPA 1001: Immediate evacuation required...",
        "severity": "CRITICAL",
        "category": "fire",
        "tags": "trapped,exit_blocked",
        "source": "NFPA_1001"
    },
    # ... add 30-50 protocols
]

async def seed():
    conn = await asyncpg.connect('postgresql://vectoruser:vectorpass@localhost:5432/safety_db')
    for p in protocols:
        vector = model.encode(p["scenario"]).tolist()
        await conn.execute("""
            INSERT INTO safety_protocols (scenario_vector, protocol_text, severity, category, tags, source)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, vector, p["text"], p["severity"], p["category"], p["tags"], p["source"])
    await conn.close()
```

## Monitoring & Debugging

**Check Service Health:**
```bash
curl http://localhost:8000/health  # Ingest
curl http://localhost:8001/health  # RAG
```

**Inspect Buffer State:**
```bash
curl http://localhost:8000/buffer/jetson_alpha_01
```

**Check RAG Processing Time:**
```bash
# Send test packet to RAG
curl -X POST http://localhost:8001/retrieve \
  -H "Content-Type: application/json" \
  -d @test_packet.json
```

**WebSocket Connection Test:**
```bash
# Using wscat
npm install -g wscat
wscat -c ws://localhost:8000/ws
```

## Performance Tuning

**Latency Targets (from RAG.MD Section 6):**
- Reflex path: < 50ms (edge + ZMQ + WS push)
- RAG path p50: < 500ms
- RAG path p95: < 1500ms
- RAG path p99: < 2000ms

**Optimization Flags:**
- Set `BATCH_FLUSH_INTERVAL=2.0` to reduce Actian write load
- Set `SCENARIO_CACHE_SIZE=20` to enable pre-computed embeddings
- Increase `PROTOCOL_INDEX_LISTS` if protocol count > 500
- Increase `INCIDENT_INDEX_LISTS` if sessions are longer than 30min

## Troubleshooting

**Service won't start:**
```bash
# Check dependencies
docker-compose ps
docker-compose logs actian  # RAG depends on Actian health check

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

**Model download slow on first start:**
- The `all-MiniLM-L6-v2` model is baked into the RAG Docker image
- If downloading at runtime, check network or pre-warm with `RUN` in Dockerfile.rag

**Actian schema not initialized:**
```bash
# Verify init.sql was executed
docker-compose exec actian psql -U vectoruser -d safety_db -c "\dt"

# Manually run init.sql
docker-compose exec -T actian psql -U vectoruser -d safety_db < init.sql
```

**ZeroMQ connection refused:**
- Ingest binds to `tcp://*:5555` inside container
- Jetson must connect to `tcp://<laptop-ip>:5555`
- Check firewall rules on host machine

## Production Deployment Notes

1. **Replace Actian Image**: The `actian/vector:latest` image may not exist publicly. Use PostgreSQL + pgvector extension as alternative:
   ```yaml
   image: ankane/pgvector:latest
   ```

2. **Enable TLS**: Add nginx reverse proxy for HTTPS on WebSocket and API endpoints

3. **Secrets Management**: Use Docker secrets instead of environment variables for passwords

4. **Resource Limits**: Add CPU/memory limits to docker-compose for safety
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2.0'
         memory: 4G
   ```

5. **Backup Strategy**: Set up automated backups of `actian_data` volume

## License

See main project LICENSE file.
