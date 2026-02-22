import time
import math

from spatial_heuristics import compute_scene_heuristics


# Maps internal fusion states → schema hazard levels
_HAZARD_MAP = {
    "SAFE":               "CLEAR",
    "FALSE_ALARM_VISUAL": "LOW",
    "HIDDEN_HEAT_SOURCE": "HIGH",
    "CRITICAL_CONFIRMED": "HIGH",   # escalates to CRITICAL when temp >= TEMP_CRIT
}


class ReflexEngine:
    TEMP_WARN = 50.0          # °C
    TEMP_CRIT = 80.0          # °C — escalates CRITICAL_CONFIRMED → CRITICAL
    CONF_THRESHOLD = 0.4
    STATIONARY_PX = 20        # pixels moved over 3s to be considered stationary
    STATIONARY_WINDOW = 3.0   # seconds
    FIRE_GROWTH_WINDOW = 5.0  # seconds used to compute growth_rate
    TRACK_EXPIRY = 5.0        # seconds before an unseen track is removed

    def __init__(self, publisher):
        self.publisher = publisher
        self.last_sent_state = {}
        self.last_sent_time = 0
        self._tracks = {}   # track_id → track record

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_frame(self, frame_shape, yolov8_results, thermal_max_c):
        now = time.time()
        h, w = frame_shape[:2]
        frame_area = h * w

        # 1. Parse detections — build flat list for spatial heuristics
        fire_dominance = 0.0
        all_detections = []

        if yolov8_results and len(yolov8_results) > 0:
            result = yolov8_results[0]
            for box in result.boxes:
                cls   = int(box.cls[0])
                label = result.names[cls]
                conf  = float(box.conf[0])
                if conf < self.CONF_THRESHOLD:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                area     = ((x2 - x1) * (y2 - y1)) / frame_area
                cx, cy   = (x1 + x2) / 2, (y1 + y2) / 2
                track_id = int(box.id[0]) if box.id is not None else None

                all_detections.append({
                    "label":      label,
                    "bbox":       [x1, y1, x2, y2],
                    "confidence": conf,
                })

                if label == "fire":
                    fire_dominance = max(fire_dominance, min(area / 0.3, 1.0))
                    if track_id is not None:
                        self._update_track(track_id, "fire", cx, cy, area, now)
                elif label == "person":
                    if track_id is not None:
                        self._update_track(track_id, "person", cx, cy, area, now)

        # 2. Expire stale tracks
        self._tracks = {
            tid: t for tid, t in self._tracks.items()
            if now - t["last_seen"] < self.TRACK_EXPIRY
        }

        # 3. Spatial heuristics — proximity, obstruction, dominance + narrative
        scene = compute_scene_heuristics(all_detections, (h, w))
        spatial_scores   = scene["scores"]
        visual_narrative = scene["narrative"][:200]
        proximity_alert  = spatial_scores["proximity"] > 0.5

        # 4. Build tracked_objects
        tracked_objects = self._build_tracked_objects(now)

        # 5. Fusion logic
        is_hot         = thermal_max_c > self.TEMP_WARN
        is_visual_fire = fire_dominance > 0.1

        if is_hot and is_visual_fire:
            internal = "CRITICAL_CONFIRMED"
        elif is_hot:
            internal = "HIDDEN_HEAT_SOURCE"
        elif is_visual_fire:
            internal = "FALSE_ALARM_VISUAL"
        else:
            internal = "SAFE"

        hazard_level = _HAZARD_MAP[internal]
        if internal == "CRITICAL_CONFIRMED" and thermal_max_c >= self.TEMP_CRIT:
            hazard_level = "CRITICAL"

        # 6. Build packet
        packet = {
            "timestamp":    now,
            "hazard_level": hazard_level,
            "scores": {
                "fire_dominance":  round(fire_dominance, 4),
                "proximity_alert": proximity_alert,
                "proximity":       spatial_scores["proximity"],
                "obstruction":     spatial_scores["obstruction"],
                "dominance":       spatial_scores["dominance"],
            },
            "sensor": {
                "thermal_max_c": round(thermal_max_c, 2),
            },
            "tracked_objects":  tracked_objects,
            "visual_narrative": visual_narrative,
        }

        if self._should_send(packet):
            self.publisher.publish(packet)
            self.last_sent_state = packet
            self.last_sent_time  = now
            print(f"[ZMQ] {hazard_level:8s} | temp={thermal_max_c:.1f}°C | "
                  f"fire={fire_dominance:.2f} | proximity={spatial_scores['proximity']:.2f} | "
                  f"obstruction={spatial_scores['obstruction']:.2f}")

    # ------------------------------------------------------------------
    # Track management
    # ------------------------------------------------------------------

    def _update_track(self, track_id, label, cx, cy, area, now):
        if track_id not in self._tracks:
            self._tracks[track_id] = {
                "label":          label,
                "first_seen":     now,
                "last_seen":      now,
                "center_history": [],
                "area_history":   [],
            }
        t = self._tracks[track_id]
        t["last_seen"] = now
        t["center_history"].append((cx, cy, now))
        t["area_history"].append((area, now))

        t["center_history"] = [
            e for e in t["center_history"] if now - e[2] < self.STATIONARY_WINDOW + 1
        ]
        t["area_history"] = [
            e for e in t["area_history"] if now - e[1] < self.FIRE_GROWTH_WINDOW + 1
        ]

    def _build_tracked_objects(self, now):
        objects = []
        for track_id, t in self._tracks.items():
            duration = round(now - t["first_seen"], 1)
            if t["label"] == "person":
                objects.append({
                    "id":                track_id,
                    "label":             "person",
                    "status":            self._person_status(t, now),
                    "duration_in_frame": duration,
                })
            elif t["label"] == "fire":
                status, growth_rate = self._fire_status(t)
                objects.append({
                    "id":          track_id,
                    "label":       "fire",
                    "status":      status,
                    "growth_rate": round(growth_rate, 3),
                })
        return objects

    # ------------------------------------------------------------------
    # Per-object computations
    # ------------------------------------------------------------------

    def _person_status(self, track, now):
        history = track["center_history"]
        old = [e for e in history if now - e[2] >= self.STATIONARY_WINDOW]
        if not old:
            return "moving"
        ox, oy, _ = old[0]
        cx, cy, _ = history[-1]
        return "stationary" if math.hypot(cx - ox, cy - oy) < self.STATIONARY_PX else "moving"

    def _fire_status(self, track):
        history = track["area_history"]
        if len(history) < 2:
            return "stable", 0.0
        old_area     = history[0][0]
        current_area = history[-1][0]
        growth_rate  = (current_area - old_area) / max(old_area, 1e-6)
        if growth_rate > 0.05:
            return "growing", growth_rate
        elif growth_rate < -0.05:
            return "shrinking", growth_rate
        return "stable", growth_rate

    # ------------------------------------------------------------------
    # Send gate
    # ------------------------------------------------------------------

    def _should_send(self, current):
        last = self.last_sent_state

        if current["hazard_level"] != last.get("hazard_level"):
            return True
        if current["scores"]["proximity_alert"] and not last.get("scores", {}).get("proximity_alert"):
            return True

        last_fire = last.get("scores", {}).get("fire_dominance", 0.0)
        if abs(current["scores"]["fire_dominance"] - last_fire) > 0.05:
            return True

        last_temp = last.get("sensor", {}).get("thermal_max_c", 0.0)
        if abs(current["sensor"]["thermal_max_c"] - last_temp) > 2.0:
            return True

        if (time.time() - self.last_sent_time) > 2.0:
            return True

        return False
