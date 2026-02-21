# Jetson → Backend Interface

**For:** Jetson Engineer
**Source:** `/fastapi/RAG.MD` Section 3.1

---

## What You Need to Do

Send JSON packets via **ZeroMQ PUB** on port **5555** with 9 required fields.

---

## Setup (3 lines)

```python
import zmq, json, time
socket = zmq.Context().socket(zmq.PUB)
socket.bind("tcp://*:5555")
time.sleep(1)  # Let backend connect
```

---

## Packet Format

```json
{
  "device_id": "jetson_alpha_01",
  "session_id": "mission_2026_02_21",
  "timestamp": 1708549201.45,
  "hazard_level": "HIGH",
  "scores": {
    "fire_dominance": 0.6,
    "smoke_opacity": 0.5,
    "proximity_alert": true
  },
  "tracked_objects": [
    {"id": 42, "label": "person", "status": "moving", "duration_in_frame": 5.0}
  ],
  "visual_narrative": "HIGH: Fire near person #42. Fire dominates 60% of view."
}
```

**Send:** `socket.send_string(json.dumps(packet))`

---

## Critical: You Must Compute visual_narrative

**Why on Jetson:** <10ms vs. 50-200ms server-side, 80% less bandwidth

**Pipeline:** `YOLO → BoT-SORT → Heuristics → Templates → narrative`

---

## 1. Fire Dominance (% of frame with fire)

```python
def compute_fire_dominance(fire_bboxes, frame_width, frame_height):
    frame_area = frame_width * frame_height
    total_fire = sum((b[2]-b[0]) * (b[3]-b[1]) for b in fire_bboxes)
    return min(1.0, total_fire / frame_area)
```

---

## 2. Proximity Alert (person near fire)

```python
def compute_proximity_alert(person_bbox, fire_bbox, frame_diagonal):
    # Check overlap
    x1 = max(person_bbox[0], fire_bbox[0])
    y1 = max(person_bbox[1], fire_bbox[1])
    x2 = min(person_bbox[2], fire_bbox[2])
    y2 = min(person_bbox[3], fire_bbox[3])

    intersection = max(0, x2-x1) * max(0, y2-y1)
    person_area = (person_bbox[2]-person_bbox[0]) * (person_bbox[3]-person_bbox[1])
    fire_area = (fire_bbox[2]-fire_bbox[0]) * (fire_bbox[3]-fire_bbox[1])
    iou = intersection / (person_area + fire_area - intersection)

    if iou > 0.1:
        return True  # Direct contact

    # Check distance
    p_center = ((person_bbox[0]+person_bbox[2])/2, (person_bbox[1]+person_bbox[3])/2)
    f_center = ((fire_bbox[0]+fire_bbox[2])/2, (fire_bbox[1]+fire_bbox[3])/2)
    distance = ((p_center[0]-f_center[0])**2 + (p_center[1]-f_center[1])**2)**0.5

    return distance < (0.15 * frame_diagonal)
```

---

## 3. Path Obstruction (forward path blocked)

```python
def compute_path_obstruction(hazard_bboxes, frame_width, frame_height):
    center_left = 0.3 * frame_width
    center_right = 0.7 * frame_width

    occupied = 0
    for bbox in hazard_bboxes:
        overlap_left = max(bbox[0], center_left)
        overlap_right = min(bbox[2], center_right)
        if overlap_right > overlap_left:
            occupied += (overlap_right - overlap_left) * (bbox[3] - bbox[1])

    corridor = (center_right - center_left) * frame_height
    return (occupied / corridor) > 0.3
```

---

## 4. Narrative Templates (use first match)

