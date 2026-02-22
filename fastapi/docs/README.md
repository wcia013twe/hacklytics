# Hacklytics Fire Safety System Documentation

**Complete documentation for the RAG-based safety-critical fire detection system**

Safety-critical fire detection backend implementing the Reflex-Cognition Split architecture.

---

## 📚 Quick Navigation

| I want to... | Go to... |
|--------------|----------|
| **Get started in 2 minutes** | [Quick Start Guide](guides/QUICK_START.md) |
| **Understand the system** | [Complete Architecture](overview/RAG.MD) |
| **Run commands** | [Makefile Guide](guides/MAKEFILE_GUIDE.md) |
| **Deploy with Docker** | [Docker Setup](setup/DOCKER_SETUP.md) |
| **Migrate to Actian** | [Actian Migration](deployment/VECTORAIDB_DEPLOYMENT.md) |
| **Implement the system** | [Execution Guide](guides/EXECUTION_GUIDE.md) |
| **Understand safety features** | [Safety Improvements](SAFETY_IMPROVEMENTS.md) |

---

## 📖 Documentation Structure

### **Architecture** - System Design & Technical Decisions
- [RAG.MD](overview/RAG.MD) - **Complete system architecture** (58KB comprehensive guide)
- [Read/Write Path Architecture](architecture/READ_WRITE_PATH_ARCHITECTURE.md) - Dual-path caching strategy
- [Semantic Cache Migration](architecture/SEMANTIC_CACHE_MIGRATION.md) - Cache optimization details
- [Spatial Awareness Implementation](architecture/SPATIAL_AWARENESS_IMPLEMENTATION_PLAN.md) - iPhone IMU/ARKit integration

### **Deployment** - Getting the System Running
- [VectorAI DB Deployment](deployment/VECTORAIDB_DEPLOYMENT.md) - Actian Vector database setup
- [Docker Setup](setup/DOCKER_SETUP.md) - Container deployment guide
- [Docker README](setup/DOCKER_README.md) - Docker architecture overview

### **Guides** - Step-by-Step Instructions
- [Quick Start](guides/QUICK_START.md) - **Fast 2-minute setup**
- [Execution Guide](guides/EXECUTION_GUIDE.md) - **How to implement all 5 prompts** (sequential or parallel)
- [Makefile Guide](guides/MAKEFILE_GUIDE.md) - All `make` commands reference
- [Incident Cleanup](guides/INCIDENT_CLEANUP.md) - **Auto-cleanup for hackathon demos**

### **Reference** - Specifications & Guidelines
- [Jetson Spec](reference/JETSON_SPEC.md) - Edge device interface specification
- [Prompts Reference](reference/README_PROMPTS.md) - Quick reference for all implementation prompts
- [Claude Guidelines](reference/CLAUDE_GUIDELINES.md) - Safety-first development workflow

### **System Prompts** - Implementation Instructions
Implementation guides for building the system (execute in order):
1. [PROMPT_01: Agents & Contracts](system_prompts/PROMPT_01_AGENTS_AND_CONTRACTS.md) - 8 agents + Pydantic models
2. [PROMPT_02: Orchestrator Core](system_prompts/PROMPT_02_ORCHESTRATOR_CORE.md) - Master orchestrator + FastAPI
3. [PROMPT_03: Test Suites](system_prompts/PROMPT_03_TEST_SUITES.md) - 7 test profiles
4. [PROMPT_04: Actian Setup](system_prompts/PROMPT_04_ACTIAN_SETUP.md) - Vector DB + schema
5. [PROMPT_05: Integration](system_prompts/PROMPT_05_INTEGRATION_DEPLOYMENT.md) - Full stack deployment

### **Testing** - Validation & Quality Assurance
- [Test Workflow](testing/TEST_WORKFLOW.md) - Visual testing diagrams
- [Safety Improvements](SAFETY_IMPROVEMENTS.md) - **Three critical safety problems solved**

### **Migration** - Database Transition
- [Actian Migration Guide](migration/ACTIAN_MIGRATION_GUIDE.md) - PostgreSQL → Actian Vector
- [Migration Summary](migration/MIGRATION_SUMMARY.md) - Decision guide

### **Planning** - Future Features
- [Temporal LLM Redis Plan](planning/TEMPORAL_LLM_REDIS_PLAN.md) - Redis caching architecture

### **Archived** - Historical Reference
- [Old README](archived/README_OLD.md) - Previous documentation version

---

## 🚀 Quick Start (30 seconds)

```bash
# From fastapi/ directory
make setup          # Initialize + build + start containers
make seed           # Seed safety protocols into database
make test-all       # Run all tests
```

**Next steps:** See [Quick Start Guide](guides/QUICK_START.md) for detailed setup.

