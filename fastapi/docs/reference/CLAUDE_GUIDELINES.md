# Claude Code Instructions

**Project:** Hacklytics Safety-Critical Fire Detection System
**Context:** RAG-based dual-path architecture (Reflex + Cognition)
**Safety Level:** CRITICAL (Life-safety system)

---

## Core Directive: Safety-First Development

This is a **life-safety system**. All changes must be:
1. **Documented** in safety improvement logs
2. **Tested** with comprehensive coverage
3. **Versioned** with appropriate git workflow
4. **Validated** for performance/latency impact

---

## Automated Logging: Performance & Safety Improvements

### When to Log to SAFETY_IMPROVEMENTS.md

**ALWAYS log these changes to `docs/SAFETY_IMPROVEMENTS.md`:**

#### 1. Performance/Latency Improvements
- [ ] Reflex path latency reduced (target: <50ms)
- [ ] Cognition path latency reduced (target: <2s)
- [ ] Embedding generation speedup
- [ ] Vector search optimization
- [ ] Database query optimization
- [ ] Context compression improvements
- [ ] Any agent processing time reduction

**Template for Performance Improvements:**
```markdown
### Performance Improvement: [Component Name]

**Date:** YYYY-MM-DD
**Component:** [Agent/Service name]
**Metric:** [What was measured]

#### Before
- Latency: Xms
- Throughput: Y ops/sec
- Resource usage: Z

#### After
- Latency: Xms (X% improvement)
- Throughput: Y ops/sec (X% improvement)
- Resource usage: Z (X% improvement)

#### Implementation
[Brief description of what changed]

#### Test Results
- Test file: `path/to/test.py`
- Tests passing: X/Y
- Performance benchmark: [results]

#### Git Reference
- Commit: `git-hash`
- Branch: `feature/perf-improvement-name` (if applicable)
```

#### 2. Guardrail/Safety Improvements
- [ ] New safety rule added
- [ ] Hazard detection enhanced
- [ ] Dangerous action blocking improved
- [ ] Sensor conflict resolution updated
- [ ] Thermal override threshold tuned
- [ ] Priority classification refined
- [ ] False positive/negative reduction

**Template for Guardrail Improvements:**
```markdown
### Guardrail Improvement: [Safety Rule Name]

**Date:** YYYY-MM-DD
**Component:** Safety Guardrails / Sensor Fusion / Priority Queue
**Safety Impact:** [CRITICAL/HIGH/MEDIUM]

#### Problem Identified
[What unsafe condition was discovered]

#### Solution
[What safety rule/logic was added/modified]

#### Test Coverage
- New test scenarios: X
- Edge cases covered: [list]
- All tests passing: ✅/❌

#### Example Scenario
**Before:** [Dangerous output example]
**After:** [Safe output example]

#### Git Reference
- Commit: `git-hash`
- Branch: `safety/rule-name` (if applicable)
```

#### 3. Context Drift/Noise Reduction
- [ ] Narrative compression improved
- [ ] Priority queue tuning
- [ ] Decay weight adjustments
- [ ] TTL optimization
- [ ] Semantic noise reduction

**Template for Context Improvements:**
```markdown
### Context Improvement: [Improvement Name]

**Date:** YYYY-MM-DD
**Component:** Temporal Buffer / Priority Queue

#### Metrics
- Narrative length: Before Xchars → After Ychars (Z% reduction)
- Compression ratio: X.XX
- Critical event retention: X%
- Noise reduction: X%

#### Impact on RAG Quality
- Retrieval precision: [improved/unchanged/degraded]
- Recommendation relevance: [qualitative assessment]

#### Git Reference
- Commit: `git-hash`
```

---

## Git Workflow: When to Branch/Commit

### Use Git Worktrees For:

**CRITICAL: Use worktrees for any safety-critical changes that might break the system.**

#### 1. Major Feature Work (ALWAYS use worktree)
```bash
# Creating a worktree for major safety feature
git worktree add ../hacklytics-safety-feature safety/new-guardrail-system
cd ../hacklytics-safety-feature
# Work in isolation, test thoroughly
# Only merge when ALL tests pass
```

**Examples requiring worktrees:**
- New safety agent implementation
- RAG retrieval algorithm changes
- Sensor fusion logic redesign
- Database schema migrations
- Multi-service integration work

