# Makefile Quick Reference Guide

**Location:** `/fastapi/Makefile`
**Purpose:** Simplified commands for building, testing, and validating each PROMPT scope

---

## Quick Start

```bash
# View all available commands
make help

# Full setup from scratch
make setup

# Run all tests
make test-all
```

---

## Prompt-Scoped Testing

Each PROMPT has a dedicated test target that validates its deliverables:

### PROMPT 1: Agents & Contracts
```bash
make test-prompt01
```

**What it tests:**
- ✅ 8 sub-agent implementations (TelemetryIngest, TemporalBuffer, etc.)
- ✅ Pydantic data models (TelemetryPacket, Protocol, HistoryEntry, etc.)
- ✅ Input/output validation
- ✅ Unit tests for each agent

**Expected output:**
```
========================================
PROMPT 1: Agents & Contracts Testing
========================================

Testing 8 sub-agents + Pydantic models...
tests/test_agents/test_telemetry_ingest.py::test_validate_schema PASSED
tests/test_agents/test_temporal_buffer.py::test_insert_packet PASSED
...
✅ PROMPT 1 validation complete
```

**Troubleshooting:**
```bash
# If tests fail, check agent implementations
make shell-rag
cd backend/agents
ls -la

# Re-run specific agent test
docker-compose exec rag python -m pytest tests/test_agents/test_temporal_buffer.py -v
```

---

### PROMPT 2: Orchestrator Core
```bash
make test-prompt02
```

**What it tests:**
- ✅ RAGOrchestrator dual-path routing
- ✅ Reflex path (<50ms latency)
- ✅ Cognition path (async, fire-and-forget)
- ✅ Error handling and graceful degradation
- ✅ Metrics collection (p50, p95 latency)

**Expected output:**
```
========================================
PROMPT 2: Orchestrator Core Testing
========================================

Testing dual-path routing, error handling, metrics...
tests/test_orchestrator.py::test_reflex_path PASSED
tests/test_orchestrator.py::test_cognition_path PASSED
tests/test_orchestrator.py::test_rag_failure_doesnt_block_reflex PASSED
...
✅ PROMPT 2 validation complete
```

**Troubleshooting:**
```bash
# Check orchestrator implementation
make shell-rag
cat backend/orchestrator.py | grep -A 20 "class RAGOrchestrator"

# Run with verbose logging
docker-compose exec rag python -m pytest tests/test_orchestrator.py -v -s
```

---

### PROMPT 3: Test Suites (7 Profiles)
```bash
make test-prompt03
```

**What it tests:**
- ✅ Test 1: Embedding Semantic Sanity
- ✅ Test 2: Protocol Retrieval Precision (≥80%)
- ✅ Test 3: Temporal Trend Accuracy (100%)
- ✅ Test 4: Incident Log Feedback Loop
- ✅ Test 5: E2E Latency Benchmark (p95 <1500ms)
- ✅ Test 6: Graceful Degradation
- ✅ Test 7: Delta Filter Validation

**Expected output:**
```
========================================
PROMPT 3: Test Suites (7 Profiles)
========================================

Running test profiles 1-7...
tests/test_profiles/test_01_embedding_sanity.py::test_semantic_similarity PASSED
tests/test_profiles/test_02_protocol_precision.py::test_retrieval_precision PASSED
tests/test_profiles/test_03_trend_accuracy.py::test_rapid_growth PASSED
tests/test_profiles/test_03_trend_accuracy.py::test_growing PASSED
tests/test_profiles/test_03_trend_accuracy.py::test_stable PASSED
tests/test_profiles/test_03_trend_accuracy.py::test_diminishing PASSED
...

Test Profile Summary:
  1. ✅ Embedding Semantic Sanity
  2. ✅ Protocol Retrieval Precision
  3. ✅ Temporal Trend Accuracy
  4. ✅ Incident Log Feedback Loop
  5. ✅ E2E Latency Benchmark
  6. ✅ Graceful Degradation
  7. ✅ Delta Filter Validation

✅ PROMPT 3 validation complete
```

