#!/usr/bin/env python3
"""
ERG 2024 Protocol Seeding Script for Actian VectorAI DB

Reads ERG 2024 PDF, extracts Guides 111-174 from the orange section,
chunks by guide, auto-classifies severity, creates embeddings,
and loads them into Actian Vector DB via gRPC.

Usage:
    python scripts/seed_erg_protocols.py --pdf ../ERG2024-Eng.pdf

Environment Variables:
    ACTIAN_HOST (default: vectoraidb)
    ACTIAN_PORT (default: 50051)
    ERG_PDF_PATH (default: data/ERG2024-Eng.pdf)
"""

import argparse
import asyncio
import os
import re
import sys
from typing import List, Dict

try:
    from pypdf import PdfReader
except ImportError:
    print("Error: pypdf is required. Run: pip install pypdf>=4.0.0")
    sys.exit(1)

from sentence_transformers import SentenceTransformer
from cortex import AsyncCortexClient

# Configuration
ACTIAN_HOST = os.getenv("ACTIAN_HOST", "vectoraidb")
ACTIAN_PORT = int(os.getenv("ACTIAN_PORT", "50051"))
DEFAULT_PDF_PATH = os.getenv("ERG_PDF_PATH", "data/ERG2024-Eng.pdf")

# Keyword definitions for classification and tagging
TAG_KEYWORDS = [
    "explosive", "flammable", "toxic", "corrosive", "asphyxiation",
    "radioactive", "oxidizer", "poison", "compressed_gas", "cryogenic",
    "spontaneous_ignition", "water_reactive", "gas", "spill", "leak", "fire"
]

def map_tag(word: str) -> str:
    word = word.lower()
    mapping = {
        "compressed": "compressed_gas",
        "gas": "compressed_gas",
        "reactive": "water_reactive",
        "ignition": "spontaneous_ignition"
    }
    return mapping.get(word, word)

def extract_tags(text: str) -> str:
    found_tags = set()
    text_lower = text.lower()
    for kw in TAG_KEYWORDS:
        if kw.replace("_", " ") in text_lower or kw in text_lower:
            found_tags.add(kw)
    return ",".join(sorted(found_tags))

def classify_severity(hazards_text: str) -> str:
    # Auto-classify severity from POTENTIAL HAZARDS keywords
    text_upper = hazards_text.upper()
    text_lower = hazards_text.lower()
    
    # CRITICAL — "EXPLODE", "fatal", "EXTREMELY HAZARDOUS", "1600 METERS"
    if ("EXPLODE" in text_upper or 
        "fatal" in text_lower or 
        "EXTREMELY HAZARDOUS" in text_upper or 
        "1600 METERS" in text_upper):
        return "CRITICAL"
        
    # HIGH — "EXTREMELY FLAMMABLE", "TOXIC", "may be fatal"
    if ("EXTREMELY FLAMMABLE" in text_upper or 
        "TOXIC" in text_upper or 
        "may be fatal" in text_lower):
        return "HIGH"
        
    # MEDIUM — "Flammable", "irritating", "corrosive"
    if ("flammable" in text_lower or 
        "irritating" in text_lower or 
        "corrosive" in text_lower):
        return "MEDIUM"
        
    # LOW — everything else
    return "LOW"

def parse_erg_pdf(pdf_path: str) -> List[Dict]:
    print(f"Reading PDF: {pdf_path}")
    reader = PdfReader(pdf_path)
    
    # Pages 150-280 in PDF are indices 149 to 279
    # We will scan through this range
    start_page = max(0, 149 - 5)  # Add some buffer just in case
    end_page = min(len(reader.pages), 285)
    
    guides_raw = {}
    current_guide_num = None
    
    # regex for GUIDE \d{3}
    guide_pattern = re.compile(r'GUIDE\s*\n?(\d{3})', re.IGNORECASE)
    
    print(f"Scanning pages {start_page+1} to {end_page}...")
    for i in range(start_page, end_page):
        page = reader.pages[i]
        text = page.extract_text()
        if not text:
            continue
            
        # Check if page contains a guide header
        match = guide_pattern.search(text)
        if match:
            guide_num = match.group(1)
            # Make sure it's in the 111-174 range
            if 111 <= int(guide_num) <= 174:
                current_guide_num = guide_num
        
        if current_guide_num:
            if current_guide_num not in guides_raw:
                guides_raw[current_guide_num] = []
            guides_raw[current_guide_num].append(text)
            
    # Process each guide
    protocols = []
    
    for guide_num, page_texts in guides_raw.items():
        full_text = "\n".join(page_texts)
        
        # Split into POTENTIAL HAZARDS vs EMERGENCY RESPONSE
        hazards_idx = full_text.upper().find("POTENTIAL HAZARDS")
        response_idx = full_text.upper().find("EMERGENCY RESPONSE")
        
        if hazards_idx != -1 and response_idx != -1 and response_idx > hazards_idx:
            hazards_text = full_text[hazards_idx:response_idx].strip()
        elif hazards_idx != -1:
            hazards_text = full_text[hazards_idx:hazards_idx+1000].strip() # Fallback
        else:
            hazards_text = full_text[:1000].strip() # Fallback
            
        severity = classify_severity(hazards_text)
        tags = extract_tags(full_text)
        
        protocols.append({
            "guide_num": guide_num,
            "protocol_text": full_text,
            "severity": severity,
            "category": "hazmat",
            "tags": tags,
            "source": f"ERG_2024_Guide_{guide_num}",
            "scenario": hazards_text,
        })
        
    print(f"Extracted {len(protocols)} guides.")
    
    # Sort protocols by guide number
    protocols.sort(key=lambda x: int(x["guide_num"]))
    return protocols


