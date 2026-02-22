# Docker Setup for Hacklytics RAG System

Clean, production-ready Docker configuration for the Temporal RAG System.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Actian    │◄────│  RAG Service │◄────│   Ingest    │
│  Vector DB  │     │   (8001)     │     │  Service    │
│   (5432)    │     └──────────────┘     │  (8000)     │
└─────────────┘                          └─────────────┘
                                               │
                                         ZeroMQ (5555)
                                               │
                                         ┌─────▼──────┐
                                         │   Jetson   │
                                         │   Orin     │
                                         └────────────┘
```

## Services

### 1. Actian Vector Database
- **Image**: `actian/vector:latest`
- **Port**: 5432
- **Purpose**: Persistent vector storage for safety protocols and incident history
- **Volumes**:
  - `actian_data` - persistent database storage
  - `init.sql` - schema initialization

### 2. RAG Service
- **Build**: `Dockerfile.rag`
- **Port**: 8001
- **Purpose**: Embedding, protocol retrieval, history search, synthesis
- **Features**:
  - Pre-downloaded sentence-transformers model (faster cold starts)
  - Async incident logging
  - Vector similarity search

### 3. Ingest Service
- **Build**: `Dockerfile.ingest`
- **Ports**: 8000 (API/WebSocket), 5555 (ZeroMQ)
- **Purpose**: Real-time telemetry ingestion, temporal buffering, trend analysis
- **Features**:
  - ZeroMQ subscriber for Jetson packets
  - 10-second sliding window buffer
  - WebSocket push to dashboard

### 4. Test Runner
- **Build**: `Dockerfile.rag` (shared with RAG service)
- **Purpose**: Containerized test execution
- **Profile**: `test` (only runs when explicitly invoked)
- **Tests**: All 7 test profiles from PROMPT_03_TEST_SUITES.md

## Quick Start

### Start All Services
```bash
docker compose up -d
```

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f rag
docker compose logs -f ingest
docker compose logs -f actian
```

### Stop Services
```bash
docker compose down
```

### Clean Rebuild
```bash
docker compose down -v  # Remove volumes
docker compose build --no-cache
docker compose up -d
```

## Running Tests

### All Tests
```bash
./run_tests.sh
# or
docker compose --profile test run --rm test
```

### Ready Tests Only (no Actian/Orchestrator dependencies)
```bash
./run_tests.sh ready
```

### Specific Test Profile
```bash
./run_tests.sh 1          # Embedding sanity
./run_tests.sh 3          # Trend accuracy
./run_tests.sh trend      # Same as above
```

### Mock Tests Only
```bash
./run_tests.sh mock
```

## Environment Variables

### Actian
- `VECTOR_DB_NAME`: Database name (default: `safety_db`)
- `POSTGRES_USER`: Database user (default: `vectoruser`)
- `POSTGRES_PASSWORD`: Database password (default: `vectorpass`)

### RAG Service
- `ACTIAN_HOST`: Actian hostname (default: `actian`)
- `ACTIAN_PORT`: Actian port (default: `5432`)
- `EMBEDDING_MODEL`: Sentence-transformers model (default: `all-MiniLM-L6-v2`)
- `BATCH_FLUSH_INTERVAL`: Incident log flush interval in seconds (default: `2.0`)
- `LOG_LEVEL`: Logging level (default: `INFO`)

### Ingest Service
- `ZMQ_BIND_ADDRESS`: ZeroMQ bind address (default: `tcp://*:5555`)
- `RAG_SERVICE_URL`: RAG API endpoint (default: `http://rag:8001`)
- `BUFFER_WINDOW_SECONDS`: Temporal buffer window (default: `10.0`)
- `LOG_LEVEL`: Logging level (default: `INFO`)

## Health Checks

All services have health check endpoints:

```bash
# RAG Service
curl http://localhost:8001/health

# Ingest Service
curl http://localhost:8000/health

# Actian (PostgreSQL protocol)
docker exec hacklytics_actian pg_isready -U vectoruser -d safety_db
```

## Persistent Volumes

### actian_data
- **Purpose**: Database storage
- **Location**: Docker managed volume
- **Persistence**: Data survives container restarts

### model_cache
- **Purpose**: Cached sentence-transformers models
- **Location**: Docker managed volume
- **Benefit**: Faster rebuilds, no re-download

### View Volumes
```bash
docker volume ls | grep hacklytics
docker volume inspect hacklytics_actian_data
```

## Development Workflow

### Live Code Updates
Backend code is mounted as read-only volumes. To see changes:

```bash
# Restart service after code changes
docker compose restart rag
docker compose restart ingest
```

### Rebuild After Dependency Changes
```bash
docker compose build rag
docker compose up -d rag
```

## Network Configuration

All services communicate via the `hacklytics_rag_network` bridge network:
- Internal DNS: Services reference each other by name (`actian`, `rag`, `ingest`)
- Isolation: Network is isolated from other Docker containers
- External Access: Only mapped ports (5432, 8000, 8001, 5555) are accessible from host

## Troubleshooting

### Service won't start
```bash
# Check logs
docker compose logs rag

# Check health
docker compose ps
```

### Database connection errors
```bash
# Verify Actian is healthy
docker compose ps actian

# Check if schema was initialized
docker exec hacklytics_actian psql -U vectoruser -d safety_db -c "\dt"
```

### Model download issues
```bash
# Clear model cache and rebuild
docker volume rm hacklytics_model_cache
docker compose build --no-cache rag
```

### Test failures
```bash
# Run specific test with verbose output
docker compose --profile test run --rm test pytest tests/test_profiles/test_01_embedding_sanity.py -vv -s
```

## Production Considerations

### Security
- [ ] Change default passwords in production
- [ ] Use Docker secrets for sensitive environment variables
- [ ] Enable TLS for Actian connections
- [ ] Restrict network access with firewall rules

### Scaling
- [ ] Use Docker Swarm or Kubernetes for multi-node deployment
- [ ] Add horizontal scaling for RAG service
- [ ] Configure Actian replication for high availability

### Monitoring
- [ ] Add Prometheus metrics endpoints
- [ ] Configure log aggregation (ELK, Grafana Loki)
- [ ] Set up alerting for health check failures

## File Structure

```
fastapi/
├── Dockerfile.rag          # RAG service image
├── Dockerfile.ingest       # Ingest service image
├── docker-compose.yml      # Orchestration config
├── run_tests.sh           # Test runner script
├── init.sql               # Database schema
├── requirements.txt       # Python dependencies
├── backend/               # Application code
└── tests/                 # Test suites
    └── test_profiles/     # 7 test profiles
```
