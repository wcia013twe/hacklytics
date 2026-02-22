#!/usr/bin/env python3
import argparse
import sys
import time

import cv2
from ultralytics import YOLO


def open_camera(src: str):
    """
    src can be:
      - "0" / "1" ... (USB camera index)
      - a path to a video file
      - a GStreamer pipeline string (advanced; optional)
    """
    # If it's a digit, treat as camera index
    if src.isdigit():
        cap = cv2.VideoCapture(int(src))
    else:
        cap = cv2.VideoCapture(src)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open video source: {src}")
    return cap


def main():
    parser = argparse.ArgumentParser(description="Quick YOLO sanity test on Jetson Nano.")
    parser.add_argument("--source", default="0", help='Camera index like "0" or path to video file.')
    parser.add_argument("--model", default="yolov8n.pt", help="Ultralytics model weights (e.g., yolov8n.pt).")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size.")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold.")
    parser.add_argument("--device", default=None, help='Set to "cpu" or "0" (GPU) if needed. Default auto.')
    parser.add_argument("--no-view", action="store_true", help="Disable preview window (headless).")
    args = parser.parse_args()

    print(f"[INFO] Loading model: {args.model}")
    model = YOLO(args.model)

    cap = open_camera(args.source)

    fps_avg = 0.0
    n = 0
    t_last = time.time()

    print("[INFO] Starting stream. Press 'q' to quit.")
    while True:
        ok, frame = cap.read()
        if not ok:
            print("[WARN] Failed to read frame; exiting.")
            break

        # Run inference
        results = model.predict(
            source=frame,
            imgsz=args.imgsz,
            conf=args.conf,
            device=args.device,
            verbose=False,
        )

        # Draw results on frame (Ultralytics helper)
        annotated = results[0].plot()

        # Simple FPS meter
        t_now = time.time()
        dt = t_now - t_last
        t_last = t_now
        fps = 1.0 / dt if dt > 0 else 0.0
        n += 1
        fps_avg = fps_avg + (fps - fps_avg) / n
        cv2.putText(
            annotated,
            f"FPS: {fps_avg:.1f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        if not args.no_view:
            cv2.imshow("YOLO Test", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        else:
            # Headless mode: just show periodic status
            if n % 60 == 0:
                print(f"[INFO] Avg FPS: {fps_avg:.1f}")

    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
