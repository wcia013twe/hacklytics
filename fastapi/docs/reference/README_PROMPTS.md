# RAG Multi-Agent System Prompts - Quick Reference

**Generated:** February 21, 2026
**Purpose:** Decompose RAG.MD into 5 executable implementation prompts for Claude Code

---

## 📋 Overview

This system implements a **safety-critical dual-path RAG architecture** with 8 specialized sub-agents coordinated by a master orchestrator.

**Architecture Highlights:**
- **Reflex Path:** <50ms edge compute → instant hazard alerts
- **Cognition Path:** 0.5-2s RAG → contextual intelligence
- **Graceful Degradation:** System continues with reflex alerts if RAG fails

---

## 📁 Files Created

### Implementation Prompts (5 files)
1. `PROMPT_01_AGENTS_AND_CONTRACTS.md` - 8 sub-agents + Pydantic models
2. `PROMPT_02_ORCHESTRATOR_CORE.md` - Master orchestrator + FastAPI service
3. `PROMPT_03_TEST_SUITES.md` - 7 test profiles with validation
4. `PROMPT_04_ACTIAN_SETUP.md` - Vector DB + schema + seeding
5. `PROMPT_05_INTEGRATION_DEPLOYMENT.md` - Full stack deployment

### Guides
- `EXECUTION_GUIDE.md` - How to run prompts sequentially or in parallel
- `README_PROMPTS.md` - This file

### For Jetson Engineer
- `JETSON_SPEC.md` - Complete interface specification (1 condensed doc)

### Original Specification
- `RAG.MD` - Original architecture document (reference)

---

## 🚀 Quick Start

### Option 1: Maximum Speed (Parallel - 2.5 hours)

```bash
# Terminal 1
# Open PROMPT_01_AGENTS_AND_CONTRACTS.md → Implement agents

# Terminal 2 (parallel)
# Open PROMPT_03_TEST_SUITES.md → Implement tests

# Terminal 3 (parallel)
# Open PROMPT_04_ACTIAN_SETUP.md → Setup database

# Back to Terminal 1 (after Prompt 1 done)
# Open PROMPT_02_ORCHESTRATOR_CORE.md → Build orchestrator

# Back to Terminal 1 (after ALL done)
# Open PROMPT_05_INTEGRATION_DEPLOYMENT.md → Deploy full stack
```

### Option 2: Sequential (Safer - 3 hours)

```bash
# Single terminal, run in order:
1. PROMPT_01 → Verify
2. PROMPT_02 → Verify
3. PROMPT_03 → Verify
4. PROMPT_04 → Verify
5. PROMPT_05 → Verify
```

**See `EXECUTION_GUIDE.md` for detailed step-by-step instructions.**

---

## 🎯 Prompt Dependencies

```
┌────────────┐
│ PROMPT 01  │  ✅ Independent
│ Agents     │  Can run in parallel
└────────────┘
      ↓
┌────────────┐
│ PROMPT 02  │  ⚠️ Depends on Prompt 1
│Orchestrator│  Uses agents from Prompt 1
└────────────┘

┌────────────┐
│ PROMPT 03  │  ✅ Independent
│   Tests    │  Can run in parallel
└────────────┘

┌────────────┐
│ PROMPT 04  │  ✅ Independent
│   Actian   │  Can run in parallel
└────────────┘

      ↓ ↓ ↓ ↓
┌────────────┐
│ PROMPT 05  │  ⚠️ Depends on ALL (1-4)
│Integration │  Final deployment
└────────────┘
```

---

## 📦 Expected Deliverables

After completing all 5 prompts:

### Code
- 8 agent classes (`backend/agents/*.py`)
- Pydantic contracts (`backend/contracts/models.py`)
- Orchestrator (`backend/orchestrator.py`)
- FastAPI service (`backend/ingest_service.py`)
- Actian connection pool (`backend/actian_pool.py`)

### Infrastructure
- Docker Compose (`docker-compose.yml`)
- Actian schema (`docker/init.sql`)
- Dockerfile for ingest service
- Environment configuration (`.env`)

### Tests
- 7 test profiles (`tests/test_profiles/`)
- Orchestrator unit tests
- E2E integration tests

### Data
- 30-50 safety protocols (seeded in Actian)
- Seeding script (`scripts/seed_protocols.py`)

### Documentation
- Quick start guide (`docs/QUICKSTART.md`)

---

## ✅ Verification Checklist

Use this to confirm each prompt completed successfully:

### After Prompt 1
- [ ] `pytest tests/agents/ -v` passes
- [ ] All 8 agents import without errors
- [ ] Pydantic models validate correctly

### After Prompt 2
- [ ] `curl http://localhost:8000/health` returns healthy
- [ ] Orchestrator processes test packets
- [ ] Reflex path executes <50ms

### After Prompt 3
- [ ] 5 out of 7 tests pass (without Actian)
- [ ] Tests 2 and 4 have mock placeholders
- [ ] Embedding sanity test passes

### After Prompt 4
- [ ] `docker ps | grep actian` shows healthy container
- [ ] Protocol count ≥10
- [ ] Test queries return results <200ms

### After Prompt 5
- [ ] `./scripts/deploy.sh` succeeds
- [ ] All E2E tests pass
- [ ] Reflex p95 < 50ms, RAG p99 < 2s
- [ ] Incident logging works

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Transport** | ZeroMQ PUB/SUB | Jetson → Backend |
| **API** | FastAPI + asyncio | Async orchestration |
| **WebSocket** | FastAPI WebSocket | Dashboard real-time updates |
| **Embedding** | all-MiniLM-L6-v2 | 384-dim semantic vectors |
| **Vector DB** | Actian Vector (or pgvector) | Hybrid vector + SQL queries |
| **Containerization** | Docker Compose | 3-service topology |
| **Language** | Python 3.11+ | All backend code |

---

## 📊 System Metrics

**Performance Targets:**
- Reflex path latency: p95 < 50ms
- RAG path latency: p99 < 2s
- Protocol retrieval precision@3: ≥80%
- Trend classification accuracy: 100%

**Throughput:**
- 10 FPS sustained
- 5 concurrent devices
- 10 WebSocket clients per session

---

## 🔧 Troubleshooting

### Common Issues

**Agents not found in Prompt 2**
→ Ensure Prompt 1 completed, check `backend/agents/` exists

**Actian connection fails**
→ Verify container health: `docker exec hacklytics_actian pg_isready -U vectordb`

**RAG latency high**
→ Check Actian indexes: `SELECT * FROM pg_stat_user_indexes;`

**E2E tests fail**
→ Verify all services healthy: `docker-compose ps`

---

## 📚 Additional Resources

- **Original Spec:** `RAG.MD`
- **Execution Guide:** `EXECUTION_GUIDE.md`
- **Quick Start:** `docs/QUICKSTART.md` (created in Prompt 5)

---

## 🎉 Next Steps

1. **Choose execution strategy** (parallel or sequential)
2. **Open first prompt** in Claude Code
3. **Follow EXECUTION_GUIDE.md** for detailed instructions
4. **Verify each step** using checklists above
5. **Deploy full stack** with Prompt 5

---

## 📞 Support

For questions or issues:
1. Check `EXECUTION_GUIDE.md` troubleshooting section
2. Review verification checklists
3. Check RAG.MD for architecture details

---

**Ready to build?** Start with `EXECUTION_GUIDE.md` for step-by-step instructions.
