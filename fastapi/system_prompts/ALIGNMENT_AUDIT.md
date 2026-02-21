# System Prompts vs RAG.MD Alignment Audit

**Date:** February 21, 2026
**Purpose:** Identify and fix all misalignments between system prompts and RAG.MD specification

---

## Critical Misalignments Found

### 🔴 PROMPT_01: AGENTS_AND_CONTRACTS.md
**Status:** PARTIALLY ALIGNED (TemporalBuffer updated, others need review)

| Issue | Current State | RAG.MD Spec | Priority |
|-------|---------------|-------------|----------|
| ✅ TrendResult model | Updated with sample_count, time_span | Matches 3.4.2 | DONE |
| ✅ TemporalBufferAgent | Complete rewrite with linear regression | Matches 3.4.1, 3.4.2 | DONE |
| ⚠️ ReflexPublisherAgent | Missing `type` field in message | Should have `type: "reflex_update"` per 3.4.3 | MEDIUM |
| ⚠️ ProtocolRetrievalAgent | Uses `<=>` operator | Should use `<->` operator per 3.3.1 | HIGH |
| ⚠️ HistoryRetrievalAgent | Simple query | Should use two-stage query per 3.3.1 | HIGH |
| ⚠️ IncidentLoggerAgent | Basic batch logic | Should match 3.4.5 exactly (AsyncIO loop, 2s interval) | MEDIUM |
| ❌ SynthesisAgent | Missing trend integration | Should use template from 3.4.4 | MEDIUM |

---

### 🔴 PROMPT_02: ORCHESTRATOR_CORE.md
**Status:** NEEDS MAJOR UPDATE

| Issue | Current State | RAG.MD Spec | Priority |
|-------|---------------|-------------|----------|
| ❌ WebSocket message format | Missing complete schema | Should match 3.4.3 exactly | HIGH |
| ❌ Trend fields | Uses old confidence field | Should use sample_count, time_span per 3.4.2 | HIGH |
| ❌ RAG response schema | Incomplete | Should include protocols array, history array per 3.4.3 | HIGH |
| ⚠️ No scenario cache mention | Not referenced | Should initialize ScenarioCache per 3.4.6 | MEDIUM |
| ⚠️ No batch writer mention | Not referenced | Should use IncidentBatchWriter per 3.4.5 | MEDIUM |

---

### 🔴 PROMPT_03: TEST_SUITES.md
**Status:** NEEDS UPDATE

| Issue | Current State | RAG.MD Spec | Priority |
|-------|---------------|-------------|----------|
| ❌ Test 3 trend thresholds | Old thresholds (0.05, 0.01) | Should use 0.10, 0.02, -0.05 per 3.4.2 | CRITICAL |
| ⚠️ Test 3 validation | Uses confidence | Should validate sample_count, time_span | HIGH |
| ⚠️ TrendResult assertions | Checks buffer_size | Should check sample_count, time_span | HIGH |
| ✅ Test 1 embedding | Correct | Matches RAG.MD Test 1 | DONE |

---

### 🔴 PROMPT_04: ACTIAN_SETUP.md
**Status:** NEEDS MAJOR UPDATE

| Issue | Current State | RAG.MD Spec | Priority |
|-------|---------------|-------------|----------|
| ❌ SQL queries missing | No implementation queries | Should include 3.3.1 queries exactly | CRITICAL |
| ❌ Batch writer missing | Not included | Should have IncidentBatchWriter class per 3.4.5 | HIGH |
| ❌ Vector normalization | Not mentioned | Must normalize embeddings for L2 distance per 3.3.1 | CRITICAL |
| ⚠️ Operator mismatch | Uses `<=>` | Should use `<->` for L2 distance per 3.3.1 | CRITICAL |
| ⚠️ Seeding script | Basic embed | Should normalize vectors before insert | HIGH |

---

### 🔴 PROMPT_05: INTEGRATION_DEPLOYMENT.md
**Status:** NOT REVIEWED YET

| Issue | Priority |
|-------|----------|
| WebSocket schemas | HIGH |
| Scenario cache initialization | MEDIUM |
| Batch writer startup | MEDIUM |
| Performance validation | MEDIUM |

---

## RAG.MD Key Sections Reference

### Section 3.3.1: Actian SQL Implementation
**Critical Details:**
- Uses `<->` operator for L2 distance (NOT `<=>`)
- Computes similarity as `1 - (vector1 <-> vector2)`
- Vectors MUST be normalized to unit length
- Protocol query: filters by severity IN ('HIGH', 'CRITICAL'), ORDER BY distance ASC, LIMIT 3
- History query: two-stage with CTE, filters by session_id and timestamp <= current

