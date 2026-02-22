# Test Workflow Diagram

## Development → Testing → Validation Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    IMPLEMENTATION PHASES                    │
└─────────────────────────────────────────────────────────────┘

PROMPT 1: Agents & Contracts
├── Implement: 8 agents + Pydantic models
├── Test: make test-prompt01
└── ✅ Pass: All agent unit tests green

        ↓

PROMPT 2: Orchestrator Core  
├── Implement: RAGOrchestrator dual-path routing
├── Test: make test-prompt02
└── ✅ Pass: Reflex + cognition paths working

        ↓

PROMPT 3: Test Suites
├── Implement: 7 test profiles
├── Test: make test-prompt03
└── ✅ Pass: All 7 profiles (embedding, protocol, trend, etc.)

        ↓

PROMPT 4: Actian Setup
├── Implement: Docker + schema + seeding
├── Test: make test-prompt04
└── ✅ Pass: DB healthy, protocols seeded, retrieval works

        ↓

PROMPT 5: Integration
├── Implement: Full pipeline (ZMQ → Actian → WebSocket)
├── Test: make test-prompt05
└── ✅ Pass: E2E latency <2s, all services healthy

        ↓

VALIDATION COMPLETE
└── Run: make test-all (validates all prompts)
```

---

## Per-Prompt Test Coverage

```
┌───────────────────────────────────────────────────────────────────┐
│ PROMPT 1: Agents & Contracts                                      │
├───────────────────────────────────────────────────────────────────┤
│ Command: make test-prompt01                                       │
│                                                                   │
│ Tests:                                                            │
│  ✓ TelemetryIngestAgent: validate_schema()                       │
│  ✓ TemporalBufferAgent: insert_packet(), evict_stale()           │
│  ✓ ReflexPublisherAgent: format_message(), broadcast()           │
│  ✓ EmbeddingAgent: embed_text() (384-dim vectors)                │
│  ✓ ProtocolRetrievalAgent: execute_vector_search()               │
│  ✓ HistoryRetrievalAgent: execute_history_search()               │
│  ✓ IncidentLoggerAgent: write_to_actian(), batch_flush()         │
│  ✓ SynthesisAgent: render_template()                             │
│  ✓ Pydantic models: TelemetryPacket, Protocol, HistoryEntry      │
│                                                                   │
│ Pass Criteria: All agents pass unit tests                         │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│ PROMPT 2: Orchestrator Core                                       │
├───────────────────────────────────────────────────────────────────┤
│ Command: make test-prompt02                                       │
│                                                                   │
│ Tests:                                                            │
│  ✓ Stage 1: Intake & validation                                  │
│  ✓ Stage 2: Reflex path (<50ms latency)                          │
│  ✓ Stage 3: Cognition path (async, fire-and-forget)              │
│  ✓ Dual-path routing (reflex always runs)                        │
│  ✓ Error handling (RAG failure doesn't block reflex)             │
│  ✓ Metrics collection (p50, p95 latency)                         │
│  ✓ Health monitoring (RAGHealth state)                           │
│                                                                   │
│ Pass Criteria: Dual-path works, graceful degradation             │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│ PROMPT 3: Test Suites (7 Profiles)                                │
├───────────────────────────────────────────────────────────────────┤
│ Command: make test-prompt03                                       │
│                                                                   │
│ Tests:                                                            │
│  1. ✓ Embedding Semantic Sanity                                  │
│      → sim(A,B) > sim(A,C) for safety-relevant semantics         │
│                                                                   │
│  2. ✓ Protocol Retrieval Precision                               │
│      → Precision@3 ≥ 80% across 10+ test narratives              │
│                                                                   │
│  3. ✓ Temporal Trend Accuracy                                    │
│      → RAPID_GROWTH: >0.10/s                                     │
│      → GROWING: >0.02/s                                          │
│      → STABLE: -0.05 to +0.02/s                                  │
│      → DIMINISHING: <-0.05/s                                     │
│                                                                   │
│  4. ✓ Incident Log Feedback Loop                                 │
│      → Packet 5 retrieves history from packets 1-4               │
│                                                                   │
│  5. ✓ E2E Latency Benchmark                                      │
│      → p50 < 500ms, p95 < 1500ms, p99 < 2000ms                   │
│                                                                   │
│  6. ✓ Graceful Degradation                                       │
│      → Reflex path continues when RAG fails                      │
│                                                                   │
│  7. ✓ Delta Filter Validation                                    │
│      → Hazard level transitions bypass delta threshold           │
│                                                                   │
│ Pass Criteria: All 7 profiles pass                               │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│ PROMPT 4: Actian Vector DB Setup                                  │
├───────────────────────────────────────────────────────────────────┤
│ Command: make test-prompt04                                       │
│                                                                   │
│ Tests:                                                            │
│  1. ✓ Container health (pg_isready)                              │
│  2. ✓ Schema verification                                        │
│      → Tables: safety_protocols, incident_log                    │
│      → Indexes: IVFFlat vector indexes, severity/session filters │
│  3. ✓ Protocol seeding                                           │
│      → Count > 0 (10+ protocols)                                 │
│  4. ✓ Vector similarity retrieval                                │
│      → Query returns top-3 protocols with similarity > 0.7       │
│                                                                   │
│ Pass Criteria: DB healthy, schema valid, protocols seeded        │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│ PROMPT 5: Integration & E2E                                       │
├───────────────────────────────────────────────────────────────────┤
│ Command: make test-prompt05                                       │
│                                                                   │
│ Tests:                                                            │
│  1. ✓ All services running                                       │
│      → actian, rag, ingest containers healthy                    │
│                                                                   │
│  2. ✓ Health checks                                              │
│      → HTTP endpoints respond (ingest:8000, rag:8001)            │
│                                                                   │
│  3. ✓ Full pipeline E2E                                          │
│      → ZMQ packet → Buffer → Embedding → Actian → WebSocket     │
│      → Reflex latency < 50ms                                     │
│      → RAG latency < 2s                                          │
│                                                                   │
│ Pass Criteria: Full pipeline works, latency targets met          │
└───────────────────────────────────────────────────────────────────┘
```

---

## Test Execution Flow

```
Developer writes code
    ↓
make test-prompt0X  ← Run prompt-specific tests
    ↓
Tests pass? ─NO→ Check logs (make logs-rag) → Fix bugs → Retry
    ↓ YES
Continue to next prompt
    ↓
All prompts complete?
    ↓ YES
make test-all  ← Validate entire system
    ↓
All tests pass? ─NO→ Debug failed prompt → Fix → Retry
    ↓ YES
✅ READY FOR DEMO
```

---

## Quick Command Reference

```bash
# Test individual prompts as you implement them
make test-prompt01  # After implementing agents
make test-prompt02  # After implementing orchestrator
make test-prompt03  # After implementing test suites
make test-prompt04  # After setting up Actian
make test-prompt05  # After full integration

# Database operations
make seed           # Seed safety protocols
make db-verify      # Check schema and data
make db-reset       # Reset database (careful!)

# Development helpers
make logs           # View all logs
make health         # Check service health
make ps             # Service status

# Full validation
make test-all       # Run all tests (prompts 1-5)
```

---

## Typical Development Session

```bash
# Morning: Start fresh
make down && make up
make health
make seed

# Implement PROMPT 1 agents
code backend/agents/telemetry_ingest.py
make test-prompt01  # Immediate feedback

# Implement PROMPT 2 orchestrator
code backend/orchestrator.py
make test-prompt02

# Debug failed test
make logs-rag
make shell-rag
python -m pytest tests/test_orchestrator.py -v -s

# Fix bug, retest
make test-prompt02  # Pass!

# End of day: Full validation
make test-all
```

---

## Continuous Integration (CI) Setup

If setting up CI (GitHub Actions, GitLab CI), use:

```yaml
# .github/workflows/test.yml
name: Test All Prompts

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Build containers
        run: make build
      
      - name: Start services
        run: make up
      
      - name: Wait for health
        run: sleep 15 && make health
      
      - name: Seed database
        run: make seed
      
      - name: Test PROMPT 1
        run: make test-prompt01
      
      - name: Test PROMPT 2
        run: make test-prompt02
      
      - name: Test PROMPT 3
        run: make test-prompt03
      
      - name: Test PROMPT 4
        run: make test-prompt04
      
      - name: Test PROMPT 5
        run: make test-prompt05
      
      - name: View logs on failure
        if: failure()
        run: make logs
```

---

**Pro Tip:** Bookmark this file for quick reference during development!
