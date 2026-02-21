import time
import bisect
from collections import deque
from typing import Dict, List
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from contracts.models import TelemetryPacket, TrendResult

class TemporalBufferAgent:
    """
    Maintains 10-second sliding window per device, computes fire growth trends.

    Design (from RAG.MD 3.4.1):
    - One buffer instance per device_id
    - Stores packets in a deque (efficient FIFO operations)
    - Evicts packets older than window_seconds on every access
    - Packets are kept in chronological order (oldest first)
    - Handles out-of-order packets using binary search insertion
    """

    def __init__(self, window_seconds: float = 10.0):
        self.buffers: Dict[str, deque] = {}
        self.window_seconds = window_seconds
        self.last_eviction_time: Dict[str, float] = {}

    async def insert_packet(self, device_id: str, packet: TelemetryPacket) -> Dict:
        """
        Task 2.1: Insert packet with out-of-order handling

        Handles WiFi jitter by maintaining chronological order.
        Discards packets older than buffer window.
        """
        if device_id not in self.buffers:
            self.buffers[device_id] = deque()
            self.last_eviction_time[device_id] = time.time()

        buffer = self.buffers[device_id]
        packet_time = packet.timestamp
        current_time = time.time()

        # Discard packets outside retention window
        if current_time - packet_time > self.window_seconds:
            return {"inserted": False, "reason": "too_old", "buffer_size": len(buffer)}

        # Evict stale packets first
        await self.evict_stale(device_id, current_time)

        # Insert packet in chronological order
        packet_dict = {
            "timestamp": packet_time,
            "scores": packet.scores.dict(),
            "packet": packet
        }

        # Common case: in-order arrival (O(1) append)
        if not buffer or packet_time >= buffer[-1]["timestamp"]:
            buffer.append(packet_dict)
        else:
            # Rare case: out-of-order packet (O(n) insertion with binary search)
            timestamps = [p["timestamp"] for p in buffer]
            insert_idx = bisect.bisect_left(timestamps, packet_time)
            buffer.insert(insert_idx, packet_dict)

        return {
            "inserted": True,
            "buffer_size": len(buffer),
            "out_of_order": packet_time < buffer[-1]["timestamp"] if len(buffer) > 1 else False
        }

    async def evict_stale(self, device_id: str, current_time: float) -> Dict:
        """
        Task 2.2: Evict stale packets (>window_seconds old)

        Lazy eviction on access (not background timer).
        """
        if device_id not in self.buffers:
            return {"evicted_count": 0, "buffer_size": 0}

        buffer = self.buffers[device_id]
        evicted = 0
        cutoff_time = current_time - self.window_seconds

        # Remove from left (oldest) until we hit a recent one
        while buffer and buffer[0]["timestamp"] < cutoff_time:
            buffer.popleft()
            evicted += 1

        self.last_eviction_time[device_id] = current_time

        return {"evicted_count": evicted, "buffer_size": len(buffer)}

    async def compute_trend(self, device_id: str) -> TrendResult:
        """
        Task 2.3: Compute fire growth trend using linear regression

        Algorithm (from RAG.MD 3.4.2):
        - Uses linear regression over fire_dominance values
        - Smooths noise better than simple delta
        - Thresholds calibrated for fire_dominance [0.0, 1.0] range

        Classification thresholds:
        - RAPID_GROWTH: growth_rate > 0.10/s (fire doubles in 10s, flashover imminent)
        - GROWING: 0.02 < growth_rate ≤ 0.10/s (steady expansion, active combustion)
        - STABLE: -0.05 ≤ growth_rate ≤ 0.02/s (contained or steady-state)
        - DIMINISHING: growth_rate < -0.05/s (suppression or fuel exhausted)
        - UNKNOWN: <2 packets in buffer or time_span <0.5s
        """
        if device_id not in self.buffers or len(self.buffers[device_id]) < 2:
            return TrendResult(
                trend_tag="UNKNOWN",
                growth_rate=0.0,
                sample_count=len(self.buffers.get(device_id, [])),
                time_span=0.0
            )

        buffer = list(self.buffers[device_id])  # Convert deque to list
        sorted_packets = sorted(buffer, key=lambda p: p["timestamp"])

        timestamps = [p["timestamp"] for p in sorted_packets]
        fire_values = [p["scores"]["fire_dominance"] for p in sorted_packets]

        time_span = timestamps[-1] - timestamps[0]

        if time_span < 0.5:  # Less than 500ms of data
            return TrendResult(
                trend_tag="UNKNOWN",
                growth_rate=0.0,
                sample_count=len(sorted_packets),
                time_span=time_span
            )

        # Linear regression slope
        growth_rate = self._linear_regression_slope(timestamps, fire_values)

        # Classify trend based on thresholds from RAG.MD 3.4.2
        if growth_rate > 0.10:
            trend_tag = "RAPID_GROWTH"
        elif growth_rate > 0.02:
            trend_tag = "GROWING"
        elif growth_rate < -0.05:
            trend_tag = "DIMINISHING"
        else:  # -0.05 to 0.02 range
            trend_tag = "STABLE"

        return TrendResult(
            trend_tag=trend_tag,
            growth_rate=round(growth_rate, 4),
            sample_count=len(sorted_packets),
            time_span=round(time_span, 2)
        )

    def _linear_regression_slope(self, x_values: List[float], y_values: List[float]) -> float:
        """
        Compute slope of best-fit line using least squares regression.

        Formula: slope = Σ((x - x_mean)(y - y_mean)) / Σ((x - x_mean)²)
        """
        n = len(x_values)
        x_mean = sum(x_values) / n
        y_mean = sum(y_values) / n

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)

        if denominator == 0:
            return 0.0  # All timestamps identical (shouldn't happen)

        return numerator / denominator
