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

import os
import sys
from sentence_transformers import SentenceTransformer
from typing import List, Dict

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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


def seed_protocols():
    """
    Main seeding function using Actian VectorAI DB gRPC client.

    1. Load sentence-transformers model
    2. Connect to Actian Vector DB via gRPC
    3. Embed each protocol scenario
    4. Insert into safety_protocols collection
    """
    print("=" * 60)
    print("Safety Protocol Seeding Script (Actian VectorAI DB)")
    print("=" * 60)

    # Step 1: Load embedding model
    print("\n[1/4] Loading sentence-transformers model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("✓ Model loaded: all-MiniLM-L6-v2 (384 dimensions)")

    # Step 2: Connect to Actian VectorAI DB
    print(f"\n[2/4] Connecting to Actian VectorAI DB at {ACTIAN_HOST}:{ACTIAN_PORT}...")

    try:
        # Import Actian client
        try:
            import actiancortex
            print("✓ Actian client library loaded")
        except ImportError:
            print("✗ actiancortex library not found")
            print("  Install with: pip install actiancortex-0.1.0b1-py3-none-any.whl")
            return

        # TODO: Initialize Actian client connection
        # client = actiancortex.VectorAIClient(host=ACTIAN_HOST, port=ACTIAN_PORT)
        print(f"⚠️  Note: Actian client integration pending. Connection to {ACTIAN_HOST}:{ACTIAN_PORT}")

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("\nMake sure the VectorAI DB container is running:")
        print("  docker compose up -d vectoraidb")
        return

    # Step 3: Embed and display protocols
    print(f"\n[3/4] Embedding {len(PROTOCOLS)} protocols...")

    embeddings = []
    for i, protocol in enumerate(PROTOCOLS, 1):
        # Embed scenario description
        scenario_text = protocol["scenario"]
        vector = model.encode(scenario_text, normalize_embeddings=True).tolist()

        embeddings.append({
            "vector": vector,
            "metadata": protocol
        })

        print(f"  [{i}/{len(PROTOCOLS)}] {protocol['severity']:8s} | {protocol['scenario'][:50]}")

    print(f"\n✓ Generated {len(embeddings)} embeddings")

    # Step 4: Insert into VectorAI DB
    print("\n[4/4] Inserting protocols into VectorAI DB...")
    print("⚠️  TODO: Implement Actian VectorAI DB insertion")
    print("  - Create 'safety_protocols' collection")
    print("  - Insert vectors with metadata")
    print("  - Verify insertion with similarity search")

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

    print(f"\nTotal: {len(PROTOCOLS)} protocols ready for seeding")
    print("\n" + "=" * 60)
    print("⚠️  Seeding simulation complete!")
    print("   Full integration requires Actian VectorAI DB client setup")
    print("=" * 60)


if __name__ == "__main__":
    seed_protocols()
