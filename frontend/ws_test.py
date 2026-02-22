import websockets
import asyncio
import json

async def listen():
    uri = 'ws://127.0.0.1:8080/ws'
    try:
        async with websockets.connect(uri) as ws:
            print('Connected')
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                print(json.dumps(data.get('rag_data'), indent=2))
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(listen())
