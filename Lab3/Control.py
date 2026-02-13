#!/usr/bin/env python3
"""
Raspberry Pi + MCP3008 (CH0) waveform analyzer:
- Estimates frequency (Hz)
- Classifies shape: sine / triangle / square

Wiring (per your notes):
MCP3008 VDD  -> 3.3V
MCP3008 VREF -> 3.3V
MCP3008 AGND -> GND
MCP3008 CLK  -> SCLK
MCP3008 DOUT -> MISO
MCP3008 DIN  -> MOSI
MCP3008 CS   -> GPIO22
MCP3008 DGND -> GND

Notes:
- This uses SPI via spidev, and uses GPIO22 as a manual chip-select.
- If you prefer hardware CE0/CE1 instead, wire CS to CE0/CE1 and remove the GPIO CS parts.

Install:
  sudo apt-get update
  sudo apt-get install -y python3-pip python3-numpy
  pip3 install spidev RPi.GPIO

Enable SPI:
  sudo raspi-config  -> Interface Options -> SPI -> Enable
"""

import time
import math
import numpy as np
import spidev
import RPi.GPIO as GPIO


# -------------------- USER SETTINGS --------------------
SPI_BUS = 0
SPI_DEV = 0                 # still used by spidev for the bus/dev, even with manual CS
CS_GPIO = 22                # your CS pin (GPIO22)
ADC_CH = 0                  # MCP3008 channel (0..7)

VREF = 3.3                  # VREF = 3.3V (your wiring)
SAMPLE_RATE = 5000          # Hz (raise if your signal is faster; keep <= ~20k typical)
CAPTURE_SECONDS = 0.40      # seconds per capture (more seconds = better low-frequency accuracy)
SPI_HZ = 1_000_000          # SPI clock (1 MHz is safe)
# ------------------------------------------------------


def setup_spi_and_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(CS_GPIO, GPIO.OUT, initial=GPIO.HIGH)

    spi = spidev.SpiDev()
    spi.open(SPI_BUS, SPI_DEV)
    spi.max_speed_hz = SPI_HZ
    spi.mode = 0
    return spi


def mcp3008_read(spi, channel: int) -> int:
    """
    Read MCP3008 single-ended channel.
    Returns 10-bit int [0..1023].
    Manual CS (GPIO22) so we can use any GPIO pin.
    """
    if not (0 <= channel <= 7):
        raise ValueError("channel must be 0..7")

    # MCP3008 protocol: start(1), single-ended(1), channel(3), then 10-bit result
    # Send 3 bytes. Example widely used:
    # byte1: 0b00000001
    # byte2: (0b10000000 | (channel << 4))
    # byte3: 0
    GPIO.output(CS_GPIO, GPIO.LOW)
    resp = spi.xfer2([0x01, (0x80 | (channel << 4)), 0x00])
    GPIO.output(CS_GPIO, GPIO.HIGH)

    value = ((resp[1] & 0x03) << 8) | resp[2]
    return value


def capture_samples(spi, fs: int, seconds: float):
    n = int(fs * seconds)
    x = np.empty(n, dtype=np.float64)

    dt = 1.0 / fs
    t0 = time.perf_counter()
    next_t = t0

    for i in range(n):
        # Read ADC
        raw = mcp3008_read(spi, ADC_CH)
        x[i] = (raw / 1023.0) * VREF

        # crude timing control; good enough for low-kHz
        next_t += dt
        while True:
            now = time.perf_counter()
            if now >= next_t:
                break

    # Actual measured sampling rate (important for frequency accuracy)
    t1 = time.perf_counter()
    actual_fs = (n - 1) / (t1 - t0) if (t1 - t0) > 0 else fs
    return x, actual_fs


def parabolic_interpolation(mags, k):
    """
    Parabolic peak interpolation around index k (FFT bin).
    Returns fractional bin offset (delta) in [-0.5, 0.5] approx.
    """
    if k <= 0 or k >= len(mags) - 1:
        return 0.0
    a = mags[k - 1]
    b = mags[k]
    c = mags[k + 1]
    denom = (a - 2*b + c)
    if denom == 0:
        return 0.0
    delta = 0.5 * (a - c) / denom
    return float(delta)


def estimate_frequency_fft(x, fs):
    """
    Robust frequency estimate using FFT peak.
    Returns (f0_hz, spectrum_freqs, spectrum_mags)
    """
    x = np.asarray(x, dtype=np.float64)

    # Detrend and window
    x0 = x - np.mean(x)
    window = np.hanning(len(x0))
    xw = x0 * window

    # rFFT
    X = np.fft.rfft(xw)
    mags = np.abs(X)
    freqs = np.fft.rfftfreq(len(xw), d=1.0/fs)

    # Ignore DC and very low bins
    low_cut_hz = 1.0
    k0 = np.searchsorted(freqs, low_cut_hz)
    if k0 >= len(mags):
        return 0.0, freqs, mags

    k_peak = int(np.argmax(mags[k0:]) + k0)

    # Parabolic interpolation for better accuracy
    delta = parabolic_interpolation(mags, k_peak)
    f0 = (k_peak + delta) * (fs / len(xw))
    return float(f0), freqs, mags


