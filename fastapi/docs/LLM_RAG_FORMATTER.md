# LLM RAG Formatter — Structured Protocol Output

## Problem

The Actian VectorDB returns raw ERG 2024 guide text verbatim. A retrieved guide is typically 400–1,200 words of multi-section prose:

```
ERG 2024 Page 278  GUIDE 174  Adsorbed Gases - Flammable or Oxidizing

POTENTIAL HAZARDS
FIRE OR EXPLOSION
• Some gases will be ignited by heat, sparks or flames.
• Vapors from liquefied gas are initially heavier than air and spread along ground.
...
EMERGENCY RESPONSE
FIRE
Small Fire: Dry chemical, CO2, water spray or regular foam.
...
```

This raw text:
- Cannot be rendered directly in the React dashboard action components
- Contains sections irrelevant to the current scene
- Has no mapping to `{target, directive}` command pairs the UI expects
- Is not grounded to the live scene (e.g., Person #42, Fire #7)

## Solution: `ProtocolFormatterAgent`

A new LLM formatting step runs **after** RAG retrieval and **before** the WebSocket broadcast in `stage_3_cognition`. It takes the retrieved ERG protocol + live scene context and outputs a structured JSON payload matching the frontend `WebSocketPayload` types exactly.

The `source_document` field (e.g., `ERG_2024_Guide_174`) is preserved as-is — it drives the source badge in the Source Intelligence panel and must never be overwritten.

---

## Pipeline Position

```
Jetson packet
    ↓
[Stage 2] Reflex broadcast  ← immediate, no LLM
    ↓
[Stage 3] Cognition path (async, <2s)
    ├── Temporal narrative synthesis  (TemporalNarrativeAgent, Ollama)
    ├── Embedding + Actian vector search
    ├── ProtocolFormatterAgent  ← NEW: formats raw ERG → structured JSON
    └── WebSocket broadcast (rag_message)
```

---

## Output Schema

The formatter must output valid JSON matching these TypeScript interfaces:

```typescript
// From frontend/src/types/websocket.ts
interface ActionCommand {
    target: string;     // Who receives the command ("Rescue Team", "IC", "All Units")
    directive: string;  // What they must do — imperative, specific, ≤12 words
}

interface RagData {
    protocol_id: string;        // ERG guide ID, e.g. "ERG_2024_Guide_174"
    hazard_type: string;        // Hazard classification, e.g. "Adsorbed Gases - Flammable"
    source_document: string;    // PRESERVED — never overwrite (drives source badge)
    source_text: string;        // Key excerpt from the ERG guide (≤3 sentences)
    actionable_commands: ActionCommand[];  // 2–4 scene-grounded commands
}

// Top-level fields also populated by formatter:
action_command: string;  // Single primary directive (≤15 words, imperative)
action_reason: string;   // Why — grounds the command in ERG + scene facts (≤25 words)
```

### Example Output (CRITICAL scene)

**Input scene:** Person #42 stationary 28s, Fire #7 growing 14%/s, gas tank proximate. ERG Guide 174 retrieved.

```json
{
  "action_command": "Evacuate all personnel — BLEVE risk, do not approach",
  "action_reason": "ERG 174: adsorbed gas containers may explode in fire. Fire growing 14%/s with gas tank in proximity.",
  "rag_data": {
    "protocol_id": "ERG_2024_Guide_174",
    "hazard_type": "Adsorbed Gases — Flammable",
    "source_document": "ERG_2024_Guide_174",
    "source_text": "Containers may explode when heated. Do not approach containers engulfed in fire. Cool with water from maximum distance.",
    "actionable_commands": [
      { "target": "Rescue Team", "directive": "Extract Person #42 via secondary exit now" },
      { "target": "All Units",   "directive": "Maintain 300ft standoff — BLEVE risk" },
      { "target": "IC",          "directive": "Transition to defensive operations immediately" }
    ]
  }
}
```

---

## Prompt Design

The formatter uses **Ollama** (same `llama3.2:1b` instance as `TemporalNarrativeAgent`) via a separate async call. The prompt is compact to stay within the 1500ms timeout budget.

```python
FORMATTER_SYSTEM_PROMPT = """You are a fire incident commander AI.
Given a retrieved ERG protocol and live scene data, output ONLY valid JSON — no preamble, no markdown.
Ground every command in the specific objects present (use IDs if given).
Keep directives short: imperative, ≤12 words each."""

def build_formatter_prompt(
    protocol_text: str,
    hazard_level: str,
    visual_narrative: str,
    tracked_objects: list,
    source: str,
) -> str:
    objects_str = ", ".join(
        f"{o['label']} #{o['id']} ({o['status']})" for o in tracked_objects
    ) or "none"

    # Trim protocol to first 600 chars to stay within context window
    protocol_excerpt = protocol_text[:600].strip()

    return f"""Scene: {hazard_level} — {visual_narrative}
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
```

---

## Agent Interface

```python
# backend/agents/protocol_formatter.py

class ProtocolFormatterAgent:
    """
    Formats raw RAG protocol text into structured WebSocketPayload fields
    using a local Ollama model.
    """

    async def format(
        self,
        protocol: Protocol,
        packet: TelemetryPacket,
        synthesized_narrative: str,
    ) -> FormatterResult:
        """
        Returns:
            FormatterResult(
                action_command: str,
                action_reason: str,
                hazard_type: str,
                source_text: str,
                actionable_commands: List[ActionCommand],
                fallback_used: bool,
            )
        """
```

**Fallback** (if Ollama times out or returns invalid JSON):
- `action_command` ← `SynthesisAgent` template output
- `source_text` ← first 300 chars of `protocol.protocol_text`
- `actionable_commands` ← `[]`
- `hazard_type` ← `protocol.category`

---

## Integration in `orchestrator.py` → `stage_3_cognition`

```python
# After protocol retrieval and synthesis:
primary_protocol = protocols[0] if protocols else None

formatter_result = None
if primary_protocol and self.protocol_formatter:
    formatter_result = await self.protocol_formatter.format(
        protocol=primary_protocol,
        packet=packet,
        synthesized_narrative=synthesized_narrative,
    )

# Build rag_message using formatter output (or fallback to template):
if formatter_result and not formatter_result.fallback_used:
    action_command = formatter_result.action_command
    action_reason  = formatter_result.action_reason
    rag_data = {
        "protocol_id":         primary_protocol.source,
        "hazard_type":         formatter_result.hazard_type,
        "source_document":     primary_protocol.source,   # PRESERVED
        "source_text":         formatter_result.source_text,
        "actionable_commands": formatter_result.actionable_commands,
    }
else:
    action_command = recommendation.recommendation
    action_reason  = synthesized_narrative
    rag_data = {
        "protocol_id":         primary_protocol.source if primary_protocol else "fallback",
        "hazard_type":         primary_protocol.category if primary_protocol else packet.hazard_level,
        "source_document":     primary_protocol.source if primary_protocol else None,
        "source_text":         primary_protocol.protocol_text[:300] if primary_protocol else recommendation.recommendation,
        "actionable_commands": [],
    }
```

---

## Performance Budget

| Step | Target | Note |
|------|--------|------|
| Temporal narrative (Ollama) | ~500ms | Already in pipeline |
| Embedding | ~350ms | Cached on repeat |
| Actian vector search | <200ms | |
| **Protocol formatter (Ollama)** | **<800ms** | Compact prompt, 80 tokens max |
| Broadcast | <5ms | |
| **Total cognition path** | **<2s** | SLA target |

The formatter prompt is kept under 800 tokens (protocol excerpt capped at 600 chars) so `llama3.2:1b` completes in ~400–700ms. Both Ollama calls share the same running instance — they are sequential, not parallel.

**If latency is tight:** run temporal narrative and protocol formatter as concurrent `asyncio` tasks since they are independent.

---

## Files to Create/Modify

| File | Change |
|------|--------|
| `backend/agents/protocol_formatter.py` | New agent |
| `backend/orchestrator.py` | Instantiate agent, call in `stage_3_cognition` |
| `backend/contracts/models.py` | Add `FormatterResult` dataclass |

No frontend changes required — output maps directly to existing `WebSocketPayload` types.
