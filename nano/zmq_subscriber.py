"""
ZeroMQ subscriber — run this on your laptop/backend.

The backend binds; the Jetson connects. This means you start this first,
then start main.py on the Jetson (order doesn't strictly matter with ZMQ,
but it's the cleaner mental model).

Usage:
    python3 zmq_subscriber.py
"""

import zmq
import json

PORT = 5555

ctx = zmq.Context()
sock = ctx.socket(zmq.SUB)
sock.bind(f"tcp://*:{PORT}")
sock.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all messages

print(f"[ZMQ] Subscriber bound on port {PORT} — waiting for Jetson...")

try:
    while True:
        raw = sock.recv_string()
        print(json.dumps(json.loads(raw), indent=2))

except KeyboardInterrupt:
    print("\n[ZMQ] Subscriber stopped.")
finally:
    sock.close()
    ctx.term()
