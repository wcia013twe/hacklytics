#!/usr/bin/env python3
"""
Mock Streaming Service - Simulates Jetson Camera Telemetry

Generates realistic fire scenario telemetry packets and streams them to FastAPI
via HTTP POST to /test/inject endpoint. Simulates various fire scenarios with
realistic temporal evolution.

Usage:
    python scripts/mock_stream_service.py
"""

import asyncio
import json
import random
import time
from datetime import datetime
from typing import Dict, List
import httpx

# FastAPI ingest service endpoint
FASTAPI_BASE_URL = "http://localhost:8000"
INJECT_ENDPOINT = f"{FASTAPI_BASE_URL}/test/inject"

# Scenario templates for realistic fire evolution
SCENARIOS = [
    {
        "name": "growing_fire_with_victim",
        "description": "Fire grows from small to large, person trapped",
        "duration_seconds": 30,
        "fire_trajectory": [0.15, 0.25, 0.40, 0.55, 0.70, 0.85],  # Growing
        "person_trajectory": [True, True, True, True, True, True],  # Trapped
        "exit_blocked": True,
    },
    {
        "name": "rapid_flashover",
        "description": "Sudden flashover conditions",
        "duration_seconds": 15,
        "fire_trajectory": [0.20, 0.35, 0.65, 0.90, 0.95, 0.98],  # Rapid growth
        "person_trajectory": [False, False, True, True, False, False],  # Person flees
        "exit_blocked": False,
    },
    {
        "name": "contained_small_fire",
        "description": "Small fire, well controlled",
        "duration_seconds": 20,
        "fire_trajectory": [0.08, 0.10, 0.12, 0.09, 0.05, 0.02],  # Diminishing
        "person_trajectory": [False, False, False, False, False, False],
        "exit_blocked": False,
    },
    {
        "name": "multiple_victims_crisis",
        "description": "Large fire with multiple trapped people",
        "duration_seconds": 25,
        "fire_trajectory": [0.30, 0.45, 0.60, 0.65, 0.70, 0.75],
        "person_trajectory": [True, True, True, True, True, True],  # Multiple people
        "exit_blocked": True,
    },
]


def generate_packet(
    device_id: str,
    scenario: Dict,
    step_index: int,
    total_steps: int,
    session_id: str = "mission_demo_001"
) -> Dict:
    """
    Generate a realistic telemetry packet based on scenario progression.

    Args:
        device_id: Unique camera/device identifier (must match pattern jetson_*)
        scenario: Scenario configuration dict
        step_index: Current step in scenario (0-indexed)
        total_steps: Total number of steps in scenario
        session_id: Mission session ID (must match pattern mission_*)

    Returns:
        Telemetry packet dict matching TelemetryPacket schema
    """
    import time

    # Interpolate fire dominance from trajectory
    trajectory = scenario["fire_trajectory"]
    fire_idx = min(int((step_index / total_steps) * len(trajectory)), len(trajectory) - 1)
    fire_dominance = trajectory[fire_idx]

    # Add random noise (+/- 5%)
    fire_dominance += random.uniform(-0.05, 0.05)
    fire_dominance = max(0.0, min(1.0, fire_dominance))

    # Person detection
    person_present = scenario["person_trajectory"][fire_idx] if fire_idx < len(scenario["person_trajectory"]) else False

    # Calculate fire growth rate (delta from previous step)
    if step_index > 0 and fire_idx > 0:
        prev_fire = trajectory[fire_idx - 1]
        fire_growth_rate = (fire_dominance - prev_fire) / (total_steps / len(trajectory))
    else:
        fire_growth_rate = 0.0

    # Determine hazard level based on fire dominance
    if fire_dominance >= 0.8:
        hazard_level = "CRITICAL"
    elif fire_dominance >= 0.6:
        hazard_level = "HIGH"
    elif fire_dominance >= 0.3:
        hazard_level = "MODERATE"
    elif fire_dominance >= 0.1:
        hazard_level = "LOW"
    else:
        hazard_level = "CLEAR"

    # Generate visual narrative
    narrative_templates = {
        "CRITICAL": [
            f"Large fire occupying {int(fire_dominance*100)}% of visual field, heavy smoke",
            f"Flashover conditions imminent, {int(fire_dominance*100)}% fire coverage",
            f"Critical fire growth detected, {int(fire_dominance*100)}% dominance"
        ],
        "HIGH": [
            f"Active fire spreading, {int(fire_dominance*100)}% of field affected",
            f"Significant fire growth, {int(fire_dominance*100)}% coverage"
        ],
        "MODERATE": [
            f"Fire detected at {int(fire_dominance*100)}% field coverage",
            f"Moderate fire activity, {int(fire_dominance*100)}% dominance"
        ],
        "LOW": [
            f"Small fire detected, {int(fire_dominance*100)}% field coverage",
            f"Minor fire activity at {int(fire_dominance*100)}%"
        ],
        "CLEAR": [
            "No active fire detected, monitoring posture",
            "Scene clear, thermal imaging normal"
        ]
    }

    visual_narrative = random.choice(narrative_templates[hazard_level])
    if person_present:
        visual_narrative += ", person detected in hazard zone"
    if scenario["exit_blocked"]:
        visual_narrative += ", exit path obstructed"

    # Smoke opacity
    smoke_opacity = round(fire_dominance * 0.8 + random.uniform(0, 0.2), 3)

    # Build packet matching TelemetryPacket schema
    packet = {
        "device_id": device_id,  # Must match jetson_* pattern
        "session_id": session_id,  # Must match mission_* pattern
        "timestamp": time.time(),  # Unix epoch timestamp
        "hazard_level": hazard_level,
        "scores": {
            "fire_dominance": round(fire_dominance, 3),
            "smoke_opacity": round(smoke_opacity, 3),
            "proximity_alert": person_present and fire_dominance > 0.3,
        },
        "tracked_objects": [
            {
                "id": 1,
                "label": "person" if person_present else "none",
                "status": "stationary" if person_present else "clear",
                "duration_in_frame": step_index * 0.5 if person_present else 0.0
            }
        ],
        "visual_narrative": visual_narrative[:200],  # Max 200 chars
    }

    return packet


