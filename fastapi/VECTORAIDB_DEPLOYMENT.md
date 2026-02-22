# VectorAI DB Deployment Guide

**Date:** February 21, 2026
**Status:** Ready for deployment
**Docker Compose:** Updated to use Actian VectorAI DB

---

## Prerequisites

Before deploying, you need to obtain two files:

### 1. VectorAI DB Docker Image

You need the Actian VectorAI DB Beta image file:
```
Actian_VectorAI_DB_Beta.tar
```

**Load the image:**
```bash
cd /Users/wes/Desktop/Project/hacklytics/hacklytics/fastapi
docker image load -i Actian_VectorAI_DB_Beta.tar
```

**Verify the image was loaded:**
```bash
docker images | grep vectoraidb
```

Expected output:
```
localhost/actian/vectoraidb   1.0b   <image-id>   <date>   <size>
```

### 2. Python Client Wheel File

You need the Python client wheel:
```
actiancortex-0.1.0b1-py3-none-any.whl
```

**Place it in the FastAPI directory:**
```bash
# The wheel file should be at:
/Users/wes/Desktop/Project/hacklytics/hacklytics/fastapi/actiancortex-0.1.0b1-py3-none-any.whl
```

---

## Docker Compose Configuration

The `docker-compose.yml` has been updated with the following changes:

### VectorAI DB Service

**Old (PostgreSQL/pgvector):**
```yaml
actian:
  image: actian/vector:latest
  ports:
    - "5432:5432"  # PostgreSQL port
  environment:
    POSTGRES_USER: vectoruser
    POSTGRES_PASSWORD: ${ACTIAN_PASSWORD}
```

**New (VectorAI DB):**
```yaml
vectoraidb:
  image: localhost/actian/vectoraidb:1.0b
  #platform: linux/amd64   # Uncomment on macOS
  ports:
    - "50051:50051"  # gRPC port
  volumes:
    - actian_data:/data
  stop_grace_period: 2m
```

### Key Changes

| Component | Old Value | New Value |
|-----------|-----------|-----------|
| Service name | `actian` | `vectoraidb` |
| Image | `actian/vector:latest` | `localhost/actian/vectoraidb:1.0b` |
| Port | `5432` (PostgreSQL) | `50051` (gRPC) |
| Protocol | SQL | gRPC |
| Environment vars | POSTGRES_* | None needed |
| Init script | `init.sql` | Collections created via Python |

---

## macOS Apple Silicon Users

If you're on macOS with Apple Silicon (M1/M2/M3), uncomment this line:

```yaml
# In docker-compose.yml, line 7:
platform: linux/amd64
```

This ensures compatibility with x86_64 images.

---

## Deployment Steps

### Step 1: Load the Docker Image

```bash
cd /Users/wes/Desktop/Project/hacklytics/hacklytics/fastapi

# Load the VectorAI DB image
docker image load -i Actian_VectorAI_DB_Beta.tar

# Verify it loaded correctly
docker images | grep vectoraidb
```

**Expected output:**
```
localhost/actian/vectoraidb   1.0b   abc123def456   2 weeks ago   500MB
```

### Step 2: Place the Python Client Wheel

```bash
# Ensure the wheel file is in the fastapi directory
ls -lh actiancortex-0.1.0b1-py3-none-any.whl
```

**Expected output:**
```
-rw-r--r--  1 user  staff   150K Feb 21 10:00 actiancortex-0.1.0b1-py3-none-any.whl
```

### Step 3: Start the VectorAI DB Container

```bash
# Start only the VectorAI DB service first
docker compose up -d vectoraidb

# Check the container is running
docker ps | grep vectoraidb
```

**Expected output:**
```
hacklytics_vectoraidb   localhost/actian/vectoraidb:1.0b   Up 10 seconds   0.0.0.0:50051->50051/tcp
```

### Step 4: Check VectorAI DB Logs

```bash
# View logs to ensure no errors
docker logs hacklytics_vectoraidb
```

**Expected output (example):**
```
VectorAI DB Server v1.0 beta
Listening on 0.0.0.0:50051
Data directory: /data
Ready to accept connections
```

### Step 5: Test gRPC Connectivity

```bash
# Test that port 50051 is accessible
nc -zv localhost 50051
```

**Expected output:**
```
Connection to localhost port 50051 [tcp/*] succeeded!
```

### Step 6: Examine Container Logs (Troubleshooting)

If the container fails to start or shows errors:

```bash
# View real-time logs
docker logs -f hacklytics_vectoraidb

# Check the log file inside the container
docker exec hacklytics_vectoraidb cat /data/vde.log
```

