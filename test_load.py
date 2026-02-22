import asyncio
from cortex import AsyncCortexClient
import time

async def test():
    client = AsyncCortexClient(address="localhost:50051")
    await client.connect()
    try:
        if await client.has_collection("safety_protocols"):
            print("Wait 2 seconds for index to load...")
            await asyncio.sleep(2)
            count = await client.count("safety_protocols")
            print(f"Safety Protocols count: {count}")
    finally:
        await client.close()

asyncio.run(test())
