import asyncio
from cortex import AsyncCortexClient

async def test():
    client = AsyncCortexClient(address="localhost:50051")
    await client.connect()
    
    try:
        count = await client.count("test_col")
        print(f"Post-restart count: {count}")
    finally:
        await client.close()

asyncio.run(test())
