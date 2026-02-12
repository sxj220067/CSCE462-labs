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
    samples = []

    # MCP3008 + Python overhead already limits speed,
    # so DO NOT sleep — it slows sampling too much.
    for _ in range(n):
        samples.append(read_adc(channel))

    return np.array(samples)


def estimate_frequency(samples, sample_rate):
    s = samples - np.mean(samples)

    # Avoid divide-by-zero
    if np.max(np.abs(s)) == 0:
        return 0.0

    # Zero-crossing frequency estimate
    zero_crossings = np.where(np.diff(np.sign(s)))[0]

    if len(zero_crossings) < 2:
        return 0.0

    # Average period in samples (two zero-crossings = half period)
    avg_half_period = np.mean(np.diff(zero_crossings))
    period_samples = avg_half_period * 2

    if period_samples == 0:
        return 0.0

    return sample_rate / period_samples


def classify_wave(samples):
    s = samples - np.mean(samples)

    max_val = np.max(np.abs(s))
    if max_val == 0:
        return "flat"

    s = s / max_val

    d = np.diff(s)

    zero_cross = np.sum(np.diff(np.sign(d)) != 0)
    flat = np.sum(np.abs(d) < 0.02) / len(d)
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

        # Debug: print first few samples so you know ADC is alive
        print("Raw samples:", samples[:10])

        shape = classify_wave(samples)
        freq = estimate_frequency(samples, sample_rate=1000)

        if shape != last_shape:
            print(f"Detected waveform: {shape}")
            last_shape = shape

        print(f"Frequency: {freq:.2f} Hz\n")
        time.sleep(0.1)  # small pause so terminal output is readable


# Run it
oscilloscope_loop()
