# Documentation Navigation Guide

**Quick reference for finding the right documentation in the reorganized structure**

---

## 🎯 What Do You Need? (Quick Jumps)

| I want to... | Go to... | Time |
|--------------|----------|------|
| **Get started FAST** | [Quick Start](guides/QUICK_START.md) | 2 min |
| **Understand the architecture** | [RAG.MD](overview/RAG.MD) | 30 min |
| **Run commands** | [Makefile Guide](guides/MAKEFILE_GUIDE.md) | 15 min |
| **Deploy with Docker** | [Docker Setup](setup/DOCKER_SETUP.md) | 20 min |
| **Migrate to Actian** | [VectorAI DB Deployment](deployment/VECTORAIDB_DEPLOYMENT.md) | 25 min |
| **Implement all 5 prompts** | [Execution Guide](guides/EXECUTION_GUIDE.md) | 10 min |
| **Understand safety features** | [Safety Improvements](SAFETY_IMPROVEMENTS.md) | 20 min |
| **See Jetson interface** | [Jetson Spec](reference/JETSON_SPEC.md) | 10 min |
| **Learn caching strategy** | [Read/Write Path Architecture](architecture/READ_WRITE_PATH_ARCHITECTURE.md) | 15 min |
| **Test the system** | [Test Workflow](testing/TEST_WORKFLOW.md) | 10 min |

---

## 📁 Complete Directory Structure

```
docs/
├── README.md                           ← Start here (master index)
├── NAVIGATION.md                       ← This file (quick navigation)
├── SAFETY_IMPROVEMENTS.md              ← Critical safety features
│
├── architecture/                       🏗️ Technical Architecture
│   ├── READ_WRITE_PATH_ARCHITECTURE.md
│   ├── SEMANTIC_CACHE_MIGRATION.md
│   └── SPATIAL_AWARENESS_IMPLEMENTATION_PLAN.md
│
├── deployment/                         🚀 Deployment & Setup
│   └── VECTORAIDB_DEPLOYMENT.md
│
├── guides/                             📘 Step-by-Step Guides
│   ├── QUICK_START.md
│   ├── EXECUTION_GUIDE.md
│   └── MAKEFILE_GUIDE.md
│
├── setup/                              ⚙️ Configuration
│   ├── DOCKER_SETUP.md
│   └── DOCKER_README.md
│
├── reference/                          📑 Specifications
│   ├── JETSON_SPEC.md
│   ├── README_PROMPTS.md
│   └── CLAUDE_GUIDELINES.md
│
├── overview/                           📖 System Overview
│   └── RAG.MD
│
├── system_prompts/                     📋 Implementation Instructions
│   ├── PROMPT_01_AGENTS_AND_CONTRACTS.md
│   ├── PROMPT_02_ORCHESTRATOR_CORE.md
│   ├── PROMPT_03_TEST_SUITES.md
│   ├── PROMPT_04_ACTIAN_SETUP.md
│   └── PROMPT_05_INTEGRATION_DEPLOYMENT.md
│
├── testing/                            🧪 Testing
│   └── TEST_WORKFLOW.md
│
├── migration/                          🔄 Database Migration
│   ├── ACTIAN_MIGRATION_GUIDE.md
│   └── MIGRATION_SUMMARY.md
│
├── planning/                           📅 Future Features
│   └── TEMPORAL_LLM_REDIS_PLAN.md
│
└── archived/                           📦 Historical Reference
    └── README_OLD.md
```

---

## 🔍 Find Documentation By Topic

### Architecture & Design

| Topic | Document | Description |
|-------|----------|-------------|
| **Complete System Architecture** | [RAG.MD](overview/RAG.MD) | 58KB comprehensive guide |
| **Dual-Path Caching** | [Read/Write Path](architecture/READ_WRITE_PATH_ARCHITECTURE.md) | READ path (fast) vs WRITE path (background) |
| **Cache Optimization** | [Semantic Cache Migration](architecture/SEMANTIC_CACHE_MIGRATION.md) | Vector → semantic bucket migration (46% code reduction) |
| **Spatial Features** | [Spatial Awareness Plan](architecture/SPATIAL_AWARENESS_IMPLEMENTATION_PLAN.md) | iPhone IMU/ARKit/LiDAR integration |

