import asyncio
from cortex import AsyncCortexClient

async def test():
    client = AsyncCortexClient(address="localhost:50051")
    await client.connect()
    
    try:
        # Check if protocols exist
        has_proto = await client.has_collection("safety_protocols")
        print(f"Collection 'safety_protocols' exists: {has_proto}")
        
        if has_proto:
            count = await client.count("safety_protocols")
            print(f"Vector count: {count}")
    finally:
        await client.close()

asyncio.run(test())
