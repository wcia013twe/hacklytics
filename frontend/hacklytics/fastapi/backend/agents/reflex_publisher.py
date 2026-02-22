import json
import time
from typing import Dict, List, Set
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from contracts.models import TelemetryPacket, TrendResult

class ReflexPublisherAgent:
    """
    Formats and broadcasts reflex updates to dashboard via WebSocket.
    """

    def __init__(self):
        # session_id -> Set[websocket_connection]
        self.ws_clients: Dict[str, Set] = {}

    async def format_reflex_message(self, packet: TelemetryPacket, trend: TrendResult) -> Dict:
        """Task 3.1: Format reflex message"""
        return {
            "message_type": "reflex_update",
            "device_id": packet.device_id,
            "session_id": packet.session_id,
            "hazard_level": packet.hazard_level,
            "scores": {
                "fire_dominance": packet.scores.fire_dominance,
                "smoke_opacity": packet.scores.smoke_opacity,
                "proximity_alert": packet.scores.proximity_alert
            },
            "trend": {
                "tag": trend.trend_tag,
                "growth_rate": trend.growth_rate,
                "sample_count": trend.sample_count,
                "time_span": trend.time_span
            },
            "timestamp": packet.timestamp
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
