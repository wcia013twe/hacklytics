"""
PROBLEM 2: Sensor Conflict Resolution Test Suite

Tests the "Split-Brain" thermal-override hierarchy where thermal sensor
takes priority over visual when temperatures exceed safety thresholds.

CRITICAL TEST SCENARIOS:
1. Thermal Override: Visual=SAFE, Thermal=HIGH → Should escalate to CRITICAL
2. False Alarm Detection: Visual=FIRE, Thermal=COOL → Should downgrade to FALSE_ALARM
3. Sensor Agreement: Both detect fire → Should confirm CRITICAL
4. Hidden Heat: Thermal=HIGH, Visual=CLEAR → Should detect HIDDEN_HEAT_SOURCE

Safety Philosophy: "Thermal trumps visual when hot"
- RGB cameras can't see through smoke
- Thermal cameras can't be fooled by reflections or lighting
"""

import sys
import time
from reflex_engine import ReflexEngine


# ============================================================================
# MOCK YOLO RESULT CLASSES
# ============================================================================

class MockTensor:
    """Simulates a tensor with tolist() method"""
    def __init__(self, data):
        self.data = data

    def tolist(self):
        return self.data


class MockBox:
    """Simulates a YOLO bounding box detection"""
    def __init__(self, cls_id, xyxy, conf):
        self.cls = [cls_id]
        self.conf = [conf]
        self.xyxy = [MockTensor(xyxy)]


class MockYOLOResult:
    """Simulates YOLO detection results"""
    def __init__(self, detections, class_names):
        """
        Args:
            detections: List of (cls_id, bbox, confidence) tuples
            class_names: Dict mapping cls_id to label (e.g., {0: 'fire', 1: 'smoke'})
        """
        self.boxes = [MockBox(cls_id, bbox, conf) for cls_id, bbox, conf in detections]
        self.names = class_names


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_test_engine():
    """Creates a reflex engine for testing (won't transmit to backend)"""
    return ReflexEngine(backend_url="http://localhost:9999/test_endpoint")


def run_test_scenario(name, description, yolo_detections, class_names, thermal_temp, smoke_detected, expected_hazard_level, expected_conflict, expected_override):
    """
    Executes a single test scenario and validates results.

    Args:
        name: Test scenario name
        description: What this test validates
        yolo_detections: List of (cls_id, bbox, confidence)
        class_names: Dict of {cls_id: label}
        thermal_temp: Temperature in Celsius
        smoke_detected: Boolean
        expected_hazard_level: Expected hazard level output
        expected_conflict: Should sensor_conflict be True?
        expected_override: Should thermal_override_active be True?

    Returns:
        Boolean: True if test passed
    """
    print(f"\n{'='*70}")
    print(f"TEST: {name}")
    print(f"{'='*70}")
    print(f"Description: {description}")
    print(f"\nInput Conditions:")
    print(f"  Visual Detections: {len(yolo_detections)} objects")
    for cls_id, bbox, conf in yolo_detections:
        print(f"    - {class_names[cls_id]} (confidence: {conf:.2f})")
    print(f"  Thermal Reading: {thermal_temp}C")
    print(f"  Smoke Sensor: {smoke_detected}")

    # Create mock YOLO results
    mock_results = [MockYOLOResult(yolo_detections, class_names)]
    frame_shape = (480, 640, 3)  # Standard VGA

    # Run reflex engine
    engine = create_test_engine()

    # Process frame and get state directly (bypasses transmission)
    state = engine.process_frame(frame_shape, mock_results, thermal_temp, smoke_detected)

    # Extract results from returned state
    actual_hazard = state.get('hazard_level', 'UNKNOWN')
    actual_conflict = state.get('sensor_conflict', False)
    actual_override = state.get('thermal_override_active', False)
    override_reason = state.get('override_reason', None)

    print(f"\nActual Output:")
    print(f"  Hazard Level: {actual_hazard}")
    print(f"  Sensor Conflict: {actual_conflict}")
    print(f"  Thermal Override: {actual_override}")
    if override_reason:
        print(f"  Override Reason: {override_reason}")

    # Validation
    hazard_match = actual_hazard == expected_hazard_level
    conflict_match = actual_conflict == expected_conflict
    override_match = actual_override == expected_override

    all_pass = hazard_match and conflict_match and override_match

    print(f"\nValidation:")
    print(f"  Hazard Level: {'PASS' if hazard_match else 'FAIL'} (expected: {expected_hazard_level})")
    print(f"  Sensor Conflict: {'PASS' if conflict_match else 'FAIL'} (expected: {expected_conflict})")
    print(f"  Thermal Override: {'PASS' if override_match else 'FAIL'} (expected: {expected_override})")

    if all_pass:
        print(f"\nRESULT: PASS")
    else:
        print(f"\nRESULT: FAIL")

    return all_pass


