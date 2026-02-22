"""
Safety Guardrails Agent: Physics-based hard constraints for fire emergency recommendations.

PURPOSE:
- Prevent "confident idiot" hallucinations where RAG retrieves wrong protocols
- Block dangerous combinations (water on grease fire, approaching 400C+ fires, etc.)
- Use simple regex/keyword matching for <5ms latency (NO LLM calls)

DESIGN PHILOSOPHY:
- LLMs and Vector Search are probabilistic (find "most similar", not "physically correct")
- Hard-coded physics rules act as final safety net before synthesis
- Better to block a good recommendation than allow a dangerous one
"""

import re
import time
from typing import Optional, Dict, Tuple
from collections import defaultdict

try:
    # Try relative import first (when used as part of package)
    from ..contracts.models import GuardrailResult, TelemetryPacket, RAGRecommendation
except ImportError:
    # Fall back to absolute import (for standalone testing)
    from contracts.models import GuardrailResult, TelemetryPacket, RAGRecommendation


class SafetyGuardrailsAgent:
    """
    Enforces physics-based safety rules to prevent dangerous recommendations.

    LATENCY BUDGET: <5ms (uses regex/keyword matching, not LLM)
    """

    # Hazard detection patterns (case-insensitive)
    FLAMMABLE_LIQUID_PATTERNS = [
        r'\b(grease|oil|gasoline|petroleum|diesel|fuel)\b',
        r'\b(cooking\s+oil|deep\s+fryer)\b',
    ]

    ELECTRICAL_PATTERNS = [
        r'\b(electrical|electric|power|voltage|circuit|wiring)\b',
        r'\b(battery|lithium|transformer|panel)\b',
    ]

    GAS_CHEMICAL_PATTERNS = [
        r'\b(gas|propane|butane|methane|chemical|solvent)\b',
        r'\b(ammonia|chlorine|acetone)\b',
    ]

    PRESSURIZED_PATTERNS = [
        r'\b(pressurized|cylinder|tank|canister)\b',
        r'\b(compressed|pressure\s+vessel)\b',
    ]

    # Dangerous action patterns (case-insensitive)
    WATER_ACTION_PATTERNS = [
        r'\b(water|spray|hose|wet|douse)\b',
        r'\b(sprinkler|hydrant)\b',
    ]

    APPROACH_ACTION_PATTERNS = [
        r'\b(approach|get\s+close|move\s+toward|enter)\b',
        r'\b(manual|hands?-on|touch)\b',
    ]

    IMPACT_ACTION_PATTERNS = [
        r'\b(impact|hit|strike|puncture|pierce|break)\b',
        r'\b(smash|crush|force)\b',
    ]

    # Metrics tracking
    def __init__(self):
        self.metrics = defaultdict(int)

    def _matches_any_pattern(self, text: str, patterns: list) -> bool:
        """Check if text matches any pattern in list (case-insensitive)."""
        text_lower = text.lower()
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return True
        return False

    def detect_hazards(self, visual_narrative: str, thermal_reading: Optional[float] = None) -> Dict[str, bool]:
        """
        Detect hazard types from visual narrative and sensor data.

        Returns:
            Dict with keys: grease, electrical, gas, high_temp, pressurized
        """
        hazards = {
            "grease": self._matches_any_pattern(visual_narrative, self.FLAMMABLE_LIQUID_PATTERNS),
            "electrical": self._matches_any_pattern(visual_narrative, self.ELECTRICAL_PATTERNS),
            "gas": self._matches_any_pattern(visual_narrative, self.GAS_CHEMICAL_PATTERNS),
            "pressurized": self._matches_any_pattern(visual_narrative, self.PRESSURIZED_PATTERNS),
            "high_temp": thermal_reading is not None and thermal_reading > 400.0
        }
        return hazards

    def detect_dangerous_actions(self, recommendation: str) -> Dict[str, bool]:
        """
        Detect dangerous actions in recommendation text.

        Returns:
            Dict with keys: water, approach, impact
        """
        actions = {
            "water": self._matches_any_pattern(recommendation, self.WATER_ACTION_PATTERNS),
            "approach": self._matches_any_pattern(recommendation, self.APPROACH_ACTION_PATTERNS),
            "impact": self._matches_any_pattern(recommendation, self.IMPACT_ACTION_PATTERNS)
        }
        return actions

    def evaluate_safety_rules(
        self,
        hazards: Dict[str, bool],
        actions: Dict[str, bool]
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Evaluate physics-based safety rules.

        Returns:
            (blocked, reason, hazard_type, dangerous_action)
        """
        # RULE 1: No water on Class B (grease/oil), Class C (electrical), or Class D (gas/chemical) fires
        if actions["water"]:
            if hazards["grease"]:
                return (
                    True,
                    "BLOCKED: Water on grease/oil fire causes explosive splatter. Use Class B fire extinguisher (CO2/foam).",
                    "grease",
                    "water"
                )
            if hazards["electrical"]:
                return (
                    True,
                    "BLOCKED: Water on electrical fire causes electrocution risk. De-energize circuit, use Class C extinguisher.",
                    "electrical",
                    "water"
                )
            if hazards["gas"]:
                return (
                    True,
                    "BLOCKED: Water ineffective on gas/chemical fire. Shut off gas supply, use appropriate Class D agent.",
                    "gas",
                    "water"
                )

        # RULE 2: No approach/manual actions when thermal > 400C (flash point of many materials)
        if hazards["high_temp"] and actions["approach"]:
            return (
                True,
                "BLOCKED: Thermal reading >400C. Do not approach. Risk of flashover, severe burns. Use remote suppression only.",
                "high_temp",
                "approach"
            )

        # RULE 3: No impact/puncture on pressurized containers (explosion/projectile risk)
        if hazards["pressurized"] and actions["impact"]:
            return (
                True,
                "BLOCKED: Pressurized container detected. Impact causes explosive rupture/projectile hazard. Evacuate area, cool from distance.",
                "pressurized",
                "impact"
            )

        # All rules passed
        return (False, None, None, None)

    def get_safe_alternative(self, hazard_type: str, dangerous_action: str) -> str:
        """
        Provide safe alternative recommendations based on hazard and action.
        """
        alternatives = {
            ("grease", "water"): "Use Class B fire extinguisher (CO2 or dry chemical). Cover with metal lid if small pan fire. Never use water.",
            ("electrical", "water"): "De-energize power source. Use Class C fire extinguisher (CO2 or dry chemical). Never use water.",
            ("gas", "water"): "Shut off gas supply at source. Use Class D extinguisher for metal fires. Evacuate if uncontrolled.",
            ("high_temp", "approach"): "Evacuate to safe distance. Use thermal camera for monitoring. Deploy remote suppression systems only.",
            ("pressurized", "impact"): "Evacuate 100m minimum. Cool container with water from safe distance. Call hazmat team.",
        }
        return alternatives.get((hazard_type, dangerous_action), "Follow general evacuation protocols. Consult fire safety expert.")

    async def validate_recommendation(
        self,
        recommendation: RAGRecommendation,
        packet: TelemetryPacket,
        thermal_reading: Optional[float] = None
    ) -> GuardrailResult:
        """
        Validate recommendation against safety guardrails.

        Args:
            recommendation: The RAG-generated recommendation to validate
            packet: Current telemetry packet with visual_narrative
            thermal_reading: Optional thermal sensor reading in Celsius

        Returns:
            GuardrailResult with block decision and safe alternative
        """
        start = time.perf_counter()

        # Step 1: Detect hazards from visual narrative and sensors
        hazards = self.detect_hazards(packet.visual_narrative, thermal_reading)

        # Step 2: Detect dangerous actions in recommendation
        actions = self.detect_dangerous_actions(recommendation.recommendation)

        # Step 3: Evaluate safety rules
        blocked, reason, hazard_type, dangerous_action = self.evaluate_safety_rules(hazards, actions)

        # Step 4: Generate safe alternative if blocked
        safe_alternative = ""
        if blocked:
            safe_alternative = self.get_safe_alternative(hazard_type, dangerous_action)
            self.metrics["guardrail_blocks_total"] += 1
        else:
            self.metrics["guardrail_pass_total"] += 1

        latency = (time.perf_counter() - start) * 1000

        return GuardrailResult(
            blocked=blocked,
            reason=reason or "Recommendation passed safety validation.",
            safe_alternative=safe_alternative,
            hazard_detected=hazard_type,
            dangerous_action=dangerous_action,
            latency_ms=latency
        )

    async def apply_guardrails(
        self,
        recommendation: RAGRecommendation,
        packet: TelemetryPacket,
        thermal_reading: Optional[float] = None
    ) -> RAGRecommendation:
        """
        Apply guardrails and modify recommendation if blocked.

        This is the main integration point for the orchestrator.

        Args:
            recommendation: Original RAG recommendation
            packet: Current telemetry packet
            thermal_reading: Optional thermal sensor reading in Celsius

        Returns:
            Modified RAGRecommendation (replaced with safe alternative if blocked)
        """
        result = await self.validate_recommendation(recommendation, packet, thermal_reading)

        if result.blocked:
            # Replace dangerous recommendation with safe alternative
            return RAGRecommendation(
                recommendation=result.safe_alternative[:300],  # Enforce max length
                matched_protocol=f"GUARDRAIL_OVERRIDE_{result.hazard_detected}",
                context_summary=f"BLOCKED: {result.reason}",
                synthesis_time_ms=recommendation.synthesis_time_ms + result.latency_ms
            )
        else:
            # Pass through original recommendation
            return recommendation

    def get_metrics(self) -> Dict[str, int]:
        """Return current metrics for observability."""
        return dict(self.metrics)

    def reset_metrics(self):
        """Reset metrics (useful for testing)."""
        self.metrics.clear()
