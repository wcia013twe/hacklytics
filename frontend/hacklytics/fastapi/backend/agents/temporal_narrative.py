"""
Temporal Narrative Agent - LLM-based temporal synthesis for RAG pipeline.

This agent uses Google Gemini Flash to synthesize 3-5 seconds of buffered
frame narratives into coherent temporal stories that capture:
- Fire progression patterns (escalation, suppression)
- Temporal context (how things changed over time)
- Safety-critical trajectories (flashover patterns, etc.)

Architecture:
- Async Gemini API integration with google-generativeai library
- Exponential backoff retry (3 attempts max)
- 200-character output strict enforcement
- <150ms latency target with 200ms hard timeout
- Graceful fallback to simple concatenation on any failure

Performance Targets:
- P95 latency: <150ms
- Fallback latency: <5ms
- Output length: 200 chars max (strict)

Safety:
- All API failures degrade gracefully to concatenation
- No crashes on malformed input
- Detailed logging for debugging
"""

import asyncio
import time
import logging
from typing import List, Dict, Optional
import google.generativeai as genai

from backend.contracts.models import TemporalSynthesisResult

logger = logging.getLogger(__name__)


class TemporalNarrativeAgent:
    """
    Synthesizes temporal narratives from buffered frame observations using Gemini Flash.

    Key Features:
    - Async API calls with timeout enforcement
    - Exponential backoff retry logic
    - 200-character strict output limit
    - Graceful fallback on any error
    - Performance metrics tracking
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-1.5-flash-002",
        max_tokens: int = 100,
        temperature: float = 0.3
    ):
        """
        Initialize Gemini client with optimized configuration.

        Args:
            api_key: Google Gemini API key
            model_name: Gemini model to use (default: gemini-1.5-flash-002)
            max_tokens: Maximum output tokens (default: 100 ≈ 200 chars)
            temperature: Temperature for generation (default: 0.3 for consistency)
        """
        if not api_key:
            logger.warning("No Gemini API key provided - will always use fallback concatenation")
            self.model = None
            self.api_available = False
        else:
            try:
                genai.configure(api_key=api_key)

                # Optimized generation config for low latency
                self.generation_config = {
                    "temperature": temperature,
                    "top_p": 0.8,
                    "top_k": 20,
                    "max_output_tokens": max_tokens,
                    "candidate_count": 1,
                }

                # Safety settings (permissive for fire safety domain)
                self.safety_settings = [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_NONE"
                    },
                ]

                self.model = genai.GenerativeModel(
                    model_name=model_name,
                    generation_config=self.generation_config,
                    safety_settings=self.safety_settings
                )

                self.api_available = True
                logger.info(f"Gemini client initialized: {model_name}")

            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.model = None
                self.api_available = False

        # Performance metrics
        self.metrics = {
            "total_requests": 0,
            "successful_syntheses": 0,
            "fallback_used": 0,
            "api_errors": 0,
            "timeouts": 0,
            "total_latency_ms": 0.0,
        }

        # Retry configuration
        self.max_retries = 3
        self.retry_delays = [0.05, 0.1, 0.2]  # Exponential backoff in seconds

        # Timeout configuration
        self.api_timeout_seconds = 0.2  # 200ms hard timeout

    async def synthesize_temporal_narrative(
        self,
        buffer_packets: List[Dict],
        lookback_seconds: float = 3.0
    ) -> TemporalSynthesisResult:
        """
        Synthesize coherent temporal narrative from recent buffer events.

        Algorithm:
        1. Filter packets to lookback window (3s default)
        2. Build timeline prompt with T-Xs annotations
        3. Call Gemini Flash with strict 200-char limit
        4. Validate output quality
        5. Fallback to concatenation on any failure

        Args:
            buffer_packets: List of buffer packets (dicts with 'timestamp', 'packet', 'priority')
            lookback_seconds: How far back to look (default: 3.0 seconds)

        Returns:
            TemporalSynthesisResult with synthesized narrative, timing, cache status
        """
        start_time = time.perf_counter()
        self.metrics["total_requests"] += 1

        # Handle empty or single-packet case
        if not buffer_packets:
            logger.debug("Empty buffer, returning empty synthesis")
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

        # If only one packet, no synthesis needed
        if len(recent_packets) <= 1:
            if recent_packets:
                narrative = recent_packets[0]["packet"].visual_narrative
                time_span = 0.0
            else:
                narrative = "No recent observations"
                time_span = 0.0

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            return TemporalSynthesisResult(
                synthesized_narrative=narrative[:200],  # Enforce 200-char limit
                original_narratives=[narrative] if recent_packets else [],
                time_span=time_span,
                synthesis_time_ms=elapsed_ms,
                event_count=len(recent_packets),
                cache_hit=False,
                fallback_used=True
            )

        # Extract original narratives
        original_narratives = [
            pkt["packet"].visual_narrative for pkt in recent_packets
        ]

        # Calculate time span
        timestamps = [pkt["timestamp"] for pkt in recent_packets]
        time_span = max(timestamps) - min(timestamps)

        # Try Gemini synthesis if API available
        if self.api_available and self.model:
            try:
                # Build prompt
                prompt = self._build_timeline_prompt(recent_packets)

                # Call Gemini API with retry logic
                synthesized_text = await self._call_gemini_api(prompt)

                # Validate synthesis
                if self._validate_synthesis(synthesized_text):
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    self.metrics["successful_syntheses"] += 1
                    self.metrics["total_latency_ms"] += elapsed_ms

                    logger.info(f"Temporal synthesis completed in {elapsed_ms:.1f}ms: {synthesized_text[:50]}...")

                    return TemporalSynthesisResult(
                        synthesized_narrative=synthesized_text[:200],  # Enforce limit
                        original_narratives=original_narratives,
                        time_span=time_span,
                        synthesis_time_ms=elapsed_ms,
                        event_count=len(recent_packets),
                        cache_hit=False,
                        fallback_used=False
                    )
                else:
                    logger.warning("Gemini synthesis validation failed, using fallback")

            except asyncio.TimeoutError:
                logger.warning(f"Gemini API timeout after {self.api_timeout_seconds*1000}ms, using fallback")
                self.metrics["timeouts"] += 1

            except Exception as e:
                logger.error(f"Gemini API error: {e}, using fallback")
                self.metrics["api_errors"] += 1

        # Fallback to concatenation
        return self._fallback_concatenation(recent_packets, original_narratives, time_span, start_time)

    def _build_timeline_prompt(self, buffer_packets: List[Dict]) -> str:
        """
        Build optimized prompt for Gemini Flash.

        Prompt Engineering Principles:
        1. Clear task definition
        2. Structured input (timeline format)
        3. Explicit constraints (200 chars)
        4. Examples (few-shot)
        5. Output format specification

        Args:
            buffer_packets: Recent buffer packets to synthesize

        Returns:
            Formatted prompt string
        """
        current_time = time.time()
        timeline = []

        for pkt in buffer_packets[-5:]:  # Last 5 packets max
            age = current_time - pkt["timestamp"]
            narrative = pkt["packet"].visual_narrative
            priority = pkt.get("priority", "CAUTION")

            # Format: "T-2.3s [CRITICAL]: Major fire 45%. Path blocked."
            timeline.append(f"T-{age:.1f}s [{priority}]: {narrative}")

        timeline_str = "\n".join(timeline)

        prompt = f"""You are a fire safety AI analyzing temporal fire progression.