async def stream_scenario(
    client: httpx.AsyncClient,
    scenario: Dict,
    device_id: str = "jetson_cam_001",
    session_id: str = "mission_demo_001"
):
    """
    Stream a complete scenario to FastAPI.

    Args:
        client: HTTP client for making requests
        scenario: Scenario configuration
        device_id: Device identifier
    """
    duration = scenario["duration_seconds"]
    packets_per_second = 2  # Simulate 2 Hz camera feed
    total_packets = duration * packets_per_second
    delay = 1.0 / packets_per_second

    print(f"\n{'=' * 60}")
    print(f"Streaming Scenario: {scenario['name']}")
    print(f"Description: {scenario['description']}")
    print(f"Duration: {duration}s | Packets: {total_packets} | Rate: {packets_per_second} Hz")
    print(f"{'=' * 60}\n")

    for step in range(total_packets):
        packet = generate_packet(device_id, scenario, step, total_packets, session_id)

        # Send to FastAPI
        try:
            response = await client.post(INJECT_ENDPOINT, json=packet)
            response.raise_for_status()

            result = response.json()

            # Display progress
            fire_dom = packet["scores"]["fire_dominance"]
            person = "👤" if packet["scores"]["proximity_alert"] else "  "
            hazard = packet["hazard_level"]
            status = "✓" if result.get("success") else "✗"

            print(
                f"{status} [{step + 1:2d}/{total_packets}] "
                f"{hazard:8s} | Fire: {fire_dom:5.2f} {person} | "
                f"Latency: {result.get('total_time_ms', 0):.1f}ms"
            )

        except Exception as e:
            print(f"✗ [{step + 1:2d}/{total_packets}] Error: {e}")

        await asyncio.sleep(delay)

    print(f"\n✓ Scenario '{scenario['name']}' completed\n")


async def main():
    """
    Main execution loop: cycle through all scenarios.
    """
    print("=" * 60)
    print("Mock Streaming Service - Fire Telemetry Simulator")
    print("=" * 60)
    print(f"\nTarget: {FASTAPI_BASE_URL}")
    print(f"Scenarios: {len(SCENARIOS)}")
    print("\nPress Ctrl+C to stop\n")

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Check if FastAPI is reachable
        try:
            response = await client.get(f"{FASTAPI_BASE_URL}/health")
            health = response.json()
            print(f"✓ FastAPI health check: {health}\n")
        except Exception as e:
            print(f"✗ Cannot reach FastAPI at {FASTAPI_BASE_URL}")
            print(f"  Error: {e}")
            print("\nMake sure FastAPI is running:")
            print("  cd fastapi && uvicorn backend.main_ingest:app --reload")
            return

        try:
            # Cycle through scenarios
            while True:
                for scenario in SCENARIOS:
                    await stream_scenario(client, scenario)
                    await asyncio.sleep(3)  # Pause between scenarios

                print("\n🔄 Restarting scenario cycle...\n")
                await asyncio.sleep(5)

        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping stream service...")


if __name__ == "__main__":
    asyncio.run(main())