#### 2. Performance Optimization (USE worktree if risky)
```bash
# If optimization might break functionality
git worktree add ../hacklytics-perf-opt perf/embedding-speedup
cd ../hacklytics-perf-opt
# Benchmark before/after, ensure no regressions
```

**When to use worktree for performance:**
- Refactoring core algorithms
- Changing concurrency patterns
- Database connection pooling changes
- Caching layer additions

**When NOT to use worktree (direct commits OK):**
- Simple query optimizations
- Adding database indexes
- Configuration tuning
- Log verbosity adjustments

#### 3. Safety Improvements (ALWAYS use worktree)
```bash
# Safety changes must be isolated and tested
git worktree add ../hacklytics-safety-fix safety/block-water-on-electrical
cd ../hacklytics-safety-fix
# Implement, test ALL scenarios, verify no regressions
```

**Safety changes requiring worktrees:**
- New guardrail rules
- Sensor conflict resolution changes
- Priority classification updates
- Thermal threshold adjustments
- Any change to hazard level logic

### Commit Frequency & Guidelines

#### Commit IMMEDIATELY After:

1. **Adding a New Safety Rule**
   ```bash
   git add backend/agents/safety_guardrails.py tests/agents/test_safety_guardrails.py
   git commit -m "feat(safety): block water on electrical fires

   - Add electrical hazard detection (power, voltage, battery, circuit)
   - Block water-based suppression on electrical fires
   - Add safe alternative: de-energize + Class C extinguisher
   - Tests: 5 new scenarios, all passing

   Safety Impact: CRITICAL - prevents electrocution
   Test Coverage: tests/agents/test_safety_guardrails.py::test_electrical_fire_water_blocked

   🤖 Generated with Claude Code
   Co-Authored-By: Claude <noreply@anthropic.com>"
   ```

2. **Performance Improvement with Benchmarks**
   ```bash
   git add backend/agents/embedding.py tests/benchmark_embedding.py
   git commit -m "perf(embedding): reduce latency by 40% with model warmup

   - Add model warmup during orchestrator startup
   - Cache tokenizer for repeat calls
   - Use half-precision on compatible hardware

   Before: 150ms avg, 250ms p95
   After: 90ms avg, 140ms p95 (40% improvement)

   Tests: tests/benchmark_embedding.py (100 iterations)

   🤖 Generated with Claude Code
   Co-Authored-By: Claude <noreply@anthropic.com>"
   ```

3. **Test Suite Additions**
   ```bash
   git add tests/agents/test_safety_guardrails.py
   git commit -m "test(safety): add 10 edge cases for compound hazards

   - Grease + electrical combination
   - Pressurized + high temperature
   - Multiple hazard types in single narrative

   Coverage: 44/44 tests passing (10 new)

   🤖 Generated with Claude Code
   Co-Authored-By: Claude <noreply@anthropic.com>"
   ```

4. **Documentation Updates**
   ```bash
   git add docs/SAFETY_IMPROVEMENTS.md
   git commit -m "docs: log guardrail improvement for gas fires

   Updated SAFETY_IMPROVEMENTS.md with new gas fire detection rule.

   🤖 Generated with Claude Code
   Co-Authored-By: Claude <noreply@anthropic.com>"
   ```

#### Commit Message Format (Safety-Critical)

```
<type>(<scope>): <subject>

<body - what changed and why>

<metrics/test results>

<safety impact - for safety changes>
<git references - for related commits>

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:**
- `feat`: New feature (safety rule, agent, etc.)
- `fix`: Bug fix (especially safety bugs)
- `perf`: Performance improvement
- `test`: Test additions/improvements
- `docs`: Documentation updates
- `refactor`: Code restructuring (no behavior change)
- `style`: Formatting changes
- `chore`: Build/tooling changes

**Scopes:**
- `safety`: Safety guardrails, sensor conflicts
- `rag`: RAG retrieval, embedding
- `orchestrator`: Dual-path coordinator
- `buffer`: Temporal buffer, priority queue
- `reflex`: Edge device reflex engine
- `db`: Database/Actian changes
- `tests`: Test infrastructure

---

## Workflow for Safety-Critical Changes

### Step-by-Step: Adding a New Safety Guardrail

```bash
# 1. Create isolated worktree
git worktree add ../hacklytics-safety-new-rule safety/new-guardrail-rule
cd ../hacklytics-safety-new-rule

# 2. Implement the rule
# Edit: backend/agents/safety_guardrails.py

