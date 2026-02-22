"""
Hacklytics Gateway — port 8000

Thin relay between the Jetson stream and the dashboard.
All interpretation (hazard classification, protocol lookup, source document)
is handled by the backend RAG pipeline on port 8001.

REST:
  GET  /health        — liveness check
  POST /sim/start     — start built-in Jetson simulation
  POST /sim/stop      — stop simulation
  GET  /sim/status    — simulation state
  POST /test/inject   — forward a Jetson packet to the backend

WebSocket:
  WS /ws             — dashboard clients connect here;
                       gateway relays messages from the backend WebSocket
"""

import asyncio
import json
import os
import time
from typing import Set, Optional

import httpx
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKEND_URL     = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
BACKEND_WS_URL  = os.getenv("BACKEND_WS_URL", "ws://127.0.0.1:8000")
SESSION_ID      = os.getenv("SESSION_ID", "mission_2026_02_21")

# ─────────────────────────────────────────────────────────────────────────────
# Jetson sim scenarios (raw telemetry only — no interpretation)
# ─────────────────────────────────────────────────────────────────────────────
JETSON_SCENARIOS = [
    {
        "device_id": "jetson_alpha_01", "session_id": SESSION_ID,
        "hazard_level": "CLEAR",
        "scores": {"fire_dominance": 0.0, "smoke_opacity": 0.0, "proximity_alert": False},
        "tracked_objects": [],
        "visual_narrative": "All zones clear. No hazards detected.",
    },
    {
        "device_id": "jetson_alpha_01", "session_id": SESSION_ID,
        "hazard_level": "LOW",
        "scores": {"fire_dominance": 0.12, "smoke_opacity": 0.10, "proximity_alert": False},
        "tracked_objects": [
            {"id": 7, "label": "fire", "status": "stable", "duration_in_frame": 5.0}
        ],
        "visual_narrative": "Small fire detected in south corner. Contained. Smoke minimal.",
    },
    {
        "device_id": "jetson_alpha_01", "session_id": SESSION_ID,
        "hazard_level": "MODERATE",
        "scores": {"fire_dominance": 0.35, "smoke_opacity": 0.45, "proximity_alert": False},
        "tracked_objects": [
            {"id": 7, "label": "fire", "status": "growing", "duration_in_frame": 18.0, "growth_rate": 0.05}
        ],
        "visual_narrative": "Fire expanding. Smoke building in upper half of structure.",
    },
    {
        "device_id": "jetson_alpha_01", "session_id": SESSION_ID,
        "hazard_level": "HIGH",
        "scores": {"fire_dominance": 0.60, "smoke_opacity": 0.75, "proximity_alert": True},
        "tracked_objects": [
            {"id": 42, "label": "person",   "status": "stationary", "duration_in_frame": 15.0},
            {"id": 7,  "label": "fire",     "status": "growing",    "duration_in_frame": 45.0, "growth_rate": 0.08},
            {"id": 9,  "label": "gas_tank", "status": "static",     "duration_in_frame": 30.0},
        ],
        "visual_narrative": "Person #42 stationary near exit. Fire growing 8%/s. Gas tank in proximity.",
    },
    {
        "device_id": "jetson_alpha_01", "session_id": SESSION_ID,
        "hazard_level": "CRITICAL",
        "scores": {"fire_dominance": 0.88, "smoke_opacity": 0.90, "proximity_alert": True},
        "tracked_objects": [
            {"id": 42, "label": "person",   "status": "stationary", "duration_in_frame": 28.0},
            {"id": 7,  "label": "fire",     "status": "growing",    "duration_in_frame": 85.0, "growth_rate": 0.14},
            {"id": 9,  "label": "gas_tank", "status": "static",     "duration_in_frame": 70.0},
        ],
        "visual_narrative": "CRITICAL: Person #42 stationary in corner. Fire #7 growing 14%/s, blocking exit. BLEVE risk.",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────
connected_clients: Set[WebSocket] = set()
sim_running   = False
sim_task: Optional[asyncio.Task]    = None
relay_task: Optional[asyncio.Task]  = None


async def broadcast(payload: dict):
    dead = set()
    msg  = json.dumps(payload)
    for ws in connected_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


# ─────────────────────────────────────────────────────────────────────────────
# Backend WebSocket relay
# ─────────────────────────────────────────────────────────────────────────────
async def _relay_from_backend():
    """Connect to backend WebSocket and relay every message to frontend clients."""
    import websockets
    uri = f"{BACKEND_WS_URL}/ws/{SESSION_ID}"
    while True:
        try:
            async with websockets.connect(uri) as backend_ws:
                print(f"[relay] connected to backend {uri}")
                async for raw in backend_ws:
                    try:
                        payload = json.loads(raw)
                        print(f"[relay] received from backend → forwarding to {len(connected_clients)} client(s): {str(payload)[:80]}")
                        await broadcast(payload)
                    except Exception as e:
                        print(f"[relay] broadcast error: {e}")
        except Exception as e:
            print(f"[relay] backend disconnected ({e}), retrying in 3s...")
            await asyncio.sleep(3)


@app.on_event("startup")
async def startup():
    global relay_task
    relay_task = asyncio.create_task(_relay_from_backend())


# ─────────────────────────────────────────────────────────────────────────────
# Simulation (sends raw Jetson packets to backend — no interpretation here)
# ─────────────────────────────────────────────────────────────────────────────
async def _run_sim():
    global sim_running
    idx = 0
    async with httpx.AsyncClient() as client:
        while sim_running:
            packet = {**JETSON_SCENARIOS[idx % len(JETSON_SCENARIOS)], "timestamp": time.time()}
            try:
                await client.post(f"{BACKEND_URL}/test/inject", json=packet, timeout=5)
                print(f"[sim] → backend: hazard={packet['hazard_level']}")
            except Exception as e:
                print(f"[sim] backend unreachable: {e}")
            idx += 1
            await asyncio.sleep(5)


# ─────────────────────────────────────────────────────────────────────────────
# REST endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "clients": len(connected_clients), "sim_running": sim_running}


@app.post("/sim/start")
async def sim_start():
    global sim_running, sim_task
    if not sim_running:
        sim_running = True
        sim_task    = asyncio.create_task(_run_sim())
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
    """Forward a Jetson packet directly to the backend for RAG processing."""
    packet.setdefault("timestamp", time.time())
    packet.setdefault("session_id", SESSION_ID)
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BACKEND_URL}/test/inject", json=packet, timeout=5)
        return resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket (frontend connects here)
# ─────────────────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    print(f"[ws] client connected  total={len(connected_clients)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"[ws] client disconnected  total={len(connected_clients)}")


if __name__ == "__main__":
    print(f"Gateway  → http://127.0.0.1:8080  (relaying from backend {BACKEND_URL})")
    uvicorn.run(app, host="127.0.0.1", port=8080)
