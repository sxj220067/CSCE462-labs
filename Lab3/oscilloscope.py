from __future__ import annotations

import time

from config import (
    SPI_BUS, SPI_DEVICE, SPI_MAX_HZ, SPI_MODE,
    USE_GPIO_CS, GPIO_CS_PIN,
    VREF,
    SAMPLE_RATE_HZ, SAMPLE_SECONDS, WAVE_CH
)
from mcp3008 import MCP3008, MCP3008Config
from wave_analysis import classify_wave


def sample_adc(adc: MCP3008, channel: int, fs_hz: float, seconds: float) -> list[int]:
    """Uniform-ish sampling loop. Python isn't real-time, so note your effective rate."""
    n = max(10, int(fs_hz * seconds))
    dt = 1.0 / fs_hz
    data: list[int] = []

    t_next = time.perf_counter()
    for _ in range(n):
        data.append(adc.read(channel))
        t_next += dt
        # Busy-wait-ish until next sample time
        while True:
            now = time.perf_counter()
            if now >= t_next:
                break
            time.sleep(0.0001)
    return data


def effective_sample_rate(start: float, end: float, n: int) -> float:
    dur = max(1e-9, end - start)
    return n / dur


def main() -> None:
    adc = MCP3008(MCP3008Config(
        bus=SPI_BUS,
        device=SPI_DEVICE,
        max_hz=SPI_MAX_HZ,
        mode=SPI_MODE,
        use_gpio_cs=USE_GPIO_CS,
        gpio_cs_pin=GPIO_CS_PIN
    ))

    last_kind = None

    try:
        print("Mini-oscilloscope (Ctrl+C to stop)")
        print(f"Sampling CH{WAVE_CH} @ target {SAMPLE_RATE_HZ} Hz for {SAMPLE_SECONDS} s, VREF={VREF} V")
        while True:
            t0 = time.perf_counter()
            samples = sample_adc(adc, WAVE_CH, SAMPLE_RATE_HZ, SAMPLE_SECONDS)
            t1 = time.perf_counter()
            fs_eff = effective_sample_rate(t0, t1, len(samples))

            res = classify_wave(samples, fs_eff)

            if res.kind != last_kind:
                print(f"Wave: {res.kind.upper()}  | f≈ {res.frequency_hz:.2f} Hz" if res.frequency_hz else f"Wave: {res.kind.upper()}")
                print(f"  confidence={res.confidence:.2f}, details={res.details}, fs_eff={fs_eff:.1f} Hz")
                last_kind = res.kind

            # brief pause so prints aren't too spammy
            time.sleep(0.10)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        adc.close()


if __name__ == "__main__":
    main()
