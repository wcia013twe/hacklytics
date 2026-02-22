# Jetson Nano Orin Setup Guide
## Connecting Your Jetson to the RAG Pipeline

This guide will help you set up your **NVIDIA Jetson Nano Orin** to stream fire detection telemetry to the RAG backend via ZeroMQ.

---

## Overview

```
┌─────────────────────┐
│  Jetson Nano Orin   │
│                     │
│  Camera → YOLO →    │
│  BoT-SORT → Compute │
│  Telemetry          │
└──────────┬──────────┘
           │ ZeroMQ
           │ tcp://BACKEND_IP:5555
           ↓
┌──────────────────────┐
│   RAG Backend        │
│   (Ingest Service)   │
│   Port 5555          │
└──────────────────────┘
```

---

## Prerequisites

### Hardware
- ✅ NVIDIA Jetson Nano Orin
- ✅ USB/CSI Camera (any camera compatible with Jetson)
- ✅ Network connection (WiFi/Ethernet) to backend server

### Software (on Jetson)
- ✅ JetPack 5.x or later
- ✅ Python 3.8+
- ✅ OpenCV with CUDA support
- ✅ PyTorch (for YOLO)

---

## Step 1: Install Dependencies on Jetson

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install ZeroMQ
sudo apt install -y libzmq3-dev
pip3 install pyzmq

# Install Python dependencies
pip3 install opencv-python numpy torch torchvision

# Optional: Install ultralytics for YOLOv8
pip3 install ultralytics
```

---

## Step 2: Configure Network

### Find Your Backend IP

On your **backend server** (where Docker is running), run:
```bash
hostname -I
```

Example output: `192.168.1.100`

### Test Connectivity from Jetson

```bash
# Ping backend from Jetson
ping 192.168.1.100

# Check if port 5555 is reachable (backend must be running)
nc -zv 192.168.1.100 5555
```

### Open Firewall on Backend (if needed)

```bash
# On backend server
sudo ufw allow 5555/tcp
sudo ufw reload
```

---

## Step 3: Jetson Streaming Script

Create this file on your Jetson: `~/fire_detection/jetson_stream.py`

```python
#!/usr/bin/env python3
"""
Jetson Nano Orin Fire Detection Stream
Sends telemetry packets to RAG backend via ZeroMQ
"""

import zmq
import json
import time
import cv2
import numpy as np
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

BACKEND_IP = "192.168.1.100"  # CHANGE THIS to your backend IP
BACKEND_PORT = 5555
DEVICE_ID = "jetson_orin_01"  # Unique identifier for this Jetson
SESSION_ID = f"mission_{datetime.now().strftime('%Y_%m_%d')}"

CAMERA_ID = 0  # 0 for USB camera, or CSI camera path
FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080

# ============================================================================
# ZeroMQ Publisher Setup
# ============================================================================

class BackendPublisher:
    """Publishes telemetry packets to RAG backend via ZeroMQ"""

    def __init__(self, backend_ip: str, port: int, device_id: str):
        self.device_id = device_id
        self.session_id = SESSION_ID

        # Create ZeroMQ context and socket
        context = zmq.Context()
        self.socket = context.socket(zmq.PUB)

        # Connect to backend (not bind - backend binds, we connect)
        endpoint = f"tcp://{backend_ip}:{port}"
        self.socket.connect(endpoint)

        print(f"✅ Connected to backend: {endpoint}")
        print(f"📡 Device ID: {device_id}")
        print(f"🎯 Session ID: {self.session_id}")

        # Give ZeroMQ time to establish connection
        time.sleep(1)

    def send_packet(self, telemetry: dict):
        """Send telemetry packet to backend"""
        try:
            packet_json = json.dumps(telemetry)
            self.socket.send_string(packet_json)
            return True
        except Exception as e:
            print(f"❌ Error sending packet: {e}")
            return False

# ============================================================================
# Computer Vision & Heuristics
# ============================================================================