**Troubleshooting:**
```bash
# Run specific test profile
docker-compose exec rag python -m pytest tests/test_profiles/test_03_trend_accuracy.py -v

# Check test data fixtures
make shell-rag
cat tests/test_profiles/conftest.py
```

---

### PROMPT 4: Actian Vector DB Setup
```bash
make test-prompt04
```

**What it tests:**
- ✅ Actian container health (pg_isready)
- ✅ Schema creation (safety_protocols, incident_log)
- ✅ Vector indexes (IVFFlat)
- ✅ Protocol seeding (10+ protocols)
- ✅ Vector similarity retrieval

**Expected output:**
```
========================================
PROMPT 4: Actian Vector DB Setup
========================================

[1/4] Checking Actian container health...
/tmp:5432 - accepting connections
✅ Actian container healthy

[2/4] Verifying schema (safety_protocols, incident_log)...
 safety_protocols
 incident_log
✅ Schema verified

[3/4] Checking protocol count...
 protocol_count
----------------
             10
(1 row)

[4/4] Testing vector similarity retrieval...
✅ Query returned 3 protocols with similarity > 0.7

✅ PROMPT 4 validation complete
```

**Troubleshooting:**
```bash
# Check Actian logs
make logs-actian

# Verify schema manually
make db-shell
\dt
\di
SELECT COUNT(*) FROM safety_protocols;

# Reset and re-seed
make db-reset
make seed
```

---

### PROMPT 5: Integration & E2E
```bash
make test-prompt05
```

**What it tests:**
- ✅ All services running (actian, rag, ingest)
- ✅ Health checks (HTTP endpoints)
- ✅ Full data flow: ZMQ → Buffer → Embedding → Actian → WebSocket
- ✅ E2E latency targets

**Expected output:**
```
========================================
PROMPT 5: Integration & E2E Testing
========================================

[1/3] Verifying all services are running...
hacklytics_actian    running
hacklytics_rag       running
hacklytics_ingest    running
✅ All services running

[2/3] Health check (ingest + rag + actian)...
Checking Ingest service...
{"status": "healthy"}

Checking RAG service...
{"status": "healthy", "actian_connected": true}

Checking Actian database...
/tmp:5432 - accepting connections

[3/3] Running E2E integration tests...
tests/test_integration/test_full_pipeline.py::test_zmq_to_websocket PASSED
tests/test_integration/test_full_pipeline.py::test_reflex_latency PASSED
tests/test_integration/test_full_pipeline.py::test_rag_recommendation PASSED
...

✅ PROMPT 5 validation complete
```

**Troubleshooting:**
```bash
# Check service status
make ps
make health

# View logs from all services
make logs

# Restart everything
make restart
```

---

## Database Operations

### Seed Safety Protocols
```bash
make seed
```

Runs `scripts/seed_protocols.py` to populate `safety_protocols` table with NFPA/OSHA protocols.

**Expected output:**
```
Running protocol seeding script...
[1/4] Loading sentence-transformers model...
✓ Model loaded: all-MiniLM-L6-v2 (384 dimensions)

[2/4] Connecting to Actian Vector DB at actian:5432...
✓ Connected to database: safety_db

[3/4] Verifying safety_protocols table exists...
✓ Table exists

[4/4] Embedding and inserting 10 protocols...
  [1/10] CRITICAL | Person trapped near fire with exit blocked
  [2/10] HIGH     | Fire blocking primary exit path
  ...
  [10/10] LOW      | Clear scene with no hazards detected

✓ Inserted 10 protocols successfully
```

---

### Verify Database State
```bash
make db-verify
```

**Shows:**
- Tables (safety_protocols, incident_log)
- Indexes (idx_protocol_vector, idx_incident_vector)
- Protocol count
- Incident count
- Protocol coverage by severity/category

**Example output:**
```
Tables:
 safety_protocols
 incident_log

Indexes:
 idx_protocol_vector
 idx_protocol_severity
 idx_incident_vector
 idx_incident_session

Protocol count:
 10

Incident count:
 142

Protocol coverage:
 severity  | category | count
-----------+----------+-------
 CRITICAL  | fire     | 3
 HIGH      | fire     | 4
 MEDIUM    | fire     | 2
 LOW       | fire     | 1
```

