import asyncio
from cortex import AsyncCortexClient

async def check():
    client = AsyncCortexClient(address="localhost:50051")
    try:
        await client.connect()
        collections = await client.list_collections()
        print(f"Collections: {[c.name for c in collections]}")
        for c in collections:
            stats = await client.get_collection_stats(c.name)
            print(f"Collection {c.name}: {stats}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(check())
