import time
import threading
import board
import busio
import cv2
import numpy as np
import adafruit_mlx90640
from ultralytics import YOLO
from flask import Flask, Response, jsonify, request
from reflex_engine import ReflexEngine
from zmq_publisher import ZmqPublisher

# --- CONFIGURATION ---
BACKEND_IP = "100.66.9.90"  # <--- REPLACE WITH YOUR COMPUTER'S IP

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max upload

UPLOAD_PATH = '/tmp/uploaded_video.mp4'
_uploaded_video_path = None

# --- HARDWARE SETUP ---
print("Initializing Hardware...")
try:
    i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)

    # Thermal Camera (MLX90640)
    mlx = adafruit_mlx90640.MLX90640(i2c)
    mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_8_HZ


except Exception as e:
    print(f"⚠️ HARDWARE ERROR: {e}")
    print("Running in EMULATION mode (No real sensors)")
    mlx = None

# --- BACKGROUND THERMAL READER ---
# mlx.getFrame() blocks until the sensor produces a new frame (~125ms at 8Hz).
# Running it in a separate thread keeps the camera loop from stalling.
_thermal_max = 25.0
_thermal_lock = threading.Lock()

def _thermal_reader():
    global _thermal_max
    buf = [0] * 768
    while True:
        try:
            mlx.getFrame(buf)
            val = float(np.max(buf))
            with _thermal_lock:
                _thermal_max = val
        except Exception:
            pass

if mlx:
    t = threading.Thread(target=_thermal_reader, daemon=True)
    t.start()

# --- SHARED SENSOR STATE (read by /sensor_data endpoint) ---
_sensor_state = {"max_temp": 25.0, "hazard_level": "CLEAR"}
_sensor_state_lock = threading.Lock()

# --- AI ENGINES ---
print("Loading YOLO Model...")
# Use TensorRT engine if available (export once with:
#   python3 -c "from ultralytics import YOLO; YOLO('~/Downloads/best.pt').export(format='engine', half=True, device=0)")
import os
_model_path = 'best.engine' if os.path.exists('best.engine') else os.path.expanduser('~/Downloads/best.pt')
print(f"  using {_model_path}")
model = YOLO(_model_path)
publisher = ZmqPublisher(BACKEND_IP)
reflex = ReflexEngine(publisher)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # discard stale frames, always grab the latest

def generate_frames():
    """
    Video Streaming Generator Function
    """
    while True:
        success, frame = cap.read()
        if not success: break

        # 1. READ SENSORS (non-blocking — background threads own the hardware)
        with _thermal_lock:
            max_temp = _thermal_max

        # 2. RUN VISION
        results = model.track(frame, persist=True, tracker="botsort.yaml", verbose=False)

        # 3. RUN REFLEX LOGIC (Sends Data to Laptop)
        reflex.process_frame(frame.shape, results, max_temp)

        # 4. UPDATE SHARED SENSOR STATE (served to browser via /sensor_data)
        with _sensor_state_lock:
            _sensor_state["max_temp"] = round(max_temp, 1)
            _sensor_state["hazard_level"] = reflex.last_sent_state.get("hazard_level", "CLEAR")

        # 5. DRAW OVERLAYS
        # Draw YOLO Boxes only — no sensor text on the video
        annotated_frame = results[0].plot(img=frame)

        # Encode to JPEG for Browser
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

def generate_uploaded_frames():
    cap_file = cv2.VideoCapture(_uploaded_video_path)
    if not cap_file.isOpened():
        return

    while True:
        success, frame = cap_file.read()
        if not success:
            break  # end of video

        results = model.track(frame, persist=True, tracker="botsort.yaml", verbose=False)
        annotated_frame = results[0].plot(img=frame)

        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    cap_file.release()

@app.route('/upload', methods=['POST'])
def upload():
    global _uploaded_video_path
    if 'video' not in request.files:
        return jsonify({'error': 'no file'}), 400
    f = request.files['video']
    if not f.filename:
        return jsonify({'error': 'empty filename'}), 400
    f.save(UPLOAD_PATH)
    _uploaded_video_path = UPLOAD_PATH
    return jsonify({'status': 'ok', 'filename': f.filename})