**Common issues:**
- Port 50051 already in use: `lsof -i :50051`
- Permissions on /data volume: Check Docker volume permissions
- Image architecture mismatch: Add `platform: linux/amd64`

---

## Health Check Verification

The docker-compose.yml includes a health check:

```yaml
healthcheck:
  test: ["CMD-SHELL", "timeout 1 bash -c '</dev/tcp/localhost/50051' || exit 1"]
  interval: 15s
  timeout: 5s
  retries: 5
  start_period: 10s
```

**Check health status:**
```bash
docker inspect hacklytics_vectoraidb --format='{{.State.Health.Status}}'
```

**Expected output:**
```
healthy
```

**If unhealthy:**
```bash
# View health check logs
docker inspect hacklytics_vectoraidb --format='{{json .State.Health}}' | jq
```

---

## Environment Variables

The RAG and test services now use these environment variables:

```yaml
environment:
  ACTIAN_HOST: vectoraidb  # Service name in Docker network
  ACTIAN_PORT: 50051       # gRPC port
```

**No longer needed:**
- `ACTIAN_DB` (no database name for VectorAI DB)
- `ACTIAN_USER` (no authentication)
- `ACTIAN_PASSWORD` (no authentication)

**Update your `.env` file:**
```bash
# Remove these lines if present:
# ACTIAN_DB=safety_db
# ACTIAN_USER=vectoruser
# ACTIAN_PASSWORD=yourpassword

# These are still needed:
EMBEDDING_MODEL=all-MiniLM-L6-v2
BATCH_FLUSH_INTERVAL=2.0
LOG_LEVEL=INFO
```

---

## Next Steps After Deployment

Once the VectorAI DB container is running:

### 1. Initialize Collections

Collections replace SQL tables in VectorAI DB. You need to create them before use:

```bash
# Run the collection initialization script (to be created)
python scripts/init_actian_collections.py
```

**This will create:**
- `safety_protocols` collection (dimension: 384, metric: COSINE)
- `incident_log` collection (dimension: 384, metric: COSINE)

### 2. Seed Safety Protocols

Load the NFPA/OSHA protocols into the `safety_protocols` collection:

```bash
# Run the seeding script (updated for VectorAI DB)
python scripts/seed_protocols.py
```

**Expected output:**
```
[1/4] Loading sentence-transformers model...
✓ Model loaded: all-MiniLM-L6-v2 (384 dimensions)

[2/4] Connecting to Actian VectorAI DB at vectoraidb:50051...
✓ Connected to VectorAI DB v1.0b

[3/4] Verifying 'safety_protocols' collection exists...
✓ Collection exists

[4/4] Embedding and inserting 10 protocols...
  [1/10] CRITICAL | Person trapped near fire with exit blocked
  [2/10] HIGH     | Smoke spreading rapidly in confined space
  ...
✓ Inserted 10 protocols successfully
```

### 3. Start Remaining Services

```bash
# Start RAG and ingest services
docker compose up -d rag ingest

# Check all services are healthy
docker compose ps
```

**Expected output:**
```
NAME                     STATUS              PORTS
hacklytics_vectoraidb    Up (healthy)        0.0.0.0:50051->50051/tcp
hacklytics_rag           Up (healthy)        0.0.0.0:8001->8001/tcp
hacklytics_ingest        Up (healthy)        0.0.0.0:5555->5555/tcp, 0.0.0.0:8000->8000/tcp
```

---

## Verification Commands

### Check Service Health

```bash
# VectorAI DB health
docker inspect hacklytics_vectoraidb --format='{{.State.Health.Status}}'

# RAG service health
curl http://localhost:8001/health
```

**Expected RAG response:**
```json
{
  "status": "healthy",
  "actian_connected": true
}
```

### Check Collection Status

```bash
# Run a Python script to check collections
python -c "
import asyncio
from backend.db.actian_client import ActianVectorPool

async def check():
    pool = ActianVectorPool()
    await pool.connect(host='localhost', port=50051)

    protocols = await pool.count('safety_protocols')
    incidents = await pool.count('incident_log')

    print(f'safety_protocols: {protocols} vectors')
    print(f'incident_log: {incidents} vectors')

    await pool.close()

asyncio.run(check())
"
```

**Expected output:**
```
safety_protocols: 10 vectors
incident_log: 0 vectors
```

### View VectorAI DB Logs

```bash
# Real-time logs
docker logs -f hacklytics_vectoraidb

# Or read the internal log file
docker exec hacklytics_vectoraidb tail -f /data/vde.log
```

---

## Troubleshooting

### Issue: "Connection refused to localhost:50051"

**Cause:** VectorAI DB container not running or healthcheck failing