INPUT - Observations (oldest → newest):
{timeline_str}

TASK:
Synthesize these observations into ONE coherent narrative that captures:
1. What changed (progression/escalation)
2. Current state
3. Trajectory (pattern)

CONSTRAINTS:
- Maximum 200 characters (STRICT)
- Present tense for current state
- Past tense for progression
- No speculation, only observed facts
- Focus on safety-critical changes

EXAMPLES:

Input:
T-3.0s [CAUTION]: Small fire 8%
T-2.0s [CAUTION]: Moderate fire 22%
T-1.0s [HIGH]: Major fire 38%
T-0.0s [CRITICAL]: Major fire 45%. Path blocked.

Output:
Fire escalated 8%→45% in 3s. Path now blocked. Matches flashover acceleration pattern.

Input:
T-5.0s [CRITICAL]: Fire 68%
T-3.0s [HIGH]: Fire 52%
T-1.0s [CAUTION]: Fire 28%
T-0.0s [CAUTION]: Fire 12%. Suppression active.

Output:
Fire suppressed from 68%→12% over 5s. Now contained and diminishing.

YOUR OUTPUT (200 chars max):"""

        return prompt

    async def _call_gemini_api(self, prompt: str) -> str:
        """
        Call Gemini API with timeout and retry logic.

        Retry Strategy:
        - 3 attempts max
        - Exponential backoff: 50ms, 100ms, 200ms
        - 200ms timeout per attempt

        Args:
            prompt: Formatted prompt string

        Returns:
            Synthesized narrative text

        Raises:
            Exception: If all retries fail
            asyncio.TimeoutError: If timeout exceeded
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # Call with timeout
                response = await asyncio.wait_for(
                    self.model.generate_content_async(prompt),
                    timeout=self.api_timeout_seconds
                )

                # Extract text
                if response and response.text:
                    return response.text.strip()
                else:
                    logger.warning(f"Empty response from Gemini (attempt {attempt + 1})")
                    last_error = Exception("Empty response from Gemini")

            except asyncio.TimeoutError:
                logger.warning(f"Gemini timeout on attempt {attempt + 1}/{self.max_retries}")
                last_error = asyncio.TimeoutError("Gemini API timeout")

                # Don't retry on timeout (already at latency limit)
                raise last_error

            except Exception as e:
                logger.warning(f"Gemini error on attempt {attempt + 1}/{self.max_retries}: {e}")
                last_error = e

                # Wait before retry (exponential backoff)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delays[attempt])

        # All retries failed
        raise last_error

    def _validate_synthesis(self, response: str) -> bool:
        """
        Validate LLM synthesis quality.

        Validation checks:
        1. Non-empty response
        2. Length within bounds (1-200 chars)
        3. No obvious errors or placeholders

        Args:
            response: Synthesized text from Gemini

        Returns:
            True if valid, False otherwise
        """
        if not response or not isinstance(response, str):
            return False

        # Check length
        if len(response) < 1 or len(response) > 200:
            logger.warning(f"Synthesis length out of bounds: {len(response)} chars")
            return False

        # Check for obvious errors
        error_patterns = [
            "error",
            "failed",
            "cannot",
            "unable",
            "N/A",
            "TODO",
            "PLACEHOLDER"
        ]

        response_lower = response.lower()
        for pattern in error_patterns:
            if pattern in response_lower:
                logger.warning(f"Synthesis contains error pattern: {pattern}")
                return False

        return True

    def _fallback_concatenation(
        self,
        packets: List[Dict],
        original_narratives: List[str],
        time_span: float,
        start_time: float
    ) -> TemporalSynthesisResult:
        """
        Safe fallback: concatenate latest narratives.

        Strategy:
        - Take most recent narrative as primary
        - If space allows, prepend previous narrative
        - Always stay within 200-char limit

        Args:
            packets: Buffer packets
            original_narratives: List of original narrative strings
            time_span: Time span in seconds
            start_time: Start time for latency calculation

        Returns:
            TemporalSynthesisResult with concatenated narrative
        """
        self.metrics["fallback_used"] += 1

        # Start with most recent
        if original_narratives:
            concatenated = original_narratives[-1]

            # Try to add previous context if space allows
            if len(original_narratives) >= 2:
                prev = original_narratives[-2]
                combined = f"{prev} → {concatenated}"

                if len(combined) <= 200:
                    concatenated = combined
        else:
            concatenated = "No observations"

        # Enforce 200-char limit
        concatenated = concatenated[:200]

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(f"Fallback concatenation in {elapsed_ms:.1f}ms: {concatenated[:50]}...")

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
        """
        Get performance metrics.

        Returns:
            Dictionary with performance statistics:
            - total_requests: Total synthesis requests
            - successful_syntheses: Successful Gemini calls
            - fallback_used: Times fallback was used
            - api_errors: API errors encountered
            - timeouts: Timeout occurrences
            - avg_latency_ms: Average latency for successful syntheses
            - success_rate: Percentage of successful syntheses
        """
        if self.metrics["successful_syntheses"] > 0:
            avg_latency = self.metrics["total_latency_ms"] / self.metrics["successful_syntheses"]
        else:
            avg_latency = 0.0

        if self.metrics["total_requests"] > 0:
            success_rate = self.metrics["successful_syntheses"] / self.metrics["total_requests"]
        else:
            success_rate = 0.0

        return {
            "total_requests": self.metrics["total_requests"],
            "successful_syntheses": self.metrics["successful_syntheses"],
            "fallback_used": self.metrics["fallback_used"],
            "api_errors": self.metrics["api_errors"],
            "timeouts": self.metrics["timeouts"],
            "avg_latency_ms": round(avg_latency, 2),
            "success_rate": round(success_rate, 3),
            "api_available": self.api_available
        }
