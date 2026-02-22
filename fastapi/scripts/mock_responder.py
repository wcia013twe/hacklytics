#!/usr/bin/env python3
"""
Mock Responder: Fire Response Unit Simulator
Standalone script - NO backend dependencies
Streams scenario events to aggregator service
"""

import asyncio
import json
import time
import sys
from datetime import datetime
from pathlib import Path
import websockets
from typing import Dict, List


class MockResponder:
    """Mock fire response unit that plays back scripted scenarios"""

    def __init__(self, scenario_file: str, aggregator_url: str = "ws://localhost:8002/responder"):
        self.scenario_file = Path(scenario_file)
        self.aggregator_url = aggregator_url
        self.scenario = self._load_scenario()
        self.start_time = None
        self.current_event_idx = 0

    def _load_scenario(self) -> Dict:
        """Load scenario from JSON file"""
        if not self.scenario_file.exists():
            raise FileNotFoundError(f"Scenario file not found: {self.scenario_file}")

        with open(self.scenario_file) as f:
            return json.load(f)

    async def run(self):
        """Execute scenario and stream to aggregator"""
        print(f"\n{'='*70}")
        print(f"🔥 Mock Responder: {self.scenario['responder_id']}")
        print(f"📍 Location: {self.scenario['location']}")
        print(f"⏱️  Duration: {self.scenario['duration_sec']}s")
        print(f"🎬 Scenario: {self.scenario['scenario_name']}")
        print(f"{'='*70}\n")

        self.start_time = time.time()

        try:
            async with websockets.connect(self.aggregator_url) as ws:
                # Send initial registration
                await ws.send(json.dumps({
                    "message_type": "responder_register",
                    "responder_id": self.scenario['responder_id'],
                    "location": self.scenario['location']
                }))

                print(f"✅ Connected to aggregator: {self.aggregator_url}\n")

                # Stream events
                for event in self.scenario['events']:
                    # Wait until event timestamp
                    elapsed = time.time() - self.start_time
                    wait_time = event['timestamp_offset'] - elapsed

                    if wait_time > 0:
                        await asyncio.sleep(wait_time)

                    # Recalculate elapsed after sleep
                    elapsed = time.time() - self.start_time

                    # Build event payload
                    payload = {
                        "message_type": "responder_update",
                        "responder_id": self.scenario['responder_id'],
                        "location": self.scenario['location'],
                        "timestamp": time.time(),
                        "hazard_level": event['hazard_level'],
                        "narrative": event['narrative'],
                        "scores": {
                            "fire_dominance": event['fire_dominance'],
                            "smoke_opacity": event['smoke_opacity']
                        },
                        "telemetry": {
                            "temp_f": event['temp_f']
                        },
                        "entities": event['entities'],
                        "responder_vitals": event['responder_vitals']
                    }

                    # Send to aggregator
                    await ws.send(json.dumps(payload))

                    # Also write to local JSON log (for aggregator to read)
                    self._append_to_log(payload)

                    # Console output with color coding
                    hazard_symbol = {
                        "CLEAR": "🟢",
                        "CAUTION": "🟡",
                        "HIGH": "🟠",
                        "CRITICAL": "🔴"
                    }.get(event['hazard_level'], "⚪")

                    print(f"[T+{int(elapsed):3d}s] {hazard_symbol} {event['hazard_level']:8} | {event['narrative'][:60]}")

                    self.current_event_idx += 1

                print(f"\n{'='*70}")
                print(f"✅ Scenario complete: {self.scenario['responder_id']}")
                print(f"   Total events: {len(self.scenario['events'])}")
                print(f"   Duration: {int(time.time() - self.start_time)}s")
                print(f"{'='*70}\n")

        except websockets.exceptions.WebSocketException as e:
            print(f"\n❌ WebSocket error: {e}")
            print(f"   Make sure aggregator is running at {self.aggregator_url}")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            sys.exit(1)

    def _append_to_log(self, event: Dict):
        """Append event to local JSON log file"""
        log_dir = Path("data/logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"{self.scenario['responder_id']}_incidents.json"

        # Read existing log
        if log_file.exists():
            with open(log_file) as f:
                log_data = json.load(f)
        else:
            log_data = {
                "responder_id": self.scenario['responder_id'],
                "location": self.scenario['location'],
                "events": []
            }

        # Append new event
        log_data['events'].append(event)

        # Write back
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python mock_responder.py <scenario_file.json>")
        print("\nExample:")
        print("  python mock_responder.py scenarios/kitchen_fire_progression.json")
        sys.exit(1)

    scenario_file = sys.argv[1]

    # Optional: custom aggregator URL
    aggregator_url = sys.argv[2] if len(sys.argv) > 2 else "ws://localhost:8002/responder"

    responder = MockResponder(scenario_file, aggregator_url)
    asyncio.run(responder.run())


if __name__ == "__main__":
    main()
