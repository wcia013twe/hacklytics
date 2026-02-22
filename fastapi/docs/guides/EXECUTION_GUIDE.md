# RAG Multi-Agent System - Execution Guide

**Purpose:** Step-by-step guide to execute all 5 prompts sequentially or in parallel for building the RAG backend.

---

## Overview

You have **5 implementation prompts** that build the complete RAG system:

| Prompt | Deliverable | Dependencies | Execution |
|--------|-------------|--------------|-----------|
| **PROMPT_01** | Agents & Contracts | None | ✅ **Independent** - Run in parallel |
| **PROMPT_02** | Orchestrator Core | Prompt 1 | ⚠️ Depends on Prompt 1 |
| **PROMPT_03** | Test Suites | None | ✅ **Independent** - Run in parallel |
| **PROMPT_04** | Actian Setup | None | ✅ **Independent** - Run in parallel |
| **PROMPT_05** | Integration & Deployment | Prompts 1-4 | ⚠️ Depends on ALL |

---

## Execution Strategy

### Option 1: Maximum Parallelization (Fastest)

**Time Estimate:** 2-3 hours total

```
┌─────────────────┐
│   Session 1     │  PROMPT_01_AGENTS_AND_CONTRACTS.md
│   (Terminal 1)  │  → Implements 8 agents + Pydantic contracts
└─────────────────┘  → ~45 minutes

┌─────────────────┐
│   Session 2     │  PROMPT_03_TEST_SUITES.md
│   (Terminal 2)  │  → Implements 7 test profiles
└─────────────────┘  → ~30 minutes

┌─────────────────┐
│   Session 3     │  PROMPT_04_ACTIAN_SETUP.md
│   (Terminal 3)  │  → Docker + schema + seeding
└─────────────────┘  → ~20 minutes

↓ Wait for Session 1 to complete ↓

┌─────────────────┐
│   Session 1     │  PROMPT_02_ORCHESTRATOR_CORE.md
│   (Terminal 1)  │  → Builds orchestrator (uses agents from Prompt 1)
└─────────────────┘  → ~40 minutes

↓ Wait for ALL sessions to complete ↓

┌─────────────────┐
│   Session 1     │  PROMPT_05_INTEGRATION_DEPLOYMENT.md
│   (Terminal 1)  │  → Full stack integration + E2E tests
└─────────────────┘  → ~30 minutes
```

**Total Time:** ~2.5 hours (with parallelization)

---

### Option 2: Sequential Execution (Safer, Easier to Debug)

**Time Estimate:** 3-4 hours total

Run prompts in order:

```
Session 1 → PROMPT_01 (45 min)
            ↓ Verify agents work
Session 1 → PROMPT_02 (40 min)
            ↓ Verify orchestrator works
Session 1 → PROMPT_03 (30 min)
            ↓ Verify tests pass
Session 1 → PROMPT_04 (20 min)
            ↓ Verify Actian works
Session 1 → PROMPT_05 (30 min)
            ↓ Verify full stack works
```

**Total Time:** ~3 hours

---

## Detailed Execution Steps

### Phase 1: Parallel Foundation (Terminals 1, 2, 3)

#### Terminal 1: Agents & Contracts

```bash
# Open PROMPT_01_AGENTS_AND_CONTRACTS.md in Claude Code
cd /Users/wes/Desktop/Project/hacklytics/hacklytics

# Give Claude this prompt:
"Implement all tasks in PROMPT_01_AGENTS_AND_CONTRACTS.md.
Create the backend/agents/ directory, backend/contracts/ directory,
and all 8 agent classes with Pydantic models. Run unit tests when done."

# Expected output:
# - backend/agents/telemetry_ingest.py
# - backend/agents/temporal_buffer.py
# - backend/agents/reflex_publisher.py
# - backend/agents/embedding.py
# - backend/agents/protocol_retrieval.py
# - backend/agents/history_retrieval.py
# - backend/agents/incident_logger.py
# - backend/agents/synthesis.py
# - backend/contracts/models.py
# - tests/agents/ (unit tests)

# Verification:
pytest tests/agents/ -v
```

**Status Check:**
```bash
# Verify all agents exist
ls backend/agents/*.py | wc -l
# Should output: 8

# Verify contracts
python -c "from backend.contracts.models import TelemetryPacket; print('✅ Contracts OK')"
```

---

#### Terminal 2: Test Suites (Parallel)

```bash
# Open PROMPT_03_TEST_SUITES.md in Claude Code (new terminal/session)

# Give Claude this prompt:
"Implement all tasks in PROMPT_03_TEST_SUITES.md.
Create tests/test_profiles/ directory with all 7 test files."

# Expected output:
# - tests/test_profiles/test_01_embedding_sanity.py
# - tests/test_profiles/test_02_protocol_precision.py
# - tests/test_profiles/test_03_trend_accuracy.py
# - tests/test_profiles/test_04_temporal_feedback.py
# - tests/test_profiles/test_05_latency_benchmark.py
# - tests/test_profiles/test_06_graceful_degradation.py
# - tests/test_profiles/test_07_delta_filter.py

# Verification:
pytest tests/test_profiles/ -v -s
# Tests 1, 3, 5, 6, 7 should PASS
# Tests 2, 4 will be SKIPPED (need Actian)
```