### Section 3.4.1: Temporal Buffer
**Critical Details:**
- Deque data structure
- Binary search insertion for out-of-order packets
- Lazy eviction on access (not background timer)
- Time-based window (10 seconds, not count-based)

### Section 3.4.2: Trend Computation
**Critical Thresholds:**
```
RAPID_GROWTH: > 0.10/s
GROWING: > 0.02/s
STABLE: -0.05 to +0.02/s
DIMINISHING: < -0.05/s
UNKNOWN: < 2 packets or < 0.5s time span
```

**Algorithm:**
- Linear regression (not simple delta)
- Returns: trend_tag, growth_rate, sample_count, time_span

### Section 3.4.3: WebSocket Schemas
**Reflex Update:**
```json
{
  "type": "reflex_update",
  "device_id": "...",
  "timestamp": 1708549201.45,
  "hazard_level": "CRITICAL",
  "scores": {...},
  "trend": {
    "trend_tag": "RAPID_GROWTH",
    "growth_rate": 0.12,
    "sample_count": 8,
    "time_span": 9.5
  }
}
```

**RAG Recommendation:**
```json
{
  "type": "rag_recommendation",
  "device_id": "...",
  "timestamp": 1708549201.45,
  "protocols": [{...}, {...}],
  "session_history": [{...}, {...}],
  "recommendation": "...",
  "processing_time_ms": 680
}
```

### Section 3.4.4: RAG Synthesis Template
**V1 Template Structure:**
1. Alert header (trend-aware)
2. Top protocol text
3. Historical context (if available)
4. Truncate to 500 chars

### Section 3.4.5: Batched Incident Writes
**Critical Details:**
- AsyncIO background task with `asyncio.create_task()`
- 2-second flush interval
- Safety overflow at 100 incidents
- Graceful shutdown flushes remaining

### Section 3.4.6: Pre-Computed Scenario Cache
**Critical Details:**
- LRU eviction
- 20 pre-populated scenarios from COMMON_SCENARIOS list
- Cache hit: <50ms latency
- Estimated 60-70% hit rate

---

## Fix Priority Order

### PHASE 1: CRITICAL FIXES (Blocks basic functionality)
1. ✅ PROMPT_01: TrendResult model → DONE
2. ✅ PROMPT_01: TemporalBufferAgent → DONE
3. ⏳ PROMPT_04: SQL queries with correct `<->` operator
4. ⏳ PROMPT_04: Vector normalization in seeding
5. ⏳ PROMPT_03: Test 3 trend thresholds

### PHASE 2: HIGH PRIORITY (Quality & correctness)
6. ⏳ PROMPT_01: ProtocolRetrievalAgent SQL
7. ⏳ PROMPT_01: HistoryRetrievalAgent SQL
8. ⏳ PROMPT_02: WebSocket message schemas
9. ⏳ PROMPT_03: TrendResult validation updates

### PHASE 3: MEDIUM PRIORITY (Optimizations)
10. ⏳ PROMPT_01: IncidentLoggerAgent batch writer
11. ⏳ PROMPT_01: SynthesisAgent template
12. ⏳ PROMPT_02: Scenario cache initialization
13. ⏳ PROMPT_05: Cache and batch writer deployment

---

## Validation Checklist

After all fixes:

- [ ] All SQL queries use `<->` operator (not `<=>`)
- [ ] All SQL queries match RAG.MD 3.3.1 exactly
- [ ] All trend thresholds match RAG.MD 3.4.2 (0.10, 0.02, -0.05)
- [ ] TrendResult model matches everywhere (sample_count, time_span)
- [ ] WebSocket schemas match RAG.MD 3.4.3 (type field, complete schemas)
- [ ] Batch writer matches RAG.MD 3.4.5 (AsyncIO, 2s interval)
- [ ] Synthesis template matches RAG.MD 3.4.4
- [ ] Vector normalization mentioned in seeding script
- [ ] Scenario cache matches RAG.MD 3.4.6 (LRU, 20 scenarios)
- [ ] All code examples are production-ready (no TODO placeholders)

---

## Next Steps

1. Execute PHASE 1 fixes (critical)
2. Execute PHASE 2 fixes (high priority)
3. Execute PHASE 3 fixes (medium priority)
4. Run validation checklist
5. Test all prompts for coherence and actionability