---

## 🏗️ Architecture Overview

```
Jetson Nano (Edge Device)
    ↓ ZeroMQ (tcp://backend:5555)
Ingest Container (:8000, :5555)
    ├─ Reflex Path (<50ms) → WebSocket Dashboard
    └─ HTTP POST ↓
RAG Container (:8001)
    ├─ Cognition Path (<2s) → Safety Guardrails
    ↓ gRPC/SQL
Actian Vector DB (:5432 or :50051)
    └─ Safety Protocols + Incident Log
```

**Dual-Path Design:**
- **Reflex Path** (<50ms): Instant critical safety alerts
- **Cognition Path** (<2s): RAG-powered recommendations with safety validation

**Read more:** [Complete Architecture](overview/RAG.MD)

---

## 📂 Complete Directory Structure

```
docs/
├── README.md                                      ← You are here
├── NAVIGATION.md                                  ← Quick topic navigation
├── SAFETY_IMPROVEMENTS.md                         ← Critical safety features
│
├── overview/                                      📖 Architecture & Design
│   └── RAG.MD                                    Complete system architecture (58KB)
│
├── architecture/                                  🏗️ Technical Architecture
│   ├── READ_WRITE_PATH_ARCHITECTURE.md           Dual-path caching strategy
│   ├── SEMANTIC_CACHE_MIGRATION.md               Cache optimization
│   └── SPATIAL_AWARENESS_IMPLEMENTATION_PLAN.md  iPhone sensor integration
│
├── deployment/                                    🚀 Deployment Guides
│   └── VECTORAIDB_DEPLOYMENT.md                  Actian Vector DB setup
│
├── guides/                                        📘 How-To Guides
│   ├── QUICK_START.md                            2-minute fast setup
│   ├── EXECUTION_GUIDE.md                        Implementing all 5 prompts
│   └── MAKEFILE_GUIDE.md                         All make commands
│
├── setup/                                         ⚙️ Setup & Configuration
│   ├── DOCKER_SETUP.md                           Container deployment
│   └── DOCKER_README.md                          Docker architecture
│
├── reference/                                     📑 Specifications & Reference
│   ├── JETSON_SPEC.md                            Edge device interface spec
│   ├── README_PROMPTS.md                         Prompts quick reference
│   └── CLAUDE_GUIDELINES.md                      Development workflow
│
├── system_prompts/                                📋 Implementation Instructions
│   ├── PROMPT_01_AGENTS_AND_CONTRACTS.md         8 agents + Pydantic models
│   ├── PROMPT_02_ORCHESTRATOR_CORE.md            Master orchestrator
│   ├── PROMPT_03_TEST_SUITES.md                  7 test profiles
│   ├── PROMPT_04_ACTIAN_SETUP.md                 Vector DB setup
│   └── PROMPT_05_INTEGRATION_DEPLOYMENT.md       Full stack integration
│
├── testing/                                       🧪 Testing & Validation
│   └── TEST_WORKFLOW.md                          Visual test diagrams
│
├── migration/                                     🔄 Database Migration
│   ├── ACTIAN_MIGRATION_GUIDE.md                 PostgreSQL → Actian
│   └── MIGRATION_SUMMARY.md                      Decision guide
│
├── planning/                                      📅 Future Planning
│   └── TEMPORAL_LLM_REDIS_PLAN.md                Redis caching architecture
│
└── archived/                                      📦 Historical Reference
    └── README_OLD.md                             Previous documentation
```

---

## 🎯 Common Tasks

### Testing
```bash
make test-prompt01   # Test agents & contracts
make test-prompt02   # Test orchestrator core
make test-prompt03   # Test 7 test profiles
make test-prompt04   # Test Actian setup
make test-prompt05   # Test E2E integration
make test-all        # Run all tests
make test-safety     # Run safety improvement tests
```

### Database Operations
```bash
make seed            # Seed safety protocols
make db-verify       # Check schema and data
make db-reset        # Reset database
```

### Development
```bash
make logs            # View all service logs
make health          # Check service health
make shell-rag       # Open RAG container shell
make shell-ingest    # Open Ingest container shell
```

**See [Makefile Guide](guides/MAKEFILE_GUIDE.md) for complete command reference.**

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Transport** | ZeroMQ (PUB/SUB) | Jetson → Backend communication |
| **API** | FastAPI + asyncio | Async request handling |
| **WebSocket** | FastAPI WebSocket | Real-time dashboard updates |
| **Embedding** | all-MiniLM-L6-v2 | 384-dim semantic vectors |
| **Vector DB** | Actian Vector / pgvector | Hybrid vector + SQL queries |
| **Cache** | Redis | Multi-layer semantic caching |
| **Containers** | Docker Compose | 3-service topology |
| **Language** | Python 3.11+ | All backend code |

