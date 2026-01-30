import time
import board
import busio
import adafruit_mcp4725

VCC = 3.3
I2C_ADDR = 0x62

i2c = busio.I2C(board.SCL, board.SDA)
dac = adafruit_mcp4725.MCP4725(i2c, address=I2C_ADDR)

def volts_to_dac(v):
    return int((v / VCC) * 4095)

def square_wave(freq, vmax, stop_check):
    period = 1.0 / freq
    half = period / 2.0

    high = volts_to_dac(vmax)
    low = volts_to_dac(0.0)

    while True:
        if stop_check():
            return
        dac.value = high
        time.sleep(half)

        if stop_check():
            return
        dac.value = low
        time.sleep(half)