# 3. Add comprehensive tests
# Edit: tests/agents/test_safety_guardrails.py

# 4. Run tests locally
python -m pytest tests/agents/test_safety_guardrails.py -v

# 5. Run full safety test suite
make test-safety

# 6. Document the improvement
# Edit: docs/SAFETY_IMPROVEMENTS.md
# Add entry using template above

# 7. Commit with detailed message
git add backend/agents/safety_guardrails.py \
        tests/agents/test_safety_guardrails.py \
        docs/SAFETY_IMPROVEMENTS.md

git commit -m "feat(safety): add radiation hazard detection

- Block manual approach to radiation sources
- Detect keywords: radioactive, radiation, nuclear, isotope
- Safe alternative: evacuate, call hazmat, use remote monitoring

Safety Impact: CRITICAL - prevents radiation exposure
Test Coverage: tests/agents/test_safety_guardrails.py::test_radiation_hazard
Tests Passing: 48/48 (4 new scenarios)

Performance: <0.01ms latency (no impact)

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# 8. Return to main worktree
cd /Users/wes/Desktop/Project/hacklytics/hacklytics/fastapi

# 9. Review the change in isolation
cd ../hacklytics-safety-new-rule
make test-safety
make test-all  # Ensure no regressions

# 10. Merge when ready (all tests pass)
git checkout main
git merge safety/new-guardrail-rule

# 11. Clean up worktree
git worktree remove ../hacklytics-safety-new-rule
```

### Step-by-Step: Performance Optimization

```bash
# 1. Benchmark current performance
make test-prompt05  # E2E latency test
# Record: Reflex: 45ms, Cognition: 1800ms

# 2. Create worktree (if risky change)
git worktree add ../hacklytics-perf-opt perf/faster-embedding
cd ../hacklytics-perf-opt

# 3. Implement optimization
# Edit: backend/agents/embedding.py

# 4. Benchmark after changes
make test-prompt05
# Record: Reflex: 45ms, Cognition: 1200ms (33% improvement)

# 5. Ensure no regressions
make test-all  # ALL tests must still pass

# 6. Document improvement
# Edit: docs/SAFETY_IMPROVEMENTS.md

# 7. Commit
git add backend/agents/embedding.py docs/SAFETY_IMPROVEMENTS.md
git commit -m "perf(rag): reduce cognition path latency by 33%

- Cache embedding model in memory
- Use batch encoding for multiple narratives
- Enable GPU acceleration on compatible hardware

Before: 1800ms avg cognition latency
After: 1200ms avg cognition latency (33% improvement)

Tests: make test-prompt05 - all passing
No regressions: make test-all - 100% passing

Logged to: docs/SAFETY_IMPROVEMENTS.md

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# 8. Merge and clean up
git checkout main
git merge perf/faster-embedding
git worktree remove ../hacklytics-perf-opt
```

---

## Automated Safety Logging Script

### When Claude Makes Safety/Performance Changes

**DIRECTIVE: After ANY of these changes, Claude MUST update `docs/SAFETY_IMPROVEMENTS.md`:**

1. Modifying `backend/agents/safety_guardrails.py`
2. Modifying `nano/reflex_engine.py` (sensor fusion logic)
3. Modifying `backend/agents/temporal_buffer.py` (priority queue)
4. Adding new safety tests
5. Performance optimization in critical path (reflex/cognition)
6. Changing thermal thresholds or hazard levels
7. Modifying priority classification logic

### Template Selection Logic

```python
# Pseudo-code for Claude's decision making
if change_type == "new_guardrail_rule":
    use_template = "Guardrail Improvement"
    section = "Problem 1: Hallucination Guardrails"

elif change_type == "sensor_fusion_update":
    use_template = "Guardrail Improvement"
    section = "Problem 2: Sensor Conflict Resolution"

elif change_type == "priority_queue_tuning":
    use_template = "Context Improvement"
    section = "Problem 3: Context Drift Management"

elif change_type == "latency_reduction":
    use_template = "Performance Improvement"
    section = "Integration Architecture > Critical Path Timing"

elif change_type == "test_coverage_increase":
    use_template = "Test Coverage Update"
    section = "Testing & Validation > Test Summary"
```

### Example: Claude Adds New Guardrail

```markdown
## Workflow

