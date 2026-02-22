#!/usr/bin/env python3
"""
Continuous Mock Nano Telemetry Stream

Simulates a Jetson Nano sending real-time fire detection telemetry to the
RAG backend. Generates realistic sensor data with temporal evolution patterns
matching actual nano hardware (YOLO, thermal camera, gas sensor).

Usage:
    python scripts/mock_nano_stream.py [--scenario SCENARIO_NAME] [--duration SECONDS]
"""

import asyncio
import argparse
import time
import random
from typing import Dict, List
import httpx

# FastAPI RAG service endpoint (direct to RAG orchestrator)
RAG_URL = "http://localhost:8001/process"

# Realistic fire evolution scenarios based on nano sensor capabilities
SCENARIOS = {
    "growing_warehouse_fire": {
        "description": "Warehouse fire growing over time, person trapped near exit",
        "duration_seconds": 60,
        "thermal_trajectory": [25, 28, 35, 45, 60, 75, 90, 105, 120, 135],  # °C
        "fire_dominance_trajectory": [0.0, 0.05, 0.15, 0.30, 0.50, 0.65, 0.80, 0.90, 0.95, 0.98],
        "smoke_trajectory": [False, False, True, True, True, True, True, True, True, True],
        "person_positions": [(0.7, 0.3)] * 10,  # Person near exit (normalized coords)
        "hazard_levels": ["SAFE", "SAFE", "THERMAL_WARNING", "HIDDEN_HEAT_SOURCE",
                         "CRITICAL_CONFIRMED", "CRITICAL_PROXIMITY", "CRITICAL_TRAPPED",
                         "THERMAL_OVERRIDE_CRITICAL", "THERMAL_OVERRIDE_CRITICAL", "THERMAL_OVERRIDE_CRITICAL"],
    },

    "rapid_flashover": {
        "description": "Sudden flashover event with rapid temperature spike",
        "duration_seconds": 30,
        "thermal_trajectory": [26, 30, 40, 65, 95, 130, 150, 180, 200, 220],
        "fire_dominance_trajectory": [0.05, 0.10, 0.25, 0.55, 0.80, 0.92, 0.96, 0.98, 0.99, 1.0],
        "smoke_trajectory": [False, True, True, True, True, True, True, True, True, True],
        "person_positions": [(0.5, 0.5), (0.6, 0.5), (0.7, 0.5), (0.8, 0.5), None, None, None, None, None, None],  # Person escapes
        "hazard_levels": ["SAFE", "THERMAL_WARNING", "HIDDEN_HEAT_SOURCE", "CRITICAL_CONFIRMED",
                         "THERMAL_OVERRIDE_CRITICAL", "THERMAL_OVERRIDE_CRITICAL", "THERMAL_OVERRIDE_CRITICAL",
                         "THERMAL_OVERRIDE_CRITICAL", "THERMAL_OVERRIDE_CRITICAL", "THERMAL_OVERRIDE_CRITICAL"],
    },

    "controlled_burn": {
        "description": "Small controlled fire that diminishes over time",
        "duration_seconds": 40,
        "thermal_trajectory": [28, 35, 42, 48, 45, 40, 35, 30, 27, 25],
        "fire_dominance_trajectory": [0.08, 0.12, 0.18, 0.20, 0.15, 0.10, 0.05, 0.02, 0.0, 0.0],
        "smoke_trajectory": [False, True, True, True, False, False, False, False, False, False],
        "person_positions": [None] * 10,  # No people
        "hazard_levels": ["SAFE", "SAFE", "THERMAL_WARNING", "THERMAL_WARNING",
                         "THERMAL_WARNING", "SAFE", "SAFE", "SAFE", "SAFE", "SAFE"],
    },

    "sensor_conflict": {
        "description": "Visual fire detected but thermal reads cool (false alarm scenario)",
        "duration_seconds": 35,
        "thermal_trajectory": [24, 25, 26, 27, 26, 25, 24, 24, 23, 23],
        "fire_dominance_trajectory": [0.0, 0.15, 0.35, 0.45, 0.40, 0.30, 0.20, 0.10, 0.0, 0.0],  # Visual false positive
        "smoke_trajectory": [False, False, False, False, False, False, False, False, False, False],
        "person_positions": [(0.3, 0.7)] * 10,
        "hazard_levels": ["SAFE", "FALSE_ALARM_VISUAL", "FALSE_ALARM_VISUAL", "FALSE_ALARM_VISUAL",
                         "FALSE_ALARM_VISUAL", "SAFE", "SAFE", "SAFE", "SAFE", "SAFE"],
    },

    "smoldering_hidden_fire": {
        "description": "Hidden heat source behind wall (thermal override scenario)",
        "duration_seconds": 50,
        "thermal_trajectory": [25, 32, 45, 58, 72, 85, 95, 105, 110, 115],
        "fire_dominance_trajectory": [0.0, 0.0, 0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50],  # Visual lags thermal
        "smoke_trajectory": [False, False, True, True, True, True, True, True, True, True],
        "person_positions": [None] * 10,
        "hazard_levels": ["SAFE", "SAFE", "THERMAL_WARNING", "HIDDEN_HEAT_SOURCE",
                         "HIDDEN_HEAT_SOURCE", "HIDDEN_HEAT_SOURCE", "THERMAL_OVERRIDE_CRITICAL",
                         "THERMAL_OVERRIDE_CRITICAL", "THERMAL_OVERRIDE_CRITICAL", "THERMAL_OVERRIDE_CRITICAL"],
    },
}


