"""
Mock server that simulates the full Jetson → Backend → Frontend pipeline.

Receives Jetson-format packets, transforms them to WebSocketPayload,
and broadcasts to connected dashboard clients.

Endpoints:
  POST /sim/start        — start the auto-escalation simulation
  POST /sim/stop         — stop the simulation
  GET  /sim/status       — check if running
  POST /test/inject      — inject a single Jetson packet manually
  WS   /ws              — dashboard WebSocket (matches frontend SOCKET_URL)
"""

import asyncio
import json
import time
from typing import Set, Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

# ─────────────────────────────────────────────────────────────────────────────
# Escalating Jetson scenarios (actual Jetson JSON format)
# ─────────────────────────────────────────────────────────────────────────────
JETSON_SCENARIOS = [
    {
        "device_id": "jetson_alpha_01",
        "session_id": "mission_2026_02_21",
        "hazard_level": "CLEAR",
        "scores": {"fire_dominance": 0.0, "smoke_opacity": 0.0, "proximity_alert": False},
        "tracked_objects": [],
        "visual_narrative": "All zones clear. No hazards detected. Normal patrol conditions.",
    },
    {
        "device_id": "jetson_alpha_01",
        "session_id": "mission_2026_02_21",
        "hazard_level": "LOW",
        "scores": {"fire_dominance": 0.12, "smoke_opacity": 0.10, "proximity_alert": False},
        "tracked_objects": [
            {"id": 7, "label": "fire", "status": "stable", "duration_in_frame": 5.0}
        ],
        "visual_narrative": "Small fire detected in south corner. Contained. Smoke minimal.",
    },
    {
        "device_id": "jetson_alpha_01",
        "session_id": "mission_2026_02_21",
        "hazard_level": "MODERATE",
        "scores": {"fire_dominance": 0.35, "smoke_opacity": 0.45, "proximity_alert": False},
        "tracked_objects": [
            {"id": 7, "label": "fire", "status": "growing", "duration_in_frame": 18.0, "growth_rate": 0.05}
        ],
        "visual_narrative": "Fire expanding. Smoke building in upper half of structure.",
    },
    {
        "device_id": "jetson_alpha_01",
        "session_id": "mission_2026_02_21",
        "hazard_level": "HIGH",
        "scores": {"fire_dominance": 0.60, "smoke_opacity": 0.75, "proximity_alert": True},
        "tracked_objects": [
            {"id": 42, "label": "person", "status": "stationary", "duration_in_frame": 15.0},
            {"id": 7, "label": "fire", "status": "growing", "duration_in_frame": 45.0, "growth_rate": 0.08},
            {"id": 9, "label": "gas_tank", "status": "static", "duration_in_frame": 30.0},
        ],
        "visual_narrative": "Person #42 stationary near exit. Fire growing 8%/s. Gas tank in proximity.",
    },
    {
        "device_id": "jetson_alpha_01",
        "session_id": "mission_2026_02_21",
        "hazard_level": "CRITICAL",
        "scores": {"fire_dominance": 0.88, "smoke_opacity": 0.90, "proximity_alert": True},
        "tracked_objects": [
            {"id": 42, "label": "person", "status": "stationary", "duration_in_frame": 28.0},
            {"id": 7, "label": "fire", "status": "growing", "duration_in_frame": 85.0, "growth_rate": 0.14},
            {"id": 9, "label": "gas_tank", "status": "static", "duration_in_frame": 70.0},
        ],
        "visual_narrative": "CRITICAL: Person #42 stationary in corner. Fire #7 growing 14%/s, blocking exit. BLEVE risk.",
    },
]

