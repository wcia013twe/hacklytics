import asyncio
import os
from cortex import AsyncCortexClient

async def check():
    try:
        client = AsyncCortexClient(address=f'{os.getenv("ACTIAN_HOST", "vectoraidb")}:{os.getenv("ACTIAN_PORT", "50051")}')
        await client.connect()
        collections = await client.list_collections()
        print(f"Collections: {[c.name for c in collections]}")
        for c in collections:
            count = await client.count(c.name)
            print(f"Collection {c.name}: {count} items")
        await client.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
