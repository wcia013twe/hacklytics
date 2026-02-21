# Temporal RAG Backend Documentation

Safety-critical fire detection backend implementing the Reflex-Cognition Split architecture.

---

## Quick Links

### 📖 Overview
- **[Architecture](overview/RAG.MD)** - Complete system architecture (58KB, comprehensive)

### 🚀 Setup & Deployment
- **[Docker Setup](setup/DOCKER_SETUP.md)** - Container deployment guide
- **[Docker README](setup/DOCKER_README.md)** - Docker architecture overview

### 🧪 Development & Testing
- **[Makefile Guide](guides/MAKEFILE_GUIDE.md)** - Command reference for all make targets
- **[Test Workflow](testing/TEST_WORKFLOW.md)** - Visual testing diagrams
- **[Quick Start](guides/QUICK_START.md)** - Fast setup for testing

### 🔄 Migration
- **[Actian Migration](migration/ACTIAN_MIGRATION_GUIDE.md)** - PostgreSQL → Actian VectorAI DB
- **[Migration Summary](migration/MIGRATION_SUMMARY.md)** - Decision guide

### 📋 Prompts (Implementation Guides)
- **[PROMPT_01](system_prompts/PROMPT_01_AGENTS_AND_CONTRACTS.md)** - Agents & Contracts
- **[PROMPT_02](system_prompts/PROMPT_02_ORCHESTRATOR_CORE.md)** - Orchestrator Core
- **[PROMPT_03](system_prompts/PROMPT_03_TEST_SUITES.md)** - Test Suites (7 profiles)
- **[PROMPT_04](system_prompts/PROMPT_04_ACTIAN_SETUP.md)** - Actian Vector DB Setup
- **[PROMPT_05](system_prompts/PROMPT_05_INTEGRATION_DEPLOYMENT.md)** - Integration & E2E

---

## Quick Start (30 seconds)

```bash
# From fastapi/ directory
make setup          # init + build + up
make seed           # Seed safety protocols
make test-all       # Run all tests
```

---

## Architecture Overview

```
Jetson Nano (Edge)
    ↓ ZeroMQ
Ingest Container (:8000, :5555)
    ↓ HTTP POST
RAG Container (:8001)
    ↓ gRPC/SQL
Actian Vector DB (:5432 or :50051)
```

**Dual-Path Design:**
- **Reflex Path** (<50ms): Critical safety alerts
- **Cognition Path** (<2s): RAG recommendations

---

## Directory Structure

```
docs/
├── README.md                    ← You are here
├── overview/
│   └── RAG.MD                   ← Complete architecture (58KB)
├── setup/
│   ├── DOCKER_SETUP.md          ← Deployment guide
│   └── DOCKER_README.md         ← Docker overview
├── guides/
│   ├── MAKEFILE_GUIDE.md        ← make commands reference
│   └── QUICK_START.md           ← Fast testing setup
├── testing/
│   └── TEST_WORKFLOW.md         ← Visual test diagrams
├── migration/
│   ├── ACTIAN_MIGRATION_GUIDE.md
│   └── MIGRATION_SUMMARY.md
└── system_prompts/
    ├── PROMPT_01_*.md           ← Implementation guides
    ├── PROMPT_02_*.md
    ├── PROMPT_03_*.md
    ├── PROMPT_04_*.md
    └── PROMPT_05_*.md
```

---

## Common Tasks

### Testing
```bash
make test-prompt01   # Test agents
make test-prompt02   # Test orchestrator
make test-prompt03   # Test 7 profiles
make test-prompt04   # Test Actian setup
make test-prompt05   # Test E2E integration
make test-all        # Run all tests
```

### Database
```bash
make seed            # Seed protocols
make db-verify       # Check schema/data
make db-reset        # Reset database
```

### Development
```bash
make logs            # View all logs
make health          # Check services
make shell-rag       # Open RAG shell
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Transport | ZeroMQ (PUB/SUB) |
| API | FastAPI + asyncio |
| Embedding | all-MiniLM-L6-v2 (384-dim) |
| Vector DB | Actian Vector / PostgreSQL+pgvector |
| Containers | Docker Compose |

---

## Getting Help

1. **Makefile commands:** `make help`
2. **Test a specific prompt:** `make test-prompt0X`
3. **Check logs:** `make logs-rag` or `make logs-ingest`
4. **Verify database:** `make db-verify`
5. **Full guide:** See [Makefile Guide](guides/MAKEFILE_GUIDE.md)

---

**Last Updated:** February 21, 2026