def estimate_frequency_zero_cross(x, fs):
    """
    Secondary frequency estimate: mean positive-going zero crossings.
    Works best for clean centered waveforms.
    """
    x0 = x - np.mean(x)
    signs = np.sign(x0)
    # positive-going crossings: (-) to (+)
    idx = np.where((signs[:-1] < 0) & (signs[1:] >= 0))[0]
    if len(idx) < 2:
        return 0.0
    periods = np.diff(idx) / fs
    if np.any(periods <= 0):
        return 0.0
    f = 1.0 / np.mean(periods)
    return float(f)


def harmonic_amplitude(freqs, mags, f0, n):
    """
    Get magnitude near nth harmonic of f0 using nearest bin.
    """
    target = n * f0
    if target <= 0:
        return 0.0
    k = int(np.argmin(np.abs(freqs - target)))
    return float(mags[k])


def classify_waveform(x, fs):
    """
    Classify waveform as sine / triangle / square using harmonic content + time-domain cues.
    Returns (label, features_dict)
    """
    # FFT-based features
    f0, freqs, mags = estimate_frequency_fft(x, fs)
    if f0 <= 0:
        return "unknown", {"f0_fft": 0.0}

    a1 = harmonic_amplitude(freqs, mags, f0, 1)
    a2 = harmonic_amplitude(freqs, mags, f0, 2)
    a3 = harmonic_amplitude(freqs, mags, f0, 3)
    a5 = harmonic_amplitude(freqs, mags, f0, 5)

    # Normalize by fundamental
    eps = 1e-12
    r2 = a2 / (a1 + eps)
    r3 = a3 / (a1 + eps)
    r5 = a5 / (a1 + eps)

    # Time-domain: "flatness" (square tends to dwell at extremes)
    x0 = x - np.mean(x)
    peak = np.max(np.abs(x0)) + eps
    xn = x0 / peak
    # fraction of samples near extremes
    frac_extreme = float(np.mean(np.abs(xn) > 0.85))

    # Triangle tends to have more constant slope -> derivative more uniform
    dx = np.diff(xn)
    slope_cv = float(np.std(dx) / (np.mean(np.abs(dx)) + eps))  # lower often looks more like triangle

    features = {
        "f0_fft": float(f0),
        "r2": float(r2),
        "r3": float(r3),
        "r5": float(r5),
        "frac_extreme": frac_extreme,
        "slope_cv": slope_cv,
    }

    # Heuristics:
    # - Sine: very low harmonics (r3, r5 small) and low extremes dwelling
    # - Square: strong odd harmonics, more extremes dwelling
    # - Triangle: odd harmonics present but decay faster (r5 much smaller vs r3), slopes more consistent
    #
    # Typical ideal:
    #   square: a3/a1 ~ 1/3 ≈ 0.33, a5/a1 ~ 0.2
    #   triangle: a3/a1 ~ 1/9 ≈ 0.11, a5/a1 ~ 1/25 = 0.04
    #   sine: a3/a1 ~ ~0
    #
    # Real signals will vary; these thresholds are forgiving.

    if r3 < 0.08 and r5 < 0.05 and r2 < 0.08:
        label = "sin"
    else:
        # likely non-sine
        if (r3 > 0.18 and r5 > 0.10) or (frac_extreme > 0.18):
            label = "square"
        else:
            # triangle-ish: noticeable r3 but much smaller r5; slopes relatively consistent
            if r3 > 0.08 and r5 < 0.08 and (r5 / (r3 + eps) < 0.65) and slope_cv < 1.2:
                label = "tri"
            else:
                # fallback between triangle/square based on harmonic decay + flatness
                label = "tri" if (r5 / (r3 + eps) < 0.8 and frac_extreme < 0.18) else "square"

    return label, features


def main():
    spi = setup_spi_and_gpio()
    try:
        while True:
            x, actual_fs = capture_samples(spi, SAMPLE_RATE, CAPTURE_SECONDS)

            f_fft, _, _ = estimate_frequency_fft(x, actual_fs)
            f_zc = estimate_frequency_zero_cross(x, actual_fs)
            shape, feats = classify_waveform(x, actual_fs)

            # pick a frequency to print (FFT usually better; use ZC as sanity check)
            f_out = f_fft if f_fft > 0 else f_zc

            print("\n--- MCP3008 CH0 Waveform ---")
            print(f"Sampling rate (measured): {actual_fs:.1f} Hz")
            print(f"Frequency (FFT):          {f_fft:.3f} Hz")
            print(f"Frequency (ZC):           {f_zc:.3f} Hz")
            print(f"Detected shape:           {shape}")

            # Useful debug features (comment out if you want it cleaner)
            print(f"Features: r2={feats.get('r2',0):.3f}, r3={feats.get('r3',0):.3f}, r5={feats.get('r5',0):.3f}, "
                  f"extreme={feats.get('frac_extreme',0):.3f}, slope_cv={feats.get('slope_cv',0):.3f}")

            time.sleep(0.2)

    finally:
        spi.close()
        GPIO.cleanup()


if __name__ == "__main__":
    main()