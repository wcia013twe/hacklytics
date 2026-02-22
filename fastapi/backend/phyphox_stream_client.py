"""
Phyphox IMU Data Stream Client

Fetches real-time IMU data from Phyphox Remote Access and displays it in the terminal.

Run this to stream IMU data:
    python backend/phyphox_stream_client.py

Configure in .env:
    IMU_POSTED_URL=http://100.66.12.17
"""

import os
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Configuration from environment
PHYPHOX_URL = os.getenv("IMU_POSTED_URL", "http://100.66.12.17")
POLL_INTERVAL = float(os.getenv("IMU_POLL_INTERVAL", "0.1"))  # 100ms default


class PhyphoxClient:
    """Client for fetching data from Phyphox Remote Access server."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'PhyphoxClient/1.0'})

    def get_data(self, *buffers):
        """
        Fetch data from Phyphox server.

        Args:
            *buffers: Buffer names to fetch (e.g., 'accX', 'accY', 'accZ', 'gyrX', etc.)

        Returns:
            dict: JSON response from Phyphox
        """
        try:
            # Build query string for specific buffers
            if buffers:
                query = '&'.join(buffers)
                url = f"{self.base_url}/get?{query}"
            else:
                url = f"{self.base_url}/get"

            response = self.session.get(url, timeout=2)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            logger.error("⏱️  Timeout connecting to Phyphox server")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ Cannot connect to {self.base_url}")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching data: {e}")
            return None

    def start_experiment(self):
        """Start the Phyphox experiment."""
        try:
            response = self.session.get(f"{self.base_url}/control?cmd=start", timeout=2)
            response.raise_for_status()
            logger.info("▶️  Started Phyphox experiment")
            return True
        except Exception as e:
            logger.error(f"❌ Error starting experiment: {e}")
            return False

    def get_experiment_info(self):
        """Get information about the current experiment."""
        try:
            response = self.session.get(f"{self.base_url}/get", timeout=2)
            response.raise_for_status()
            data = response.json()
            return data
        except Exception as e:
            logger.error(f"❌ Error getting experiment info: {e}")
            return None


def format_sensor_data(data: dict) -> str:
    """Format sensor data for terminal display."""
    if not data or 'buffer' not in data:
        return "No data"

    buffers = data['buffer']
    parts = []

    # Try to extract accelerometer data
    if 'accX' in buffers and 'accY' in buffers and 'accZ' in buffers:
        acc_x = buffers['accX']['buffer'][-1] if buffers['accX']['buffer'] else 0
        acc_y = buffers['accY']['buffer'][-1] if buffers['accY']['buffer'] else 0
        acc_z = buffers['accZ']['buffer'][-1] if buffers['accZ']['buffer'] else 0
        parts.append(f"Acc: ({acc_x:7.3f}, {acc_y:7.3f}, {acc_z:7.3f})")

    # Try to extract gyroscope data
    if 'gyrX' in buffers and 'gyrY' in buffers and 'gyrZ' in buffers:
        gyr_x = buffers['gyrX']['buffer'][-1] if buffers['gyrX']['buffer'] else 0
        gyr_y = buffers['gyrY']['buffer'][-1] if buffers['gyrY']['buffer'] else 0
        gyr_z = buffers['gyrZ']['buffer'][-1] if buffers['gyrZ']['buffer'] else 0
        parts.append(f"Gyr: ({gyr_x:7.3f}, {gyr_y:7.3f}, {gyr_z:7.3f})")

    # Try timestamp
    if 'time' in buffers or 't' in buffers:
        time_key = 'time' if 'time' in buffers else 't'
        time_val = buffers[time_key]['buffer'][-1] if buffers[time_key]['buffer'] else 0
        parts.append(f"t={time_val:.3f}s")

    return " | ".join(parts) if parts else str(list(buffers.keys()))


def stream_imu_data():
    """Main streaming loop."""
    client = PhyphoxClient(PHYPHOX_URL)

    print("\n" + "="*80)
    print("🚀 Phyphox IMU Data Stream Client")
    print("="*80)
    print(f"📡 Connecting to: {PHYPHOX_URL}")
    print(f"⏱️  Poll interval: {POLL_INTERVAL}s ({1/POLL_INTERVAL:.1f} Hz)")
    print("\nPress Ctrl+C to stop")
    print("="*80 + "\n")

    # Test connection
    logger.info("🔍 Testing connection to Phyphox...")
    info = client.get_experiment_info()

    if info is None:
        logger.error("\n❌ Failed to connect to Phyphox server!")
        logger.error(f"\n   Make sure:")
        logger.error(f"   1. Phyphox app is open on your phone")
        logger.error(f"   2. 'Remote Access' is enabled (three-dot menu)")
        logger.error(f"   3. Your computer and phone are on the same network")
        logger.error(f"   4. The URL {PHYPHOX_URL} is correct\n")
        return

    logger.info("✅ Connected to Phyphox!")

    # Display available buffers
    if 'buffer' in info:
        available_buffers = list(info['buffer'].keys())
        logger.info(f"📊 Available data buffers: {', '.join(available_buffers)}")

    # Auto-start if not measuring
    if 'status' in info and not info['status'].get('measuring', False):
        logger.info("▶️  Experiment not running, starting it...")
        client.start_experiment()
        time.sleep(0.5)

    print("\n" + "="*80)
    print("📊 LIVE IMU DATA STREAM")
    print("="*80 + "\n")

    packet_count = 0

    try:
        while True:
            # Fetch latest data
            data = client.get_data()

            if data:
                packet_count += 1
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                sensor_str = format_sensor_data(data)

                # Print to terminal
                print(f"[{timestamp}] #{packet_count:5d} | {sensor_str}")

            # Sleep before next poll
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n" + "="*80)
        logger.info("⏹️  Stopping stream...")
        logger.info(f"📊 Total packets received: {packet_count}")
        print("="*80 + "\n")


if __name__ == "__main__":
    stream_imu_data()
