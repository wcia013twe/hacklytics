# System Prompts Update Summary

**Date:** February 21, 2026
**Updated By:** AI Assistant
**Reason:** RAG.MD Section 3.4 (Implementation Specifications) added detailed algorithms and data structures

---

## Changes Made

### ✅ PROMPT_01_AGENTS_AND_CONTRACTS.md - UPDATED

**Changes:**
1. **Added Context Section References** - Added comprehensive references to new RAG.MD sections:
   - Section 3.3.1: Actian SQL queries with `<->` operator
   - Section 3.4.1: TemporalBuffer implementation details
   - Section 3.4.2: Trend computation algorithm
   - Section 3.4.3: WebSocket message schemas
   - Section 3.4.4: RAG synthesis templates
   - Section 3.4.5: Batched incident writes
   - Section 3.4.6: Pre-computed scenario cache

2. **Updated TrendResult Model** - Replaced `confidence` and `buffer_size` with:
   - `sample_count`: Number of packets analyzed
   - `time_span`: Time range of buffer in seconds
   - Added docstring explaining thresholds from RAG.MD 3.4.2

3. **Complete TemporalBufferAgent Rewrite** - Replaced with production implementation from RAG.MD 3.4.1:
   - Binary search insertion for out-of-order packets
   - Proper timestamp-based eviction
   - Linear regression with exact thresholds (RAPID_GROWTH >0.10, GROWING >0.02, STABLE -0.05 to +0.02, DIMINISHING <-0.05)
   - Includes `_linear_regression_slope()` helper method
   - Added detailed validation test cases from RAG.MD Test 3

---

## Remaining Updates Needed

###  PROMPT_02_ORCHESTRATOR_CORE.md - NEEDS UPDATE

**Required Changes:**
1. Update `ReflexPublisherAgent` WebSocket message format to match RAG.MD 3.4.3 schemas:
   ```json
   {
     "type": "reflex_update",  // Add type field
     "trend": {
       "trend_tag": "...",
       "growth_rate": 0.12,
       "sample_count": 8,       // NEW
       "time_span": 9.5         // NEW
     }
   }
   ```

2. Update orchestrator to reference RAG.MD 3.4.5 for batched incident writes

3. Add reference to RAG.MD 3.4.6 for scenario cache initialization

---

### ⏳ PROMPT_03_TEST_SUITES.md - NEEDS UPDATE

**Required Changes:**
1. **Test 3 (Temporal Buffer Trend Accuracy)** - Update to use new thresholds:
   ```python
   # Old thresholds
   RAPID_GROWTH: >0.05/s
   GROWING: >0.01/s

   # New thresholds (RAG.MD 3.4.2)
   RAPID_GROWTH: >0.10/s
   GROWING: >0.02/s
   STABLE: -0.05 to +0.02/s
   DIMINISHING: <-0.05/s
   ```

2. **Test 1 (Embedding Sanity)** - Already matches RAG.MD, no changes needed

3. **Test 5 (End-to-End Latency)** - Add reference to RAG.MD 3.4.6 cache for p50 <50ms target

---

### ⏳ PROMPT_04_ACTIAN_SETUP.md - NEEDS MAJOR UPDATE

**Required Changes:**
1. **Add SQL Queries from RAG.MD 3.3.1:**
   ```sql
   -- Protocol Retrieval Query (exact from RAG.MD)
   SELECT
       protocol_text,
       source,
       severity,
       tags,
       (1 - (scenario_vector <-> $1)) AS similarity_score
   FROM safety_protocols
   WHERE severity IN ('HIGH', 'CRITICAL')
   ORDER BY scenario_vector <-> $1 ASC
   LIMIT 3;

   -- Session History Query (exact from RAG.MD)
   WITH scored_incidents AS (
       SELECT
           raw_narrative,
           trend_tag,
           hazard_level,
           fire_dominance,
           timestamp,
           (1 - (narrative_vector <-> $1)) AS similarity_score
       FROM incident_log
       WHERE session_id = $2
         AND timestamp <= $3
       ORDER BY narrative_vector <-> $1 ASC
       LIMIT 20
   )
   SELECT *
   FROM scored_incidents
   WHERE similarity_score > 0.70
   ORDER BY timestamp DESC
   LIMIT 5;
   ```

2. **Add Batched Writer Implementation** from RAG.MD 3.4.5:
   - `IncidentBatchWriter` class with 2-second flush intervals
   - AsyncIO background task for flushing
   - Safety overflow at 100 incidents

3. **Update Seeding Script** to embed protocols and note normalization requirement

---

### ⏳ PROMPT_05_INTEGRATION_DEPLOYMENT.md - NEEDS UPDATE

