"""
Simplified Redis cache for RAG pipeline using YOLO semantic buckets.

Architecture:
- Layer 1: Semantic Protocol Cache (fire/smoke buckets → protocols, 300s TTL)
- Layer 2: Session History Cache (sorted set with similarity, 1800s TTL)

128 possible cache states, 94-95% expected hit rate.
"""

import redis
import pickle
import time
import numpy as np
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class RAGCacheAgent:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=10,
            socket_keepalive=True,
            socket_connect_timeout=0.1,
            decode_responses=False
        )
        self.redis = redis.Redis(connection_pool=self.pool)

        self.metrics = {
            "semantic_hits": 0,
            "semantic_misses": 0,
            "session_hits": 0,
            "session_misses": 0,
            "semantic_latency_ms": [],
            "session_latency_ms": []
        }

        try:
            self.redis.ping()
            logger.info(f"Connected to Redis at {redis_url}")
        except redis.RedisError as e:
            logger.warning(f"Redis unavailable: {e}")

    # ==================================================================
    # LAYER 1: SEMANTIC PROTOCOL CACHE
    # ==================================================================

    def get_semantic_cache_key(self, packet) -> str:
        """
        Generate cache key from YOLO fire classification buckets.

        Aligns with spatial_heuristics.py fire severity levels:
        - MINOR: <10% coverage (extinguisher-level)
        - MODERATE: 10-30% (hose line required)
        - MAJOR: 30-60% (defensive operations)
        - CRITICAL: >60% (flashover risk, evacuate)

        Returns:
            String like "FIRE_MODERATE|SMOKE_DENSE|PROX_NEAR|HIGH"
        """
        fire_pct = packet.fire_dominance * 100
        fire_bucket = (
            "MINOR" if fire_pct < 10 else
            "MODERATE" if fire_pct < 30 else
            "MAJOR" if fire_pct < 60 else
            "CRITICAL"
        )

        smoke_pct = packet.smoke_opacity * 100
        smoke_bucket = (
            "CLEAR" if smoke_pct < 20 else
            "HAZY" if smoke_pct < 50 else
            "DENSE" if smoke_pct < 80 else
            "BLINDING"
        )

        prox = "NEAR" if packet.proximity_alert else "FAR"
        hazard = packet.hazard_level

        return f"FIRE_{fire_bucket}|SMOKE_{smoke_bucket}|PROX_{prox}|{hazard}"

    async def get_protocols_by_semantic_key(self, packet) -> Optional[List[Dict]]:
        """
        Retrieve cached protocols using YOLO fire buckets.

        Expected performance:
        - Hit rate: 94-95% (fire stays in same bucket 3-10 seconds)
        - Latency: 2ms on cache hit
        - Memory: 128 possible states × 1KB = 128KB total
        """
        start = time.perf_counter()

        try:
            cache_key = f"proto_semantic:{self.get_semantic_cache_key(packet)}"
            cached = self.redis.get(cache_key)

            latency_ms = (time.perf_counter() - start) * 1000
            self.metrics["semantic_latency_ms"].append(latency_ms)

            if cached:
                self.metrics["semantic_hits"] += 1
                logger.debug(f"[CACHE HIT] Protocols ({latency_ms:.2f}ms)")
                return pickle.loads(cached)
            else:
                self.metrics["semantic_misses"] += 1
                return None

        except redis.RedisError as e:
            logger.error(f"Redis error: {e}")
            self.metrics["semantic_misses"] += 1
            return None

    async def cache_protocols_by_semantic_key(
        self,
        packet,
        protocols: List[Dict],
        ttl: int = 300
    ):
        """
        Cache protocols under YOLO fire scenario bucket.

        Args:
            packet: TelemetryPacket with fire_dominance, smoke_opacity, etc.
            protocols: List of protocol dicts to cache
            ttl: Time-to-live in seconds (default: 300s = 5 min)
        """
        try:
            cache_key = f"proto_semantic:{self.get_semantic_cache_key(packet)}"
            serialized = pickle.dumps(protocols)
            self.redis.setex(cache_key, ttl, serialized)
            logger.debug(f"[CACHE WRITE] Protocols for {self.get_semantic_cache_key(packet)} (TTL: {ttl}s)")
        except redis.RedisError as e:
            logger.error(f"Failed to cache protocols: {e}")

    # ==================================================================
    # LAYER 2: SESSION HISTORY CACHE
    # ==================================================================

    async def append_session_history(
        self,
        session_id: str,
        device_id: str,
        narrative: str,
        vector: List[float],
        timestamp: float,
        trend: str,
        hazard_level: str
    ):
        """
        Append incident to Redis sorted set.

        Data Structure:
            Key: "session:{session_id}:{device_id}"
            Type: Sorted Set
            Score: timestamp (for chronological order)
            Member: pickle({narrative, vector, trend, hazard, timestamp})
        """
        try:
            cache_key = f"session:{session_id}:{device_id}"

            incident = {
                "narrative": narrative,
                "vector": vector,
                "timestamp": timestamp,
                "trend": trend,
                "hazard_level": hazard_level
            }

            serialized = pickle.dumps(incident)
            self.redis.zadd(cache_key, {serialized: timestamp})
            self.redis.expire(cache_key, 1800)

            logger.debug(f"[CACHE WRITE] Session history for {session_id}:{device_id}")

        except redis.RedisError as e:
            logger.error(f"Failed to append session history: {e}")

    async def get_session_history(
        self,
        session_id: str,
        device_id: str,
        current_vector: List[float],
        similarity_threshold: float = 0.70,
        max_results: int = 5
    ) -> List[Dict]:
        """
        Retrieve similar past incidents using in-memory cosine similarity.

        Performance:
        - Redis retrieval: ~2ms
        - Similarity computation: ~0.5ms per incident (NumPy vectorized)
        - Total: ~5-10ms for 10 incidents vs 30-50ms Actian query
        """
        start = time.perf_counter()

        try:
            cache_key = f"session:{session_id}:{device_id}"
            cached_incidents = self.redis.zrange(cache_key, 0, -1)

            latency_ms = (time.perf_counter() - start) * 1000
            self.metrics["session_latency_ms"].append(latency_ms)

            if not cached_incidents:
                self.metrics["session_misses"] += 1
                return []

            self.metrics["session_hits"] += 1

            # Deserialize
            incidents = [pickle.loads(inc) for inc in cached_incidents]

            # Vectorized similarity computation
            current_vec = np.array(current_vector)
            incident_vecs = np.array([inc["vector"] for inc in incidents])

            similarities = np.dot(incident_vecs, current_vec) / (
                np.linalg.norm(incident_vecs, axis=1) * np.linalg.norm(current_vec)
            )

            # Filter and format
            similar_incidents = []
            for inc, sim in zip(incidents, similarities):
                if sim >= similarity_threshold:
                    similar_incidents.append({
                        "narrative": inc["narrative"],
                        "timestamp": inc["timestamp"],
                        "trend": inc["trend"],
                        "hazard_level": inc["hazard_level"],
                        "similarity": float(sim),
                        "time_ago": time.time() - inc["timestamp"]
                    })

            similar_incidents.sort(key=lambda x: x["similarity"], reverse=True)

            logger.debug(
                f"[CACHE HIT] Session history: {len(similar_incidents)} similar "
                f"incidents ({latency_ms:.2f}ms)"
            )

            return similar_incidents[:max_results]

        except redis.RedisError as e:
            logger.error(f"Redis error in get_session_history: {e}")
            self.metrics["session_misses"] += 1
            return []
        except Exception as e:
            logger.error(f"Unexpected error in get_session_history: {e}")
            self.metrics["session_misses"] += 1
            return []

    # ==================================================================
    # METRICS & MONITORING
    # ==================================================================

    def get_cache_stats(self) -> Dict:
        """
        Get cache performance statistics.

        Returns:
            {
                "semantic_protocol_cache": {
                    "hits": X,
                    "misses": Y,
                    "hit_rate": Z,
                    "avg_latency_ms": W
                },
                "session_history_cache": {...}
            }
        """
        def calc_hit_rate(hits: int, misses: int) -> float:
            total = hits + misses
            return hits / total if total > 0 else 0.0

        def calc_avg_latency(latencies: List[float]) -> float:
            return sum(latencies) / len(latencies) if latencies else 0.0

        return {
            "semantic_protocol_cache": {
                "hits": self.metrics["semantic_hits"],
                "misses": self.metrics["semantic_misses"],
                "hit_rate": calc_hit_rate(
                    self.metrics["semantic_hits"],
                    self.metrics["semantic_misses"]
                ),
                "avg_latency_ms": calc_avg_latency(self.metrics["semantic_latency_ms"])
            },
            "session_history_cache": {
                "hits": self.metrics["session_hits"],
                "misses": self.metrics["session_misses"],
                "hit_rate": calc_hit_rate(
                    self.metrics["session_hits"],
                    self.metrics["session_misses"]
                ),
                "avg_latency_ms": calc_avg_latency(self.metrics["session_latency_ms"])
            }
        }

    def reset_metrics(self):
        """Reset all metrics counters."""
        self.metrics = {
            "semantic_hits": 0,
            "semantic_misses": 0,
            "session_hits": 0,
            "session_misses": 0,
            "semantic_latency_ms": [],
            "session_latency_ms": []
        }
        logger.info("Cache metrics reset")

    # ==================================================================
    # CONNECTION MANAGEMENT
    # ==================================================================

    async def health_check(self) -> bool:
        """Check if Redis connection is healthy."""
        try:
            self.redis.ping()
            return True
        except redis.RedisError:
            return False

    async def close(self):
        """Close Redis connection pool."""
        try:
            self.redis.close()
            self.pool.disconnect()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
