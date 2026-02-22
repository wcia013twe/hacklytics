#!/usr/bin/env python3
"""
Test VectorAI DB connectivity using the Cortex Python client.
This will help diagnose if the server is actually running despite health check failures.
"""

import sys
import time

try:
    from cortex import CortexClient
    print("✓ Cortex client library found")
except ImportError:
    print("✗ Cortex client not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "actian-cortex-client"])
    from cortex import CortexClient
    print("✓ Cortex client installed")

def test_connection(server_address="localhost:50051", timeout_seconds=10):
    """
    Attempt to connect to VectorAI DB and run health check.

    Args:
        server_address: gRPC server address (default: localhost:50051)
        timeout_seconds: How long to wait for connection
    """
    print(f"\n{'='*60}")
    print(f"Testing VectorAI DB connection at {server_address}")
    print(f"{'='*60}\n")

    try:
        print(f"[1/3] Creating Cortex client...")
        client = CortexClient(server_address)
        print(f"      ✓ Client created successfully")

        print(f"\n[2/3] Calling health_check()...")
        start_time = time.time()

        # Try health check with timeout
        version, uptime = client.health_check()

        elapsed = time.time() - start_time
        print(f"      ✓ Health check passed!")
        print(f"      - Version: {version}")
        print(f"      - Uptime: {uptime}")
        print(f"      - Response time: {elapsed:.2f}s")

        print(f"\n[3/3] Testing basic collection operation...")
        # Try creating a test collection
        test_collection = f"test_collection_{int(time.time())}"
        client.create_collection(
            name=test_collection,
            dimension=128,
            distance_metric="cosine"
        )
        print(f"      ✓ Created test collection: {test_collection}")

        # Clean up
        client.delete_collection(test_collection)
        print(f"      ✓ Deleted test collection")

        print(f"\n{'='*60}")
        print(f"✅ SUCCESS: VectorAI DB is working correctly!")
        print(f"{'='*60}\n")

        return True

    except ConnectionError as e:
        print(f"      ✗ Connection failed: {e}")
        print(f"\n{'='*60}")
        print(f"❌ FAILED: Cannot connect to VectorAI DB")
        print(f"{'='*60}\n")
        print(f"\nTroubleshooting:")
        print(f"1. Check if container is running: docker ps | grep vectoraidb")
        print(f"2. Check container logs: docker logs hacklytics_vectoraidb")
        print(f"3. Verify port 50051 is exposed: docker port hacklytics_vectoraidb")
        print(f"4. Check if server process is running: docker exec hacklytics_vectoraidb ps aux")
        return False

    except Exception as e:
        print(f"      ✗ Unexpected error: {type(e).__name__}: {e}")
        print(f"\n{'='*60}")
        print(f"❌ FAILED: Unexpected error occurred")
        print(f"{'='*60}\n")
        return False

if __name__ == "__main__":
    # Allow custom server address from command line
    server = sys.argv[1] if len(sys.argv) > 1 else "localhost:50051"

    success = test_connection(server)
    sys.exit(0 if success else 1)
