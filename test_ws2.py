import asyncio
import urllib.request
from urllib.error import HTTPError
import base64
import os

def test_upgrade():
    key = base64.b64encode(os.urandom(16)).decode('utf-8')
    req = urllib.request.Request("http://127.0.0.1:8001/ws/test", headers={
        "Connection": "Upgrade",
        "Upgrade": "websocket",
        "Sec-WebSocket-Version": "13",
        "Sec-WebSocket-Key": key
    })
    try:
        with urllib.request.urlopen(req) as response:
            print("Status:", response.status)
            print(response.headers)
    except HTTPError as e:
        print(f"Failed with {e.code}: {e.read().decode('utf-8', errors='ignore')}")
        print(e.headers)

test_upgrade()
