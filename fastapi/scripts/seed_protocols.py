#!/usr/bin/env python3
"""
Safety Protocol Seeding Script for Actian VectorAI DB

Embeds NFPA/OSHA safety protocols and loads them into Actian Vector DB via gRPC.
Based on RAG.MD Section 5 (Phase 1: Actian Schema & Protocol Seeding)

Usage:
    python scripts/seed_protocols.py

Environment Variables:
    ACTIAN_HOST (default: vectoraidb)
    ACTIAN_PORT (default: 50051)
"""

import asyncio
import os
import sys
from typing import List, Dict

from sentence_transformers import SentenceTransformer
from cortex import AsyncCortexClient

# Load environment variables
ACTIAN_HOST = os.getenv("ACTIAN_HOST", "vectoraidb")
ACTIAN_PORT = int(os.getenv("ACTIAN_PORT", "50051"))

# Safety protocols database
PROTOCOLS: List[Dict] = [
    {
        "scenario": "Person trapped near fire with exit blocked",
        "protocol_text": "NFPA 1001: Immediate evacuation required when fire occupies >40% of visual field and victims are present. Establish defensive perimeter. Prioritize victim rescue via secondary exit.",
        "severity": "CRITICAL",
        "category": "fire",
        "tags": "trapped,exit_blocked,evacuation,rescue",
        "source": "NFPA_1001"
    },
    {
        "scenario": "Fire blocking primary exit path",
        "protocol_text": "OSHA 29CFR: Ensure all personnel have clear egress path. If primary path is obstructed by fire, initiate rescue protocol via secondary exit. Do not attempt passage through active fire.",
        "severity": "HIGH",
        "category": "fire",
        "tags": "exit_blocked,path_obstructed,egress",
        "source": "OSHA_29CFR"
    },
    {
        "scenario": "Rapid fire growth detected",
        "protocol_text": "NFPA 1710: When fire growth rate exceeds 10% per second, flashover conditions are imminent. Evacuate all personnel immediately. Transition to defensive operations.",
        "severity": "CRITICAL",
        "category": "fire",
        "tags": "rapid_growth,flashover,evacuation",
        "source": "NFPA_1710"
    },
    {
        "scenario": "Person stationary near growing fire",
        "protocol_text": "Fire Safety Protocol: If victim is stationary near active fire for >10 seconds, assume incapacitation. Initiate immediate rescue with backup team. Deploy thermal imaging to locate victim.",
        "severity": "HIGH",
        "category": "fire",
        "tags": "stationary,victim,rescue,incapacitation",
        "source": "FSP_GENERAL"
    },
    {
        "scenario": "Smoke inhalation risk with low visibility",
        "protocol_text": "OSHA Respiratory Protection: When smoke opacity exceeds 60%, respiratory hazard is present. All personnel must use SCBA. Visibility <3 feet requires thermal imaging for navigation.",
        "severity": "HIGH",
        "category": "fire",
        "tags": "smoke,respiratory,visibility,SCBA",
        "source": "OSHA_29CFR"
    },
    {
        "scenario": "Fire diminishing after suppression",
        "protocol_text": "NFPA 1001: Continue monitoring for 15 minutes after fire appears extinguished. Check for hidden fire in walls/ceiling. Maintain water supply until overhaul is complete.",
        "severity": "MEDIUM",
        "category": "fire",
        "tags": "diminishing,suppression,overhaul",
        "source": "NFPA_1001"
    },
    {
        "scenario": "Multiple people near active fire",
        "protocol_text": "Mass Casualty Protocol: When >2 victims are present in hazard zone, establish triage point. Evacuate ambulatory victims first. Deploy additional rescue teams for non-ambulatory victims.",
        "severity": "CRITICAL",
        "category": "fire",
        "tags": "multiple_victims,mass_casualty,triage",
        "source": "MCP_GENERAL"
    },
    {
        "scenario": "Small contained fire with clear exits",
        "protocol_text": "Standard Fire Response: Deploy Class A extinguisher or 1.5-inch hose line. Maintain egress path. Monitor for extension. No immediate evacuation required if fire <10% of visual field.",
        "severity": "LOW",
        "category": "fire",
        "tags": "contained,small_fire,extinguisher",
        "source": "FSP_GENERAL"
    },
    {
        "scenario": "Fire spreading with structural risk",
        "protocol_text": "NFPA 1500: When fire involves structural elements (walls, ceiling, load-bearing), transition to defensive operations. Evacuate building. Monitor for collapse indicators.",
        "severity": "CRITICAL",
        "category": "fire",
        "tags": "structural,spreading,collapse_risk,defensive",
        "source": "NFPA_1500"
    },
    {
        "scenario": "Clear scene with no hazards detected",
        "protocol_text": "All Clear Protocol: Maintain monitoring posture. Continue thermal scans every 30 seconds. Stand ready for redeployment. Document scene status for incident report.",
        "severity": "LOW",
        "category": "fire",
        "tags": "clear,monitoring,standby",
        "source": "FSP_GENERAL"
    },
]


