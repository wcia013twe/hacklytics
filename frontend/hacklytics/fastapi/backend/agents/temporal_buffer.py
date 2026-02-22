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

    Priority Queue System (Problem 3):
    - CRITICAL events (explosion, trapped, spread): 30s retention
    - SAFE events (clear, stable, contained): 5s retention
    - CAUTION events (smoke, moderate): 10s retention (default)
    """

    # Priority-based TTL configuration
    PRIORITY_TTL = {
        "CRITICAL": 30.0,  # Critical events stay longer
        "CAUTION": 10.0,   # Medium priority events (default)
        "SAFE": 5.0        # Safe events expire quickly
    }

    # Keywords for auto-classification
    CRITICAL_KEYWORDS = ["explosion", "trapped", "spread", "flashover", "collapse"]
    SAFE_KEYWORDS = ["clear", "stable", "contained", "suppressed", "extinguished"]

    def __init__(self, window_seconds: float = 10.0):
        self.buffers: Dict[str, deque] = {}
        self.window_seconds = window_seconds
        self.last_eviction_time: Dict[str, float] = {}

        # Metrics for observability
        self.metrics = {
            "avg_narrative_length": [],
            "compression_ratio": [],
            "critical_events_retained": 0,
            "total_events_processed": 0
        }

    def _classify_priority(self, packet: TelemetryPacket) -> str:
        """
        Auto-classify packet priority based on hazard level and narrative keywords.

        Priority Rules:
        1. CRITICAL: hazard_level=CRITICAL OR contains critical keywords
        2. SAFE: hazard_level=CLEAR/LOW OR contains safe keywords
        3. CAUTION: Everything else (default)
        """
        # Use explicit priority if provided
        if packet.priority:
            return packet.priority

        narrative_lower = packet.visual_narrative.lower()

        # Check for critical keywords or hazard level
        if packet.hazard_level == "CRITICAL" or any(kw in narrative_lower for kw in self.CRITICAL_KEYWORDS):
            return "CRITICAL"

        # Check for safe keywords or low hazard level
        if packet.hazard_level in ["CLEAR", "LOW"] or any(kw in narrative_lower for kw in self.SAFE_KEYWORDS):
            return "SAFE"

        # Default to CAUTION for MODERATE/HIGH
        return "CAUTION"

    async def insert_packet(self, device_id: str, packet: TelemetryPacket) -> Dict:
        """
        Task 2.1: Insert packet with out-of-order handling and priority classification.

        Handles WiFi jitter by maintaining chronological order.
        Discards packets older than priority-based retention window.
        """
        if device_id not in self.buffers:
            self.buffers[device_id] = deque()
            self.last_eviction_time[device_id] = time.time()

        buffer = self.buffers[device_id]
        packet_time = packet.timestamp
        current_time = time.time()

        # Auto-classify priority
        priority = self._classify_priority(packet)
        ttl = self.PRIORITY_TTL[priority]

        # Track metrics
        self.metrics["total_events_processed"] += 1
        if priority == "CRITICAL":
            self.metrics["critical_events_retained"] += 1

        # Discard packets outside priority-based retention window
        if current_time - packet_time > ttl:
            return {
                "inserted": False,
                "reason": "too_old",
                "buffer_size": len(buffer),
                "priority": priority,
                "ttl": ttl
            }

        # Evict stale packets first
        await self.evict_stale(device_id, current_time)

        # Insert packet in chronological order with priority metadata
        packet_dict = {
            "timestamp": packet_time,
            "scores": packet.scores.dict(),
            "packet": packet,
            "priority": priority,
            "ttl": ttl,
            "expires_at": packet_time + ttl
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
            "out_of_order": packet_time < buffer[-1]["timestamp"] if len(buffer) > 1 else False,
            "priority": priority,
            "ttl": ttl
        }

    async def evict_stale(self, device_id: str, current_time: float) -> Dict:
        """
        Task 2.2: Evict stale packets using priority-based TTL.

        Lazy eviction on access (not background timer).
        Uses expires_at field to determine if packet should be evicted.
        """
        if device_id not in self.buffers:
            return {"evicted_count": 0, "buffer_size": 0}

        buffer = self.buffers[device_id]
        evicted = 0
        evicted_by_priority = {"CRITICAL": 0, "CAUTION": 0, "SAFE": 0}

        # Remove from left (oldest) until we hit a non-expired one
        while buffer and buffer[0].get("expires_at", buffer[0]["timestamp"] + self.window_seconds) < current_time:
            evicted_packet = buffer.popleft()
            evicted += 1
            priority = evicted_packet.get("priority", "CAUTION")
            evicted_by_priority[priority] += 1

        self.last_eviction_time[device_id] = current_time

        return {
            "evicted_count": evicted,
            "buffer_size": len(buffer),
            "evicted_by_priority": evicted_by_priority
        }

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

    def _calculate_decay_weight(self, packet_age: float, priority: str) -> float:
        """
        Calculate decay weight for narrative generation based on packet age and priority.

        Decay Rules:
        - Recent events (last 3s): weight = 1.0
        - Mid-age events (3-10s): weight = 0.5
        - Old critical events (10-30s): weight = 0.3
        - Old non-critical events (>10s): weight = 0.1
        """
        if packet_age <= 3.0:
            return 1.0
        elif packet_age <= 10.0:
            return 0.5
        elif priority == "CRITICAL":
            return 0.3
        else:
            return 0.1

    async def compress_narrative(self, packets: List[Dict], max_chars: int = 500) -> Dict:
        """
        Compress visual narratives to max_chars, prioritizing critical and recent events.

        Algorithm:
        1. Apply decay weights to all packets
        2. Sort by weight (descending)
        3. Build narrative until max_chars limit
        4. Truncate oldest non-critical first if needed

        Returns:
            {
                "narrative": str,
                "original_length": int,
                "compressed_length": int,
                "compression_ratio": float,
                "events_included": int,
                "events_excluded": int,
                "critical_events_retained": int
            }
        """
        if not packets:
            return {
                "narrative": "",
                "original_length": 0,
                "compressed_length": 0,
                "compression_ratio": 1.0,
                "events_included": 0,
                "events_excluded": 0,
                "critical_events_retained": 0
            }

        current_time = time.time()

        # Calculate weights for each packet
        weighted_packets = []
        for pkt in packets:
            packet_age = current_time - pkt["timestamp"]
            priority = pkt.get("priority", "CAUTION")
            weight = self._calculate_decay_weight(packet_age, priority)

            weighted_packets.append({
                "narrative": pkt["packet"].visual_narrative,
                "weight": weight,
                "priority": priority,
                "timestamp": pkt["timestamp"],
                "age": packet_age
            })

        # Sort by weight (descending), then by recency (descending)
        weighted_packets.sort(key=lambda x: (x["weight"], -x["age"]), reverse=True)

        # Build compressed narrative
        narrative_parts = []
        total_length = 0
        events_included = 0
        events_excluded = 0
        critical_retained = 0

        for pkt in weighted_packets:
            narrative_text = pkt["narrative"]
            # Add age context for older events
            if pkt["age"] > 5.0:
                age_str = f"{int(pkt['age'])}s ago: "
                narrative_text = age_str + narrative_text

            potential_length = total_length + len(narrative_text) + 3  # +3 for "... "

            if potential_length <= max_chars:
                narrative_parts.append(narrative_text)
                total_length = potential_length
                events_included += 1
                if pkt["priority"] == "CRITICAL":
                    critical_retained += 1
            else:
                events_excluded += 1

        # Join narratives with separator
        compressed_narrative = "... ".join(narrative_parts)

        # Calculate original length
        original_narrative = "... ".join([p["packet"].visual_narrative for p in packets])
        original_length = len(original_narrative)
        compressed_length = len(compressed_narrative)

        # Update metrics
        self.metrics["avg_narrative_length"].append(compressed_length)
        if original_length > 0:
            compression_ratio = compressed_length / original_length
            self.metrics["compression_ratio"].append(compression_ratio)
        else:
            compression_ratio = 1.0

        return {
            "narrative": compressed_narrative,
            "original_length": original_length,
            "compressed_length": compressed_length,
            "compression_ratio": round(compression_ratio, 3),
            "events_included": events_included,
            "events_excluded": events_excluded,
            "critical_events_retained": critical_retained
        }

    def get_metrics_summary(self) -> Dict:
        """
        Get summary of buffer metrics for observability.

        Returns:
            {
                "avg_narrative_length": float,
                "avg_compression_ratio": float,
                "critical_events_retained": int,
                "total_events_processed": int
            }
        """
        avg_length = sum(self.metrics["avg_narrative_length"]) / len(self.metrics["avg_narrative_length"]) \
            if self.metrics["avg_narrative_length"] else 0.0

        avg_compression = sum(self.metrics["compression_ratio"]) / len(self.metrics["compression_ratio"]) \
            if self.metrics["compression_ratio"] else 1.0

        return {
            "avg_narrative_length": round(avg_length, 2),
            "avg_compression_ratio": round(avg_compression, 3),
            "critical_events_retained": self.metrics["critical_events_retained"],
            "total_events_processed": self.metrics["total_events_processed"]
        }
