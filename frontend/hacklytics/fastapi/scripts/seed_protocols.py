#!/usr/bin/env python3
"""
Safety Protocol Seeding Script

Embeds NFPA/OSHA safety protocols and loads them into Actian Vector DB.
Based on RAG.MD Section 5 (Phase 1: Actian Schema & Protocol Seeding)

Usage:
    python scripts/seed_protocols.py

Environment Variables:
    ACTIAN_HOST (default: localhost)
    ACTIAN_PORT (default: 5432)
    ACTIAN_DB (default: safety_db)
    ACTIAN_USER (default: vectoruser)
    ACTIAN_PASSWORD (default: vectorpass)
"""

import os
import asyncio
import asyncpg
from sentence_transformers import SentenceTransformer
from typing import List, Dict

# Load environment variables
ACTIAN_HOST = os.getenv("ACTIAN_HOST", "localhost")
ACTIAN_PORT = int(os.getenv("ACTIAN_PORT", "5432"))
ACTIAN_DB = os.getenv("ACTIAN_DB", "safety_db")
ACTIAN_USER = os.getenv("ACTIAN_USER", "vectoruser")
ACTIAN_PASSWORD = os.getenv("ACTIAN_PASSWORD", "vectorpass")

# Safety protocols database
# TODO: Expand this list to 30-50 protocols covering NFPA 1001, OSHA 29CFR, etc.
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
    # Add more protocols here to reach 30-50 total
    # Cover scenarios: flashover, backdraft, rescue, ventilation, water supply, hazmat, etc.
]


async def seed_protocols():
    """
    Main seeding function.

    1. Load sentence-transformers model
    2. Connect to Actian Vector DB
    3. Embed each protocol scenario
    4. Insert into safety_protocols table
    """
    print("=" * 60)
    print("Safety Protocol Seeding Script")
    print("=" * 60)

    # Step 1: Load embedding model
    print("\n[1/4] Loading sentence-transformers model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("✓ Model loaded: all-MiniLM-L6-v2 (384 dimensions)")

    # Step 2: Connect to database
    print(f"\n[2/4] Connecting to Actian Vector DB at {ACTIAN_HOST}:{ACTIAN_PORT}...")
    try:
        conn = await asyncpg.connect(
            host=ACTIAN_HOST,
            port=ACTIAN_PORT,
            database=ACTIAN_DB,
            user=ACTIAN_USER,
            password=ACTIAN_PASSWORD
        )
        print(f"✓ Connected to database: {ACTIAN_DB}")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("\nMake sure the Actian container is running:")
        print("  docker-compose up -d actian")
        return

    # Step 3: Check if table exists
    print("\n[3/4] Verifying safety_protocols table exists...")
    table_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'safety_protocols'
        )
    """)

    if not table_exists:
        print("✗ Table 'safety_protocols' not found!")
        print("  Run init.sql first: docker-compose exec -T actian psql -U vectoruser -d safety_db < init.sql")
        await conn.close()
        return

    print("✓ Table exists")

    # Step 4: Clear existing protocols (optional - comment out for append mode)
    existing_count = await conn.fetchval("SELECT COUNT(*) FROM safety_protocols")
    if existing_count > 0:
        print(f"\n⚠️  Found {existing_count} existing protocols. Clearing table...")
        await conn.execute("DELETE FROM safety_protocols")
        print("✓ Table cleared")

    # Step 5: Insert protocols
    print(f"\n[4/4] Embedding and inserting {len(PROTOCOLS)} protocols...")

    for i, protocol in enumerate(PROTOCOLS, 1):
        # Embed scenario description
        scenario_text = protocol["scenario"]
        vector = model.encode(scenario_text, normalize_embeddings=True).tolist()

        # Insert into database
        await conn.execute("""
            INSERT INTO safety_protocols (
                scenario_vector,
                protocol_text,
                severity,
                category,
                tags,
                source
            ) VALUES ($1, $2, $3, $4, $5, $6)
        """,
            vector,
            protocol["protocol_text"],
            protocol["severity"],
            protocol["category"],
            protocol["tags"],
            protocol["source"]
        )

        print(f"  [{i}/{len(PROTOCOLS)}] {protocol['severity']:8s} | {protocol['scenario'][:50]}")

    print(f"\n✓ Inserted {len(PROTOCOLS)} protocols successfully")

    # Step 6: Verify insertion
    print("\n[Verification] Checking protocol coverage...")
    coverage = await conn.fetch("""
        SELECT severity, category, COUNT(*) as count
        FROM safety_protocols
        GROUP BY severity, category
        ORDER BY severity, category
    """)

    print("\nProtocol Coverage by Severity & Category:")
    print("-" * 50)
    for row in coverage:
        print(f"  {row['severity']:10s} | {row['category']:15s} | {row['count']:3d} protocols")

    # Step 7: Test retrieval
    print("\n[Test] Testing vector similarity retrieval...")
    test_query = "Person trapped with fire blocking exit"
    test_vector = model.encode(test_query, normalize_embeddings=True).tolist()

    results = await conn.fetch("""
        SELECT
            protocol_text,
            severity,
            source,
            (1 - (scenario_vector <-> $1::vector)) AS similarity_score
        FROM safety_protocols
        ORDER BY scenario_vector <-> $1::vector ASC
        LIMIT 3
    """, test_vector)

    print(f"\nTest Query: '{test_query}'")
    print("Top 3 Matching Protocols:")
    print("-" * 50)
    for i, row in enumerate(results, 1):
        print(f"\n{i}. [{row['severity']}] {row['source']}")
        print(f"   Similarity: {row['similarity_score']:.3f}")
        print(f"   Protocol: {row['protocol_text'][:100]}...")

    # Close connection
    await conn.close()
    print("\n" + "=" * 60)
    print("Seeding complete! ✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_protocols())
