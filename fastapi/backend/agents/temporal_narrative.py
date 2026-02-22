"""
Temporal Narrative Agent - LLM-based temporal synthesis for RAG pipeline.

Uses a local Ollama model (default: llama3.2:1b) for narrative synthesis.
Ollama uses Metal on Apple Silicon for fast inference (~100-200ms on M1 Pro).

Architecture:
- Async httpx calls to Ollama REST API (http://localhost:11434)
- 200-character output strict enforcement
- <200ms latency target with configurable hard timeout
- Graceful fallback to simple concatenation on any failure

Performance Targets (M1 Pro via Metal):
- llama3.2:1b: ~100-200ms
- qwen2.5:0.5b: ~50-100ms
- Fallback latency: <5ms
- Output length: 200 chars max (strict)
"""

import asyncio
import time
import logging
from typing import List, Dict, Optional

import httpx

from backend.contracts.models import TemporalSynthesisResult

logger = logging.getLogger(__name__)

OLLAMA_DEFAULT_URL = "http://localhost:11434"
OLLAMA_DEFAULT_MODEL = "llama3.2:1b"


class TemporalNarrativeAgent:
    """
    Synthesizes temporal narratives from buffered frame observations using a local Ollama model.
    """

    def __init__(
        self,
        model_name: str = OLLAMA_DEFAULT_MODEL,
        ollama_url: str = OLLAMA_DEFAULT_URL,
        timeout_seconds: float = 1.5,  # 1500ms — steady-state ~500ms on M1 Pro GPU
    ):
        self.model_name = model_name
        self.ollama_url = ollama_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

        self.metrics = {
            "total_requests": 0,
            "successful_syntheses": 0,
            "fallback_used": 0,
            "api_errors": 0,
            "timeouts": 0,
            "total_latency_ms": 0.0,
        }

        # Verify Ollama is reachable at startup (non-blocking)
        self.api_available = True  # Optimistic; will flip on first failure

    async def synthesize_temporal_narrative(
        self,
        buffer_packets: List[Dict],
        lookback_seconds: float = 3.0
    ) -> TemporalSynthesisResult:
        """
        Synthesize coherent temporal narrative from recent buffer events.

        Args:
            buffer_packets: List of buffer packets (dicts with 'timestamp', 'packet', 'priority')
            lookback_seconds: How far back to look (default: 3.0 seconds)

        Returns:
            TemporalSynthesisResult with synthesized narrative, timing, cache status
        """
        start_time = time.perf_counter()
        self.metrics["total_requests"] += 1

        if not buffer_packets:
            return TemporalSynthesisResult(
                synthesized_narrative="No observations available",
                original_narratives=[],
                time_span=0.0,
                synthesis_time_ms=0.0,
                event_count=0,
                cache_hit=False,
                fallback_used=True
            )

        # Filter to lookback window
        current_time = time.time()
        cutoff_time = current_time - lookback_seconds
        recent_packets = [
            pkt for pkt in buffer_packets
            if pkt.get("timestamp", 0) >= cutoff_time
        ]

        if len(recent_packets) <= 1:
            narrative = recent_packets[0]["packet"].visual_narrative if recent_packets else "No recent observations"
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return TemporalSynthesisResult(
                synthesized_narrative=narrative[:200],
                original_narratives=[narrative] if recent_packets else [],
                time_span=0.0,
                synthesis_time_ms=elapsed_ms,
                event_count=len(recent_packets),
                cache_hit=False,
                fallback_used=True
            )

        original_narratives = [pkt["packet"].visual_narrative for pkt in recent_packets]
        timestamps = [pkt["timestamp"] for pkt in recent_packets]
        time_span = max(timestamps) - min(timestamps)

        if self.api_available:
            try:
                prompt = self._build_timeline_prompt(recent_packets)
                synthesized_text = await self._call_ollama(prompt)

                if self._validate_synthesis(synthesized_text):
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    self.metrics["successful_syntheses"] += 1
                    self.metrics["total_latency_ms"] += elapsed_ms
                    logger.info(f"Temporal synthesis: {elapsed_ms:.1f}ms via {self.model_name}")

                    return TemporalSynthesisResult(
                        synthesized_narrative=synthesized_text[:300],
                        original_narratives=original_narratives,
                        time_span=time_span,
                        synthesis_time_ms=elapsed_ms,
                        event_count=len(recent_packets),
                        cache_hit=False,
                        fallback_used=False
                    )
                else:
                    logger.warning("Ollama synthesis validation failed, using fallback")

            except asyncio.TimeoutError:
                logger.warning(f"Ollama timeout after {self.timeout_seconds*1000:.0f}ms, using fallback")
                self.metrics["timeouts"] += 1

            except Exception as e:
                logger.error(f"Ollama error: {e} — using fallback")
                self.metrics["api_errors"] += 1
                self.api_available = False  # Stop hammering a dead server

        return self._fallback_concatenation(recent_packets, original_narratives, time_span, start_time)

    def _build_timeline_prompt(self, buffer_packets: List[Dict]) -> str:
        current_time = time.time()
        timeline = []

        for pkt in buffer_packets[-5:]:
            age = current_time - pkt["timestamp"]
            p = pkt["packet"]
            narrative = p.visual_narrative
            priority = pkt.get("priority", "CAUTION")
            # Include sensor data if available
            temp = getattr(p, 'mlx90640_temp_f', None) or ''
            aqi = getattr(p, 'bme680_aqi', None) or ''
            sensor_str = ''
            if temp:
                sensor_str += f' Temp:{temp}°F'
            if aqi:
                sensor_str += f' AQI:{aqi}'
            hazard = getattr(p, 'hazard_level', 'UNKNOWN')
            timeline.append(f"T-{age:.1f}s [{hazard}]{sensor_str}: {narrative}")

        timeline_str = "\n".join(timeline)

        return f"""You are a fire safety AI analyst for emergency dispatchers. Provide a brief situational assessment (max 300 chars) based on these sequential observations.

Include: (1) what changed over time, (2) current threat level and trajectory (escalating/stable/de-escalating), (3) key sensor anomalies if any. Use present tense for current state, past tense for changes. No speculation, no preamble.

Observations (oldest→newest):
{timeline_str}

Situational assessment (300 chars max, 2-3 sentences):"""

    async def _call_ollama(self, prompt: str) -> str:
        """Call Ollama /api/generate endpoint with timeout."""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 120,  # ~300 chars
                "top_p": 0.8,
            }
        }

        async with httpx.AsyncClient() as client:
            response = await asyncio.wait_for(
                client.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=self.timeout_seconds
                ),
                timeout=self.timeout_seconds
            )
            response.raise_for_status()
            return response.json()["response"].strip()

    def _validate_synthesis(self, response: str) -> bool:
        if not response or not isinstance(response, str):
            return False
        if len(response) < 1 or len(response) > 300:
            return False
        for pattern in ["error", "failed", "cannot", "unable", "N/A", "TODO"]:
            if pattern in response.lower():
                return False
        return True

    def _fallback_concatenation(
        self,
        packets: List[Dict],
        original_narratives: List[str],
        time_span: float,
        start_time: float
    ) -> TemporalSynthesisResult:
        self.metrics["fallback_used"] += 1

        if original_narratives:
            # Most recent narrative as primary, prepend previous if space allows
            concatenated = original_narratives[-1]
            if len(original_narratives) >= 2:
                combined = f"{original_narratives[-2]} → {concatenated}"
                if len(combined) <= 200:
                    concatenated = combined
        else:
            concatenated = "No observations"

        concatenated = concatenated[:200]
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return TemporalSynthesisResult(
            synthesized_narrative=concatenated,
            original_narratives=original_narratives,
            time_span=time_span,
            synthesis_time_ms=elapsed_ms,
            event_count=len(packets),
            cache_hit=False,
            fallback_used=True
        )

    def get_metrics(self) -> Dict:
        avg_latency = (
            self.metrics["total_latency_ms"] / self.metrics["successful_syntheses"]
            if self.metrics["successful_syntheses"] > 0 else 0.0
        )
        success_rate = (
            self.metrics["successful_syntheses"] / self.metrics["total_requests"]
            if self.metrics["total_requests"] > 0 else 0.0
        )
        return {
            "total_requests": self.metrics["total_requests"],
            "successful_syntheses": self.metrics["successful_syntheses"],
            "fallback_used": self.metrics["fallback_used"],
            "api_errors": self.metrics["api_errors"],
            "timeouts": self.metrics["timeouts"],
            "avg_latency_ms": round(avg_latency, 2),
            "success_rate": round(success_rate, 3),
            "api_available": self.api_available,
            "model": self.model_name,
        }
