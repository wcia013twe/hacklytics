# Documentation Navigation Guide

Quick reference for finding the right documentation.

---

## 🎯 What Do You Need?

### "I need to get started FAST"
→ [guides/QUICK_START.md](guides/QUICK_START.md) (2-minute setup)

### "I need to understand the architecture"
→ [overview/RAG.MD](overview/RAG.MD) (Complete 58KB doc)

### "I need to know what commands to run"
→ [guides/MAKEFILE_GUIDE.md](guides/MAKEFILE_GUIDE.md) (All `make` commands)

### "I need to deploy with Docker"
→ [setup/DOCKER_SETUP.md](setup/DOCKER_SETUP.md)

### "I need to test my code"
→ [testing/TEST_WORKFLOW.md](testing/TEST_WORKFLOW.md) (Visual diagrams)

### "I need to migrate to Actian VectorAI DB"
→ [migration/ACTIAN_MIGRATION_GUIDE.md](migration/ACTIAN_MIGRATION_GUIDE.md) (Step-by-step)

### "I need to decide: Actian or PostgreSQL?"
→ [migration/MIGRATION_SUMMARY.md](migration/MIGRATION_SUMMARY.md) (Decision guide)

### "I need to implement PROMPT 1-5"
→ [system_prompts/](system_prompts/) directory

---

## 📁 Directory Structure

```
docs/
├── README.md                         ← Central index (start here)
├── NAVIGATION.md                     ← This file
│
├── overview/                         📖 Architecture & Design
│   └── RAG.MD                        Complete system architecture
│
├── guides/                           🔧 How-To Guides
│   ├── QUICK_START.md                2-minute setup
│   └── MAKEFILE_GUIDE.md             Command reference
│
├── setup/                            🚀 Deployment
│   ├── DOCKER_SETUP.md               Container deployment
│   └── DOCKER_README.md              Docker overview
│
├── testing/                          🧪 Testing & Validation
│   └── TEST_WORKFLOW.md              Visual test diagrams
│
├── migration/                        🔄 Database Migration
│   ├── ACTIAN_MIGRATION_GUIDE.md     PostgreSQL → Actian
│   └── MIGRATION_SUMMARY.md          Decision guide
│
└── system_prompts/                   📋 Implementation Guides
    ├── PROMPT_01_*.md                Agents & Contracts
    ├── PROMPT_02_*.md                Orchestrator Core
    ├── PROMPT_03_*.md                Test Suites
    ├── PROMPT_04_*.md                Actian Setup
    └── PROMPT_05_*.md                Integration & E2E
```

---

## 🔍 Finding Information

### By Topic

| Topic | File |
|-------|------|
| **Architecture** | [overview/RAG.MD](overview/RAG.MD) |
| **Quick Setup** | [guides/QUICK_START.md](guides/QUICK_START.md) |
| **Commands** | [guides/MAKEFILE_GUIDE.md](guides/MAKEFILE_GUIDE.md) |
| **Docker** | [setup/DOCKER_SETUP.md](setup/DOCKER_SETUP.md) |
| **Testing** | [testing/TEST_WORKFLOW.md](testing/TEST_WORKFLOW.md) |
| **Migration** | [migration/MIGRATION_SUMMARY.md](migration/MIGRATION_SUMMARY.md) |
| **PROMPT 1** | [system_prompts/PROMPT_01_*.md](system_prompts/PROMPT_01_AGENTS_AND_CONTRACTS.md) |
| **PROMPT 2** | [system_prompts/PROMPT_02_*.md](system_prompts/PROMPT_02_ORCHESTRATOR_CORE.md) |
| **PROMPT 3** | [system_prompts/PROMPT_03_*.md](system_prompts/PROMPT_03_TEST_SUITES.md) |
| **PROMPT 4** | [system_prompts/PROMPT_04_*.md](system_prompts/PROMPT_04_ACTIAN_SETUP.md) |
| **PROMPT 5** | [system_prompts/PROMPT_05_*.md](system_prompts/PROMPT_05_INTEGRATION_DEPLOYMENT.md) |

### By File Size

| Size | File | Purpose |
|------|------|---------|
| 58KB | [overview/RAG.MD](overview/RAG.MD) | Comprehensive architecture |
| 15KB | [migration/ACTIAN_MIGRATION_GUIDE.md](migration/ACTIAN_MIGRATION_GUIDE.md) | Migration steps |
| 10KB | [guides/MAKEFILE_GUIDE.md](guides/MAKEFILE_GUIDE.md) | Command reference |
| 8KB | [testing/TEST_WORKFLOW.md](testing/TEST_WORKFLOW.md) | Test diagrams |
| 6KB | [migration/MIGRATION_SUMMARY.md](migration/MIGRATION_SUMMARY.md) | Decision guide |
| 4KB | [guides/QUICK_START.md](guides/QUICK_START.md) | Fast setup |

**Read time:**
- Quick start: 2-3 minutes
- Command guide: 10-15 minutes
- Architecture: 30-45 minutes

---

## 🚀 Recommended Reading Order

### For New Developers

1. **[README.md](README.md)** (5 min) - Overview
2. **[guides/QUICK_START.md](guides/QUICK_START.md)** (3 min) - Setup
3. **[overview/RAG.MD](overview/RAG.MD)** (30 min) - Deep dive
4. **[guides/MAKEFILE_GUIDE.md](guides/MAKEFILE_GUIDE.md)** (15 min) - Commands
5. **[testing/TEST_WORKFLOW.md](testing/TEST_WORKFLOW.md)** (10 min) - Testing

### For Implementation (PROMPT Order)

1. **[system_prompts/PROMPT_01_*.md](system_prompts/PROMPT_01_AGENTS_AND_CONTRACTS.md)** - Agents
2. **[system_prompts/PROMPT_02_*.md](system_prompts/PROMPT_02_ORCHESTRATOR_CORE.md)** - Orchestrator
3. **[system_prompts/PROMPT_03_*.md](system_prompts/PROMPT_03_TEST_SUITES.md)** - Tests
4. **[system_prompts/PROMPT_04_*.md](system_prompts/PROMPT_04_ACTIAN_SETUP.md)** - Database
5. **[system_prompts/PROMPT_05_*.md](system_prompts/PROMPT_05_INTEGRATION_DEPLOYMENT.md)** - Integration

Test after each: `make test-prompt01`, `make test-prompt02`, etc.

### For Database Migration

1. **[migration/MIGRATION_SUMMARY.md](migration/MIGRATION_SUMMARY.md)** (10 min) - Decision
2. **[migration/ACTIAN_MIGRATION_GUIDE.md](migration/ACTIAN_MIGRATION_GUIDE.md)** (30 min) - Steps
3. **[system_prompts/PROMPT_04_*.md](system_prompts/PROMPT_04_ACTIAN_SETUP.md)** (20 min) - Setup

---

## 💡 Pro Tips

1. **Bookmark this file** for quick navigation
2. **Start with QUICK_START** to get hands-on immediately
3. **Read RAG.MD section-by-section** as you implement features
4. **Keep MAKEFILE_GUIDE open** while developing
5. **Follow PROMPT order** (01 → 02 → 03 → 04 → 05)

---

## 🔗 External Links

- **GitHub Issues:** [Report bugs here]
- **Architecture Diagram:** See [overview/RAG.MD](overview/RAG.MD) Section 2.1
- **Tech Stack:** See [README.md](README.md)

---

**Last Updated:** February 21, 2026
**Organization:** Logical categorization by purpose
**Total Docs:** 13 markdown files
