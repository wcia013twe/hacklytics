#!/usr/bin/env python3
"""
Building-Wide Intelligence Aggregator
Collects data from multiple responders and synthesizes mission context
"""

import asyncio
import json
import time
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import aiohttp

app = FastAPI(title="Building Intelligence Aggregator")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class ResponderState:
    """Tracks state for one responder unit"""

    def __init__(self, responder_id: str, location: str):
        self.responder_id = responder_id
        self.location = location
        self.latest_event: Optional[Dict] = None
        self.event_history: List[Dict] = []
        self.last_update: float = time.time()
        self.current_hazard: str = "CLEAR"

    def update(self, event: Dict):
        """Update responder state with new event"""
        self.latest_event = event
        self.event_history.append(event)
        self.last_update = time.time()
        self.current_hazard = event.get('hazard_level', 'CLEAR')

        # Keep only last 10 events
        if len(self.event_history) > 10:
            self.event_history = self.event_history[-10:]


class AggregatorState:
    """Global aggregator state"""

    def __init__(self):
        self.responders: Dict[str, ResponderState] = {}
        self.dashboard_clients: List[WebSocket] = []
        self.last_aggregation: Optional[Dict] = None
        self.aggregation_count: int = 0
        self.backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000")

    def register_responder(self, responder_id: str, location: str):
        """Register a new responder unit"""
        if responder_id not in self.responders:
            self.responders[responder_id] = ResponderState(responder_id, location)
            print(f"✅ Registered responder: {responder_id} ({location})")

    def update_responder(self, responder_id: str, event: Dict):
        """Update responder with new event"""
        if responder_id in self.responders:
            self.responders[responder_id].update(event)

    def get_critical_responders(self) -> List[ResponderState]:
        """Get all responders in CRITICAL or HIGH state"""
        return [
            r for r in self.responders.values()
            if r.current_hazard in ['CRITICAL', 'HIGH']
        ]

    def should_aggregate(self) -> bool:
        """Determine if aggregation should be triggered"""
        # Trigger if any responder is CRITICAL
        critical = [r for r in self.responders.values() if r.current_hazard == 'CRITICAL']
        return len(critical) > 0

# Global state
state = AggregatorState()

# ============================================================================
# GEMINI LLM INTEGRATION
# ============================================================================

# Configure Gemini
gemini_api_key = os.getenv("GEMINI_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel('gemini-1.5-flash-002')
else:
    model = None
    print("⚠️  GEMINI_API_KEY not set - using fallback synthesis")


async def synthesize_building_context(responders: List[ResponderState]) -> str:
    """
    Use Gemini to synthesize building-wide situation report

    Input: All responder states
    Output: Concise mission context (200-300 chars)
    """

    if not model:
        # Fallback: simple concatenation
        critical_count = len([r for r in responders if r.current_hazard == 'CRITICAL'])
        return f"MULTI-LOCATION EMERGENCY: {critical_count} CRITICAL zones detected across building"

    # Build prompt from responder data
    responder_summaries = []
    for r in responders:
        if r.latest_event:
            responder_summaries.append(
                f"📍 {r.location} ({r.responder_id}):\n"
                f"   Status: {r.current_hazard}\n"
                f"   Situation: {r.latest_event.get('narrative', 'N/A')}\n"
                f"   Fire: {r.latest_event['scores']['fire_dominance']:.0%}, "
                f"Temp: {r.latest_event['telemetry']['temp_f']}°F\n"
                f"   Responder: HR={r.latest_event['responder_vitals']['heart_rate']}, "
                f"O2={r.latest_event['responder_vitals']['o2_level']}%, "
                f"AQI={r.latest_event['responder_vitals']['aqi']}"
            )

    prompt = f"""You are a fire command AI analyzing a multi-location emergency response mission.

CURRENT SITUATION ACROSS ALL LOCATIONS:

{chr(10).join(responder_summaries)}

TASK: Synthesize a building-wide tactical situation report.

REQUIREMENTS:
1. Identify the PRIMARY threat (which location is most critical)
2. Note any spreading/escalation patterns between locations
3. Flag responders in immediate danger (high HR, low O2, high AQI)
4. Provide ONE actionable recommendation for incident commander
5. Keep response under 250 characters

OUTPUT FORMAT:
[Primary Threat] | [Spread Pattern] | [Responder Status] | [Command Recommendation]

EXAMPLE:
Kitchen CRITICAL flashover imminent | Fire spreading to hallway (smoke detected) | R-KITCHEN-01 in danger zone (HR 165, AQI 380) | EVACUATE Kitchen unit, establish defensive perimeter at hallway

YOUR SYNTHESIS:"""

    # Call Gemini
    try:
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=150,
                temperature=0.3,  # Low temp for consistent, factual output
            )
        )

        synthesis = response.text.strip()
        print(f"\n🧠 LLM SYNTHESIS:\n{synthesis}\n")
        return synthesis

    except Exception as e:
        print(f"❌ LLM synthesis failed: {e}")
        # Fallback
        critical_count = len([r for r in responders if r.current_hazard == 'CRITICAL'])
        return f"MULTI-LOCATION EMERGENCY: {critical_count} CRITICAL zones, LLM synthesis unavailable"

# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

