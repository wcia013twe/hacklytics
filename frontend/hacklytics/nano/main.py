import time
import board
import busio
import cv2
import numpy as np
import adafruit_mlx90640
import adafruit_bme680
from ultralytics import YOLO
from flask import Flask, Response
from reflex_engine import ReflexEngine

# --- CONFIGURATION ---
LAPTOP_IP = "192.168.1.XX"  # <--- REPLACE WITH YOUR COMPUTER'S IP
BACKEND_URL = f"http://{LAPTOP_IP}:8000/ingest"

app = Flask(__name__)

# --- HARDWARE SETUP ---
print("Initializing Hardware...")
try:
    i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
    
    # Thermal Camera (MLX90640)
    mlx = adafruit_mlx90640.MLX90640(i2c)
    mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_8_HZ
    frame_thermal = [0] * 768
    
    # Gas Sensor (BME680)
    bme = adafruit_bme680.Adafruit_BME680_I2C(i2c)
    # Calibrate Baseline (Assume clean air at startup)
    print("Calibrating Gas Sensor...")
    gas_baseline = bme.gas
    print(f"Baseline Resistance: {gas_baseline} Ohms")

except Exception as e:
    print(f"⚠️ HARDWARE ERROR: {e}")
    print("Running in EMULATION mode (No real sensors)")
    mlx = None
    bme = None

# --- AI ENGINES ---
print("Loading YOLO Model...")
model = YOLO('yolov8n.pt')
reflex = ReflexEngine(BACKEND_URL)
cap = cv2.VideoCapture(0)

def get_thermal_overlay(temp_grid, img_shape):
    """
    Upscales 32x24 thermal data to match Webcam resolution
    """
    h, w = img_shape[:2]
    grid = np.array(temp_grid).reshape((24, 32))
    
    # Resize to match webcam
    heatmap = cv2.resize(grid, (w, h), interpolation=cv2.INTER_CUBIC)
    
    # Normalize and Color Map
    norm = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    color_map = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
    
    return color_map, np.max(grid)

def generate_frames():
    """
    Video Streaming Generator Function
    """
    while True:
        success, frame = cap.read()
        if not success: break

        # 1. READ SENSORS
        max_temp = 25.0
        is_smoke = False
        thermal_img = None

        if mlx:
            try:
                mlx.getFrame(frame_thermal)
                thermal_img, max_temp = get_thermal_overlay(frame_thermal, frame.shape)
            except Exception: pass # Ignore I2C errors
        
        if bme:
             # If gas resistance drops below 80% of baseline -> Smoke
             if (bme.gas / gas_baseline) < 0.8: 
                 is_smoke = True

        # 2. RUN VISION
        results = model(frame, verbose=False)

        # 3. RUN REFLEX LOGIC (Sends Data to Laptop)
        reflex.process_frame(frame.shape, results, max_temp, is_smoke)
        
        # 4. DRAW OVERLAYS
        # Blend Thermal if available (70% Optical, 30% Thermal)
        if thermal_img is not None:
             frame = cv2.addWeighted(frame, 0.7, thermal_img, 0.3, 0)

        # Draw YOLO Boxes
        annotated_frame = results[0].plot(img=frame)
        
        # Draw HUD
        status_color = (0,0,255) if is_smoke or max_temp > 50 else (0,255,0)
        cv2.putText(annotated_frame, f"Temp: {max_temp:.1f}C", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
        
        if is_smoke:
            cv2.putText(annotated_frame, "SMOKE DETECTED", (10, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)

        # Encode to JPEG for Browser
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return "<h1>Dispatcher Live Feed</h1><img src='/video_feed' width='100%'>"

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # Run Web Server on Port 5000
    app.run(host='0.0.0.0', port=5000, threaded=True)