def interpolate_trajectory(trajectory: List, step: int, total_steps: int) -> float:
    """Smoothly interpolate between trajectory points."""
    if len(trajectory) == 0:
        return 0.0

    # Map step to trajectory index
    position = (step / total_steps) * (len(trajectory) - 1)
    idx = int(position)
    fraction = position - idx

    if idx >= len(trajectory) - 1:
        return trajectory[-1]

    # Linear interpolation
    return trajectory[idx] + (trajectory[idx + 1] - trajectory[idx]) * fraction


def generate_nano_telemetry(
    scenario: Dict,
    step: int,
    total_steps: int,
    device_id: str = "jetson_nano_001",
    session_id: str = "mission_test_001"
) -> Dict:
    """
    Generate realistic nano telemetry packet matching the reflex_engine.py output format.

    Simulates:
    - YOLO object detection (fire, smoke, person)
    - MLX90640 thermal camera readings
    - BME680 gas sensor
    - Spatial heuristics (proximity, obstruction, dominance)
    """

    # Interpolate sensor values
    thermal = interpolate_trajectory(scenario["thermal_trajectory"], step, total_steps)
    fire_dom = interpolate_trajectory(scenario["fire_dominance_trajectory"], step, total_steps)
    smoke_idx = int((step / total_steps) * (len(scenario["smoke_trajectory"]) - 1))
    smoke = scenario["smoke_trajectory"][smoke_idx]

    person_idx = int((step / total_steps) * (len(scenario["person_positions"]) - 1))
    person_pos = scenario["person_positions"][person_idx]

    hazard_idx = int((step / total_steps) * (len(scenario["hazard_levels"]) - 1))
    hazard_level = scenario["hazard_levels"][hazard_idx]

    # Add realistic noise
    thermal += random.uniform(-2.0, 2.0)
    fire_dom += random.uniform(-0.03, 0.03)
    fire_dom = max(0.0, min(1.0, fire_dom))

    # Generate visual narrative based on detections
    narrative_parts = []
    if fire_dom > 0.1:
        narrative_parts.append(f"Fire detected covering {int(fire_dom * 100)}% of field")
    if smoke:
        narrative_parts.append("smoke present")
    if person_pos:
        narrative_parts.append(f"person at position ({person_pos[0]:.2f}, {person_pos[1]:.2f})")
    if thermal > 50:
        narrative_parts.append(f"elevated temperature {thermal:.1f}°C")

    visual_narrative = ", ".join(narrative_parts) if narrative_parts else "No hazards detected"

    # Calculate spatial scores
    proximity_score = 0.0
    obstruction_score = 0.0
    dominance_score = fire_dom

    if person_pos and fire_dom > 0.1:
        # Person near fire increases proximity score
        distance = ((person_pos[0] - 0.5) ** 2 + (person_pos[1] - 0.5) ** 2) ** 0.5
        proximity_score = max(0.0, 1.0 - distance)

        # High fire coverage + person = obstruction
        if fire_dom > 0.5:
            obstruction_score = min(1.0, fire_dom * 0.8)

    # Map extended hazard levels to standard TelemetryPacket format
    standard_hazard_map = {
        "SAFE": "CLEAR",
        "THERMAL_WARNING": "LOW",
        "FALSE_ALARM_VISUAL": "LOW",
        "HIDDEN_HEAT_SOURCE": "MODERATE",
        "VISUAL_FIRE_UNCONFIRMED": "MODERATE",
        "SMOKE_DANGER": "HIGH",
        "CRITICAL_CONFIRMED": "CRITICAL",
        "CRITICAL_PROXIMITY": "CRITICAL",
        "CRITICAL_TRAPPED": "CRITICAL",
        "THERMAL_OVERRIDE_CRITICAL": "CRITICAL",
    }

    standard_hazard = standard_hazard_map.get(hazard_level, "MODERATE")

    # Calculate smoke opacity from fire dominance and smoke sensor
    smoke_opacity = min(1.0, fire_dom * 0.7 + (0.3 if smoke else 0.0))

    # Build packet matching TelemetryPacket schema
    packet = {
        "device_id": device_id,
        "session_id": session_id,
        "timestamp": time.time(),
        "hazard_level": standard_hazard,
        "scores": {
            "fire_dominance": round(fire_dom, 3),
            "smoke_opacity": round(smoke_opacity, 3),
            "proximity_alert": proximity_score > 0.5
        },
        "tracked_objects": [],
        "visual_narrative": visual_narrative[:200],
    }

    # Add tracked objects
    if fire_dom > 0.1:
        packet["tracked_objects"].append({
            "id": 1,
            "label": "fire",
            "status": "growing" if fire_dom > 0.5 else "detected",
            "duration_in_frame": step * 0.5
        })

    if smoke:
        packet["tracked_objects"].append({
            "id": 2,
            "label": "smoke",
            "status": "present",
            "duration_in_frame": step * 0.5
        })

    if person_pos:
        packet["tracked_objects"].append({
            "id": 3,
            "label": "person",
            "status": "stationary",
            "duration_in_frame": step * 0.5
        })

    return packet


