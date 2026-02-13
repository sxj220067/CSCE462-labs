import time
import board
import busio
import adafruit_mcp4725

VCC = 3.3
I2C_ADDR = 0x62
SAMPLE_RATE = 2000  # Hz

i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
dac = adafruit_mcp4725.MCP4725(i2c, address=I2C_ADDR)

def volts_to_dac(v):
    return int((v / VCC) * 65535)

def measure_write_time():
    t0 = time.perf_counter()
    dac.value = 0
    t1 = time.perf_counter()
    return t1 - t0

WRITE_TIME = measure_write_time()

def triangle_wave(freq, vmax, stop_check):
    samples_per_cycle = int(SAMPLE_RATE / freq)
    half = samples_per_cycle // 2
    dt = 1.0 / SAMPLE_RATE

    while True:
        # ramp up
        for i in range(half):
            if stop_check():
                return

            voltage = vmax * (i / (half - 1))

            # measure write time
            t0 = time.perf_counter()
            dac.value = volts_to_dac(voltage)
            elapsed = time.perf_counter() - t0

            # sleep for remaining time
            remaining = dt - elapsed
            if remaining > 0:
                time.sleep(remaining)

        # ramp down
        for i in range(half):
            if stop_check():
                return

            voltage = vmax * (1.0 - i / (half - 1))

            t0 = time.perf_counter()
            dac.value = volts_to_dac(voltage)
            elapsed = time.perf_counter() - t0

            remaining = dt - elapsed
            if remaining > 0:
                time.sleep(remaining)
