#!/usr/bin/env python3
"""
Test VectorAI DB Search Functionality
"""

import asyncio
import os
import sys

try:
    from cortex import AsyncCortexClient
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("Error: actiancortex and sentence_transformers packages required.")
    sys.exit(1)

ACTIAN_HOST = os.getenv("ACTIAN_HOST", "localhost")
ACTIAN_PORT = int(os.getenv("ACTIAN_PORT", "50051"))

async def main():
    address = f"{ACTIAN_HOST}:{ACTIAN_PORT}"
    print(f"Connecting to VectorAI DB at {address}...")
    
    client = AsyncCortexClient(address=address)
    
    try:
        await client.connect()
        print("✅ Connected\n")

        print("Counting vectors in 'safety_protocols'...")
        count = await client.get_vector_count("safety_protocols")
        print(f"✅ Found {count} vectors in collection\n")

        print("Loading embedding model (all-MiniLM-L6-v2)...")
        model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ Model loaded\n")
        
        # Flush the collection to ensure data is searchable
        print("Flushing collection...")
        await client.flush("safety_protocols")
        print("✅ Flushed\n")

        # Explicitly check elements
        print("Explicitly fetching guides 111-174 (first 3 IDs)...")
        records = await client.get_many("safety_protocols", [1, 2, 3], with_vectors=True, with_payload=True)
        for i, (vec, payload) in enumerate(records):
            if payload:
                vec_len = len(vec) if vec else 0
                print(f"ID {i+1} exists - Source: {payload.get('source')}, Severity: {payload.get('severity')}, Vector Len: {vec_len}")
            else:
                print(f"ID {i+1} missing or has no payload!")
        print("\n")

        queries = [
            "toxic gas leak in warehouse",
            "radioactive material spill on highway",
            "person trapped near large explosive fire",
            "a cat stuck in a tree"
        ]

        for query_text in queries:
            print(f"--- Search: '{query_text}' ---")
            query_vector = model.encode(query_text, normalize_embeddings=True).tolist()
            
            results = await client.search(
                collection_name="safety_protocols",
                query=query_vector,
                with_payload=True,
            )
            
            if not results:
                print("No results found.")
            else:
                for idx, r in enumerate(results):
                    source = r.payload.get('source', 'Unknown')
                    severity = r.payload.get('severity', 'Unknown')
                    tags = r.payload.get('tags', '')
                    print(f"{idx+1}. Score: {r.score:.4f} | Source: {source} | Severity: {severity}")
                    print(f"   Tags: {tags}")
            print()
            
    except Exception as e:
        print(f"\n❌ Search Test Failed: {e}")
        sys.exit(1)
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
