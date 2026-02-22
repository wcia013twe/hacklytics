#!/usr/bin/env python3
"""
Actian VectorAI DB Collection Initialization Script

Creates the safety_protocols and incident_log collections with 384-dim COSINE vectors.
Uses get_or_create_collection() for idempotency — safe to run multiple times.

Usage:
    python scripts/init_actian_collections.py

Environment Variables:
    ACTIAN_HOST (default: vectoraidb)
    ACTIAN_PORT (default: 50051)
"""

import asyncio
import os
import sys

from cortex import AsyncCortexClient


ACTIAN_HOST = os.getenv("ACTIAN_HOST", "vectoraidb")
ACTIAN_PORT = int(os.getenv("ACTIAN_PORT", "50051"))

COLLECTIONS = [
    {
        "name": "safety_protocols",
        "vector_size": 384,
        "distance": "COSINE",
    },
    {
        "name": "incident_log",
        "vector_size": 384,
        "distance": "COSINE",
    },
]


async def main():
    address = f"{ACTIAN_HOST}:{ACTIAN_PORT}"
    print("=" * 60)
    print("Actian VectorAI DB — Collection Initialization")
    print("=" * 60)
    print(f"\n[1/3] Connecting to {address} ...")

    client = AsyncCortexClient(address=address)
    await client.connect()
    print("✓ Connected")

    # Health check
    print("\n[2/3] Running health check ...")
    collections_before = await client.list_collections()
    print(f"✓ Healthy — {len(collections_before)} existing collection(s)")

    # Create collections
    print(f"\n[3/3] Ensuring {len(COLLECTIONS)} collections exist ...")
    for spec in COLLECTIONS:
        col = await client.get_or_create_collection(
            name=spec["name"],
            vector_size=spec["vector_size"],
            distance=spec["distance"],
        )
        print(f"  ✓ {spec['name']} (dim={spec['vector_size']}, dist={spec['distance']})")

    # Verification
    collections_after = await client.list_collections()
    names = [c.name for c in collections_after]
    for spec in COLLECTIONS:
        assert spec["name"] in names, f"Collection {spec['name']} missing after creation!"
    print(f"\n✓ Verified: {names}")

    await client.close()
    print("\n" + "=" * 60)
    print("Collection initialization complete.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
