import spidev
import time
import numpy as np

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

def read_adc(channel):
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    value = ((adc[1] & 3) << 8) + adc[2]
    return value

def sample_wave(channel=0, sample_rate=1000, duration=0.2):
    n = int(sample_rate * duration)
    dt = 1.0 / sample_rate
    samples = []

    for _ in range(n):
        samples.append(read_adc(channel))
        time.sleep(dt)

    return np.array(samples)


def classify_wave(samples):
    # Normalize
    s = samples - np.mean(samples)
    s = s / np.max(np.abs(s))

    # First derivative
    d = np.diff(s)

    # Feature 1: number of zero-crossings in derivative
    zero_cross = np.sum(np.diff(np.sign(d)) != 0)

    # Feature 2: flatness (square waves have long flat regions)
    flat = np.sum(np.abs(d) < 0.02) / len(d)

    # Feature 3: linearity (triangle waves have consistent slope)
    slope_std = np.std(d)

    # Classification logic
    if flat > 0.25:
        return "square"
    elif slope_std < 0.15:
        return "triangle"
    else:
        return "sine"

def oscilloscope_loop():
    last_shape = None

    while True:
        samples = sample_wave(sample_rate=1000, duration=0.2)

        shape = classify_wave(samples)
        freq = estimate_frequency(samples, sample_rate=1000)

        if shape != last_shape:
            print(f"Detected waveform: {shape}")
            last_shape = shape

        print(f"Frequency: {freq:.2f} Hz")