# ============================================================================
# TEST SCENARIOS
# ============================================================================

def test_scenario_1_thermal_override_critical():
    """
    SCENARIO 1: Thermal Override (Extreme Heat)
    Visual: Clear path (no detections)
    Thermal: 120C (critical)
    Expected: THERMAL_OVERRIDE_CRITICAL with conflict flag

    Rationale: Smoke may be transparent to RGB camera, but thermal can't be fooled.
    """
    return run_test_scenario(
        name="Scenario 1: Thermal Override (Extreme Heat)",
        description="Visual sees nothing, thermal reads 120C. Should force CRITICAL.",
        yolo_detections=[],  # No visual detections
        class_names={},
        thermal_temp=120.0,
        smoke_detected=False,
        expected_hazard_level="THERMAL_OVERRIDE_CRITICAL",
        expected_conflict=True,
        expected_override=True
    )


def test_scenario_2_hidden_heat_source():
    """
    SCENARIO 2: Hidden Heat Source
    Visual: Clear path
    Thermal: 80C (danger)
    Expected: HIDDEN_HEAT_SOURCE with conflict and override

    Rationale: Fire behind wall, or transparent smoke obscuring visual.
    """
    return run_test_scenario(
        name="Scenario 2: Hidden Heat Source",
        description="Visual clear, thermal 80C. Should detect HIDDEN_HEAT_SOURCE.",
        yolo_detections=[],
        class_names={},
        thermal_temp=80.0,
        smoke_detected=False,
        expected_hazard_level="HIDDEN_HEAT_SOURCE",
        expected_conflict=True,
        expected_override=True
    )


def test_scenario_3_false_alarm_visual():
    """
    SCENARIO 3: False Alarm (Visual)
    Visual: Fire detected
    Thermal: 25C (cool)
    Expected: FALSE_ALARM_VISUAL with conflict

    Rationale: YOLO might detect flames on a TV screen, or red/orange objects.
    """
    return run_test_scenario(
        name="Scenario 3: False Alarm (Visual)",
        description="Visual detects fire, but thermal reads 25C. Likely false positive.",
        yolo_detections=[
            (0, [200, 150, 350, 300], 0.85)  # Fire detection
        ],
        class_names={0: 'fire'},
        thermal_temp=25.0,
        smoke_detected=False,
        expected_hazard_level="FALSE_ALARM_VISUAL",
        expected_conflict=True,
        expected_override=False
    )


def test_scenario_4_critical_confirmed():
    """
    SCENARIO 4: Both Sensors Agree
    Visual: Fire detected (in upper left, not blocking path)
    Thermal: 90C (high)
    Expected: CRITICAL_CONFIRMED (or spatial variant), no conflict

    Rationale: Both sensors confirm threat - highest confidence scenario.
    Note: May return CRITICAL_TRAPPED if fire blocks center corridor.
    """
    return run_test_scenario(
        name="Scenario 4: Sensors Agree (Critical Confirmed)",
        description="Both visual and thermal detect fire. Should confirm CRITICAL.",
        yolo_detections=[
            (0, [50, 100, 150, 200], 0.92)  # Fire detection (upper left, not center)
        ],
        class_names={0: 'fire'},
        thermal_temp=90.0,
        smoke_detected=False,
        expected_hazard_level="CRITICAL_CONFIRMED",
        expected_conflict=False,
        expected_override=False
    )