```python
def generate_narrative(tracked_objects, fire_dom, proximity, path_blocked):
    people = [o for o in tracked_objects if o['label'] == 'person']

    # CRITICAL: proximity + major fire
    if proximity and fire_dom > 0.3 and people:
        return f"CRITICAL: Fire near person #{people[0]['id']}. Fire dominates {int(fire_dom*100)}% of view."

    # HIGH: blocked path or major fire
    if path_blocked or fire_dom > 0.6:
        return f"Fire dominates {int(fire_dom*100)}% of view. Exit path blocked."

    # MODERATE: some fire
    if fire_dom > 0.1:
        return f"Fire detected. Fire dominates {int(fire_dom*100)}% of view."

    # LOW: objects present
    if tracked_objects:
        return f"{len(tracked_objects)} objects detected."

    # SAFE
    return "No hazards detected."
```

Truncate to 200 chars: `narrative[:200]`

---

## 5. Hazard Level

```python
def compute_hazard_level(fire_dom, smoke_op, proximity):
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
```

---

## Complete Example

```python
import zmq, json, time

class BackendPublisher:
    def __init__(self):
        self.socket = zmq.Context().socket(zmq.PUB)
        self.socket.bind("tcp://*:5555")
        time.sleep(1)
        self.session_id = f"mission_{time.strftime('%Y_%m_%d')}"

    def send(self, yolo_output, tracked_objects, frame_w, frame_h):
        # Extract bboxes
        fires = [o['bbox'] for o in tracked_objects if o['label'] == 'fire']
        people = [o['bbox'] for o in tracked_objects if o['label'] == 'person']
        hazards = fires + [o['bbox'] for o in tracked_objects if o['label'] == 'smoke']

        # Compute heuristics
        fire_dom = self.compute_fire_dominance(fires, frame_w, frame_h)
        smoke_op = 0.5  # Your smoke computation here

        proximity = False
        if fires and people:
            diagonal = (frame_w**2 + frame_h**2)**0.5
            proximity = self.compute_proximity_alert(people[0], fires[0], diagonal)

        path_blocked = self.compute_path_obstruction(hazards, frame_w, frame_h)

        # Build packet
        packet = {
            "device_id": "jetson_alpha_01",
            "session_id": self.session_id,
            "timestamp": time.time(),
            "hazard_level": self.compute_hazard_level(fire_dom, smoke_op, proximity),
            "scores": {
                "fire_dominance": fire_dom,
                "smoke_opacity": smoke_op,
                "proximity_alert": proximity
            },
            "tracked_objects": [
                {"id": o['id'], "label": o['label'],
                 "status": o.get('status', 'unknown'),
                 "duration_in_frame": o.get('duration', 0.0)}
                for o in tracked_objects
            ],
            "visual_narrative": self.generate_narrative(
                tracked_objects, fire_dom, proximity, path_blocked
            )
        }

        self.socket.send_string(json.dumps(packet))
        print(f"[SENT] {packet['hazard_level']} | {packet['visual_narrative'][:50]}")

    # Include compute_fire_dominance, compute_proximity_alert,
    # compute_path_obstruction, generate_narrative, compute_hazard_level
    # from above

# Usage
publisher = BackendPublisher()
for frame in camera_stream:
    yolo_output = run_yolo(frame)
    tracked = run_botsort(yolo_output)
    publisher.send(yolo_output, tracked, 1920, 1080)
```

---

## Checklist

- [ ] ZeroMQ installed: `pip install pyzmq`
- [ ] Fire dominance computed (0.0-1.0)
- [ ] Proximity alert computed (bool)
- [ ] Path obstruction computed (bool)
- [ ] Narrative generator implemented (<200 chars)
- [ ] Hazard level classifier (CLEAR/LOW/MODERATE/HIGH/CRITICAL)
- [ ] Test: `print(json.dumps(packet, indent=2))`

---

## Network

**Find your IP:** `hostname -I`
**Backend connects to:** `tcp://YOUR_JETSON_IP:5555`

---

## Troubleshooting

**Not receiving?**
```bash
sudo ufw allow 5555
netstat -an | grep 5555
```

**Backend errors?**
- Hazard level must be uppercase
- Narrative must be ≤200 chars
- All 9 fields required

---

That's it. ZeroMQ fire-and-forget, no acks needed.