**Status Check:**
```bash
# Count test files
ls tests/test_profiles/*.py | wc -l
# Should output: 7

# Run tests
pytest tests/test_profiles/test_01_embedding_sanity.py -v
pytest tests/test_profiles/test_03_trend_accuracy.py -v
```

---

#### Terminal 3: Actian Setup (Parallel)

```bash
# Open PROMPT_04_ACTIAN_SETUP.md in Claude Code (new terminal/session)

# Give Claude this prompt:
"Implement all tasks in PROMPT_04_ACTIAN_SETUP.md.
Create Docker Compose for Actian, SQL schema, seeding script, and test queries."

# Expected output:
# - docker/docker-compose.actian.yml
# - docker/init.sql
# - scripts/seed_protocols.py
# - scripts/test_actian_queries.py
# - backend/actian_pool.py

# Start Actian:
docker-compose -f docker/docker-compose.actian.yml up -d

# Wait for health:
docker exec hacklytics_actian pg_isready -U vectordb

# Seed protocols:
python scripts/seed_protocols.py

# Test queries:
python scripts/test_actian_queries.py
```

**Status Check:**
```bash
# Verify Actian running
docker ps | grep actian
# Should show container as "Up" and "healthy"

# Verify schema
docker exec hacklytics_actian psql -U vectordb -d safety_rag -c "\dt"
# Should list: safety_protocols, incident_log

# Verify protocols seeded
docker exec hacklytics_actian psql -U vectordb -d safety_rag -c "SELECT COUNT(*) FROM safety_protocols;"
# Should return: ≥10 (expand to 30-50 for production)
```

---

### Phase 2: Orchestrator (Terminal 1 only)

**⚠️ WAIT for Prompt 1 (Agents) to complete before starting Prompt 2**

```bash
# In Terminal 1 (where you ran Prompt 1)

# Give Claude this prompt:
"Implement all tasks in PROMPT_02_ORCHESTRATOR_CORE.md.
Build the RAGOrchestrator class and FastAPI ingest service.
This depends on the agents from Prompt 1."

# Expected output:
# - backend/orchestrator.py
# - backend/ingest_service.py
# - tests/test_orchestrator.py

# Start service locally (without Docker):
python backend/ingest_service.py

# In another terminal, test:
curl http://localhost:8000/health
curl -X POST http://localhost:8000/test/inject -H "Content-Type: application/json" -d '{...}'

# Run orchestrator tests:
pytest tests/test_orchestrator.py -v
```

**Status Check:**
```bash
# Verify orchestrator exists
ls backend/orchestrator.py

# Verify service starts
curl http://localhost:8000/health | jq '.status'
# Should return: "healthy"

# Check metrics
curl http://localhost:8000/health | jq '.metrics'
```

---

### Phase 3: Integration (Terminal 1 only)

**⚠️ WAIT for ALL prompts (1-4) to complete before starting Prompt 5**

```bash
# In Terminal 1

# Give Claude this prompt:
"Implement all tasks in PROMPT_05_INTEGRATION_DEPLOYMENT.md.
Create full Docker Compose stack, integrate Actian with orchestrator,
run E2E tests. This depends on Prompts 1, 2, 3, and 4."

# Expected output:
# - docker-compose.yml (root level)
# - backend/Dockerfile.ingest
# - backend/requirements.txt
# - .env
# - scripts/deploy.sh
# - tests/integration/test_e2e_pipeline.py
# - docs/QUICKSTART.md

# Deploy full stack:
./scripts/deploy.sh

# Verify all services:
docker-compose ps

# Run E2E tests:
pytest tests/integration/test_e2e_pipeline.py -v -s
```

**Status Check:**
```bash
# Verify all containers running
docker-compose ps
# Should show: actian (healthy), ingest (healthy)

# Test full pipeline
curl -X POST http://localhost:8000/test/inject -H "Content-Type: application/json" -d @tests/fixtures/critical_packet.json

# Check incident log populated
docker exec hacklytics_actian psql -U vectordb -d safety_rag -c "SELECT COUNT(*) FROM incident_log;"
# Should increase with each packet

# Check latency metrics
curl http://localhost:8000/health | jq '.metrics'
# Verify: reflex_p95 < 50ms, rag_p95 < 2000ms
```

---

## Verification Checklist

After completing all 5 prompts:

### ✅ Prompt 1 Verification
- [ ] 8 agent files created in `backend/agents/`
- [ ] Pydantic contracts in `backend/contracts/models.py`
- [ ] Unit tests pass: `pytest tests/agents/ -v`
- [ ] No import errors: `python -c "from backend.agents import *"`