async def main():
    print("=" * 60)
    print("Safety Protocol Seeding Script (Actian VectorAI DB)")
    print("=" * 60)

    # Step 1: Load embedding model
    print("\n[1/4] Loading sentence-transformers model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("✓ Model loaded: all-MiniLM-L6-v2 (384 dimensions)")

    # Step 2: Connect to Actian VectorAI DB
    address = f"{ACTIAN_HOST}:{ACTIAN_PORT}"
    print(f"\n[2/4] Connecting to Actian VectorAI DB at {address}...")

    client = AsyncCortexClient(address=address)
    await client.connect()
    print("✓ Connected")

    # Step 3: Embed protocols
    print(f"\n[3/4] Embedding {len(PROTOCOLS)} protocols...")

    ids = []
    vectors = []
    payloads = []

    for i, protocol in enumerate(PROTOCOLS, 1):
        scenario_text = protocol["scenario"]
        vector = model.encode(scenario_text, normalize_embeddings=True).tolist()

        ids.append(i)
        vectors.append(vector)
        payloads.append({
            "protocol_text": protocol["protocol_text"],
            "severity": protocol["severity"],
            "category": protocol["category"],
            "tags": protocol["tags"],
            "source": protocol["source"],
            "scenario": protocol["scenario"],
        })

        print(f"  [{i}/{len(PROTOCOLS)}] {protocol['severity']:8s} | {protocol['scenario'][:50]}")

    print(f"\n✓ Generated {len(vectors)} embeddings")

    # Step 4: Batch upsert into VectorAI DB
    print("\n[4/4] Upserting protocols into safety_protocols collection...")

    await client.batch_upsert(
        collection_name="safety_protocols",
        ids=ids,
        vectors=vectors,
        payloads=payloads,
    )

    print(f"✓ Upserted {len(ids)} protocols")

    # Verification: run a test search
    print("\n[Verify] Running test search: 'fire growing rapidly' ...")
    test_vector = model.encode("fire growing rapidly", normalize_embeddings=True).tolist()
    results = await client.search(
        collection_name="safety_protocols",
        query=test_vector,
        top_k=3,
        with_payload=True,
    )

    print(f"✓ Test search returned {len(results)} results:")
    for r in results:
        print(f"  - score={r.score:.4f} | {r.payload.get('severity', '?'):8s} | {r.payload.get('scenario', '?')[:50]}")

    await client.close()

    # Display protocol summary
    print("\n" + "=" * 60)
    print("Protocol Summary:")
    print("=" * 60)

    severity_counts = {}
    for protocol in PROTOCOLS:
        severity = protocol["severity"]
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    print("\nBy Severity:")
    for severity, count in sorted(severity_counts.items()):
        print(f"  {severity:10s}: {count:2d} protocols")

    print(f"\nTotal: {len(PROTOCOLS)} protocols seeded successfully")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
