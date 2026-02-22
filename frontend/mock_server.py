import asyncio
import json
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

app = FastAPI()

# A mock sequence simulating an escalating scenario
MOCK_STATES = [
    {
        "system_status": "nominal",
        "action_command": "Environment Safe. Monitoring...",
        "action_reason": "All telemetry within normal bounds.",
        "rag_data": {
            "protocol_id": "100",
            "hazard_type": "None",
            "source_text": "Standard monitoring operational. Continue normal duties."
        },
        "scene_context": {
            "entities": [],
            "telemetry": {"temp_f": 72, "trend": "stable"}
        }
    },
    {
        "system_status": "warning",
        "action_command": "Caution: Fire Detected.",
        "action_reason": "Tracking expansion...",
        "rag_data": {
            "protocol_id": "205",
            "hazard_type": "Combustible Area",
            "source_text": "Small localized fires should be monitored for expansion. Prepare class B extinguishers."
        },
        "scene_context": {
            "entities": [
                {"name": "fire", "duration_sec": 12, "trend": "expanding"}
            ],
            "telemetry": {"temp_f": 180, "trend": "rising"}
        }
    },
    {
        "system_status": "warning",
        "action_command": "Caution: Gas Tank in Proximity.",
        "action_reason": "Potential fuel source identified near fire zone.",
        "rag_data": {
            "protocol_id": "312",
            "hazard_type": "Pressurized Container",
            "source_text": "Pressurized tanks expose a severe risk if ambient temperature exceeds 200F."
        },
        "scene_context": {
            "entities": [
                {"name": "fire", "duration_sec": 45, "trend": "expanding"},
                {"name": "gas_tank", "duration_sec": 30, "trend": "static"}
            ],
            "telemetry": {"temp_f": 250, "trend": "rising"}
        }
    },
    {
        "system_status": "critical",
        "action_command": "EVACUATE 100FT IMMEDIATELY",
        "action_reason": "Imminent BLEVE Explosion Risk",
        "rag_data": {
            "protocol_id": "402",
            "hazard_type": "Propane Proximity",
            "source_text": "Boiling Liquid Expanding Vapor Explosion occurs when pressurized tanks reach critical temp. Minimum standoff: 100ft."
        },
        "scene_context": {
            "entities": [
                {"name": "fire", "duration_sec": 85, "trend": "expanding"},
                {"name": "gas_tank", "duration_sec": 70, "trend": "static"}
            ],
            "telemetry": {"temp_f": 450, "trend": "rising"}
        }
    }
]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Dashboard connected.")
    try:
        idx = 0
        while True:
            # Get current state from sequence
            state = MOCK_STATES[idx % len(MOCK_STATES)]
            idx += 1
            
            # Construct the payload
            payload = {
                "timestamp": time.time(),
                **state
            }
            
            # Send payload
            await websocket.send_text(json.dumps(payload))
            print(f"Sent state: {state['system_status']}")
            
            # Wait 5 seconds before next state
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        print("Dashboard disconnected.")

if __name__ == "__main__":
    print("Starting mock websocket server on ws://127.0.0.1:8000/ws")
    uvicorn.run(app, host="127.0.0.1", port=8000)