1. Claude implements new rule in `safety_guardrails.py`
2. Claude adds tests in `test_safety_guardrails.py`
3. Claude runs: `python -m pytest tests/agents/test_safety_guardrails.py`
4. **AUTOMATICALLY append to `docs/SAFETY_IMPROVEMENTS.md`:**

---

### Guardrail Improvement: Biological Hazard Detection

**Date:** 2026-02-21
**Component:** Safety Guardrails Agent
**Safety Impact:** CRITICAL

#### Problem Identified
RAG might recommend manual handling of biological hazards (infectious materials,
biohazard waste) without proper PPE or containment protocols.

#### Solution
Added biological hazard detection:
- Keywords: `biohazard`, `infectious`, `pathogen`, `contaminated`, `blood`, `medical waste`
- Blocked actions: `touch`, `handle`, `manual`, `bare hands`, `direct contact`
- Safe alternative: "Do not touch. Use full PPE (gloves, mask, gown). Call biohazard team.
  Contain area and prevent spread."

#### Test Coverage
- New test scenarios: 4
- Edge cases covered: multiple biohazards, medical context, false positives (medical personnel)
- All tests passing: ✅ 52/52

#### Example Scenario
**Before:** "Clean up medical waste from crash site."
**After:** "BLOCKED: Do not touch. Use full PPE (gloves, mask, gown). Call biohazard team.
Contain area and prevent spread."

#### Git Reference
- Commit: `abc1234`
- Branch: `safety/biological-hazard-detection`

---
```

5. Claude commits with detailed message (see format above)

---

## Pre-Deployment Checklist

Before deploying ANY safety-critical change:

- [ ] All tests passing (`make test-all`)
- [ ] Safety tests passing (`make test-safety`)
- [ ] Performance benchmarks run (if applicable)
- [ ] No latency regressions in critical path
- [ ] `docs/SAFETY_IMPROVEMENTS.md` updated
- [ ] Git commit with detailed message
- [ ] Code review completed (if team project)
- [ ] Rollback plan documented

---

## Performance Budgets (HARD LIMITS)

**DO NOT merge changes that violate these budgets:**

| Component | Budget | Monitor |
|-----------|--------|---------|
| Reflex Path (total) | <50ms | `reflex.latency_ms` |
| Edge Sensor Fusion | <5ms | Edge device timing |
| Temporal Buffer Insert | <10ms | `buffer.insert_ms` |
| Cognition Path (total) | <2s | `rag.latency_ms` |
| Embedding Generation | <150ms | `embedding.latency_ms` |
| Vector Search (Actian) | <500ms | `db.search_ms` |
| Synthesis | <100ms | `synthesis.latency_ms` |
| Safety Guardrails | <5ms | `guardrail.latency_ms` |

**If optimization EXCEEDS budget:**
1. Document the violation in commit message
2. Create issue to track technical debt
3. Add TODO in code with target budget
4. Set up monitoring alert

---

## Test Coverage Requirements

**DO NOT merge safety changes without:**

- [ ] Unit tests for new logic
- [ ] Integration tests for agent interaction
- [ ] Edge case tests (minimum 3 per rule)
- [ ] Performance regression tests
- [ ] Backward compatibility tests (existing tests still pass)

**Target Coverage:**
- Safety Guardrails: >90% line coverage
- Sensor Fusion: >85% line coverage
- Priority Queue: >80% line coverage
- Orchestrator: >75% line coverage

---

## Rollback Procedures

### If Safety Bug Discovered in Production

```bash
# 1. IMMEDIATELY revert to last known good commit
git log --oneline -20  # Find last good commit
git revert <bad-commit-hash>

# 2. Rebuild and redeploy
cd fastapi
docker compose down
docker compose build
docker compose up -d

# 3. Verify rollback
make health
make test-safety

# 4. Document the incident
# Edit: docs/INCIDENTS.md (create if not exists)

