# Jetson Nano Orin → RAG Pipeline Quick Start

## 🚀 Quick Connection Steps

### 1. Start Backend (on your Mac)
```bash
cd /Users/wes/Desktop/Project/hacklytics/hacklytics/fastapi
docker-compose up -d
```

### 2. Find Backend IP
```bash
hostname -I
# Example: 192.168.1.100
```

### 3. On Jetson: Install Dependencies
```bash
pip3 install pyzmq opencv-python numpy
```

### 4. On Jetson: Run Stream Script
```bash
# Copy the script from: fastapi/docs/hardware/JETSON_NANO_ORIN_SETUP.md
# Edit BACKEND_IP to match your Mac's IP
python3 jetson_stream.py
```

### 5. View Dashboard
```bash
# Terminal dashboard
cd fastapi/scripts
python3 terminal_dashboard.py

# Or browser dashboard
open http://localhost:8080/realtime_dashboard.html
```

---

## 📊 What You'll See

**Terminal Dashboard** shows real-time:
- ✅ **Claude API Calls** (header - always visible)
- 🔥 **Fire Dominance** (% of frame)
- ⚠️ **Hazard Level** (CLEAR → CRITICAL)
- 📈 **Scene Detection** (when buffer ≥2 packets)
- 🤖 **API Usage Ratio** (Claude calls / scenes detected)

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| "Connection refused" | Check backend IP, open port: `sudo ufw allow 5555/tcp` |
| "Camera not found" | Try different CAMERA_ID values (0, 1, 2) |
| No dashboard data | Check session_id matches, refresh browser |
| Invalid packet errors | Check Docker logs: `docker logs -f fastapi-rag-1` |

---

## 📖 Full Documentation

👉 **[Complete Setup Guide](fastapi/docs/hardware/JETSON_NANO_ORIN_SETUP.md)**

Includes:
- ✅ Full Python streaming script (copy-paste ready)
- ✅ YOLO integration example
- ✅ Computer vision heuristics
- ✅ Network configuration
- ✅ Performance tuning tips

---

## 🎯 Next Steps

1. ✅ Test with mock detection (provided script works out-of-the-box)
2. ✅ Verify dashboard shows data
3. ✅ Replace mock_detect_objects() with your YOLO model
4. ✅ Add BoT-SORT for object tracking
5. ✅ Tune fire dominance and proximity thresholds

---

**ZeroMQ Endpoint**: `tcp://YOUR_BACKEND_IP:5555`
**Dashboard**: http://localhost:8080/realtime_dashboard.html
**Logs**: `docker logs -f fastapi-rag-1`
