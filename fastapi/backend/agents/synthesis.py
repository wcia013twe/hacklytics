import time
from typing import List, Dict
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from contracts.models import Protocol, HistoryEntry, RAGRecommendation

class SynthesisAgent:
    """
    Generates actionable recommendations from retrieved context (template-based v1).
    """

    FALLBACK_TEMPLATES = {
        "CRITICAL": "CRITICAL hazard detected. Fire trend: {trend}. Evacuate immediately. Follow emergency protocols.",
        "HIGH": "HIGH hazard detected. Fire trend: {trend}. Prepare for evacuation. Monitor situation closely.",
        "default": "Hazard conditions detected. Fire trend: {trend}. Follow standard safety procedures."
    }

    async def select_primary_protocol(self, protocols: List[Protocol], context: Dict) -> Protocol:
        """Task 8.1: Select primary protocol (highest similarity)"""
        if not protocols:
            return None
        return protocols[0]  # Already sorted by similarity

    async def render_template(
        self,
        protocols: List[Protocol],
        history: List[HistoryEntry],
        current_context: Dict
    ) -> RAGRecommendation:
        """
        Task 8.2: Render template-based recommendation

        Returns:
            RAGRecommendation with synthesized text
        """
        start = time.perf_counter()

        hazard = current_context["hazard_level"]
        trend = current_context["trend_tag"]
        growth = current_context["growth_rate"]
        proximity = current_context["proximity_alert"]

        primary_protocol = await self.select_primary_protocol(protocols, current_context)

        if primary_protocol:
            # Use retrieved protocol
            recommendation = f"{primary_protocol.protocol_text}\n\n"
            recommendation += f"Current trend: {trend} ({growth:+.3f}/s). "

            if proximity:
                recommendation += "⚠️ Personnel in proximity to hazard. "

            if history:
                recommendation += f"Similar to {len(history)} recent incident(s)."

            matched_protocol = primary_protocol.source
        else:
            # Use fallback template
            template = self.FALLBACK_TEMPLATES.get(hazard, self.FALLBACK_TEMPLATES["default"])
            recommendation = template.format(trend=trend)
            matched_protocol = "fallback"

        # Truncate to 300 chars
        if len(recommendation) > 300:
            recommendation = recommendation[:297] + "..."

        synthesis_time = (time.perf_counter() - start) * 1000

        return RAGRecommendation(
            recommendation=recommendation,
            matched_protocol=matched_protocol,
            context_summary=f"{hazard} | {trend} | {len(protocols)} protocols | {len(history)} history",
            synthesis_time_ms=synthesis_time
        )