### Deployment & Setup

| Topic | Document | Description |
|-------|----------|-------------|
| **VectorAI DB Deployment** | [VectorAI DB](deployment/VECTORAIDB_DEPLOYMENT.md) | Actian Vector database setup |
| **Docker Deployment** | [Docker Setup](setup/DOCKER_SETUP.md) | Container orchestration guide |
| **Docker Architecture** | [Docker README](setup/DOCKER_README.md) | 3-service topology details |

### Guides & How-Tos

| Topic | Document | Description |
|-------|----------|-------------|
| **Fast Setup** | [Quick Start](guides/QUICK_START.md) | 2-minute getting started |
| **Implementation Guide** | [Execution Guide](guides/EXECUTION_GUIDE.md) | How to execute all 5 prompts |
| **Command Reference** | [Makefile Guide](guides/MAKEFILE_GUIDE.md) | All `make` commands |

### Reference Materials

| Topic | Document | Description |
|-------|----------|-------------|
| **Edge Device Interface** | [Jetson Spec](reference/JETSON_SPEC.md) | ZeroMQ packet format & heuristics |
| **Prompt Overview** | [README Prompts](reference/README_PROMPTS.md) | Quick reference for all 5 prompts |
| **Development Guidelines** | [Claude Guidelines](reference/CLAUDE_GUIDELINES.md) | Safety-first development workflow |

### System Prompts (Implementation)

| Prompt | Document | What It Builds |
|--------|----------|----------------|
| **PROMPT_01** | [Agents & Contracts](system_prompts/PROMPT_01_AGENTS_AND_CONTRACTS.md) | 8 agents + Pydantic models |
| **PROMPT_02** | [Orchestrator Core](system_prompts/PROMPT_02_ORCHESTRATOR_CORE.md) | Master orchestrator + FastAPI |
| **PROMPT_03** | [Test Suites](system_prompts/PROMPT_03_TEST_SUITES.md) | 7 test profiles |
| **PROMPT_04** | [Actian Setup](system_prompts/PROMPT_04_ACTIAN_SETUP.md) | Vector DB + schema |
| **PROMPT_05** | [Integration](system_prompts/PROMPT_05_INTEGRATION_DEPLOYMENT.md) | Full stack E2E |

### Testing & Validation

| Topic | Document | Description |
|-------|----------|-------------|
| **Test Workflow** | [Test Workflow](testing/TEST_WORKFLOW.md) | Visual testing diagrams |
| **Safety Features** | [Safety Improvements](SAFETY_IMPROVEMENTS.md) | 3 critical problems solved (66 tests) |

### Database Migration

| Topic | Document | Description |
|-------|----------|-------------|
| **Migration Decision** | [Migration Summary](migration/MIGRATION_SUMMARY.md) | Actian vs PostgreSQL comparison |
| **Migration Steps** | [Actian Migration Guide](migration/ACTIAN_MIGRATION_GUIDE.md) | PostgreSQL → Actian Vector |

---

## 🚀 Recommended Reading Paths

### **New to the Project?**
```
1. README.md (5 min)                   ← Overview & quick links
2. Quick Start (3 min)                 ← Get hands-on
3. RAG.MD (30 min)                     ← Deep architecture understanding
4. Makefile Guide (15 min)             ← Command reference
5. Test Workflow (10 min)              ← Testing approach
```

### **Ready to Implement?**
```
1. Execution Guide (10 min)            ← Implementation strategy
2. PROMPT_01 → test (45 min)          ← Build agents
3. PROMPT_02 → test (40 min)          ← Build orchestrator
4. PROMPT_03 → test (30 min)          ← Build tests
5. PROMPT_04 → test (20 min)          ← Setup database
6. PROMPT_05 → test (30 min)          ← E2E integration
```

### **Need to Deploy?**
```
1. Docker Setup (20 min)               ← Container architecture
2. VectorAI DB Deployment (25 min)     ← Database setup
3. Quick Start (3 min)                 ← Verify deployment
```

