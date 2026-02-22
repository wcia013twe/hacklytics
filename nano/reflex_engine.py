import time
import requests
import json
import numpy as np
from spatial_heuristics import compute_scene_heuristics, get_vulnerability_level

class ReflexEngine:
    def __init__(self, backend_url, threshold=0.05):
        self.url = backend_url
        self.threshold = threshold
        self.last_sent_state = {}
        self.last_sent_time = 0
        self.session = requests.Session()

        # --- HARDWARE THRESHOLDS ---
        self.TEMP_WARN = 50.0  # °C (Warning)
        self.TEMP_CRIT = 80.0  # °C (Critical)

        # --- THERMAL OVERRIDE THRESHOLDS (PROBLEM 2: Split-Brain Resolution) ---
        self.TEMP_DANGER_THRESHOLD = 60.0   # °C - Force minimum DANGER level
        self.TEMP_CRITICAL_THRESHOLD = 100.0  # °C - Force CRITICAL override
        self.TEMP_SAFE_THRESHOLD = 30.0     # °C - Below this, thermal likely safe

    def process_frame(self, frame_shape, yolov8_results, thermal_max_c, smoke_detected):
        """
        Decides if the current situation warrants an alert.
        Enhanced with spatial heuristics for advanced scene understanding.

        PROBLEM 2 IMPLEMENTATION: Thermal-Override "Trump Card" Logic
        - Thermal sensor takes priority over visual when temperatures exceed thresholds
        - Prevents false negatives when smoke is transparent to RGB camera
        - Logs sensor conflicts for debugging and safety analysis

        Returns:
            current_state dict (for testing purposes)
        """
        # 1. Reset State
        current_state = {
            "timestamp": time.time(),
            "fire_intensity": 0.0,
            "temp_max": thermal_max_c,
            "smoke_sensor": smoke_detected,
            "hazard_level": "SAFE",
            "hazards_detected": [],
            "visual_narrative": "",  # NEW: Natural language scene description
            "scores": {              # NEW: Spatial heuristic scores
                "proximity": 0.0,
                "obstruction": 0.0,
                "dominance": 0.0
            },
            # PROBLEM 2: Sensor conflict tracking
            "sensor_conflict": False,
            "override_reason": None,
            "thermal_override_active": False
        }

        # 2. Extract All Detections (for spatial analysis)
        all_detections = []
        fire_visual_intensity = 0.0

        # Iterate through detected boxes and collect ALL detections
        if len(yolov8_results) > 0:
            h, w = frame_shape[:2]

            for box in yolov8_results[0].boxes:
                cls = int(box.cls[0])
                label = yolov8_results[0].names[cls]
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                box_area = ((x2-x1) * (y2-y1)) / (w*h)

                # Collect detection for spatial analysis
                detection = {
                    'label': label,
                    'bbox': [x1, y1, x2, y2],
                    'confidence': conf,
                    'normalized_area': box_area
                }
                all_detections.append(detection)

                # Legacy fire intensity calculation (preserved for backward compatibility)
                if label == 'fire' and conf > 0.4:
                    fire_visual_intensity = max(fire_visual_intensity, min(box_area / 0.3, 1.0))
                    current_state["hazards_detected"].append("visual_fire")

                elif label == 'smoke' and conf > 0.4:
                     current_state["hazards_detected"].append("visual_smoke")

            # 3. SPATIAL HEURISTICS ANALYSIS (NEW)
            if all_detections:
                spatial_results = compute_scene_heuristics(all_detections, frame_shape[:2])

                # Update state with spatial analysis
                current_state["scores"] = spatial_results["scores"]
                current_state["visual_narrative"] = spatial_results["narrative"]

                # Use dominance score to enhance fire_intensity calculation
                # Combines legacy box-area method with new spatial dominance
                spatial_fire_intensity = spatial_results["scores"]["dominance"]
                current_state["fire_intensity"] = max(fire_visual_intensity, spatial_fire_intensity)
            else:
                current_state["fire_intensity"] = fire_visual_intensity
                current_state["visual_narrative"] = "No hazards detected."

        else:
            current_state["fire_intensity"] = fire_visual_intensity
            current_state["visual_narrative"] = "No objects detected in scene."

        # 4. FUSION LOGIC WITH THERMAL-OVERRIDE HIERARCHY (PROBLEM 2)
        # ================================================================
        # CRITICAL SAFETY RULE: Thermal > Visual
        # If thermal reads danger, visual "safe" signals are IGNORED
        # ================================================================

        # Extract sensor states
        is_visual_fire = current_state["fire_intensity"] > 0.1
        is_proximity_critical = current_state["scores"]["proximity"] > 0.7
        is_path_blocked = current_state["scores"]["obstruction"] > 0.3

        # Determine visual assessment (what camera thinks)
        if is_visual_fire:
            visual_assessment = "FIRE_DETECTED"
        elif current_state["fire_intensity"] > 0.0 or len(current_state["hazards_detected"]) > 0:
            visual_assessment = "HAZARD_DETECTED"
        else:
            visual_assessment = "SAFE"

        # ================================================================
        # THERMAL OVERRIDE HIERARCHY (Trump Card Logic)
        # ================================================================

        # TIER 1: EXTREME HEAT (>100°C) - FORCE CRITICAL
        if thermal_max_c > self.TEMP_CRITICAL_THRESHOLD:
            current_state["hazard_level"] = "THERMAL_OVERRIDE_CRITICAL"
            current_state["thermal_override_active"] = True
            current_state["override_reason"] = f"Extreme thermal reading: {thermal_max_c:.1f}C (>100C threshold)"

            # Check for sensor conflict
            if visual_assessment == "SAFE":
                current_state["sensor_conflict"] = True
                conflict_msg = f"SENSOR CONFLICT: Visual={visual_assessment}, Thermal={thermal_max_c:.0f}C -> OVERRIDING to CRITICAL"
                print(f"[THERMAL OVERRIDE] {conflict_msg}")
                current_state["override_reason"] += " | Visual reported safe but thermal critical"

            # Console warning
            print(f"THERMAL OVERRIDE: {thermal_max_c:.1f}C detected (CRITICAL)")

        # TIER 2: HIGH HEAT (60-100°C) - FORCE MINIMUM DANGER
        elif thermal_max_c > self.TEMP_DANGER_THRESHOLD:
            # Initial assessment: at least DANGER level
            if is_visual_fire:
                # Both sensors agree - confirmed threat
                current_state["hazard_level"] = "CRITICAL_CONFIRMED"

                # Spatial context escalation
                if is_proximity_critical:
                    current_state["hazard_level"] = "CRITICAL_PROXIMITY"
                elif is_path_blocked:
                    current_state["hazard_level"] = "CRITICAL_TRAPPED"
            else:
                # Thermal shows heat but visual doesn't see fire
                current_state["hazard_level"] = "HIDDEN_HEAT_SOURCE"
                current_state["thermal_override_active"] = True
                current_state["sensor_conflict"] = True
                current_state["override_reason"] = f"Thermal: {thermal_max_c:.1f}C, Visual: No fire detected"

                conflict_msg = f"SENSOR CONFLICT: Visual=SAFE, Thermal={thermal_max_c:.0f}C -> HIDDEN_HEAT_SOURCE"
                print(f"[THERMAL OVERRIDE] {conflict_msg}")

        # TIER 3: WARM (50-60°C) - WARNING RANGE
        elif thermal_max_c > self.TEMP_WARN:
            if is_visual_fire:
                # Both sensors agree on threat
                current_state["hazard_level"] = "CRITICAL_CONFIRMED"

                # Spatial escalation
                if is_proximity_critical:
                    current_state["hazard_level"] = "CRITICAL_PROXIMITY"
                elif is_path_blocked:
                    current_state["hazard_level"] = "CRITICAL_TRAPPED"
            else:
                # Warm but no visual confirmation
                current_state["hazard_level"] = "THERMAL_WARNING"
                current_state["override_reason"] = f"Elevated temperature: {thermal_max_c:.1f}C"

        # TIER 4: NORMAL THERMAL (<50°C) - Visual takes lead
        else:
            if is_visual_fire and thermal_max_c < self.TEMP_SAFE_THRESHOLD:
                # Visual says fire but thermal is cool - likely false positive
                current_state["hazard_level"] = "FALSE_ALARM_VISUAL"
                current_state["sensor_conflict"] = True
                current_state["override_reason"] = f"Visual fire detected but thermal only {thermal_max_c:.1f}C"

                conflict_msg = f"SENSOR CONFLICT: Visual=FIRE, Thermal={thermal_max_c:.0f}C -> FALSE_ALARM_VISUAL"
                print(f"[CONFLICT DETECTED] {conflict_msg}")

            elif is_visual_fire:
                # Visual fire with mild heat - possible early stage fire
                current_state["hazard_level"] = "VISUAL_FIRE_UNCONFIRMED"
                current_state["override_reason"] = f"Visual fire present, thermal: {thermal_max_c:.1f}C"

            elif smoke_detected:
                current_state["hazard_level"] = "SMOKE_DANGER"

            # Otherwise, remains SAFE

        # 5. Transmit if meaningful change occurred
        if self._should_send_update(current_state):
            self._transmit(current_state)

        # Return state for testing purposes
        return current_state

    def _should_send_update(self, current):
        last = self.last_sent_state

        # Basic state changes
        if current['hazard_level'] != last.get('hazard_level'): return True
        if current['smoke_sensor'] != last.get('smoke_sensor'): return True
        if abs(current['temp_max'] - last.get('temp_max', 0)) > 2.0: return True

        # NEW: Spatial heuristic score changes (detect significant scene changes)
        last_scores = last.get('scores', {})
        if abs(current['scores']['proximity'] - last_scores.get('proximity', 0)) > 0.15: return True
        if abs(current['scores']['obstruction'] - last_scores.get('obstruction', 0)) > 0.20: return True
        if abs(current['scores']['dominance'] - last_scores.get('dominance', 0)) > 0.10: return True

        # Heartbeat every 2 seconds
        if (time.time() - self.last_sent_time) > 2.0: return True
        return False

    def _transmit(self, data):
        try:
             # Very short timeout prevents blocking the camera
             self.session.post(self.url, json=data, timeout=0.1)
             self.last_sent_state = data
             self.last_sent_time = time.time()

             # Enhanced console output with spatial narrative and thermal override status
             narrative_preview = data.get('visual_narrative', '')[:60]  # First 60 chars
             scores = data.get('scores', {})

             # PROBLEM 2: Enhanced display for thermal overrides
             status_icon = "SENT"
             if data.get('thermal_override_active'):
                 status_icon = "THERMAL OVERRIDE"
             elif data.get('sensor_conflict'):
                 status_icon = "CONFLICT"

             print(f"[{status_icon}] {data['hazard_level']} | Temp {data['temp_max']:.1f}C")
             print(f"   Scores: P={scores.get('proximity', 0):.2f} O={scores.get('obstruction', 0):.2f} D={scores.get('dominance', 0):.2f}")

             # Display override reason if present
             if data.get('override_reason'):
                 print(f"   Override: {data['override_reason']}")

             if narrative_preview:
                 print(f"   Scene: {narrative_preview}...")
        except:
             pass # Fail silently if laptop is offline