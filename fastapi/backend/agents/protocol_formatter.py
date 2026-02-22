import asyncio
import time
import logging
import json
from typing import List, Dict

import httpx
from backend.contracts.models import FormatterResult, ActionCommand, Protocol, TelemetryPacket

logger = logging.getLogger(__name__)

OLLAMA_DEFAULT_URL = "http://localhost:11434"
OLLAMA_DEFAULT_MODEL = "llama3.2:1b"

FORMATTER_SYSTEM_PROMPT = """You are a fire fire incident commander AI.
Given a retrieved ERG protocol and live scene data, output ONLY valid JSON — no preamble, no markdown.
Ground every command in the specific objects present (use IDs if given).
Keep directives short: imperative, ≤12 words each."""

class ProtocolFormatterAgent:
    """
    Formats raw RAG protocol text into structured WebSocketPayload fields
    using a local Ollama model.
    """

    def __init__(
        self,
        model_name: str = OLLAMA_DEFAULT_MODEL,
        ollama_url: str = OLLAMA_DEFAULT_URL,
        timeout_seconds: float = 10.0,
    ):
        self.model_name = model_name
        self.ollama_url = ollama_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

        self.metrics = {
            "total_requests": 0,
            "successful_formats": 0,
            "fallback_used": 0,
            "api_errors": 0,
            "timeouts": 0,
            "total_latency_ms": 0.0,
        }

        self.api_available = True

    async def format(
        self,
        protocol: Protocol,
        packet: TelemetryPacket,
        synthesized_narrative: str,
    ) -> FormatterResult:
        """
        Formats raw protocol text into a structured JSON string containing actionable components.
        """
        start_time = time.perf_counter()
        self.metrics["total_requests"] += 1

        if self.api_available:
            try:
                prompt = self._build_formatter_prompt(
                    protocol.protocol_text,
                    packet.hazard_level,
                    synthesized_narrative,
                    [obj.dict() for obj in packet.tracked_objects],
                    protocol.source
                )
                formatted_response = await self._call_ollama(prompt)
                logger.info(f"Ollama raw response: {formatted_response[:500]}...")
                
                try:
                    # Clean up response (sometimes Ollama wraps json in markdown block randomly)
                    if formatted_response.startswith('```json'):
                        formatted_response = formatted_response[7:]
                    elif formatted_response.startswith('```'):
                        formatted_response = formatted_response[3:]
                    
                    if formatted_response.endswith('```'):
                        formatted_response = formatted_response[:-3]
                    
                    formatted_response = formatted_response.strip()
                    logger.debug(f"Ollama cleaned response: {formatted_response}")

                    parsed = json.loads(formatted_response)
                    
                    commands = []
                    for cmd in parsed.get("actionable_commands", []):
                        commands.append(ActionCommand(
                            target=cmd.get("target", "All Units"),
                            directive=cmd.get("directive", "Maintain safety")
                        ))
                    
                    result = FormatterResult(
                        action_command=parsed.get("action_command", "No immediate action specified")[:150], # Ensure sanity length
                        action_reason=parsed.get("action_reason", "Reason not specified")[:250],
                        hazard_type=parsed.get("hazard_type", protocol.category),
                        source_text=parsed.get("source_text", protocol.protocol_text[:300]),
                        actionable_commands=commands,
                        fallback_used=False
                    )

                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    self.metrics["successful_formats"] += 1
                    self.metrics["total_latency_ms"] += elapsed_ms
                    logger.info(f"Protocol formatting: {elapsed_ms:.1f}ms via {self.model_name}")

                    return result

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse Ollama JSON output: {e}, Output was: {formatted_response}")
                    # Let it fall through to fallback

            except asyncio.TimeoutError:
                logger.warning(f"Ollama timeout after {self.timeout_seconds*1000:.0f}ms in ProtocolFormatterAgent, using fallback")
                self.metrics["timeouts"] += 1

            except Exception as e:
                logger.error(f"Ollama error in ProtocolFormatterAgent: {e} — using fallback")
                self.metrics["api_errors"] += 1
                # Don't permanently disable — Ollama may recover on the next packet

        # Fallback
        return self._fallback_formatter(protocol, synthesized_narrative, start_time)

    def _build_formatter_prompt(
        self,
        protocol_text: str,
        hazard_level: str,
        visual_narrative: str,
        tracked_objects: list,
        source: str,
    ) -> str:
        objects_str = ", ".join(
            f"{o.get('label', 'unknown')} #{o.get('id', 'N/A')} ({o.get('status', 'unknown')})" for o in tracked_objects
        ) or "none"

        # Trim protocol to first 600 chars to stay within context window
        protocol_excerpt = protocol_text[:600].strip()

        return f"""{FORMATTER_SYSTEM_PROMPT}

Scene: {hazard_level} — {visual_narrative}
Detected: {objects_str}
Source: {source}

ERG Protocol (excerpt):
{protocol_excerpt}

Output JSON only:
{{
  "action_command": "<primary directive, ≤15 words>",
  "action_reason": "<ERG reference + scene fact, ≤25 words>",
  "hazard_type": "<ERG hazard class name>",
  "source_text": "<key excerpt, ≤3 sentences>",
  "actionable_commands": [
    {{"target": "<who>", "directive": "<what, ≤12 words>"}},
    {{"target": "<who>", "directive": "<what, ≤12 words>"}}
  ]
}}"""

    async def _call_ollama(self, prompt: str) -> str:
        """Call Ollama /api/generate endpoint with timeout."""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Lower temperature for formatting
                "num_predict": 500,   # Enough headroom for full JSON payload
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

    def _fallback_formatter(
        self,
        protocol: Protocol,
        synthesized_narrative: str,
        start_time: float
    ) -> FormatterResult:
        self.metrics["fallback_used"] += 1
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        # Define generic fallback commands based on hazard level if possible
        fallback_commands = [
            ActionCommand(target="Incident Commander", directive="Review ERG Guide " + protocol.source),
            ActionCommand(target="First Responders", directive="Establish isolation zone per " + protocol.category)
        ]

        # action_command will be populated from Synthesis recommendation in orchestrator
        return FormatterResult(
            action_command="Follow standard procedures",  # Overwritten in orchestrator
            action_reason=synthesized_narrative[:250],
            hazard_type=protocol.category,
            source_text=protocol.protocol_text[:300],
            actionable_commands=fallback_commands,
            fallback_used=True
        )

    def get_metrics(self) -> Dict:
        avg_latency = (
            self.metrics["total_latency_ms"] / self.metrics["successful_formats"]
            if self.metrics["successful_formats"] > 0 else 0.0
        )
        success_rate = (
            self.metrics["successful_formats"] / self.metrics["total_requests"]
            if self.metrics["total_requests"] > 0 else 0.0
        )
        return {
            "total_requests": self.metrics["total_requests"],
            "successful_formats": self.metrics["successful_formats"],
            "fallback_used": self.metrics["fallback_used"],
            "api_errors": self.metrics["api_errors"],
            "timeouts": self.metrics["timeouts"],
            "avg_latency_ms": round(avg_latency, 2),
            "success_rate": round(success_rate, 3),
            "api_available": self.api_available,
            "model": self.model_name,
        }