### **Working on Safety Features?**
```
1. Safety Improvements (20 min)        ← 3 critical problems
2. Claude Guidelines (15 min)          ← Safety-first workflow
3. Read/Write Path Architecture (15 min) ← Performance patterns
```

### **Migrating Database?**
```
1. Migration Summary (10 min)          ← Decision guide
2. VectorAI DB Deployment (25 min)     ← Actian setup
3. Actian Migration Guide (30 min)     ← Migration steps
```

---

## 📊 Documentation by Size (Reading Time)

| Size | Reading Time | Document |
|------|-------------|----------|
| **58KB** | 30-45 min | [RAG.MD](overview/RAG.MD) |
| **Large** | 20-30 min | [VectorAI DB Deployment](deployment/VECTORAIDB_DEPLOYMENT.md) |
| **Large** | 20-30 min | [Safety Improvements](SAFETY_IMPROVEMENTS.md) |
| **Medium** | 15-20 min | [Actian Migration Guide](migration/ACTIAN_MIGRATION_GUIDE.md) |
| **Medium** | 15-20 min | [Spatial Awareness Plan](architecture/SPATIAL_AWARENESS_IMPLEMENTATION_PLAN.md) |
| **Medium** | 15-20 min | [Read/Write Path Architecture](architecture/READ_WRITE_PATH_ARCHITECTURE.md) |
| **Medium** | 10-15 min | [Makefile Guide](guides/MAKEFILE_GUIDE.md) |
| **Medium** | 10-15 min | [Execution Guide](guides/EXECUTION_GUIDE.md) |
| **Small** | 5-10 min | [Quick Start](guides/QUICK_START.md) |
| **Small** | 5-10 min | [Test Workflow](testing/TEST_WORKFLOW.md) |

---

## 🎨 Documentation Categories

### 🏗️ **Architecture** (Technical Design)
- System design decisions
- Performance optimizations
- Future features planning

### 🚀 **Deployment** (Getting It Running)
- Database setup
- Container orchestration
- Production deployment

### 📘 **Guides** (Step-by-Step)
- Quick start instructions
- Implementation workflows
- Command references

### ⚙️ **Setup** (Configuration)
- Docker configuration
- Environment setup
- Service topology

### 📑 **Reference** (Specifications)
- API specifications
- Interface contracts
- Development guidelines

### 📖 **Overview** (Understanding)
- Complete architecture
- System design philosophy
- Component interactions

### 📋 **System Prompts** (Implementation)
- Executable instructions
- Component implementation
- Integration guides

### 🧪 **Testing** (Validation)
- Test workflows
- Safety validation
- Performance benchmarks

### 🔄 **Migration** (Database Transition)
- Migration guides
- Decision matrices
- Step-by-step procedures

---

## 💡 Pro Tips

1. **Start with README.md** - Best overview and navigation hub
2. **Bookmark this file** - Quick topic lookups
3. **Use Quick Start** - Get hands-on experience immediately
4. **Read RAG.MD section-by-section** - Don't try to absorb all 58KB at once
5. **Keep Makefile Guide open** - Reference during development
6. **Follow PROMPT order** - Dependencies exist (01 → 02 → 03 → 04 → 05)
7. **Check Safety Improvements** - Understand critical safety patterns
8. **Test after each PROMPT** - Use `make test-promptXX` to verify

---

## 🔗 External References

- **Main README:** [README.md](README.md)
- **GitHub Issues:** [Report bugs/issues here]
- **Tech Stack Details:** See [README.md](README.md) Tech Stack section
- **Performance Targets:** See [README.md](README.md) System Performance section

---

## 📦 What's Archived?

The `archived/` directory contains:
- **README_OLD.md** - Previous documentation version (before reorganization)

These are kept for historical reference but are no longer maintained.

---

**Last Updated:** February 21, 2026
**Documentation Version:** 2.0 (Reorganized structure)
**Total Active Documents:** 25 markdown files
**Organization:** Categorized by function for easy navigation
**Status:** ✅ Complete and up-to-date
