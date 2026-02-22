import asyncio
import websockets

async def test():
    try:
        async with websockets.connect("ws://127.0.0.1:8001/ws/test") as ws:
            print("Connected successfully!")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())
