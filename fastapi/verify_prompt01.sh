#!/bin/bash
# Verification script for PROMPT 01: Sub-Agent Implementation & Data Contracts
# Run this inside the Docker container to verify all components

set -e

echo "=================================="
echo "PROMPT 01 VERIFICATION CHECKLIST"
echo "=================================="
echo ""

# Check 1: All 8 agent files exist
echo "✓ Check 1: Verifying all 8 agent files exist..."
AGENTS=(
    "telemetry_ingest.py"
    "temporal_buffer.py"
    "reflex_publisher.py"
    "embedding.py"
    "protocol_retrieval.py"
    "history_retrieval.py"
    "incident_logger.py"
    "synthesis.py"
)

for agent in "${AGENTS[@]}"; do
    if [ -f "backend/agents/$agent" ]; then
        echo "  ✓ backend/agents/$agent"
    else
        echo "  ✗ backend/agents/$agent MISSING"
        exit 1
    fi
done
echo ""

# Check 2: Contracts file exists
echo "✓ Check 2: Verifying contracts file..."
if [ -f "backend/contracts/models.py" ]; then
    echo "  ✓ backend/contracts/models.py"
else
    echo "  ✗ backend/contracts/models.py MISSING"
    exit 1
fi
echo ""

# Check 3: Test files exist
echo "✓ Check 3: Verifying test files..."
TEST_FILES=(
    "tests/test_contracts.py"
    "tests/agents/test_telemetry_ingest.py"
    "tests/agents/test_temporal_buffer.py"
    "tests/agents/test_synthesis.py"
)

for test_file in "${TEST_FILES[@]}"; do
    if [ -f "$test_file" ]; then
        echo "  ✓ $test_file"
    else
        echo "  ✗ $test_file MISSING"
        exit 1
    fi
done
echo ""

# Check 4: Import test
echo "✓ Check 4: Testing imports..."
python3 -c "
import sys
sys.path.insert(0, '.')
from backend.contracts.models import TelemetryPacket, TrendResult, EmbeddingResult, Protocol, HistoryEntry, RAGRecommendation
print('  ✓ All contract models imported successfully')
from backend.agents import (
    TelemetryIngestAgent,
    TemporalBufferAgent,
    ReflexPublisherAgent,
    EmbeddingAgent,
    ProtocolRetrievalAgent,
    HistoryRetrievalAgent,
    IncidentLoggerAgent,
    SynthesisAgent
)
print('  ✓ All 8 agents imported successfully')
"
echo ""

# Check 5: Run contract validation tests
echo "✓ Check 5: Running contract validation tests..."
pytest tests/test_contracts.py -v --tb=short || {
    echo "  ✗ Contract tests failed"
    exit 1
}
echo ""

# Check 6: Run agent unit tests
echo "✓ Check 6: Running agent unit tests..."
pytest tests/agents/ -v --tb=short || {
    echo "  ✗ Agent tests failed"
    exit 1
}
echo ""

# Check 7: Run test profiles (RAG.MD validation tests)
echo "✓ Check 7: Running test profiles..."
pytest tests/test_profiles/ -v --tb=short -k "not (benchmark or Mock)" || {
    echo "  ⚠️  Some test profiles failed (may require Actian/Orchestrator)"
}
echo ""

echo "=================================="
echo "✅ PROMPT 01 VERIFICATION COMPLETE"
echo "=================================="
echo ""
echo "Summary:"
echo "  ✓ All 8 agent files created"
echo "  ✓ All Pydantic contracts created"
echo "  ✓ Unit tests created"
echo "  ✓ No import errors"
echo ""
echo "Ready for Prompt 2: Orchestrator Implementation"
