#!/bin/bash
# Test Runner for Dockerized RAG System
# Based on PROMPT_03_TEST_SUITES.md

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  Hacklytics RAG System - Test Suite Runner"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Parse command line arguments
TEST_PROFILE="${1:-all}"
VERBOSE="${2:--v}"

case $TEST_PROFILE in
  1|embedding)
    echo "🧪 Running Test 1: Embedding Semantic Sanity"
    docker compose --profile test run --rm test pytest tests/test_profiles/test_01_embedding_sanity.py $VERBOSE -s
    ;;
  2|protocol)
    echo "🧪 Running Test 2: Protocol Retrieval Precision"
    docker compose --profile test run --rm test pytest tests/test_profiles/test_02_protocol_precision.py $VERBOSE -s
    ;;
  3|trend)
    echo "🧪 Running Test 3: Temporal Trend Accuracy"
    docker compose --profile test run --rm test pytest tests/test_profiles/test_03_trend_accuracy.py $VERBOSE -s
    ;;
  4|feedback)
    echo "🧪 Running Test 4: Incident Log Temporal Feedback"
    docker compose --profile test run --rm test pytest tests/test_profiles/test_04_temporal_feedback.py $VERBOSE -s
    ;;
  5|latency)
    echo "🧪 Running Test 5: End-to-End Latency Benchmark"
    docker compose --profile test run --rm test pytest tests/test_profiles/test_05_latency_benchmark.py $VERBOSE -s
    ;;
  6|degradation)
    echo "🧪 Running Test 6: Graceful Degradation"
    docker compose --profile test run --rm test pytest tests/test_profiles/test_06_graceful_degradation.py $VERBOSE -s
    ;;
  7|delta)
    echo "🧪 Running Test 7: Delta Filter Validation"
    docker compose --profile test run --rm test pytest tests/test_profiles/test_07_delta_filter.py $VERBOSE -s
    ;;
  all)
    echo "🧪 Running All Test Profiles (1-7)"
    docker compose --profile test run --rm test pytest tests/test_profiles/ $VERBOSE -s
    ;;
  ready)
    echo "🧪 Running Ready Tests Only (no Actian/Orchestrator dependencies)"
    echo "   - Test 1: Embedding Semantic Sanity"
    echo "   - Test 3: Temporal Trend Accuracy"
    echo "   - Test 7: Delta Filter Validation"
    docker compose --profile test run --rm test pytest \
      tests/test_profiles/test_01_embedding_sanity.py \
      tests/test_profiles/test_03_trend_accuracy.py \
      tests/test_profiles/test_07_delta_filter.py \
      $VERBOSE -s
    ;;
  mock)
    echo "🧪 Running Mock Tests Only (placeholder implementations)"
    echo "   - Test 2: Protocol Retrieval Precision (mock)"
    echo "   - Test 4: Temporal Feedback (mock)"
    echo "   - Test 5: Latency Benchmark (mock)"
    echo "   - Test 6: Graceful Degradation (mock)"
    docker compose --profile test run --rm test pytest \
      tests/test_profiles/test_02_protocol_precision.py::test_protocol_retrieval_mock \
      tests/test_profiles/test_04_temporal_feedback.py::test_temporal_feedback_mock \
      tests/test_profiles/test_05_latency_benchmark.py::test_latency_benchmark_mock \
      tests/test_profiles/test_06_graceful_degradation.py::test_graceful_degradation_mock \
      $VERBOSE -s
    ;;
  *)
    echo "Usage: ./run_tests.sh [TEST_PROFILE] [PYTEST_FLAGS]"
    echo ""
    echo "TEST_PROFILE options:"
    echo "  1, embedding     - Test 1: Embedding Semantic Sanity"
    echo "  2, protocol      - Test 2: Protocol Retrieval Precision"
    echo "  3, trend         - Test 3: Temporal Trend Accuracy"
    echo "  4, feedback      - Test 4: Incident Log Temporal Feedback"
    echo "  5, latency       - Test 5: End-to-End Latency Benchmark"
    echo "  6, degradation   - Test 6: Graceful Degradation"
    echo "  7, delta         - Test 7: Delta Filter Validation"
    echo "  all              - Run all test profiles (default)"
    echo "  ready            - Run tests that don't require Actian/Orchestrator"
    echo "  mock             - Run mock/placeholder tests only"
    echo ""
    echo "Examples:"
    echo "  ./run_tests.sh                  # Run all tests"
    echo "  ./run_tests.sh ready            # Run ready tests only"
    echo "  ./run_tests.sh 1                # Run embedding sanity test"
    echo "  ./run_tests.sh trend -vv        # Run trend tests with extra verbosity"
    exit 1
    ;;
esac

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Test execution complete"
echo "═══════════════════════════════════════════════════════════"
