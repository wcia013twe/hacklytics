#!/usr/bin/env python3
"""
Test script to verify dashboard integration with backend.

Tests:
1. Dashboard can connect via WebSocket
2. Backend sends correctly formatted messages
3. API endpoints work as fallback
"""

import asyncio
import json
import httpx
import websockets
from datetime import datetime


async def test_websocket_connection():
    """Test WebSocket connection to /ws/dashboard-001"""
    print("\n" + "="*60)
    print("TEST 1: WebSocket Connection")
    print("="*60)

    uri = "ws://localhost:8000/ws/dashboard-001"

    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ Connected to {uri}")

            # Send ping
            await websocket.send(json.dumps({"type": "ping"}))
            print("✅ Sent ping message")

            # Wait for any messages (timeout after 2 seconds)
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                data = json.loads(message)
                print(f"✅ Received message: {data.get('message_type', 'unknown')}")
                print(f"   Data: {json.dumps(data, indent=2)[:200]}...")
            except asyncio.TimeoutError:
                print("ℹ️  No messages received (normal if no telemetry active)")

            return True

    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
        return False


async def test_inject_endpoint():
    """Test /test/inject endpoint with sample telemetry"""
    print("\n" + "="*60)
    print("TEST 2: Test Inject Endpoint")
    print("="*60)

    # Sample telemetry packet
    sample_packet = {
        "timestamp": datetime.now().timestamp(),
        "session_id": "dashboard-001",
        "device_id": "test-device",
        "hazard_level": "HIGH",
        "scores": {
            "fire_dominance": 0.85,
            "smoke_opacity": 0.60,
            "proximity_alert": True
        },
        "tracked_objects": [],
        "visual_narrative": "High fire detected in area, person nearby",
        "location": {"latitude": 0, "longitude": 0}
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://localhost:8000/test/inject",
                json=sample_packet,
                timeout=5.0
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Packet injected successfully")
                print(f"   Success: {result.get('success', False)}")
                print(f"   Total time: {result.get('total_time_ms', 0):.2f}ms")
                return True
            else:
                print(f"❌ Injection failed: HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False

        except Exception as e:
            print(f"❌ Injection failed: {e}")
            return False


async def test_api_metrics():
    """Test /api/metrics endpoint"""
    print("\n" + "="*60)
    print("TEST 3: API Metrics Endpoint")
    print("="*60)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "http://localhost:8000/api/metrics",
                timeout=5.0
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Metrics endpoint working")
                print(f"   Status: {data.get('status')}")
                print(f"   RAG Healthy: {data.get('rag_healthy')}")
                print(f"   Metrics: {json.dumps(data.get('metrics', {}), indent=2)}")
                print(f"   Latest Data: {len(data.get('latest_data', {}))} devices")
                return True
            else:
                print(f"❌ Metrics failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Metrics failed: {e}")
            return False


async def test_health_endpoint():
    """Test /health endpoint"""
    print("\n" + "="*60)
    print("TEST 4: Health Check Endpoint")
    print("="*60)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "http://localhost:8000/health",
                timeout=5.0
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health endpoint working")
                print(f"   Status: {data.get('status')}")
                print(f"   RAG Healthy: {data.get('rag_healthy')}")
                return True
            else:
                print(f"❌ Health check failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Dashboard Integration Test Suite")
    print("="*60)
    print("Testing connection between dashboard.html and backend...")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = []

    # Test 1: Health check
    results.append(("Health Check", await test_health_endpoint()))

    # Test 2: API metrics
    results.append(("API Metrics", await test_api_metrics()))

    # Test 3: WebSocket
    results.append(("WebSocket", await test_websocket_connection()))

    # Test 4: Inject endpoint
    results.append(("Test Inject", await test_inject_endpoint()))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)

    print(f"\n{total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("\n✅ All tests passed! Dashboard should work correctly.")
        print("\nTo view the dashboard:")
        print("  1. Make sure ingest service is running: python -m backend.main_ingest")
        print("  2. Open browser to: http://localhost:8000")
        print("  3. WebSocket will auto-connect to: ws://localhost:8000/ws/dashboard-001")
    else:
        print("\n⚠️  Some tests failed. Check backend service status.")
        print("   Ensure the ingest service is running on port 8000")


if __name__ == "__main__":
    asyncio.run(main())
