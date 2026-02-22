# thermal_dashboard.py
# MLX90640 live heatmap + BME680 overlay (Jetson-friendly, safe formatting)

import time
import numpy as np
import cv2
from smbus2 import SMBus
import bme680

import board
import busio
import adafruit_mlx90640


I2C_BUS = 7
SCALE = 20  # 32x24 -> 640x480

# -------------------------
# Helpers
# -------------------------
def safe_fmt(value, fmt: str) -> str:
    """Format numeric values safely; return N/A if None."""
    return format(value, fmt) if value is not None else "N/A"


# -------------------------
# Setup BME680
# -------------------------
bus = SMBus(I2C_BUS)

# If your BME680 is 0x76 instead, change to I2C_ADDR_PRIMARY
bme = bme680.BME680(bme680.I2C_ADDR_SECONDARY, i2c_device=bus)

bme.set_humidity_oversample(bme680.OS_2X)
bme.set_pressure_oversample(bme680.OS_4X)
bme.set_temperature_oversample(bme680.OS_8X)
bme.set_filter(bme680.FILTER_SIZE_3)

bme.set_gas_status(bme680.ENABLE_GAS_MEAS)
bme.set_gas_heater_temperature(320)
bme.set_gas_heater_duration(150)

# -------------------------
# Setup MLX90640
# -------------------------
i2c = busio.I2C(board.SCL, board.SDA)  # frequency not reliably settable on Jetson via Blinka
mlx = adafruit_mlx90640.MLX90640(i2c)
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ

frame = [0.0] * 768  # 32x24 thermal frame

# Cache last-good BME values to avoid flickering N/A
last_temp = None
last_humidity = None
last_gas = None
last_gas_stable = False

print("Thermal dashboard running. Press 'q' to quit.")

while True:
    # ---- Read MLX ----
    try:
        mlx.getFrame(frame)
    except ValueError:
        continue  # occasional read/CRC error is normal

    img = np.array(frame, dtype=np.float32).reshape((24, 32))
    tmin = float(img.min())
    tmax = float(img.max())

    # Normalize to 0..255 for display
    norm = (img - tmin) / (tmax - tmin + 1e-6)
    img8 = (norm * 255).astype(np.uint8)

    # Upscale
    img_big = cv2.resize(img8, (32 * SCALE, 24 * SCALE), interpolation=cv2.INTER_NEAREST)

    # Apply colormap
    heatmap = cv2.applyColorMap(img_big, cv2.COLORMAP_INFERNO)

    # Hottest pixel marker
    y, x = np.unravel_index(np.argmax(img), img.shape)
    cv2.circle(
        heatmap,
        (x * SCALE + SCALE // 2, y * SCALE + SCALE // 2),
        6,
        (255, 255, 255),
        2,
    )

    # ---- Read BME680 ----
    if bme.get_sensor_data():
        d = bme.data
        last_temp = float(d.temperature)
        last_humidity = float(d.humidity)

        if d.heat_stable:
            last_gas = float(d.gas_resistance)
            last_gas_stable = True
        else:
            last_gas_stable = False

    # ---- Overlay Text ----
    cv2.putText(
        heatmap,
        f"Thermal Min: {tmin:.1f}C  Max: {tmax:.1f}C",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        heatmap,
        f"Ambient: {safe_fmt(last_temp, '.1f')}C  Humidity: {safe_fmt(last_humidity, '.1f')}%",
        (10, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    if last_gas is None:
        gas_text = "N/A"
    else:
        gas_text = f"{last_gas:.0f} Ohm" + ("" if last_gas_stable else " (warming)")

    cv2.putText(
        heatmap,
        f"Gas Resistance: {gas_text}",
        (10, 90),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.imshow("Thermal + BME680 Dashboard", heatmap)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

    time.sleep(0.1)

cv2.destroyAllWindows()