async def stream_scenario_continuous(
    client: httpx.AsyncClient,
    scenario_name: str,
    duration_override: int = None
):
    """Stream a scenario continuously to the backend."""
    scenario = SCENARIOS[scenario_name]
    duration = duration_override or scenario["duration_seconds"]

    print(f"\n{'=' * 80}")
    print(f"📡 Mock Nano Telemetry Stream")
    print(f"{'=' * 80}")
    print(f"Scenario: {scenario_name}")
    print(f"Description: {scenario['description']}")
    print(f"Duration: {duration}s | Update Rate: 2 Hz")
    print(f"Target: {RAG_URL}")
    print(f"{'=' * 80}\n")

    packets_per_second = 2
    total_packets = duration * packets_per_second
    delay = 1.0 / packets_per_second

    start_time = time.time()
    packets_sent = 0
    packets_success = 0

    for step in range(total_packets):
        packet = generate_nano_telemetry(scenario, step, total_packets)

        try:
            response = await client.post(RAG_URL, json=packet, timeout=5.0)
            response.raise_for_status()
            result = response.json()
            packets_success += 1

            # Display progress
            elapsed = time.time() - start_time
            fire = packet["scores"]["fire_dominance"]
            hazard = packet["hazard_level"]
            has_person = any(obj["label"] == "person" for obj in packet["tracked_objects"])

            status_icon = "🔥" if hazard == "CRITICAL" else "⚠️" if hazard in ["HIGH", "MODERATE"] else "✓"
            person_icon = " 👤" if has_person else ""

            print(
                f"{status_icon} [{step + 1:3d}/{total_packets}] "
                f"T:{elapsed:5.1f}s | {hazard:10s} | "
                f"Fire:{fire:5.2f}{person_icon} | "
                f"Latency:{result.get('total_time_ms', 0):5.1f}ms"
            )

        except httpx.TimeoutException:
            print(f"✗ [{step + 1:3d}/{total_packets}] Timeout - backend may be overloaded")
        except httpx.HTTPStatusError as e:
            print(f"✗ [{step + 1:3d}/{total_packets}] HTTP {e.response.status_code}: {e.response.text[:100]}")
        except Exception as e:
            print(f"✗ [{step + 1:3d}/{total_packets}] Error: {str(e)[:100]}")

        packets_sent += 1
        await asyncio.sleep(delay)

    # Summary
    print(f"\n{'=' * 80}")
    print(f"Stream Complete")
    print(f"{'=' * 80}")
    print(f"Packets Sent: {packets_sent}")
    print(f"Packets Success: {packets_success} ({packets_success/packets_sent*100:.1f}%)")
    print(f"Total Duration: {time.time() - start_time:.1f}s")
    print(f"{'=' * 80}\n")


async def main():
    parser = argparse.ArgumentParser(description="Mock Nano Telemetry Stream")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="growing_warehouse_fire",
        help="Scenario to stream"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Override scenario duration (seconds)"
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Loop scenario continuously until Ctrl+C"
    )

    args = parser.parse_args()

    print("\n📋 Available Scenarios:")
    for name, scenario in SCENARIOS.items():
        marker = "→" if name == args.scenario else " "
        print(f"  {marker} {name:30s} - {scenario['description']}")
    print()

    async with httpx.AsyncClient() as client:
        # Health check
        try:
            response = await client.get("http://localhost:8001/health", timeout=3.0)
            print(f"✓ RAG service health: {response.json()}\n")
        except Exception as e:
            print(f"✗ Cannot reach RAG service at http://localhost:8001")
            print(f"  Error: {e}")
            print("\nMake sure Docker services are running:")
            print("  docker compose up -d")
            return

        try:
            if args.loop:
                print("🔄 Looping scenario (Ctrl+C to stop)\n")
                while True:
                    await stream_scenario_continuous(client, args.scenario, args.duration)
                    print("⏸️  Pausing 5s before next iteration...\n")
                    await asyncio.sleep(5)
            else:
                await stream_scenario_continuous(client, args.scenario, args.duration)

        except KeyboardInterrupt:
            print("\n\n⏹️  Stream stopped by user")


if __name__ == "__main__":
    asyncio.run(main())