---

### Reset Database
```bash
make db-reset
```

**Warning:** This deletes ALL data in Actian. Use for clean starts.

**What it does:**
1. Drops `incident_log` table
2. Drops `safety_protocols` table
3. Re-runs `init.sql` to recreate schema
4. Prompts you to run `make seed`

---

## Common Workflows

### First-Time Setup
```bash
# 1. Initialize environment
make init

# 2. Build containers
make build

# 3. Start services
make up

# 4. Wait for health checks
make health

# 5. Seed database
make seed

# 6. Verify everything
make test-all
```

---

### After Code Changes (Agent Implementation)
```bash
# 1. Rebuild RAG container
docker-compose build rag

# 2. Restart RAG service
docker-compose restart rag

# 3. Test specific prompt
make test-prompt01

# Or test all
make test-all
```

---

### After Schema Changes (init.sql)
```bash
# 1. Reset database
make db-reset

# 2. Re-seed protocols
make seed

# 3. Verify schema
make db-verify

# 4. Test Actian integration
make test-prompt04
```

---

### Debugging a Failed Test
```bash
# 1. Check which test failed
make test-prompt03

# 2. View detailed logs
make logs-rag

# 3. Open shell in container
make shell-rag

# 4. Run test manually with verbose output
python -m pytest tests/test_profiles/test_03_trend_accuracy.py -v -s

# 5. Check agent code
cat backend/agents/temporal_buffer.py
```

---

### Monitoring During Development
```bash
# Terminal 1: Live logs
make logs

# Terminal 2: Service status
watch -n 5 'make ps'

# Terminal 3: Health checks
watch -n 10 'make health'

# Terminal 4: Database state
watch -n 15 'make db-verify'
```

---

## Test Coverage Summary

| Prompt | Command | Tests | Pass Criteria |
|--------|---------|-------|---------------|
| PROMPT 1 | `make test-prompt01` | Agent unit tests | All 8 agents pass |
| PROMPT 2 | `make test-prompt02` | Orchestrator tests | Dual-path routing works |
| PROMPT 3 | `make test-prompt03` | 7 test profiles | All profiles pass |
| PROMPT 4 | `make test-prompt04` | Actian setup | Schema + seeding verified |
| PROMPT 5 | `make test-prompt05` | E2E integration | Full pipeline works |

---

## Quick Troubleshooting

### "Actian not ready" error
```bash
# Check if container is running
docker ps | grep actian

# View logs
make logs-actian

# Restart Actian
docker-compose restart actian

# Wait for health check
docker-compose exec actian pg_isready -U vectoruser
```

---

### "Agent tests not found" error
```bash
# Verify test directory exists
make shell-rag
ls tests/test_agents/

# If missing, create tests or check mount
docker-compose exec rag ls /app/tests/
```

---

### "RAG service not responding" error
```bash
# Check if RAG is running
docker ps | grep rag

# Check logs for errors
make logs-rag

# Rebuild and restart
docker-compose build rag
docker-compose up -d rag
```

---

### "Protocol count is 0" error
```bash
# Re-seed protocols
make seed

# Verify seed script ran
docker-compose exec -T actian psql -U vectoruser -d safety_db \
  -c "SELECT COUNT(*) FROM safety_protocols;"

# Check seed script
make shell-rag
cat scripts/seed_protocols.py
```

---

## Pro Tips

1. **Use `make help` often** - The help menu is always up-to-date
2. **Test incrementally** - Run `make test-prompt0X` after each prompt implementation
3. **Check logs first** - 90% of issues are visible in `make logs`
4. **Reset database cleanly** - Use `make db-reset` instead of manual SQL
5. **Verify before E2E** - Run `make health` and `make db-verify` before integration tests

---

**Last Updated:** February 21, 2026
**Makefile Location:** `/fastapi/Makefile`
**Related Docs:** See `PROMPT_01` through `PROMPT_05` in `/fastapi/system_prompts/`
