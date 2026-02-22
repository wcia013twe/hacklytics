import asyncio
from cortex import AsyncCortexClient

async def test():
    client = AsyncCortexClient(address="localhost:50051")
    await client.connect()
    
    try:
        if not await client.has_collection("test_col"):
            await client.create_collection("test_col", 10, "COSINE")
            
        await client.upsert("test_col", 1, [0.1]*10, {"foo": "bar"})
        count = await client.count("test_col")
        print(f"Pre-restart count: {count}")
    finally:
        await client.close()

asyncio.run(test())
