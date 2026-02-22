#!/usr/bin/env python3
"""
Quick Healthcheck Script for Actian VectorAI DB via gRPC
"""

import asyncio
import os
import sys

try:
    from cortex import AsyncCortexClient
except ImportError:
    print("Error: actiancortex package not found.")
    sys.exit(1)

ACTIAN_HOST = os.getenv("ACTIAN_HOST", "localhost")
ACTIAN_PORT = int(os.getenv("ACTIAN_PORT", "50051"))

async def main():
    address = f"{ACTIAN_HOST}:{ACTIAN_PORT}"
    print(f"Connecting to VectorAI DB at {address}...")
    
    client = AsyncCortexClient(address=address)
    
    try:
        await client.connect()
        # Verify connection and ping health
        version, uptime = await client.health_check()
        print("\n✅ Health Check Passed!")
        print(f"   Database Version : {version}")
        print(f"   Uptime (seconds): {uptime}")
        
    except Exception as e:
        print(f"\n❌ Health Check Failed: {e}")
        sys.exit(1)
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
