import time
import requests
import json
import numpy as np

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

    def process_frame(self, frame_shape, yolov8_results, thermal_max_c, smoke_detected):
        """
        Decides if the current situation warrants an alert.
        """
        # 1. Reset State
        current_state = {
            "timestamp": time.time(),
            "fire_intensity": 0.0,      
            "temp_max": thermal_max_c,  
            "smoke_sensor": smoke_detected, 
            "hazard_level": "SAFE",     
            "hazards_detected": []
        }

        # 2. Extract Visual Features
        fire_visual_intensity = 0.0
        
        # Iterate through detected boxes
        if len(yolov8_results) > 0:
            for box in yolov8_results[0].boxes:
                cls = int(box.cls[0])
                label = yolov8_results[0].names[cls]
                conf = float(box.conf[0])

                # Normalize Box Area
                h, w = frame_shape[:2]
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                box_area = ((x2-x1) * (y2-y1)) / (w*h)

                if label == 'fire' and conf > 0.4:
                    fire_visual_intensity = max(fire_visual_intensity, min(box_area / 0.3, 1.0))
                    current_state["hazards_detected"].append("visual_fire")
                
                elif label == 'smoke' and conf > 0.4:
                     current_state["hazards_detected"].append("visual_smoke")

        current_state["fire_intensity"] = fire_visual_intensity

        # 3. FUSION LOGIC (The "Smart Dispatcher" Logic)
        is_hot = thermal_max_c > self.TEMP_WARN
        is_visual_fire = fire_visual_intensity > 0.1
        
        if is_hot and is_visual_fire:
            current_state["hazard_level"] = "CRITICAL_CONFIRMED"
        elif is_hot and not is_visual_fire:
            current_state["hazard_level"] = "HIDDEN_HEAT_SOURCE"
        elif not is_hot and is_visual_fire:
            current_state["hazard_level"] = "FALSE_ALARM_VISUAL"
        elif smoke_detected:
            current_state["hazard_level"] = "SMOKE_DANGER"

        # 4. Transmit if meaningful change occurred
        if self._should_send_update(current_state):
            self._transmit(current_state)

    def _should_send_update(self, current):
        last = self.last_sent_state
        
        if current['hazard_level'] != last.get('hazard_level'): return True
        if current['smoke_sensor'] != last.get('smoke_sensor'): return True
        if abs(current['temp_max'] - last.get('temp_max', 0)) > 2.0: return True 
        
        # Heartbeat every 2 seconds
        if (time.time() - self.last_sent_time) > 2.0: return True
        return False

    def _transmit(self, data):
        try:
             # Very short timeout prevents blocking the camera
             self.session.post(self.url, json=data, timeout=0.1)
             self.last_sent_state = data
             self.last_sent_time = time.time()
             print(f"📡 SENT: {data['hazard_level']} | Temp {data['temp_max']:.1f}C")
        except:
             pass # Fail silently if laptop is offline