async def main():
    parser = argparse.ArgumentParser(description="Seed ERG 2024 Protocols")
    parser.add_argument("--pdf", type=str, default=DEFAULT_PDF_PATH, help="Path to ERG 2024 PDF")
    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        print(f"Error: PDF not found at {args.pdf}")
        sys.exit(1)

    print("=" * 60)
    print("ERG 2024 Protocol Seeding Script (Actian VectorAI DB)")
    print("=" * 60)

    # Step 1: Parse PDF
    print("\n[1/5] Parsing ERG 2024 PDF...")
    protocols = parse_erg_pdf(args.pdf)
    if not protocols:
        print("No guides extracted. Exiting.")
        sys.exit(1)

    # Step 2: Load embedding model
    print("\n[2/5] Loading sentence-transformers model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("✓ Model loaded: all-MiniLM-L6-v2 (384 dimensions)")

    # Step 3: Connect to Actian VectorAI DB
    address = f"{ACTIAN_HOST}:{ACTIAN_PORT}"
    print(f"\n[3/5] Connecting to Actian VectorAI DB at {address}...")

    client = AsyncCortexClient(address=address)
    await client.connect()
    print("✓ Connected")

    # Step 4: Embed protocols
    print(f"\n[4/5] Embedding {len(protocols)} protocols...")

    ids = []
    vectors = []
    payloads = []

    for i, protocol in enumerate(protocols):
        # We start IDs from 1
        protocol_id = i + 1
        scenario_text = protocol["scenario"]
        # Limit scenario text length for embedding if it's too long, but usually it's fine
        vector = model.encode(scenario_text, normalize_embeddings=True).tolist()

        ids.append(protocol_id)
        vectors.append(vector)
        payloads.append({
            "protocol_text": protocol["protocol_text"],
            "severity": protocol["severity"],
            "category": protocol["category"],
            "tags": protocol["tags"],
            "source": protocol["source"],
            "scenario": protocol["scenario"],
        })

    print(f"\n✓ Generated {len(vectors)} embeddings")

    severity_counts = {}
    for p in protocols:
        sev = p["severity"]
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    print("\nSeverity Distribution:")
    for sev, count in sorted(severity_counts.items()):
        print(f"  {sev:10s}: {count:2d} guides")

    # Step 5: Clear and Batch upsert into VectorAI DB
    print("\n[5/5] Upserting protocols into safety_protocols collection...")
    
    # Delete existing points (replace all existing protocols)
    # The prompt says: "Delete all existing points, then batch_upsert() with int IDs 1..64"
    # To drop the old data and avoid the FAISS invisible ID bug, we use recreate_collection:
    from cortex import DistanceMetric
    try:
        print("Recreating safety_protocols collection...")
        await client.recreate_collection(
            name="safety_protocols",
            dimension=384,
            distance_metric=DistanceMetric.COSINE,
        )
        print("✓ Cleared existing protocols (recreated collection)")
    except Exception as e:
        print(f"Warning during recreate_collection: {e}")

    # Fall back to single upsert due to batch API bugs
    for v_id, vector, payload in zip(ids, vectors, payloads):
        await client.upsert(
            collection_name="safety_protocols",
            id=v_id,
            vector=vector,
            payload=payload,
        )

    print(f"✓ Upserted {len(ids)} protocols")

    # Verification: run 3 test searches
    print("\n[Verify] Running verification searches...")
    
    test_queries = [
        "flammable gas leak",
        "explosive cargo fire",
        "toxic chemical spill"
    ]
    
    for query_text in test_queries:
        print(f"\n  Search: '{query_text}'")
        test_vector = model.encode(query_text, normalize_embeddings=True).tolist()
        try:
            results = await client.search(
                collection_name="safety_protocols",
                query=test_vector,
                top_k=3,
                with_payload=True,
            )
            for r in results:
                guide_src = r.payload.get('source', '?')
                sev = r.payload.get('severity', '?')
                print(f"    - score={r.score:.4f} | {guide_src} | {sev}")
        except Exception as e:
            print(f"    Search failed: {e}")

    await client.close()

    print("\n" + "=" * 60)
    print(f"Total: {len(protocols)} protocols seeded successfully")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
