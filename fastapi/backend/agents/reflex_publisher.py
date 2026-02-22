import json
import time
from typing import Dict, List, Set
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from contracts.models import TelemetryPacket, TrendResult

# Simple enum conversions — not interpretation, just type mapping
_STATUS_MAP = {
    "CLEAR": "nominal", "LOW": "nominal",
    "MODERATE": "warning", "HIGH": "warning",
    "CRITICAL": "critical",
}
_TREND_MAP = {
    "growing": "expanding", "stable": "static",
    "stationary": "static", "static": "static", "diminishing": "diminishing",
}


class ReflexPublisherAgent:
    """
    Formats and broadcasts reflex updates to dashboard via WebSocket.
    Emits WebSocketPayload format so the frontend receives consistent messages
    from both the reflex path and the RAG cognition path.
    """

    def __init__(self):
        # session_id -> Set[websocket_connection]
        self.ws_clients: Dict[str, Set] = {}

    async def format_reflex_message(self, packet: TelemetryPacket, trend: TrendResult) -> Dict:
        """Task 3.1: Format reflex message as WebSocketPayload."""
        temp_f = round(72 + packet.scores.fire_dominance * 428)
        entities = [
            {
                "name": o.label,
                "duration_sec": o.duration_in_frame,
                "trend": _TREND_MAP.get(o.status, "static"),
            }
            for o in packet.tracked_objects
        ]
        return {
            "timestamp": packet.timestamp,
            "system_status": _STATUS_MAP[packet.hazard_level],
            "action_command": f"{packet.hazard_level} — Retrieving protocols...",
            "action_reason": packet.visual_narrative,
            "rag_data": None,   # populated by cognition path once RAG completes
            "scene_context": {
                "entities": entities,
                "telemetry": {
                    "temp_f": temp_f,
                    "trend": "rising" if packet.scores.fire_dominance > 0.1 else "stable",
                },
                "responders": [{
                    "id": packet.device_id,
                    "name": "RESCUE-1",
                    "status": _STATUS_MAP[packet.hazard_level],
                    "vitals": {
                        "heart_rate": 0,
                        "o2_level": 0,
                        "aqi": round(packet.scores.smoke_opacity * 500),
                    },
                    "body_cam_url": "http://100.116.21.87:5000/video_feed",
                    "thermal_cam_url": "http://100.116.21.87:5000/video_feed",
                }],
                "synthesized_insights": {
                    "threat_vector": packet.visual_narrative,
                    "evacuation_radius_ft": None,
                    "resource_bottleneck": None,
                    "max_temp_f": temp_f,
                    "max_aqi": round(packet.scores.smoke_opacity * 500),
                },
            },
        }

    async def websocket_broadcast(self, message: Dict, session_id: str, timeout_ms: int = 10) -> Dict:
        """
        Task 3.2: Broadcast to all WebSocket clients in session

        Returns:
            {"clients_reached": int, "send_time_ms": float}
        """
        start = time.perf_counter()

        if session_id not in self.ws_clients or not self.ws_clients[session_id]:
            # No clients connected - this is OK, not an error
            return {"clients_reached": 0, "send_time_ms": 0}

        clients_reached = 0
        failed_clients = set()

        for ws in self.ws_clients[session_id]:
            try:
                await ws.send_json(message)
                clients_reached += 1
            except Exception as e:
                # Client disconnected, mark for removal
                failed_clients.add(ws)

        # Remove failed clients
        self.ws_clients[session_id] -= failed_clients

        send_time = (time.perf_counter() - start) * 1000
        return {"clients_reached": clients_reached, "send_time_ms": send_time}

    def register_client(self, session_id: str, ws):
        """Add WebSocket client to broadcast group"""
        if session_id not in self.ws_clients:
            self.ws_clients[session_id] = set()
        self.ws_clients[session_id].add(ws)

    def unregister_client(self, session_id: str, ws):
        """Remove WebSocket client from broadcast group"""
        if session_id in self.ws_clients:
            self.ws_clients[session_id].discard(ws)
