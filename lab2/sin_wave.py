import time
import math
import board
import busio
import adafruit_mcp4725

# I2C + DAC setup
i2c = busio.I2C(board.SCL, board.SDA)
dac = adafruit_mcp4728.MCP4728(i2c, address=0x62)

def sin_wave():
    t = 0.0
    tStep = 0.05   # controls frequency

    while True:
        voltage = 2048 * (1.0 + 0.5 * math.sin(6.2832 * t))
        dac.channel_a.value = int(voltage * 32)  # scale to 16-bit
        t += tStep
        time.sleep(0.0005)

sin_wave()