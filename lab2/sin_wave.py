import time
import math
import board
import busio
import adafruit_mcp4725

# I2C + DAC setup (MCP4725 is 12-bit, single channel)
i2c = busio.I2C(board.SCL, board.SDA)
dac = adafruit_mcp4725.MCP4725(i2c, address=0x62)

def sin_wave():
    t = 0.0
    tStep = 0.05  # controls frequency

    while True:
        # 12-bit output range: 0..4095
        value = int(2048 * (1.0 + 0.5 * math.sin(6.2832 * t)))

        # safety clamp (optional but good)
        if value < 0:
            value = 0
        elif value > 4095:
            value = 4095

        dac.value = value
        t += tStep
        time.sleep(0.0005)

sin_wave()