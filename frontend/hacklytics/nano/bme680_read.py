import time
import bme680
from smbus2 import SMBus

BUS_NUM = 7  # you detected the sensor on bus 7
ADDR = bme680.I2C_ADDR_SECONDARY  # 0x77

bus = SMBus(BUS_NUM)
sensor = bme680.BME680(ADDR, i2c_device=bus)

sensor.set_humidity_oversample(bme680.OS_2X)
sensor.set_pressure_oversample(bme680.OS_4X)
sensor.set_temperature_oversample(bme680.OS_8X)
sensor.set_filter(bme680.FILTER_SIZE_3)

sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)
sensor.set_gas_heater_temperature(320)
sensor.set_gas_heater_duration(150)

print("BME680 on /dev/i2c-7 @ 0x77 (Ctrl+C to stop)")
while True:
   if sensor.get_sensor_data():
    d = sensor.data

    if d.heat_stable:
        print(f"Temp: {d.temperature:.2f} °C")
        print(f"Gas: {d.gas_resistance:.0f} Ω")
    else:
        print("Gas sensor warming up...")
