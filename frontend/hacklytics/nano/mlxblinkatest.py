import time
import numpy as np
import cv2

import board
import busio
import adafruit_mlx90640

# I2C init (Blinka)
i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)

mlx = adafruit_mlx90640.MLX90640(i2c)
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ  # bump later if stable

frame = [0.0] * 768  # 32x24

SCALE = 20  # upscales 32x24 -> 640x480

print("Starting MLX90640 viewer. Press 'q' to quit.")

while True:
    try:
        mlx.getFrame(frame)
    except ValueError:
        # occasional read/CRC hiccup; just retry
        continue

    img = np.array(frame, dtype=np.float32).reshape((24, 32))

    tmin = float(img.min())
    tmax = float(img.max())

    # Normalize to 0..255 for display
    # Add a tiny epsilon to avoid divide-by-zero if scene is uniform
    norm = (img - tmin) / (tmax - tmin + 1e-6)
    gray8 = (norm * 255.0).astype(np.uint8)

    # Upscale so it's visible
    gray8_big = cv2.resize(gray8, (32 * SCALE, 24 * SCALE), interpolation=cv2.INTER_NEAREST)

    # Apply a colormap for better visibility
    heat = cv2.applyColorMap(gray8_big, cv2.COLORMAP_INFERNO)

    # Overlay info
    cv2.putText(
        heat,
        f"min {tmin:.1f}C  max {tmax:.1f}C",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.imshow("MLX90640 Thermal View", heat)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cv2.destroyAllWindows()