**Required Changes:**
1. **Add Scenario Cache Initialization** from RAG.MD 3.4.6:
   ```python
   COMMON_SCENARIOS = [
       "Fire detected, no victims visible",
       "Fire growing, person nearby",
       # ... 18 more scenarios from RAG.MD 3.4.6
   ]

   cache = ScenarioCache(embedding_model, actian_db, capacity=20)
   await cache.initialize(COMMON_SCENARIOS)
   ```

2. **Update WebSocket Schema Documentation** - Reference RAG.MD 3.4.3 for complete schemas

3. **Add Performance Validation** - Verify cache hit rate 60-70%, cache hit latency <50ms

---

## Implementation Priority

### HIGH PRIORITY (Blocks Implementation)
1. ✅ **PROMPT_01** - DONE (agents depend on correct data contracts)
2. ⏳ **PROMPT_04** - SQL queries are critical for database interaction
3. ⏳ **PROMPT_03** - Test thresholds must match implementation

### MEDIUM PRIORITY (Quality Improvements)
4. ⏳ **PROMPT_02** - WebSocket schema updates improve clarity
5. ⏳ **PROMPT_05** - Cache and batch writer are optional optimizations

---

## How to Apply Remaining Updates

### For PROMPT_02:
```bash
# Open PROMPT_02_ORCHESTRATOR_CORE.md
# Find ReflexPublisherAgent.format_reflex_message()
# Update trend dict to include sample_count and time_span
# Add reference comment: "// Schema from RAG.MD 3.4.3"
```

### For PROMPT_03:
```bash
# Open PROMPT_03_TEST_SUITES.md
# Find Test 3: Temporal Buffer Trend Accuracy
# Update growth rate thresholds to match RAG.MD 3.4.2
# Add test case validation references
```

### For PROMPT_04:
```bash
# Open PROMPT_04_ACTIAN_SETUP.md
# Add new section: "SQL Query Implementations"
# Copy queries from RAG.MD 3.3.1
# Add IncidentBatchWriter class from RAG.MD 3.4.5
# Update seeding script to normalize embeddings
```

### For PROMPT_05:
```bash
# Open PROMPT_05_INTEGRATION_DEPLOYMENT.md
# Add ScenarioCache initialization in startup section
# Copy COMMON_SCENARIOS list from RAG.MD 3.4.6
# Add cache performance validation to deployment checklist
```

---

## Verification Checklist

After all updates:

- [ ] All prompts reference correct RAG.MD sections
- [ ] Trend thresholds match across PROMPT_01 and PROMPT_03
- [ ] SQL queries match RAG.MD 3.3.1 exactly
- [ ] WebSocket schemas match RAG.MD 3.4.3
- [ ] Batch writer follows RAG.MD 3.4.5 design
- [ ] Scenario cache uses RAG.MD 3.4.6 common scenarios
- [ ] All code examples are production-ready (no placeholders)

---

## Key Improvements from RAG.MD Section 3.4

### 1. Temporal Buffer (3.4.1)
- ✅ Binary search for out-of-order packets
- ✅ Time-based (not count-based) eviction
- ✅ Lazy eviction on access
- ✅ Per-device buffer registry

### 2. Trend Computation (3.4.2)
- ✅ Linear regression (not simple delta)
- ✅ Calibrated thresholds with real-world meanings
- ✅ Minimum 2 packets and 0.5s time span
- ✅ Explicit formula implementation

### 3. WebSocket Schemas (3.4.3)
- ⏳ Complete JSON schemas with all fields
- ⏳ Message type field for routing
- ⏳ Processing time metrics

### 4. SQL Queries (3.3.1)
- ⏳ Actian-specific `<->` operator
- ⏳ Two-stage filtering for session history
- ⏳ Vector normalization requirements

### 5. Batch Writer (3.4.5)
- ⏳ AsyncIO background flush loop
- ⏳ 2-second flush intervals
- ⏳ 100-incident safety overflow
- ⏳ Graceful error handling

### 6. Scenario Cache (3.4.6)
- ⏳ LRU eviction policy
- ⏳ 20 pre-populated scenarios
- ⏳ 10x latency improvement on cache hits
- ⏳ 60-70% estimated hit rate

---

## Status Summary

| Prompt | Status | Critical? | Next Action |
|--------|--------|-----------|-------------|
| PROMPT_01 | ✅ Complete | YES | None - ready for use |
| PROMPT_02 | ⏳ Partial | NO | Update WebSocket schema |
| PROMPT_03 | ⏳ Needs update | YES | Update trend thresholds |
| PROMPT_04 | ⏳ Needs major update | YES | Add SQL queries + batch writer |
| PROMPT_05 | ⏳ Needs update | NO | Add scenario cache init |

**Estimated time to complete remaining updates:** 45-60 minutes

---

## Notes

- PROMPT_01 is production-ready and can be used immediately
- PROMPT_04 requires the most work (SQL queries + batch writer implementation)
- PROMPT_03 threshold updates are critical for Test 3 to pass
- PROMPT_02 and PROMPT_05 updates are quality improvements, not blockers