# 5. Create hotfix branch to fix issue
git worktree add ../hacklytics-hotfix hotfix/safety-bug-fix
cd ../hacklytics-hotfix
# Fix, test, merge ASAP
```

### Emergency Contacts (Update with Team Info)

- **Safety Lead:** [Name] <email>
- **On-Call Engineer:** [Name] <phone>
- **System Owner:** [Name] <email>

---

## Metrics & Monitoring

### Required Dashboards

1. **Safety Guardrails Dashboard**
   - `guardrail.blocks` (counter)
   - `guardrail.pass` (counter)
   - `guardrail.latency_ms` (histogram)
   - Block rate by hazard type

2. **Sensor Conflict Dashboard**
   - `sensor_conflict` events (time series)
   - `thermal_override_active` percentage
   - Conflict rate over time
   - Thermal readings heatmap

3. **Context Compression Dashboard**
   - `avg_narrative_length` (gauge)
   - `compression_ratio` (gauge)
   - `critical_events_retained` (gauge)

### Alert Thresholds

```yaml
alerts:
  - name: High Guardrail Block Rate
    condition: guardrail_blocks / (guardrail_blocks + guardrail_pass) > 0.5
    severity: WARNING
    action: Investigate RAG retrieval quality

  - name: Reflex Path Slow
    condition: p95(reflex.latency_ms) > 50
    severity: CRITICAL
    action: Immediate investigation, possible rollback

  - name: Cognition Path Slow
    condition: p95(rag.latency_ms) > 2000
    severity: HIGH
    action: Investigate embedding/search latency

  - name: High Sensor Conflict Rate
    condition: sensor_conflict_rate > 0.3
    severity: WARNING
    action: Check sensor calibration
```

---

## Examples of Good Commits

### Example 1: Safety Rule Addition
```
feat(safety): add confined space oxygen depletion detection

- Detect confined spaces (tank, vault, silo, tunnel, shaft)
- Block entry recommendations when oxygen < 19.5%
- Safe alternative: ventilate, test atmosphere, use SCBA

Safety Impact: CRITICAL - prevents asphyxiation
Test Coverage: tests/agents/test_safety_guardrails.py::test_confined_space
Tests Passing: 56/56 (4 new scenarios)

Performance: 0.003ms latency (no impact)

Logged to: docs/SAFETY_IMPROVEMENTS.md (Problem 1, line 234)

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

### Example 2: Performance Optimization
```
perf(db): add vector index to protocols table

- Create IVFFlat index on embedding column
- Reduces search time from 450ms to 180ms (60% improvement)
- Index build time: 3 minutes (one-time cost)

Before: 450ms avg search latency
After: 180ms avg search latency (60% improvement)

Tests: make test-prompt04 - all passing
Index creation: scripts/create_vector_index.sql

Logged to: docs/SAFETY_IMPROVEMENTS.md (Performance section)

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

### Example 3: Test Coverage Increase
```
test(safety): add 15 compound hazard scenarios

- Multi-hazard combinations (grease+electrical, gas+pressurized)
- Ambiguous language variants
- False positive prevention tests

Coverage increase: 44 tests -> 59 tests (34% increase)
All passing: ✅ 59/59

Logged to: docs/SAFETY_IMPROVEMENTS.md (Test Summary)

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Quick Reference Commands

```bash
# Run all safety tests
make test-safety

# Run all tests (full validation)
make test-all

# Check service health
make health

# View logs
make logs-rag
make logs-ingest

# Create worktree for safety work
git worktree add ../hacklytics-safety-<feature> safety/<feature-name>

# Create worktree for performance work
git worktree add ../hacklytics-perf-<feature> perf/<feature-name>

# List all worktrees
git worktree list

# Remove completed worktree
git worktree remove ../hacklytics-<feature>

# Check performance budgets
make test-prompt05  # E2E latency benchmark
```

---

## When to Ask for Human Review

**ALWAYS ask for review before merging:**

1. Changes to sensor fusion logic (thermal override thresholds)
2. New hazard types added to guardrails
3. Priority queue algorithm changes
4. Database schema migrations
5. Performance optimizations that change core algorithms
6. Any change that causes test failures
7. Any change that violates performance budgets

**Can merge without review (but still commit properly):**

1. Documentation updates
2. Test additions (no code changes)
3. Log message improvements
4. Configuration tuning (within documented ranges)
5. Minor refactoring (no behavior change, all tests pass)

---

## Summary: The Three Rules

### Rule 1: Log All Safety/Performance Changes
Every guardrail, latency improvement, or safety fix → `docs/SAFETY_IMPROVEMENTS.md`

### Rule 2: Use Worktrees for Risky Changes
Safety features, major performance work, sensor logic → isolated worktree

### Rule 3: Commit Early, Commit Often
After every logical unit of work, with detailed messages

---

**Last Updated:** 2026-02-21
**System Version:** v1.0 (Initial Safety Improvements)
**Next Review:** After 100 runtime hours or first incident
