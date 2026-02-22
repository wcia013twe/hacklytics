import json
import logging
from typing import Dict, Tuple
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from contracts.models import TelemetryPacket

logger = logging.getLogger(__name__)

class TelemetryIngestAgent:
    """
    Validates incoming ZMQ packets and routes to device-specific buffers.
    """

    def __init__(self):
        self.malformed_count = 0
        self.valid_count = 0

    async def validate_schema(self, raw_json: str) -> Tuple[bool, Dict]:
        """
        Task 1.2: Validate schema

        Returns:
            (valid, result) where result contains either parsed_packet or errors
        """
        try:
            data = json.loads(raw_json)
            packet = TelemetryPacket(**data)
            self.valid_count += 1
            return True, {"parsed_packet": packet, "errors": []}
        except json.JSONDecodeError as e:
            self.malformed_count += 1
            logger.error(f"Invalid JSON: {e}")
            return False, {"parsed_packet": None, "errors": [f"JSON decode error: {str(e)}"]}
        except Exception as e:
            self.malformed_count += 1
            logger.error(f"Schema validation failed: {e}")
            return False, {"parsed_packet": None, "errors": [str(e)]}

    async def route_to_buffer(self, packet: TelemetryPacket) -> str:
        """
        Task 1.3: Route to buffer

        Returns:
            buffer_key (device_id)
        """
        return packet.device_id

    def get_stats(self) -> Dict:
        return {
            "valid_count": self.valid_count,
            "malformed_count": self.malformed_count,
            "error_rate": self.malformed_count / max(1, self.valid_count + self.malformed_count)
        }
