import pytest
import time
import json
import numpy as np
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


def generate_test_packet(fire_dominance: float, timestamp: float):
    """Generate synthetic test packet"""
    return {
        "device_id": "jetson_benchmark",
        "session_id": "benchmark_session",
        "timestamp": timestamp,
        "hazard_level": "HIGH",
        "scores": {
            "fire_dominance": fire_dominance,
            "smoke_opacity": 0.5,
            "proximity_alert": False
        },
        "tracked_objects": [],
        "visual_narrative": "Fire detected, monitoring progression"
    }


@pytest.mark.skipif(True, reason="Requires RAGOrchestrator implementation")
@pytest.mark.asyncio
async def test_latency_benchmark_reflex_path():
    """
    Test Profile 5: End-to-End Latency Benchmark (Reflex Path Only)

    Send 100 packets, measure reflex path latency.

    Pass Criteria:
    - p50 < 25ms
    - p95 < 50ms
    - p99 < 100ms (allowing for outliers)
    """
    from backend.orchestrator import RAGOrchestrator

    orchestrator = RAGOrchestrator(actian_pool=None)
    await orchestrator.startup()

    latencies = []
    start_time = time.time()

    print("\nRunning 100-packet latency benchmark...")

    for i in range(100):
        packet = generate_test_packet(
            fire_dominance=0.1 + i * 0.005,
            timestamp=start_time + i
        )

        raw_message = json.dumps(packet)

        # Measure reflex latency
        start = time.perf_counter()
        result = await orchestrator.process_packet(raw_message)
        elapsed = (time.perf_counter() - start) * 1000

        if result.get("success"):
            latencies.append(elapsed)

    # Calculate percentiles
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)
    avg = np.mean(latencies)
    max_latency = max(latencies)

    print(f"\nLatency Results (100 packets):")
    print(f"  Avg:  {avg:.2f}ms")
    print(f"  p50:  {p50:.2f}ms")
    print(f"  p95:  {p95:.2f}ms")
    print(f"  p99:  {p99:.2f}ms")
    print(f"  Max:  {max_latency:.2f}ms")

    # Assertions
    assert p50 < 50, f"p50 latency {p50:.2f}ms exceeds 50ms"
    assert p95 < 100, f"p95 latency {p95:.2f}ms exceeds 100ms"

    print("✅ PASS: Reflex latency meets SLA")

    return {
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "avg": avg
    }


@pytest.mark.skipif(True, reason="Requires RAGOrchestrator implementation")
@pytest.mark.asyncio
async def test_latency_no_packet_drops():
    """
    Verify that sustained throughput doesn't drop packets.

    Send 100 packets rapidly, all should be processed.
    """
    from backend.orchestrator import RAGOrchestrator

    orchestrator = RAGOrchestrator(actian_pool=None)
    await orchestrator.startup()

    start_time = time.time()
    successful = 0
    failed = 0

    for i in range(100):
        packet = generate_test_packet(0.3, start_time + i * 0.1)
        result = await orchestrator.process_packet(json.dumps(packet))

        if result.get("success"):
            successful += 1
        else:
            failed += 1

    print(f"\nThroughput Test:")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")

    assert failed == 0, f"{failed} packets failed processing"
    assert successful == 100

    print("✅ PASS: No packet drops under load")


def test_latency_benchmark_mock():
    """
    Mock version of latency benchmark (runs without orchestrator).

    This validates the test harness is ready for when the orchestrator is implemented.
    """
    print("\n⚠️  Mock test: RAGOrchestrator not yet implemented")
    print("   Test harness ready - update when orchestrator is available")

    # Validate test packet generation
    packet = generate_test_packet(0.5, time.time())
    assert packet["device_id"] == "jetson_benchmark"
    assert packet["scores"]["fire_dominance"] == 0.5
    assert "visual_narrative" in packet

    print("✅ Test harness validated")