# Mock RAG protocols keyed by hazard level
MOCK_PROTOCOLS = {
    "CLEAR": {
        "protocol_id": "100",
        "hazard_type": "None",
        "source_text": "Standard monitoring operational. Continue normal duties.",
        "actionable_commands": [{"target": "ALL UNITS", "directive": "Maintain patrol vectors"}],
    },
    "LOW": {
        "protocol_id": "201",
        "hazard_type": "Minor Fire",
        "source_text": "Localized fire detected. Monitor for expansion. Stage extinguisher.",
        "actionable_commands": [{"target": "Alpha-1", "directive": "Monitor fire size and trend"}],
    },
    "MODERATE": {
        "protocol_id": "205",
        "hazard_type": "Combustible Area",
        "source_text": "Small localized fires should be monitored for expansion. Prepare class B extinguishers.",
        "actionable_commands": [
            {"target": "Alpha-1", "directive": "Report fire size & trend"},
            {"target": "Charlie-3", "directive": "Monitor sudden AQI drop"},
        ],
    },
    "HIGH": {
        "protocol_id": "312",
        "hazard_type": "Pressurized Container",
        "source_text": "Pressurized tanks expose a severe risk if ambient temperature exceeds 200F. Personnel must evacuate 50ft.",
        "actionable_commands": [
            {"target": "Alpha-1", "directive": "Evacuate 50ft — gas tank proximity"},
            {"target": "ALL UNITS", "directive": "Prepare for rapid egress"},
        ],
    },
    "CRITICAL": {
        "protocol_id": "402",
        "hazard_type": "Propane Proximity / BLEVE",
        "source_text": "Boiling Liquid Expanding Vapor Explosion risk. Pressurized tank near critical temp. Minimum standoff: 100ft.",
        "actionable_commands": [
            {"target": "Alpha-1", "directive": "EVACUATE NORTH — 100FT (BLEVE)"},
            {"target": "Charlie-3", "directive": "ABORT EAST WING (COLLAPSE RISK)"},
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Transform: Jetson packet → WebSocketPayload (what the frontend expects)
# ─────────────────────────────────────────────────────────────────────────────

STATUS_MAP = {
    "CLEAR": "nominal",
    "LOW": "nominal",
    "MODERATE": "warning",
    "HIGH": "warning",
    "CRITICAL": "critical",
}

COMMAND_MAP = {
    "CLEAR": "Environment Safe. Monitoring...",
    "LOW": "Caution: Fire Detected. Monitoring.",
    "MODERATE": "Warning: Fire Expanding. Prepare Response.",
    "HIGH": "Warning: Multiple Hazards. Stage Evacuation.",
    "CRITICAL": "EVACUATE 100FT IMMEDIATELY",
}

TREND_MAP = {
    "growing": "expanding",
    "stable": "static",
    "stationary": "static",
    "static": "static",
    "diminishing": "diminishing",
}


def _object_to_entity(obj: dict) -> dict:
    raw_status = obj.get("status", "static")
    return {
        "name": obj["label"],
        "duration_sec": obj.get("duration_in_frame", 0.0),
        "trend": TREND_MAP.get(raw_status, "static"),
    }


def transform_to_payload(jetson: dict) -> dict:
    hazard = jetson["hazard_level"]
    scores = jetson["scores"]

    entities = [_object_to_entity(o) for o in jetson.get("tracked_objects", [])]

    # Derive a rough temp_f from fire_dominance (0→72°F, 1→500°F)
    temp_f = round(72 + scores["fire_dominance"] * 428)
    temp_trend = "rising" if scores["fire_dominance"] > 0.1 else "stable"

    return {
        "timestamp": time.time(),
        "system_status": STATUS_MAP[hazard],
        "action_command": COMMAND_MAP[hazard],
        "action_reason": jetson["visual_narrative"],
        "rag_data": MOCK_PROTOCOLS[hazard],
        "scene_context": {
            "entities": entities,
            "telemetry": {"temp_f": temp_f, "trend": temp_trend},
            "responders": [],           # extend here when responder data is available
            "synthesized_insights": {
                "threat_vector": jetson["visual_narrative"],
                "evacuation_radius_ft": 100 if hazard == "CRITICAL" else (50 if hazard == "HIGH" else None),
                "resource_bottleneck": None,
                "max_temp_f": temp_f,
                "max_aqi": round(scores["smoke_opacity"] * 500),
            },
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────

connected_clients: Set[WebSocket] = set()
sim_running = False
sim_task: Optional[asyncio.Task] = None


async def _broadcast(payload: dict):
    dead = set()
    message = json.dumps(payload)
    for ws in connected_clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


async def _run_simulation():
    """Cycle through JETSON_SCENARIOS every 5 seconds."""
    global sim_running
    idx = 0
    while sim_running:
        jetson = {**JETSON_SCENARIOS[idx % len(JETSON_SCENARIOS)], "timestamp": time.time()}
        payload = transform_to_payload(jetson)
        await _broadcast(payload)
        print(f"[sim] broadcast: hazard={jetson['hazard_level']}  clients={len(connected_clients)}")
        idx += 1
        await asyncio.sleep(5)


# ─────────────────────────────────────────────────────────────────────────────
# REST endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/sim/start")
async def sim_start():
    global sim_running, sim_task
    if not sim_running:
        sim_running = True
        sim_task = asyncio.create_task(_run_simulation())
    return {"running": sim_running}


@app.post("/sim/stop")
async def sim_stop():
    global sim_running, sim_task
    sim_running = False
    if sim_task:
        sim_task.cancel()
        sim_task = None
    return {"running": sim_running}


@app.get("/sim/status")
async def sim_status():
    return {"running": sim_running}


@app.post("/test/inject")
async def test_inject(packet: dict):
    """Inject a single Jetson-format packet and broadcast to connected clients."""
    # Stamp timestamp if missing
    packet.setdefault("timestamp", time.time())
    payload = transform_to_payload(packet)
    await _broadcast(payload)
    return {"success": True, "clients_reached": len(connected_clients)}


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket endpoint (matches frontend SOCKET_URL = ws://127.0.0.1:8000/ws)
# ─────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    print(f"[ws] client connected  (total={len(connected_clients)})")
    try:
        while True:
            await websocket.receive_text()   # keep-alive / ping
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"[ws] client disconnected  (total={len(connected_clients)})")


if __name__ == "__main__":
    print("Mock server running on http://127.0.0.1:8000")
    print("  WebSocket : ws://127.0.0.1:8000/ws")
    print("  Sim start : POST /sim/start")
    print("  Sim stop  : POST /sim/stop")
    print("  Inject    : POST /test/inject  (Jetson JSON body)")
    uvicorn.run(app, host="127.0.0.1", port=8000)
