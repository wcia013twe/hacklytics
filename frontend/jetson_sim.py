"""
Jetson Nano Simulator — sends escalating telemetry packets to the gateway.

Usage:
    python jetson_sim.py                        # auto-escalate every 5s
    python jetson_sim.py --interval 2           # faster, every 2s
    python jetson_sim.py --scenario critical    # jump straight to critical
    python jetson_sim.py --loop                 # cycle through all scenarios repeatedly

The gateway transforms these into WebSocketPayload and pushes to the dashboard.
"""

import argparse
import json
import time
import urllib.request
import urllib.error

GATEWAY_URL = "http://127.0.0.1:8080/test/inject"

SCENARIOS = {
    "clear": {
        "device_id": "jetson_alpha_01",
        "session_id": "mission_2026_02_21",
        "hazard_level": "CLEAR",
        "scores": {"fire_dominance": 0.0, "smoke_opacity": 0.0, "proximity_alert": False},
        "tracked_objects": [],
        "visual_narrative": "All zones clear. No hazards detected. Normal patrol conditions.",
    },
    "low": {
        "device_id": "jetson_alpha_01",
        "session_id": "mission_2026_02_21",
        "hazard_level": "LOW",
        "scores": {"fire_dominance": 0.12, "smoke_opacity": 0.10, "proximity_alert": False},
        "tracked_objects": [
            {"id": 7, "label": "fire", "status": "stable", "duration_in_frame": 5.0}
        ],
        "visual_narrative": "Small fire detected in south corner. Contained. Smoke minimal.",
    },
    "moderate": {
        "device_id": "jetson_alpha_01",
        "session_id": "mission_2026_02_21",
        "hazard_level": "MODERATE",
        "scores": {"fire_dominance": 0.35, "smoke_opacity": 0.45, "proximity_alert": False},
        "tracked_objects": [
            {"id": 7, "label": "fire", "status": "growing", "duration_in_frame": 18.0, "growth_rate": 0.05}
        ],
        "visual_narrative": "Fire expanding. Smoke building in upper half of structure.",
    },
    "high": {
        "device_id": "jetson_alpha_01",
        "session_id": "mission_2026_02_21",
        "hazard_level": "HIGH",
        "scores": {"fire_dominance": 0.60, "smoke_opacity": 0.75, "proximity_alert": True},
        "tracked_objects": [
            {"id": 42, "label": "person",   "status": "stationary", "duration_in_frame": 15.0},
            {"id": 7,  "label": "fire",     "status": "growing",    "duration_in_frame": 45.0, "growth_rate": 0.08},
            {"id": 9,  "label": "gas_tank", "status": "static",     "duration_in_frame": 30.0},
        ],
        "visual_narrative": "Person #42 stationary near exit. Fire growing 8%/s. Gas tank in proximity.",
    },
    "critical": {
        "device_id": "jetson_alpha_01",
        "session_id": "mission_2026_02_21",
        "hazard_level": "CRITICAL",
        "scores": {"fire_dominance": 0.88, "smoke_opacity": 0.90, "proximity_alert": True},
        "tracked_objects": [
            {"id": 42, "label": "person",   "status": "stationary", "duration_in_frame": 28.0},
            {"id": 7,  "label": "fire",     "status": "growing",    "duration_in_frame": 85.0, "growth_rate": 0.14},
            {"id": 9,  "label": "gas_tank", "status": "static",     "duration_in_frame": 70.0},
        ],
        "visual_narrative": "CRITICAL: Person #42 stationary in corner. Fire #7 growing 14%/s, blocking exit. BLEVE risk.",
    },
}

ESCALATION_ORDER = ["clear", "low", "moderate", "high", "critical"]


def send_packet(packet: dict) -> dict:
    packet = {**packet, "timestamp": time.time()}
    body   = json.dumps(packet).encode()
    req    = urllib.request.Request(
        GATEWAY_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def print_packet(name: str, packet: dict, result: dict):
    hazard   = packet["hazard_level"]
    clients  = result.get("clients_reached", "?")
    status   = result.get("system_status", "?")
    objects  = ", ".join(o["label"] for o in packet.get("tracked_objects", [])) or "none"
    scores   = packet["scores"]

    print(f"\n{'─'*55}")
    print(f"  Scenario   : {name.upper()} → {hazard}")
    print(f"  Status     : {status}   clients={clients}")
    print(f"  Scores     : fire={scores['fire_dominance']:.2f}  smoke={scores['smoke_opacity']:.2f}  proximity={scores['proximity_alert']}")
    print(f"  Objects    : {objects}")
    print(f"  Narrative  : {packet['visual_narrative']}")
    print(f"{'─'*55}")


def main():
    parser = argparse.ArgumentParser(description="Jetson Nano simulator")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between packets (default: 5)")
    parser.add_argument("--scenario", choices=ESCALATION_ORDER, default=None, help="Send a single scenario and exit")
    parser.add_argument("--loop",     action="store_true", help="Loop through all scenarios repeatedly")
    args = parser.parse_args()

    print(f"Jetson Simulator → {GATEWAY_URL}")

    # Single scenario mode
    if args.scenario:
        packet = SCENARIOS[args.scenario]
        try:
            result = send_packet(packet)
            print_packet(args.scenario, packet, result)
        except Exception as e:
            print(f"[ERROR] {e} — is the gateway running? (python gateway.py)")
        return

    # Escalation / loop mode
    order = ESCALATION_ORDER
    idx   = 0
    print(f"Auto-escalating every {args.interval}s. Ctrl+C to stop.\n")

    try:
        while True:
            name   = order[idx % len(order)]
            packet = SCENARIOS[name]
            try:
                result = send_packet(packet)
                print_packet(name, packet, result)
            except urllib.error.URLError as e:
                print(f"[ERROR] Cannot reach gateway: {e.reason}")
                print("        Make sure gateway.py is running: python gateway.py")

            if not args.loop and idx == len(order) - 1:
                print("\n[done] Full escalation sequence complete.")
                break

            idx += 1
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n[stopped]")


if __name__ == "__main__":
    main()
