import spidev
import time
import numpy as np

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

def read_adc(channel):
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    return ((adc[1] & 3) << 8) + adc[2]

def sample_wave(channel=0, duration=0.2):
    samples = []
    t0 = time.perf_counter()

    # sample as fast as possible for "duration"
    while (time.perf_counter() - t0) < duration:
        samples.append(read_adc(channel))

    t1 = time.perf_counter()
    fs_eff = len(samples) / (t1 - t0)  # effective sampling rate
    return np.array(samples, dtype=float), fs_eff

def moving_average(x, w=5):
    if w <= 1:
        return x
    return np.convolve(x, np.ones(w)/w, mode="same")

def estimate_frequency_hysteresis(samples, fs, hyst=0.08):
    # remove DC and normalize
    s = samples - np.mean(samples)
    peak = np.max(np.abs(s))
    if peak < 1e-9:
        return 0.0
    s = s / peak

    # optional smoothing (helps noise)
    s = moving_average(s, w=5)

    # hysteresis zero crossing: count only rising crossings through +hyst
    # after being below -hyst
    crossings = []
    state = "low"  # low means we've been below -hyst
    for i in range(1, len(s)):
        if state == "low":
            if s[i] > hyst and s[i-1] <= hyst:
                crossings.append(i)
                state = "high"
        else:
            if s[i] < -hyst:
                state = "low"

    if len(crossings) < 2:
        return 0.0

    # period in samples between successive rising crossings
    periods = np.diff(crossings)
    if np.mean(periods) <= 0:
        return 0.0

    return fs / np.mean(periods)

def classify_wave(samples):
    s = samples - np.mean(samples)
    peak = np.max(np.abs(s))
    if peak < 1e-9:
        return "flat"
    s = s / peak
    s = moving_average(s, w=5)

    d = np.diff(s)

    flat = np.sum(np.abs(d) < 0.02) / len(d)  # plateau-ish
    slope_std = np.std(d)

    if flat > 0.25:
        return "square"
    elif slope_std < 0.12:
        return "triangle"
    else:
        return "sine"

def oscilloscope_loop():
    last_shape = None
    while True:
        samples, fs_eff = sample_wave(channel=0, duration=0.2)

        shape = classify_wave(samples)
        freq = estimate_frequency_hysteresis(samples, fs_eff)

        if shape != last_shape:
            print(f"Detected waveform: {shape}")
            last_shape = shape

        print(f"fs_eff: {fs_eff:.1f} Hz | Frequency: {freq:.2f} Hz")
        time.sleep(0.1)

oscilloscope_loop()