def test_scenario_5_smoke_with_high_thermal():
    """
    SCENARIO 5: Smoke + High Thermal
    Visual: Smoke detected
    Thermal: 110C (critical)
    Expected: THERMAL_OVERRIDE_CRITICAL (thermal wins over visual smoke)

    Rationale: Thermal severity overrides visual smoke classification.
    """
    return run_test_scenario(
        name="Scenario 5: Smoke Visual + High Thermal Override",
        description="Visual detects smoke, thermal reads 110C. Thermal should escalate.",
        yolo_detections=[
            (1, [200, 50, 500, 250], 0.78)  # Smoke detection
        ],
        class_names={1: 'smoke'},
        thermal_temp=110.0,
        smoke_detected=True,
        expected_hazard_level="THERMAL_OVERRIDE_CRITICAL",
        expected_conflict=False,  # No conflict since both detect hazard
        expected_override=True
    )


def test_scenario_6_thermal_warning():
    """
    SCENARIO 6: Thermal Warning (50-60C range)
    Visual: Clear
    Thermal: 55C (warning)
    Expected: THERMAL_WARNING

    Rationale: Elevated temperature but not immediately dangerous. Monitor situation.
    """
    return run_test_scenario(
        name="Scenario 6: Thermal Warning (Elevated Temperature)",
        description="Visual clear, thermal 55C. Should issue thermal warning.",
        yolo_detections=[],
        class_names={},
        thermal_temp=55.0,
        smoke_detected=False,
        expected_hazard_level="THERMAL_WARNING",
        expected_conflict=False,
        expected_override=False
    )


def test_scenario_7_visual_unconfirmed():
    """
    SCENARIO 7: Visual Fire Unconfirmed
    Visual: Fire detected
    Thermal: 45C (warm but not hot)
    Expected: VISUAL_FIRE_UNCONFIRMED

    Rationale: Visual sees fire, thermal slightly elevated but not critical.
    Could be early-stage fire or controlled flame.
    """
    return run_test_scenario(
        name="Scenario 7: Visual Fire Unconfirmed (Mild Heat)",
        description="Visual fire with 45C thermal. Possible early-stage fire.",
        yolo_detections=[
            (0, [150, 100, 250, 200], 0.72)  # Fire detection
        ],
        class_names={0: 'fire'},
        thermal_temp=45.0,
        smoke_detected=False,
        expected_hazard_level="VISUAL_FIRE_UNCONFIRMED",
        expected_conflict=False,
        expected_override=False
    )


def test_scenario_8_proximity_escalation():
    """
    SCENARIO 8: Proximity-Based Escalation
    Visual: Fire directly overlapping person
    Thermal: 85C
    Expected: CRITICAL_PROXIMITY (spatial escalation)

    Rationale: Fire proximity to vulnerable object increases threat level.
    Note: Requires IoU > 0.1 or distance < 15% of frame diagonal for proximity > 0.7
    """
    return run_test_scenario(
        name="Scenario 8: Proximity Escalation",
        description="Fire detected overlapping person with 85C thermal. Should escalate to CRITICAL_PROXIMITY.",
        yolo_detections=[
            (0, [200, 200, 350, 350], 0.88),  # Fire
            (2, [250, 250, 400, 450], 0.92)   # Person with significant overlap
        ],
        class_names={0: 'fire', 2: 'person'},
        thermal_temp=85.0,
        smoke_detected=False,
        expected_hazard_level="CRITICAL_PROXIMITY",
        expected_conflict=False,
        expected_override=False
    )


def test_scenario_9_safe_conditions():
    """
    SCENARIO 9: All Safe
    Visual: No detections
    Thermal: 22C
    Expected: SAFE

    Rationale: Baseline safe condition.
    """
    return run_test_scenario(
        name="Scenario 9: Safe Conditions (Baseline)",
        description="No visual detections, thermal at 22C. Should remain SAFE.",
        yolo_detections=[],
        class_names={},
        thermal_temp=22.0,
        smoke_detected=False,
        expected_hazard_level="SAFE",
        expected_conflict=False,
        expected_override=False
    )


