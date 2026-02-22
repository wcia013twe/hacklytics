import asyncio
import os
import sys
import time
from sentence_transformers import SentenceTransformer

# Add parent to path to import backend modules if needed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cortex import AsyncCortexClient

async def benchmark_db():
    print("============================================================")
    print("Benchmarking Actian VectorAI DB Search Latency")
    print("============================================================\n")
    
    # Connect
    actian_host = os.getenv("ACTIAN_HOST", "localhost")
    actian_port = int(os.getenv("ACTIAN_PORT", 50051))
    print(f"Connecting to {actian_host}:{actian_port}...")
    client = AsyncCortexClient(address=f"{actian_host}:{actian_port}")
    await client.connect()
    print("Connected.\n")
    
    # Pre-embed query to isolate DB time
    print("Pre-loading embedding model (Warmup)...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    query_text = "toxic gas leak in warehouse"
    vector = model.encode(query_text, normalize_embeddings=True).tolist()
    print("Model loaded and query embedded.\n")
    
    # 1. First query (Cold Start in DB context)
    print("--- 1. Testing DB Cold Search (First Query) ---")
    start = time.perf_counter()
    await client.search(
        collection_name="safety_protocols",
        query=vector,
        top_k=2,
        with_payload=False
    )
    first_query_time = (time.perf_counter() - start) * 1000
    print(f"First Search Latency: {first_query_time:.2f} ms\n")
    
    # 2. Loop for average (Warm Search)
    num_tests = 100
    print(f"--- 2. Testing DB Warm Search (Average over {num_tests} Queries) ---")
    latencies = []
    
    for i in range(num_tests):
        start = time.perf_counter()
        await client.search(
            collection_name="safety_protocols",
            query=vector,
            top_k=2,
            with_payload=True
        )
        latency = (time.perf_counter() - start) * 1000
        latencies.append(latency)
        
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    min_latency = min(latencies)
    
    print(f"Completed {num_tests} queries.")
    print(f"▶ Average Latency: {avg_latency:.2f} ms")
    print(f"▶ Minimum Latency: {min_latency:.2f} ms")
    print(f"▶ Maximum Latency: {max_latency:.2f} ms")
    
    print("\n============================================================")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(benchmark_db())
