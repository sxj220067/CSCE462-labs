import time
import math
import board
import busio
import adafruit_mcp4725

VCC = 3.3
I2C_ADDR = 0x62
SAMPLE_RATE = 2000  # Hz

i2c = busio.I2C(board.SCL, board.SDA)
dac = adafruit_mcp4725.MCP4725(i2c, address=I2C_ADDR)

def volts_to_dac(v):
    return int((v / VCC) * 4095)

def sin_wave(freq, vmax, stop_check):
    dt = 1.0 / SAMPLE_RATE
    phase = 0.0
    omega = 2.0 * math.pi * freq

    amplitude = vmax / 2.0
    offset = vmax / 2.0

    while True:
        if stop_check():
            return

        voltage = offset + amplitude * math.sin(phase)
        dac.value = volts_to_dac(voltage)

        phase += omega * dt
        if phase >= 2.0 * math.pi:
            phase -= 2.0 * math.pi

        time.sleep(dt)