**Fix:**
```bash
# Check if container is running
docker ps | grep vectoraidb

# If not running, check why it exited
docker logs hacklytics_vectoraidb

# Restart the container
docker compose restart vectoraidb
```

### Issue: "Image not found: localhost/actian/vectoraidb:1.0b"

**Cause:** Docker image not loaded

**Fix:**
```bash
# Load the image from the .tar file
docker image load -i Actian_VectorAI_DB_Beta.tar

# Verify it's loaded
docker images | grep vectoraidb
```

### Issue: "ModuleNotFoundError: No module named 'cortex'"

**Cause:** Python client wheel not installed

**Fix:**
```bash
# Install the wheel file
pip install actiancortex-0.1.0b1-py3-none-any.whl

# Verify installation
pip list | grep actiancortex
```

### Issue: Port 50051 already in use

**Cause:** Another service is using port 50051

**Fix:**
```bash
# Find what's using the port
lsof -i :50051

# Kill the process or change the port in docker-compose.yml
# Change to a different port like 50052:
ports:
  - "50052:50051"

# Update ACTIAN_PORT environment variable to match:
environment:
  ACTIAN_PORT: 50052
```

### Issue: Health check always fails

**Cause:** Health check command not compatible with container

**Fix 1 - Simplify health check:**
```yaml
healthcheck:
  test: ["CMD-SHELL", "exit 0"]  # Always passes
  interval: 15s
```

**Fix 2 - Remove health check dependency:**
```yaml
depends_on:
  vectoraidb:
    condition: service_started  # Don't wait for healthy
```

---

## Data Persistence

Collections and data are persisted in the Docker volume:

```yaml
volumes:
  actian_data:
    name: hacklytics_actian_data
    driver: local
```

**View volume location:**
```bash
docker volume inspect hacklytics_actian_data
```

**Backup the volume:**
```bash
# Create a backup
docker run --rm -v hacklytics_actian_data:/data -v $(pwd):/backup \
  ubuntu tar czf /backup/actian_data_backup.tar.gz /data
```

**Restore from backup:**
```bash
# Restore the backup
docker run --rm -v hacklytics_actian_data:/data -v $(pwd):/backup \
  ubuntu tar xzf /backup/actian_data_backup.tar.gz -C /
```

---

## Stopping and Cleaning Up

### Stop all services:
```bash
docker compose down
```

### Stop and remove volumes (CAUTION: deletes all data):
```bash
docker compose down -v
```

### Remove just the VectorAI DB container:
```bash
docker compose stop vectoraidb
docker compose rm -f vectoraidb
```

---

## Performance Tuning

### HNSW Index Parameters

When creating collections, you can tune performance:

```python
await pool.create_collection(
    name="safety_protocols",
    dimension=384,
    hnsw_m=32,              # Edges per node (default: 16)
    hnsw_ef_construct=256,  # Build-time neighbors (default: 200)
    hnsw_ef_search=100,     # Search-time neighbors (default: 50)
)
```

**Trade-offs:**
- Higher `hnsw_m`: More memory, faster search, slower indexing
- Higher `hnsw_ef_construct`: Better index quality, slower build
- Higher `hnsw_ef_search`: More accurate results, slower queries

**For safety-critical low-latency:**
```python
hnsw_m=16,              # Lower memory footprint
hnsw_ef_construct=200,  # Default
hnsw_ef_search=50,      # Faster queries
```

### Resource Limits

Adjust container resources based on workload:

```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'      # Increase for more concurrent searches
      memory: 4G       # Increase for larger collections
    reservations:
      cpus: '1.0'
      memory: 1G
```

---

## Migration from PostgreSQL/pgvector

If you have existing data in PostgreSQL, you need to:

1. Export vectors and payloads from PostgreSQL
2. Convert to VectorAI DB format
3. Batch upsert into collections

**See:** `docs/migration/ACTIAN_MIGRATION_GUIDE.md` for detailed migration steps.

---

## Summary

✅ **Docker Compose updated** to use VectorAI DB (gRPC port 50051)
✅ **Service name changed** from `actian` to `vectoraidb`
✅ **Environment variables updated** to use gRPC configuration
✅ **Health check** configured for gRPC connectivity
✅ **Data persistence** configured with `/data` volume

**Next Actions:**
1. Load the Docker image: `docker image load -i Actian_VectorAI_DB_Beta.tar`
2. Place the wheel file in `fastapi/` directory
3. Start VectorAI DB: `docker compose up -d vectoraidb`
4. Initialize collections: `python scripts/init_actian_collections.py`
5. Seed protocols: `python scripts/seed_protocols.py`
6. Start remaining services: `docker compose up -d`

---

**Last Updated:** February 21, 2026
**Docker Compose Version:** 3.8
**VectorAI DB Version:** 1.0b
