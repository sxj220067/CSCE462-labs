#!/usr/bin/env python3
import time
import numpy as np
import spidev
import RPi.GPIO as GPIO

# ===== Circuit wiring from Lab 3 =====
# MCP3008: CLK->SCLK, DOUT->MISO, DIN->MOSI
# CS -> GPIO22 (BCM), VDD/VREF->3.3V, AGND/DGND->GND   [oai_citation:1‡Lab 3.pdf](sediment://file_00000000968471fda69a8e9e44f834ec)
CS_PIN = 22

# ===== Channels (edit if your lab uses different ones) =====
LIGHT_CH = 0          # Light sensor (0..3.3V -> 0..100)
TEMP_CH  = 1          # Temp sensor  (0..3.3V -> -50..280 F)
WAVE_CH  = 2          # Put your waveform on CH0/CH2/CH4; change this to match

VREF = 3.3

# ===== SPI setup =====
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000
spi.mode = 0
spi.no_cs = True  # manual CS because CS is on GPIO22   [oai_citation:2‡Lab 3.pdf](sediment://file_00000000968471fda69a8e9e44f834ec)

GPIO.setmode(GPIO.BCM)
GPIO.setup(CS_PIN, GPIO.OUT, initial=GPIO.HIGH)

def read_adc(ch: int) -> int:
    """Read MCP3008 channel ch (0..7). Returns 0..1023."""
    if not (0 <= ch <= 7):
        raise ValueError("channel must be 0..7")

    GPIO.output(CS_PIN, GPIO.LOW)
    r = spi.xfer2([1, (8 + ch) << 4, 0])
    GPIO.output(CS_PIN, GPIO.HIGH)

    return ((r[1] & 3) << 8) | r[2]

def adc_to_volts(adc: int) -> float:
    return (adc * VREF) / 1023.0

def light_0_to_100(volts: float) -> float:
    # Lab: 0..3.3V -> 0..100   [oai_citation:3‡Lab 3.pdf](sediment://file_00000000968471fda69a8e9e44f834ec)
    return (volts / VREF) * 100.0

def temp_f(volts: float) -> float:
    # Lab: 0..3.3V -> -50..280 F   [oai_citation:4‡Lab 3.pdf](sediment://file_00000000968471fda69a8e9e44f834ec)
    return -50.0 + (volts / VREF) * (280.0 - (-50.0))

# ---------- Wave functions ----------
def capture_samples(ch: int, n: int = 2048):
    """Capture n samples as fast as possible and measure effective sample rate."""
    x = np.empty(n, dtype=np.float32)
    t0 = time.perf_counter()
    for i in range(n):
        x[i] = read_adc(ch)
    t1 = time.perf_counter()
    fs_eff = n / max(1e-9, (t1 - t0))
    return x, fs_eff

def estimate_freq_fft(samples: np.ndarray, fs: float) -> float:
    """Estimate frequency using FFT peak."""
    x = samples - np.mean(samples)
    if np.max(np.abs(x)) < 1e-6:
        return 0.0

    w = np.hanning(len(x))
    X = np.fft.rfft(x * w)
    mag = np.abs(X)
    freqs = np.fft.rfftfreq(len(x), d=1.0/fs)

    mag[:3] = 0.0  # ignore DC/low bins
    k = int(np.argmax(mag))
    return float(freqs[k])

def classify_wave(samples: np.ndarray) -> str:
    """Classify square/triangle/sine using simple slopes + plateaus."""
    x = samples - np.mean(samples)
    peak = np.max(np.abs(x))
    if peak < 1e-6:
        return "flat"

    x = x / peak

    # small smoothing to reduce ADC noise
    x = np.convolve(x, np.ones(5)/5, mode="same")

    dx = np.diff(x)
    plateau_frac = np.mean(np.abs(x) > 0.90)     # square has plateaus near +/-1
    slope_std = np.std(dx)                       # triangle has more uniform slope

    if plateau_frac > 0.25:
        return "square"
    elif slope_std < 0.12:
        return "triangle"
    else:
        return "sine"

def main():
    try:
        print("Lab 3 Required Demo (Ctrl+C to stop)")
        print(f"LIGHT_CH={LIGHT_CH}, TEMP_CH={TEMP_CH}, WAVE_CH={WAVE_CH}, CS=GPIO{CS_PIN}\n")

        last_shape = None

        while True:
            # --- Sensors ---
            light_adc = read_adc(LIGHT_CH)
            temp_adc  = read_adc(TEMP_CH)

            light_v = adc_to_volts(light_adc)
            temp_v  = adc_to_volts(temp_adc)

            light_val = light_0_to_100(light_v)
            temp_val  = temp_f(temp_v)

            # --- Wave ---
            wave_samples, fs_eff = capture_samples(WAVE_CH, n=2048)
            freq = estimate_freq_fft(wave_samples, fs_eff)
            shape = classify_wave(wave_samples)

            if shape != last_shape:
                print(f"Waveform detected: {shape.upper()}")
                last_shape = shape

            print(f"Light: {light_val:6.1f}/100  | Temp: {temp_val:7.1f} F | f≈ {freq:8.2f} Hz")
            time.sleep(0.25)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        GPIO.output(CS_PIN, GPIO.HIGH)
        GPIO.cleanup(CS_PIN)
        spi.close()

if __name__ == "__main__":
    main()