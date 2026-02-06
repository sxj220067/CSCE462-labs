import time
import board
import busio
import adafruit_mcp4725

VCC = 3.3
I2C_ADDR = 0x62

i2c = busio.I2C(board.SCL, board.SDA)
dac = adafruit_mcp4725.MCP4725(i2c, address=I2C_ADDR)

def volts_to_dac(v):
    return int((v / VCC) * 65535)

def measure_write_time():
    t0 = time.perf_counter()
    dac.value = 0
    t1 = time.perf_counter()
    return t1 - t0

WRITE_TIME = measure_write_time()

def square_wave(freq, vmax, stop_check):
    period = 1.0 / freq
    half = period / 2.0

    high = volts_to_dac(vmax)
    low = volts_to_dac(0.0)

    while True:
        if stop_check():
            return

        t0 = time.perf_counter()
        dac.value = high
        elapsed = time.perf_counter() - t0
        time.sleep(max(0, half - elapsed))

        if stop_check():
            return

        t0 = time.perf_counter()
        dac.value = low
        elapsed = time.perf_counter() - t0
        time.sleep(max(0, half - elapsed))