---

## 📊 System Performance Targets

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| **Reflex Path Latency** | <50ms (p95) | ~30ms | ✅ |
| **Cognition Path Latency** | <2s (p99) | ~500ms | ✅ |
| **Protocol Retrieval Precision** | ≥80% (@3) | ~85% | ✅ |
| **Cache Hit Rate** | ≥60% | ~94% | ✅ |
| **Throughput** | 10 FPS sustained | 10+ FPS | ✅ |

---

## 🧪 Comprehensive Test Coverage

- **66 safety test scenarios** (100% passing)
  - Hallucination guardrails: 34 tests
  - Sensor conflict resolution: 11 tests
  - Context drift management: 21 tests

**Run:** `make test-safety`

**Details:** [Safety Improvements](SAFETY_IMPROVEMENTS.md)

---

## 📖 Recommended Reading Paths

### **For New Developers**
1. [README.md](README.md) (this file) - 5 minutes
2. [Quick Start](guides/QUICK_START.md) - 3 minutes
3. [Complete Architecture](overview/RAG.MD) - 30 minutes
4. [Makefile Guide](guides/MAKEFILE_GUIDE.md) - 15 minutes
5. [Test Workflow](testing/TEST_WORKFLOW.md) - 10 minutes

### **For Implementation (PROMPT Order)**
1. Read [Execution Guide](guides/EXECUTION_GUIDE.md) - 10 minutes
2. Execute [PROMPT_01](system_prompts/PROMPT_01_AGENTS_AND_CONTRACTS.md) → Test
3. Execute [PROMPT_02](system_prompts/PROMPT_02_ORCHESTRATOR_CORE.md) → Test
4. Execute [PROMPT_03](system_prompts/PROMPT_03_TEST_SUITES.md) → Test
5. Execute [PROMPT_04](system_prompts/PROMPT_04_ACTIAN_SETUP.md) → Test
6. Execute [PROMPT_05](system_prompts/PROMPT_05_INTEGRATION_DEPLOYMENT.md) → Test

**Parallel execution:** See [Execution Guide](guides/EXECUTION_GUIDE.md) for faster approach.

### **For Database Migration**
1. [Migration Summary](migration/MIGRATION_SUMMARY.md) - Decision guide (10 min)
2. [VectorAI DB Deployment](deployment/VECTORAIDB_DEPLOYMENT.md) - Deployment (20 min)
3. [Actian Migration Guide](migration/ACTIAN_MIGRATION_GUIDE.md) - Step-by-step (30 min)

### **For Safety-Critical Development**
1. [Safety Improvements](SAFETY_IMPROVEMENTS.md) - Three critical problems solved
2. [Claude Guidelines](reference/CLAUDE_GUIDELINES.md) - Safety-first workflow
3. [Read/Write Path Architecture](architecture/READ_WRITE_PATH_ARCHITECTURE.md) - Performance optimization

---

## 🔐 Safety Features

**Three Critical Problems Solved:**
1. **Hallucination Guardrails** - Blocks dangerous RAG recommendations (e.g., water on grease fires)
2. **Sensor Conflict Resolution** - Thermal trump card hierarchy when visual/thermal disagree
3. **Context Drift Management** - Priority queue prevents narrative bloat

**Latency:** <5ms guardrails, no performance impact
**Test Coverage:** 66 comprehensive test scenarios

**Read more:** [Safety Improvements](SAFETY_IMPROVEMENTS.md)

---

## 🆘 Getting Help

1. **Quick commands:** `make help`
2. **Test specific prompt:** `make test-prompt0X`
3. **Check logs:** `make logs-rag` or `make logs-ingest`
4. **Verify database:** `make db-verify`
5. **Health check:** `make health`
6. **Full command guide:** [Makefile Guide](guides/MAKEFILE_GUIDE.md)
7. **Architecture questions:** [RAG.MD](overview/RAG.MD)
8. **Safety questions:** [Safety Improvements](SAFETY_IMPROVEMENTS.md)

---

## 🔗 Additional Resources

- **Original Architecture Spec:** [RAG.MD](overview/RAG.MD) (Section-by-section deep dive)
- **Jetson Interface:** [Jetson Spec](reference/JETSON_SPEC.md) (Edge device integration)
- **Implementation Prompts:** [system_prompts/](system_prompts/) (All 5 prompts)
- **Docker Architecture:** [Docker Setup](setup/DOCKER_SETUP.md) (Container details)

---

**Last Updated:** February 21, 2026
**Documentation Version:** 2.0 (Reorganized and consolidated)
**Total Documents:** 26 markdown files across 10 categories
**Status:** ✅ Production ready with comprehensive test coverage