def compute_fire_dominance(fire_bboxes: list, frame_w: int, frame_h: int) -> float:
    """
    Compute fire dominance: percentage of frame covered by fire

    Args:
        fire_bboxes: List of [x1, y1, x2, y2] bounding boxes
        frame_w, frame_h: Frame dimensions

    Returns:
        Float between 0.0 and 1.0
    """
    if not fire_bboxes:
        return 0.0

    frame_area = frame_w * frame_h
    total_fire_area = sum(
        (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        for bbox in fire_bboxes
    )

    return min(1.0, total_fire_area / frame_area)


def compute_proximity_alert(person_bbox: list, fire_bbox: list, frame_diagonal: float) -> bool:
    """
    Check if person is dangerously close to fire

    Args:
        person_bbox: [x1, y1, x2, y2]
        fire_bbox: [x1, y1, x2, y2]
        frame_diagonal: sqrt(width^2 + height^2)

    Returns:
        True if proximity alert should trigger
    """
    # Check for overlap (IoU)
    x1 = max(person_bbox[0], fire_bbox[0])
    y1 = max(person_bbox[1], fire_bbox[1])
    x2 = min(person_bbox[2], fire_bbox[2])
    y2 = min(person_bbox[3], fire_bbox[3])

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    person_area = (person_bbox[2] - person_bbox[0]) * (person_bbox[3] - person_bbox[1])
    fire_area = (fire_bbox[2] - fire_bbox[0]) * (fire_bbox[3] - fire_bbox[1])

    if intersection > 0:
        iou = intersection / (person_area + fire_area - intersection)
        if iou > 0.1:
            return True  # Direct contact/overlap

    # Check distance between centers
    p_center_x = (person_bbox[0] + person_bbox[2]) / 2
    p_center_y = (person_bbox[1] + person_bbox[3]) / 2
    f_center_x = (fire_bbox[0] + fire_bbox[2]) / 2
    f_center_y = (fire_bbox[1] + fire_bbox[3]) / 2

    distance = np.sqrt((p_center_x - f_center_x)**2 + (p_center_y - f_center_y)**2)

    # Alert if within 15% of frame diagonal
    return distance < (0.15 * frame_diagonal)


def compute_hazard_level(fire_dom: float, smoke_op: float, proximity: bool) -> str:
    """
    Classify hazard level based on fire dominance, smoke, and proximity

    Returns: "CLEAR" | "LOW" | "MODERATE" | "HIGH" | "CRITICAL"
    """
    if proximity and fire_dom > 0.4:
        return "CRITICAL"
    elif fire_dom > 0.6 or smoke_op > 0.8:
        return "CRITICAL"
    elif fire_dom > 0.4 or smoke_op > 0.6:
        return "HIGH"
    elif fire_dom > 0.2 or smoke_op > 0.4:
        return "MODERATE"
    elif fire_dom > 0.05 or smoke_op > 0.1:
        return "LOW"
    return "CLEAR"


def generate_visual_narrative(tracked_objects: list, fire_dom: float, proximity: bool) -> str:
    """
    Generate concise visual narrative (max 200 chars)

    Args:
        tracked_objects: List of detected objects
        fire_dom: Fire dominance (0.0-1.0)
        proximity: Whether proximity alert is active

    Returns:
        Narrative string (≤200 chars)
    """
    people = [obj for obj in tracked_objects if obj['label'] == 'person']

    # CRITICAL: proximity + major fire
    if proximity and fire_dom > 0.3 and people:
        narrative = f"CRITICAL: Fire near person #{people[0]['id']}. Fire dominates {int(fire_dom*100)}% of view."

    # HIGH: major fire
    elif fire_dom > 0.6:
        narrative = f"Fire dominates {int(fire_dom*100)}% of view. Exit path may be blocked."

    # MODERATE: some fire
    elif fire_dom > 0.1:
        narrative = f"Fire detected. Fire dominates {int(fire_dom*100)}% of view."

    # LOW: objects present
    elif tracked_objects:
        obj_summary = ", ".join(f"{obj['label']} #{obj['id']}" for obj in tracked_objects[:3])
        narrative = f"{len(tracked_objects)} objects detected: {obj_summary}"

    # CLEAR
    else:
        narrative = "No hazards detected. Area clear."

    # Enforce 200-char limit
    return narrative[:200]


# ============================================================================
# Mock Detection (Replace with Your YOLO Model)
# ============================================================================

def mock_detect_objects(frame: np.ndarray) -> list:
    """
    REPLACE THIS with your actual YOLO detection

    This is a placeholder that returns mock detections for testing.

    Expected output format:
    [
        {
            'id': int,          # Object tracking ID
            'label': str,       # 'fire', 'person', 'smoke', etc.
            'bbox': [x1, y1, x2, y2],  # Bounding box
            'confidence': float,
            'status': str,      # 'moving', 'stationary', etc.
            'duration': float   # Seconds in frame
        },
        ...
    ]
    """
    # MOCK DETECTION - Replace with real YOLO
    return [
        {
            'id': 1,
            'label': 'fire',
            'bbox': [500, 400, 700, 600],
            'confidence': 0.95,
            'status': 'growing',
            'duration': 2.5
        }
    ]


# ============================================================================
# Main Streaming Loop
# ============================================================================

def main():
    print("\n" + "="*80)
    print("🔥 JETSON NANO ORIN → RAG PIPELINE STREAMER")
    print("="*80)

    # Initialize publisher
    publisher = BackendPublisher(BACKEND_IP, BACKEND_PORT, DEVICE_ID)

    # Initialize camera
    print(f"\n📹 Opening camera {CAMERA_ID}...")
    cap = cv2.VideoCapture(CAMERA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    if not cap.isOpened():
        print("❌ Error: Could not open camera")
        return

    print("✅ Camera opened successfully")
    print(f"\n🚀 Starting stream... (Press Ctrl+C to stop)")
    print("="*80 + "\n")

    frame_count = 0
    frame_diagonal = np.sqrt(FRAME_WIDTH**2 + FRAME_HEIGHT**2)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠️  Failed to read frame")
                time.sleep(0.1)
                continue

            frame_count += 1

            # ===== REPLACE THIS WITH YOUR YOLO MODEL =====
            detected_objects = mock_detect_objects(frame)
            # ==============================================

            # Extract fire and person bounding boxes
            fire_bboxes = [obj['bbox'] for obj in detected_objects if obj['label'] == 'fire']
            person_bboxes = [obj['bbox'] for obj in detected_objects if obj['label'] == 'person']

            # Compute heuristics
            fire_dom = compute_fire_dominance(fire_bboxes, FRAME_WIDTH, FRAME_HEIGHT)
            smoke_op = 0.3  # TODO: Implement smoke detection

            proximity = False
            if fire_bboxes and person_bboxes:
                proximity = compute_proximity_alert(person_bboxes[0], fire_bboxes[0], frame_diagonal)

            hazard_level = compute_hazard_level(fire_dom, smoke_op, proximity)
            narrative = generate_visual_narrative(detected_objects, fire_dom, proximity)

            # Build telemetry packet
            telemetry = {
                "device_id": publisher.device_id,
                "session_id": publisher.session_id,
                "timestamp": time.time(),
                "hazard_level": hazard_level,
                "scores": {
                    "fire_dominance": fire_dom,
                    "smoke_opacity": smoke_op,
                    "proximity_alert": proximity
                },
                "tracked_objects": [
                    {
                        "id": obj['id'],
                        "label": obj['label'],
                        "status": obj.get('status', 'unknown'),
                        "duration_in_frame": obj.get('duration', 0.0)
                    }
                    for obj in detected_objects
                ],
                "visual_narrative": narrative
            }

            # Send to backend
            success = publisher.send_packet(telemetry)

            if success:
                print(f"[{frame_count:5d}] {hazard_level:8s} | Fire: {fire_dom:5.1%} | {narrative[:50]}")

            # Control frame rate (adjust as needed)
            time.sleep(0.5)  # 2 FPS

    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping stream...")

    finally:
        cap.release()
        print("✅ Camera released")
        print("✅ Stream ended\n")


if __name__ == "__main__":
    main()
```

---

## Step 4: Run the Stream

### On Backend (Start Docker Services)

```bash
cd /Users/wes/Desktop/Project/hacklytics/hacklytics/fastapi
docker-compose up -d
```

### On Jetson

```bash
# Make script executable
chmod +x ~/fire_detection/jetson_stream.py

# Run the stream
python3 ~/fire_detection/jetson_stream.py
```

---

## Step 5: Verify Connection

### Check Backend Logs

```bash
# On your Mac/backend
docker logs -f fastapi-rag-1

# You should see:
# "Reflex: jetson_orin_01 | HIGH | GROWING | 45.23ms | 0 clients"
```

### View Dashboard

Open your browser:
```
http://localhost:8080/realtime_dashboard.html
```

Or use terminal dashboard:
```bash
python3 scripts/terminal_dashboard.py
```

---

## Step 6: Integration with YOLO

Replace the `mock_detect_objects()` function with your actual YOLO model:

```python
from ultralytics import YOLO

# Load your trained model
model = YOLO('path/to/your/fire_detection_model.pt')

def detect_objects(frame: np.ndarray) -> list:
    """Run YOLO inference on frame"""
    results = model(frame, conf=0.5)

    detected_objects = []
    for r in results:
        for box in r.boxes:
            detected_objects.append({
                'id': int(box.id) if hasattr(box, 'id') else 0,
                'label': model.names[int(box.cls)],
                'bbox': box.xyxy[0].tolist(),
                'confidence': float(box.conf),
                'status': 'detected',
                'duration': 1.0  # Track this with BoT-SORT
            })

    return detected_objects
```

---

## Troubleshooting

### ❌ "Connection refused" error

**Cause**: Backend not reachable or firewall blocking

**Fix**:
```bash
# On backend
sudo ufw allow 5555/tcp
netstat -an | grep 5555  # Should show LISTEN
```

### ❌ "Camera not found"

**Cause**: Wrong camera ID

**Fix**:
```bash
# List available cameras
v4l2-ctl --list-devices

# Try different IDs in script: CAMERA_ID = 0, 1, 2, etc.
```

### ❌ Backend shows "Invalid packet" errors

**Cause**: Missing required fields or wrong format

**Fix**: Check logs for specific validation errors. Common issues:
- `hazard_level` must be uppercase: "HIGH", not "high"
- `visual_narrative` must be ≤200 chars
- All 9 fields must be present

### ❌ No data appearing on dashboard

**Cause**: WebSocket not connected or session_id mismatch

**Fix**:
- Check browser console for WebSocket errors
- Ensure `session_id` on Jetson matches what dashboard expects
- Try refreshing dashboard

---

## Next Steps

1. ✅ **Test with mock data** (use provided script as-is)
2. ✅ **Verify backend receives packets** (check Docker logs)
3. ✅ **View dashboard** (http://localhost:8080)
4. ✅ **Integrate your YOLO model** (replace mock_detect_objects)
5. ✅ **Add BoT-SORT tracking** (for persistent object IDs)
6. ✅ **Implement smoke detection** (update smoke_opacity calculation)

---

## Performance Tips

- **Reduce latency**: Lower camera resolution or frame rate
- **Batch processing**: Send packets every N frames instead of every frame
- **GPU acceleration**: Ensure YOLO runs on CUDA (check with `nvidia-smi`)
- **Network optimization**: Use wired Ethernet instead of WiFi

---

## Reference

- Full packet spec: [JETSON_SPEC.md](../reference/JETSON_SPEC.md)
- RAG architecture: [RAG.MD](../overview/RAG.MD)
- Testing workflow: [TEST_WORKFLOW.md](../testing/TEST_WORKFLOW.md)

---

**Questions?** Check logs with `docker logs -f fastapi-rag-1`