### ✅ Prompt 2 Verification
- [ ] Orchestrator created: `backend/orchestrator.py`
- [ ] Ingest service created: `backend/ingest_service.py`
- [ ] Service starts: `curl http://localhost:8000/health`
- [ ] Tests pass: `pytest tests/test_orchestrator.py -v`

### ✅ Prompt 3 Verification
- [ ] 7 test files in `tests/test_profiles/`
- [ ] Tests 1, 3, 5, 6, 7 pass (without Actian)
- [ ] Tests 2, 4 have mock placeholders

### ✅ Prompt 4 Verification
- [ ] Actian container running: `docker ps | grep actian`
- [ ] Schema created: `\dt` shows 2 tables
- [ ] Protocols seeded: ≥10 entries
- [ ] Test queries pass: `python scripts/test_actian_queries.py`

### ✅ Prompt 5 Verification
- [ ] Full stack deploys: `./scripts/deploy.sh`
- [ ] All services healthy: `docker-compose ps`
- [ ] E2E tests pass: `pytest tests/integration/ -v`
- [ ] Reflex latency p95 < 50ms
- [ ] RAG latency p99 < 2s
- [ ] Incident logging works
- [ ] WebSocket connections stable

---

## Troubleshooting

### Issue: Prompt 2 fails because agents not found
**Solution:** Ensure Prompt 1 completed successfully. Check imports.

### Issue: Actian won't start
**Solution:**
```bash
docker-compose -f docker/docker-compose.actian.yml down -v
docker-compose -f docker/docker-compose.actian.yml up -d
```

### Issue: E2E tests fail with Actian connection error
**Solution:** Verify Actian is healthy and accessible:
```bash
docker exec hacklytics_actian pg_isready -U vectordb
python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('postgresql://vectordb:vectordb_pass@localhost:5432/safety_rag'))"
```

### Issue: RAG latency exceeds 2s
**Solution:** Check Actian index health:
```bash
docker exec -it hacklytics_actian psql -U vectordb -d safety_rag
SELECT * FROM pg_stat_user_indexes WHERE tablename = 'safety_protocols';
```

### Issue: Reflex latency exceeds 50ms
**Solution:** Check buffer computation time, reduce packet processing overhead.

---

## Summary

**Fastest Path (Parallel):**
1. Open 3 terminals/Claude sessions
2. Run Prompts 1, 3, 4 in parallel (~45 min)
3. Run Prompt 2 in Terminal 1 after Prompt 1 completes (~40 min)
4. Run Prompt 5 in Terminal 1 after ALL complete (~30 min)
5. **Total: ~2.5 hours**

**Safest Path (Sequential):**
1. Run Prompt 1 → Verify → Run Prompt 2 → Verify → Run Prompt 3 → Verify → Run Prompt 4 → Verify → Run Prompt 5 → Verify
2. **Total: ~3 hours**

---

## Expected Final Structure

```
hacklytics/
├── backend/
│   ├── agents/
│   │   ├── telemetry_ingest.py
│   │   ├── temporal_buffer.py
│   │   ├── reflex_publisher.py
│   │   ├── embedding.py
│   │   ├── protocol_retrieval.py
│   │   ├── history_retrieval.py
│   │   ├── incident_logger.py
│   │   └── synthesis.py
│   ├── contracts/
│   │   └── models.py
│   ├── orchestrator.py
│   ├── ingest_service.py
│   ├── actian_pool.py
│   ├── Dockerfile.ingest
│   └── requirements.txt
├── docker/
│   ├── docker-compose.actian.yml
│   └── init.sql
├── scripts/
│   ├── seed_protocols.py
│   ├── test_actian_queries.py
│   └── deploy.sh
├── tests/
│   ├── agents/
│   ├── test_orchestrator.py
│   ├── test_profiles/
│   │   ├── test_01_embedding_sanity.py
│   │   ├── test_02_protocol_precision.py
│   │   ├── test_03_trend_accuracy.py
│   │   ├── test_04_temporal_feedback.py
│   │   ├── test_05_latency_benchmark.py
│   │   ├── test_06_graceful_degradation.py
│   │   └── test_07_delta_filter.py
│   └── integration/
│       └── test_e2e_pipeline.py
├── docs/
│   └── QUICKSTART.md
├── docker-compose.yml
├── .env
├── RAG.MD
├── PROMPT_01_AGENTS_AND_CONTRACTS.md
├── PROMPT_02_ORCHESTRATOR_CORE.md
├── PROMPT_03_TEST_SUITES.md
├── PROMPT_04_ACTIAN_SETUP.md
├── PROMPT_05_INTEGRATION_DEPLOYMENT.md
└── EXECUTION_GUIDE.md (this file)
```

---

🎉 **You're ready to build!** Start with the parallel approach for maximum speed.
