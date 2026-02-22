import asyncio
import urllib.request
from urllib.error import HTTPError

def test_upgrade():
    req = urllib.request.Request("http://127.0.0.1:8001/ws/test", headers={
        "Connection": "Upgrade",
        "Upgrade": "websocket",
        "Sec-WebSocket-Version": "13",
        "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="
    })
    try:
        with urllib.request.urlopen(req) as response:
            print(response.read())
    except HTTPError as e:
        print(f"Failed with {e.code}: {e.read().decode()}")
        print(e.headers)

test_upgrade()