@app.route('/uploaded_feed')
def uploaded_feed():
    if not _uploaded_video_path:
        return 'No video uploaded', 404
    return Response(generate_uploaded_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/sensor_data')
def sensor_data():
    with _sensor_state_lock:
        return jsonify(_sensor_state)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return '''<!DOCTYPE html>
<html>
<head>
  <title>Dispatcher Live Feed</title>
  <style>
    body { margin: 0; background: #111; color: #eee; font-family: monospace; }
    #feed { width: 100%; display: block; }
    #sensor-panel {
      display: flex; gap: 24px; padding: 12px 16px;
      background: #1a1a1a; font-size: 1.1rem; align-items: center;
    }
    .sensor-item { display: flex; flex-direction: column; }
    .label { font-size: 0.75rem; color: #888; text-transform: uppercase; }
    .value { font-size: 1.4rem; font-weight: bold; }
    #hazard.CLEAR    { color: #4caf50; }
    #hazard.LOW      { color: #cddc39; }
    #hazard.MODERATE { color: #ff9800; }
    #hazard.HIGH     { color: #f44336; }
    #hazard.CRITICAL { color: #f44336; animation: blink 0.5s step-start infinite; }
    @keyframes blink { 50% { opacity: 0; } }
    #upload-panel {
      display: flex; gap: 12px; padding: 10px 16px;
      background: #222; align-items: center; border-bottom: 1px solid #333;
    }
    #upload-panel input[type=file] { color: #eee; }
    button {
      background: #333; color: #eee; border: 1px solid #555;
      padding: 6px 14px; cursor: pointer; font-family: monospace;
    }
    button:hover { background: #444; }
    button.active { border-color: #4caf50; color: #4caf50; }
    #upload-status { font-size: 0.85rem; color: #888; }
  </style>
</head>
<body>
  <div id="upload-panel">
    <input type="file" id="file-input" accept="video/*">
    <button onclick="uploadVideo()">Upload & Analyse</button>
    <button id="btn-live"     class="active" onclick="setMode('live')">Live Camera</button>
    <button id="btn-uploaded"               onclick="setMode('uploaded')">Uploaded Video</button>
    <span id="upload-status"></span>
  </div>
  <div id="sensor-panel">
    <div class="sensor-item">
      <span class="label">Thermal Max</span>
      <span class="value" id="temp">--</span>
    </div>
    <div class="sensor-item">
      <span class="label">Hazard Level</span>
      <span class="value" id="hazard">--</span>
    </div>
  </div>
  <img id="feed" src="/video_feed">
  <script>
    function setMode(mode) {
      const feed = document.getElementById('feed');
      document.getElementById('btn-live').classList.toggle('active', mode === 'live');
      document.getElementById('btn-uploaded').classList.toggle('active', mode === 'uploaded');
      feed.src = mode === 'live' ? '/video_feed' : '/uploaded_feed';
    }

    function uploadVideo() {
      const file = document.getElementById('file-input').files[0];
      if (!file) { alert('Select a video file first'); return; }
      const status = document.getElementById('upload-status');
      status.textContent = 'Uploading...';
      const form = new FormData();
      form.append('video', file);
      fetch('/upload', { method: 'POST', body: form })
        .then(r => r.json())
        .then(d => {
          if (d.status === 'ok') {
            status.textContent = d.filename + ' ready';
            setMode('uploaded');
          } else {
            status.textContent = 'Error: ' + d.error;
          }
        });
    }

    function refresh() {
      fetch('/sensor_data')
        .then(r => r.json())
        .then(d => {
          document.getElementById('temp').textContent = d.max_temp + ' °C';

          const hazard = document.getElementById('hazard');
          hazard.textContent = d.hazard_level;
          hazard.className = 'value ' + d.hazard_level;
        });
    }
    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>'''

if __name__ == '__main__':
    # Run Web Server on Port 5000
    app.run(host='0.0.0.0', port=5000, threaded=True)
