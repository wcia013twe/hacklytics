# Temporal RAG Backend

Safety-critical fire detection system with dual-path architecture (Reflex + Cognition).

---

## Quick Start

```bash
make setup && make seed && make test-all
```

**Time:** ~2 minutes

---

## Architecture

```
Jetson Nano → ZeroMQ → Ingest → RAG → Actian Vector DB
              (edge)    (:8000)  (:8001)  (:5432)
```

**Dual-Path Design:**
- **Reflex** (<50ms): Immediate hazard alerts
- **Cognition** (<2s): Protocol retrieval + recommendations

See [docs/overview/RAG.MD](docs/overview/RAG.MD) for complete architecture.

---

## Documentation

| Topic | Link |
|-------|------|
| 📖 **Overview** | [docs/overview/RAG.MD](docs/overview/RAG.MD) |
| 🚀 **Setup** | [docs/setup/DOCKER_SETUP.md](docs/setup/DOCKER_SETUP.md) |
| 🧪 **Testing** | [docs/testing/TEST_WORKFLOW.md](docs/testing/TEST_WORKFLOW.md) |
| 📋 **Commands** | [docs/guides/MAKEFILE_GUIDE.md](docs/guides/MAKEFILE_GUIDE.md) |
| 🔄 **Migration** | [docs/migration/MIGRATION_SUMMARY.md](docs/migration/MIGRATION_SUMMARY.md) |
| ⚡ **Quick Start** | [docs/guides/QUICK_START.md](docs/guides/QUICK_START.md) |

**Implementation Guides:** See [docs/system_prompts/](docs/system_prompts/)

---

## Common Commands

```bash
# Full setup
make setup          # init + build + up
make seed           # Seed protocols
make test-all       # Run all tests

# Testing by component
make test-prompt01  # Agents
make test-prompt02  # Orchestrator
make test-prompt03  # Test suites
make test-prompt04  # Actian DB
make test-prompt05  # E2E integration

# Development
make logs           # View logs
make health         # Check services
make db-verify      # Check database

# Help
make help           # Show all commands
```

---

## Project Structure

```
fastapi/
├── backend/                 # Python source code
│   ├── agents/             # 8 specialized agents
│   ├── contracts/          # Pydantic models
│   ├── orchestrator.py     # Dual-path coordinator
│   └── main_*.py           # FastAPI services
├── tests/                  # Test suites
│   ├── test_agents/        # Agent unit tests
│   ├── test_profiles/      # 7 test profiles
│   └── test_integration/   # E2E tests
├── scripts/                # Utilities
│   ├── seed_protocols.py   # DB seeding
│   └── test_actian_*.py    # DB verification
├── docs/                   # Documentation
│   ├── overview/           # Architecture
│   ├── guides/             # How-to guides
│   ├── testing/            # Test workflows
│   └── system_prompts/     # Implementation guides
├── docker-compose.yml      # Service definitions
├── Makefile               # Development commands
└── README.md              # This file
```

---

## Tech Stack

- **Transport:** ZeroMQ (PUB/SUB)
- **API:** FastAPI + asyncio
- **Embedding:** all-MiniLM-L6-v2 (384-dim)
- **Vector DB:** Actian Vector / PostgreSQL+pgvector
- **Containers:** Docker Compose

---

## Testing

Run tests for each implementation phase:

```bash
make test-prompt01   # PROMPT 1: Agents & Contracts
make test-prompt02   # PROMPT 2: Orchestrator Core
make test-prompt03   # PROMPT 3: Test Suites (7 profiles)
make test-prompt04   # PROMPT 4: Actian Setup
make test-prompt05   # PROMPT 5: E2E Integration
```

See [docs/testing/TEST_WORKFLOW.md](docs/testing/TEST_WORKFLOW.md) for details.

---

## Development Workflow

1. **Implement a PROMPT** (e.g., agents from PROMPT_01)
2. **Test immediately:** `make test-prompt01`
3. **Fix issues:** Check logs with `make logs-rag`
4. **Verify database:** `make db-verify`
5. **Move to next PROMPT**

Full guide: [docs/guides/MAKEFILE_GUIDE.md](docs/guides/MAKEFILE_GUIDE.md)

---

## Getting Help

```bash
make help           # Show all commands
make logs           # View service logs
make health         # Check service status
make db-verify      # Check database state
```

**Documentation:** [docs/README.md](docs/README.md)

---

## License

[Add license here]

---

**Project:** Hacklytics Safety-Critical Fire Detection
**Architecture:** Reflex-Cognition Split
**Status:** Development