@app.websocket("/responder")
async def responder_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for mock responders to stream updates
    """
    await websocket.accept()
    responder_id = None

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get('message_type')

            if msg_type == 'responder_register':
                responder_id = data['responder_id']
                location = data['location']
                state.register_responder(responder_id, location)

            elif msg_type == 'responder_update':
                responder_id = data['responder_id']
                state.update_responder(responder_id, data)

                print(f"📡 {responder_id}: {data['hazard_level']:8} | {data['narrative'][:50]}...")

                # Check if aggregation should be triggered
                if state.should_aggregate():
                    await trigger_aggregation()

    except WebSocketDisconnect:
        if responder_id:
            print(f"❌ Responder disconnected: {responder_id}")


@app.websocket("/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for dashboard to receive aggregated intelligence (optional)
    """
    await websocket.accept()
    state.dashboard_clients.append(websocket)
    print(f"📊 Dashboard connected (total: {len(state.dashboard_clients)})")

    try:
        # Send latest aggregation if available
        if state.last_aggregation:
            await websocket.send_json(state.last_aggregation)

        # Keep connection alive
        while True:
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        state.dashboard_clients.remove(websocket)
        print(f"📊 Dashboard disconnected (remaining: {len(state.dashboard_clients)})")

# ============================================================================
# AGGREGATION LOGIC
# ============================================================================

async def trigger_aggregation():
    """
    Trigger building-wide intelligence aggregation
    Called when any responder reaches CRITICAL state
    """

    print(f"\n{'='*70}")
    print(f"🚨 AGGREGATION TRIGGERED (count: {state.aggregation_count + 1})")
    print(f"{'='*70}")

    # Get all responders with data
    active_responders = [
        r for r in state.responders.values()
        if r.latest_event is not None
    ]

    if len(active_responders) == 0:
        print("⚠️  No active responders to aggregate")
        return

    # Call LLM to synthesize
    synthesis_start = time.time()
    building_synthesis = await synthesize_building_context(active_responders)
    synthesis_time = (time.time() - synthesis_start) * 1000

    # Build actionable commands per responder
    actionable_commands = []
    for r in active_responders:
        if r.current_hazard == "CRITICAL":
            actionable_commands.append({
                "target": r.responder_id,
                "directive": f"EVACUATE - {r.location} compromised"
            })
        elif r.current_hazard == "HIGH":
            actionable_commands.append({
                "target": r.responder_id,
                "directive": f"ESTABLISH DEFENSIVE PERIMETER - Monitor {r.location}"
            })

    # Format as RAG recommendation (matches existing dashboard message type)
    aggregation_as_rag = {
        "message_type": "rag_recommendation",
        "device_id": "BUILDING_AGGREGATOR",
        "recommendation": building_synthesis,
        "matched_protocol": f"Multi-Location Protocol 999 (aggregated {len(active_responders)} units)",
        "processing_time_ms": synthesis_time,
        "protocols_count": len(active_responders),
        "history_count": sum(len(r.event_history) for r in active_responders),
        "cache_stats": {},
        # Extra metadata for debugging
        "aggregation_metadata": {
            "responder_count": len(active_responders),
            "critical_locations": [r.location for r in active_responders if r.current_hazard == "CRITICAL"],
            "timestamp": time.time()
        },
        # RAG data structure (for IntelligencePanel display)
        "rag_data": {
            "protocol_id": "999",
            "hazard_type": "MULTI-LOCATION EMERGENCY",
            "source_text": building_synthesis,
            "actionable_commands": actionable_commands
        }
    }

    # Store aggregation
    state.last_aggregation = aggregation_as_rag
    state.aggregation_count += 1

    # Broadcast to backend for relay to dashboard
    await broadcast_to_backend(aggregation_as_rag)

    print(f"✅ Aggregation sent to backend ({synthesis_time:.1f}ms LLM synthesis)")
    print(f"{'='*70}\n")


async def broadcast_to_backend(message: Dict):
    """Send aggregation to backend /broadcast endpoint"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{state.backend_url}/broadcast",
                json=message,
                timeout=aiohttp.ClientTimeout(total=2)
            ) as resp:
                if resp.status == 200:
                    print(f"✅ Sent aggregation to backend: {state.backend_url}/broadcast")
                else:
                    print(f"⚠️  Backend returned status {resp.status}")
    except Exception as e:
        print(f"❌ Failed to send to backend: {e}")

# ============================================================================
# HTTP ENDPOINTS (for debugging)
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "responders": len(state.responders),
        "dashboard_clients": len(state.dashboard_clients),
        "aggregations": state.aggregation_count,
        "gemini_configured": model is not None
    }


@app.get("/status")
async def get_status():
    """Get current aggregator state"""
    return {
        "responders": {
            r_id: {
                "location": r.location,
                "hazard_level": r.current_hazard,
                "last_update": r.last_update,
                "event_count": len(r.event_history)
            }
            for r_id, r in state.responders.items()
        },
        "last_aggregation": state.last_aggregation,
        "aggregation_count": state.aggregation_count,
        "backend_url": state.backend_url
    }

# ============================================================================
# STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Startup banner"""
    print("\n" + "="*70)
    print("🏢 Building Intelligence Aggregator")
    print("="*70)
    print(f"Responder WebSocket: ws://localhost:8002/responder")
    print(f"Dashboard WebSocket:  ws://localhost:8002/dashboard (optional)")
    print(f"Status endpoint:      http://localhost:8002/status")
    print(f"Backend relay:        {state.backend_url}/broadcast")
    print(f"Gemini LLM:          {'✅ Configured' if model else '❌ Not configured'}")
    print("="*70 + "\n")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
