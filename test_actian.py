import asyncio
from cortex import AsyncCortexClient

async def test_collections():
    client = AsyncCortexClient(address="localhost:50051")
    await client.connect()
    try:
        has_protocol = await client.has_collection("safety_protocols")
        print(f"Has safety_protocols: {has_protocol}")
        if has_protocol:
            stats = await client.get_collection_stats("safety_protocols")
            print(f"Stats: {stats}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()

asyncio.run(test_collections())
