# Jetson Nano Orin Setup Checklist

Use this checklist to track your setup progress.

---

## Phase 1: Backend Setup (on Mac)

- [ ] Docker services running: `cd fastapi && docker-compose up -d`
- [ ] Services healthy: `docker ps` shows all containers running
- [ ] Find backend IP: `hostname -I` → Write it down: `_________________`
- [ ] Port 5555 open: `sudo ufw allow 5555/tcp` (if using firewall)
- [ ] Test endpoint: `curl http://localhost:8001/health` → should return `{"status":"ok"}`

---

## Phase 2: Jetson Hardware Setup

- [ ] Jetson Nano Orin powered on and connected to network
- [ ] Camera connected (USB or CSI)
- [ ] Can ping backend from Jetson: `ping YOUR_BACKEND_IP`
- [ ] JetPack installed (check: `jetson_release`)

---

## Phase 3: Jetson Software Setup

- [ ] Python 3.8+ installed: `python3 --version`
- [ ] Install ZeroMQ: `pip3 install pyzmq`
- [ ] Install OpenCV: `pip3 install opencv-python`
- [ ] Install NumPy: `pip3 install numpy`
- [ ] Optional - Install YOLO: `pip3 install ultralytics torch torchvision`

---

## Phase 4: Deploy Streaming Script

- [ ] Copy script from `fastapi/docs/hardware/JETSON_NANO_ORIN_SETUP.md`
- [ ] Save as: `~/fire_detection/jetson_stream.py`
- [ ] Edit `BACKEND_IP` in script to match your Mac's IP
- [ ] Edit `DEVICE_ID` to unique identifier (e.g., "jetson_orin_01")
- [ ] Edit `CAMERA_ID` if needed (0 for USB, check with `v4l2-ctl --list-devices`)
- [ ] Make executable: `chmod +x ~/fire_detection/jetson_stream.py`

---

## Phase 5: Test Connection

- [ ] Run script: `python3 ~/fire_detection/jetson_stream.py`
- [ ] See "✅ Connected to backend" message
- [ ] See "✅ Camera opened successfully" message
- [ ] See packet count incrementing: `[    1] CLEAR    | ...`

---

## Phase 6: Verify Backend Reception

- [ ] Check backend logs: `docker logs -f fastapi-rag-1`
- [ ] See messages like: `"Reflex: jetson_orin_01 | CLEAR | STABLE | 45ms"`
- [ ] See scene detection: `"🔍 Scene detection: buffer has X packets"`
- [ ] See Claude calls (if API key set): `"🤖 CALLING CLAUDE API"`

---

## Phase 7: Dashboard Verification

### Terminal Dashboard
- [ ] Run: `cd fastapi/scripts && python3 terminal_dashboard.py`
- [ ] See packets appearing in "RECENT PACKETS" section
- [ ] See "Claude API Calls" counter in header
- [ ] See "API Usage" percentage (should be high if API key is valid)

### Browser Dashboard (Optional)
- [ ] Open: http://localhost:8080/realtime_dashboard.html
- [ ] WebSocket connected (check browser console)
- [ ] Real-time data appearing

---

## Phase 8: Integration (Next Steps)

- [ ] Replace `mock_detect_objects()` with your YOLO model
- [ ] Test fire detection with real fire images/video
- [ ] Implement smoke detection (update `smoke_op` calculation)
- [ ] Add BoT-SORT for persistent object tracking
- [ ] Tune thresholds:
  - [ ] Fire dominance buckets (0.0, 0.1, 0.2, 0.4, 0.6, 1.0)
  - [ ] Proximity distance (currently 15% of frame diagonal)
  - [ ] Hazard level thresholds

---

## Troubleshooting Log

Use this section to track any issues:

**Issue 1:**
- Problem: ________________________________________________
- Solution: ________________________________________________
- Status: ☐ Unresolved  ☐ Resolved

**Issue 2:**
- Problem: ________________________________________________
- Solution: ________________________________________________
- Status: ☐ Unresolved  ☐ Resolved

**Issue 3:**
- Problem: ________________________________________________
- Solution: ________________________________________________
- Status: ☐ Unresolved  ☐ Resolved

---

## Performance Metrics

After setup, record your performance:

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Jetson → Backend latency | <100ms | _____ ms | ☐ |
| Backend processing (Reflex) | <50ms | _____ ms | ☐ |
| Backend processing (RAG) | <2000ms | _____ ms | ☐ |
| Claude API success rate | >80% | _____ % | ☐ |
| Frame rate (Jetson) | 2-10 FPS | _____ FPS | ☐ |

---

## Configuration Details

**Backend IP**: `_________________`

**Jetson Device ID**: `_________________`

**Camera ID**: `_________________`

**Session ID**: `_________________`

**YOLO Model Path**: `_________________`

**Frame Resolution**: `_____ x _____`

**Notes**:
```
________________________________________________________________
________________________________________________________________
________________________________________________________________
```

---

## ✅ Setup Complete!

Once all checkboxes are ticked, you're ready to:
1. Run live fire detection demos
2. Test Claude API integration
3. Evaluate RAG recommendation quality
4. Fine-tune detection thresholds
5. Deploy to production scenarios

**Documentation**:
- [Full Setup Guide](fastapi/docs/hardware/JETSON_NANO_ORIN_SETUP.md)
- [Quick Start](JETSON_QUICKSTART.md)
- [Packet Spec](fastapi/docs/reference/JETSON_SPEC.md)