def test_scenario_10_extreme_thermal_with_fire():
    """
    SCENARIO 10: Extreme Thermal + Visual Fire
    Visual: Fire detected
    Thermal: 400C (extreme - like in problem description)
    Expected: THERMAL_OVERRIDE_CRITICAL

    Rationale: Validates the original problem scenario - extreme heat should
    override even when visual agrees, to emphasize thermal severity.
    """
    return run_test_scenario(
        name="Scenario 10: Extreme Thermal (400C) + Fire",
        description="Visual fire + 400C thermal. Should force THERMAL_OVERRIDE_CRITICAL.",
        yolo_detections=[
            (0, [200, 150, 400, 350], 0.95)  # Fire detection
        ],
        class_names={0: 'fire'},
        thermal_temp=400.0,
        smoke_detected=False,
        expected_hazard_level="THERMAL_OVERRIDE_CRITICAL",
        expected_conflict=False,  # Both detect hazard, but thermal is extreme
        expected_override=True
    )


# ============================================================================
# PERFORMANCE BENCHMARKING
# ============================================================================

def benchmark_latency():
    """
    Measures processing latency to ensure <50ms requirement for edge deployment.
    """
    import io
    import contextlib

    print(f"\n{'='*70}")
    print(f"PERFORMANCE BENCHMARK: Processing Latency")
    print(f"{'='*70}")
    print(f"Requirement: <50ms per frame (edge device constraint)")

    engine = create_test_engine()
    frame_shape = (480, 640, 3)

    # Test scenario: Fire detection with thermal override
    mock_results = [MockYOLOResult(
        [(0, [200, 150, 350, 300], 0.85)],
        {0: 'fire'}
    )]

    # Suppress console output during benchmark
    with contextlib.redirect_stdout(io.StringIO()):
        # Warm-up run
        _ = engine.process_frame(frame_shape, mock_results, 120.0, False)

        # Benchmark runs
        num_runs = 100
        latencies = []

        for _ in range(num_runs):
            start_time = time.perf_counter()
            _ = engine.process_frame(frame_shape, mock_results, 120.0, False)
            end_time = time.perf_counter()
            latencies.append((end_time - start_time) * 1000)  # Convert to ms

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    min_latency = min(latencies)

    print(f"\nResults ({num_runs} iterations):")
    print(f"  Average Latency: {avg_latency:.2f}ms")
    print(f"  Min Latency: {min_latency:.2f}ms")
    print(f"  Max Latency: {max_latency:.2f}ms")

    passed = avg_latency < 50.0
    print(f"\nPerformance Test: {'PASS' if passed else 'FAIL'}")

    if not passed:
        print(f"  WARNING: Average latency {avg_latency:.2f}ms exceeds 50ms requirement!")

    return passed


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    """Runs all test scenarios and reports results"""
    print("\n" + "="*70)
    print("SENSOR CONFLICT RESOLUTION TEST SUITE")
    print("PROBLEM 2: Thermal Override 'Trump Card' Hierarchy")
    print("="*70)

    test_functions = [
        test_scenario_1_thermal_override_critical,
        test_scenario_2_hidden_heat_source,
        test_scenario_3_false_alarm_visual,
        test_scenario_4_critical_confirmed,
        test_scenario_5_smoke_with_high_thermal,
        test_scenario_6_thermal_warning,
        test_scenario_7_visual_unconfirmed,
        test_scenario_8_proximity_escalation,
        test_scenario_9_safe_conditions,
        test_scenario_10_extreme_thermal_with_fire,
    ]

    results = []
    for test_func in test_functions:
        try:
            passed = test_func()
            results.append((test_func.__name__, passed))
        except Exception as e:
            print(f"\nERROR in {test_func.__name__}: {e}")
            results.append((test_func.__name__, False))

    # Run performance benchmark
    print("\n")
    perf_passed = benchmark_latency()
    results.append(("Performance Benchmark", perf_passed))

    # Summary report
    print(f"\n{'='*70}")
    print(f"TEST SUMMARY")
    print(f"{'='*70}")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {test_name}")

    print(f"\n{'='*70}")
    print(f"RESULTS: {passed_count}/{total_count} tests passed")
    print(f"{'='*70}")

    if passed_count == total_count:
        print("\nALL TESTS PASSED")
        return 0
    else:
        print(f"\n{total_count - passed_count} TEST(S) FAILED")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
