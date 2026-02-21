import time
import numpy as np
from smbus2 import SMBus
import mlx90640

BUS_NUM = 7  # You detected the sensor on bus 7
I2C_ADDR = 0x33

bus = SMBus(BUS_NUM)
sensor = mlx90640.MLX90640(bus, I2C_ADDR)

sensor.set_refresh_rate(mlx90640.RefreshRate.REFRESH_4_HZ)

frame = [0] * 768  # 32x24 pixels

print("Reading MLX90640...")

while True:
    try:
        sensor.get_frame(frame)
        data = np.array(frame)

        print(
            f"Min: {data.min():.2f}°C | "
            f"Max: {data.max():.2f}°C | "
            f"Avg: {data.mean():.2f}°C"
        )

        time.sleep(0.5)

    except Exception as e:
        print("Read error:", e)
        continue
