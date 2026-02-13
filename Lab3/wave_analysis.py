from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional
import math

try:
    import numpy as np  # type: ignore
except Exception:
    np = None  # type: ignore


@dataclass
class WaveResult:
    kind: str                    # 'sine' | 'triangle' | 'square' | 'unknown'
    frequency_hz: Optional[float]
    confidence: float            # 0..1
    details: str


def _to_float_list(x: List[int]) -> List[float]:
    return [float(v) for v in x]


def _normalize(samples: List[float]) -> List[float]:    
    # Remove DC offset and scale to roughly [-1, 1]
    mean = sum(samples) / max(1, len(samples))
    centered = [s - mean for s in samples]
    peak = max((abs(v) for v in centered), default=1.0)
    if peak < 1e-9:
        peak = 1.0
    return [v / peak for v in centered]


def estimate_frequency(samples: List[int], fs: float) -> Optional[float]:
    """Estimate dominant frequency using FFT (if numpy) or autocorrelation fallback."""
    if len(samples) < 10 or fs <= 0:
        return None

    x = _normalize(_to_float_list(samples))

    # FFT method (preferred)
    if np is not None and len(x) >= 64:
        arr = np.array(x, dtype=float)
        n = int(2 ** math.ceil(math.log2(len(arr))))  # next pow2
        window = np.hanning(len(arr))
        arrw = arr * window
        fft = np.fft.rfft(arrw, n=n)
        mag = np.abs(fft)
        freqs = np.fft.rfftfreq(n, d=1.0 / fs)

        # Ignore DC and very low bins
        mag[0:2] = 0
        idx = int(np.argmax(mag))
        if idx <= 0 or idx >= len(freqs):
            return None
        return float(freqs[idx])

    # Autocorrelation fallback (simple)
    # Find lag of first significant peak after lag=0
    n = len(x)
    max_lag = min(n - 1, int(fs / 2))  # don't search beyond half-second equivalent
    if max_lag < 5:
        return None

    def corr(lag: int) -> float:
        s = 0.0
        for i in range(n - lag):
            s += x[i] * x[i + lag]
        return s

    c0 = corr(0)
    if abs(c0) < 1e-9:
        return None

    # compute correlations for lags
    corrs = [corr(l) / c0 for l in range(max_lag + 1)]

    # find first peak after lag=0: local max above threshold
    threshold = 0.2
    best_lag = None
    for l in range(2, max_lag - 1):
        if corrs[l] > threshold and corrs[l] > corrs[l - 1] and corrs[l] > corrs[l + 1]:
            best_lag = l
            break

    if best_lag is None:
        return None

    return fs / best_lag


def classify_wave(samples: List[int], fs: float) -> WaveResult:
    """Noise-tolerant classification: square vs triangle vs sine.

    Heuristics used:
    - Square: large fraction of samples near +1 or -1 (plateaus), sharp transitions (high kurtosis-ish)
    - Triangle: derivative is often ~constant (many samples have similar slope), fewer plateaus
    - Sine: smooth; slope varies continuously; fewer plateaus and less constant-slope structure
    """
    if len(samples) < 30:
        return WaveResult("unknown", None, 0.0, "Not enough samples")

    x = _normalize(_to_float_list(samples))

    # Plateaus: fraction of samples close to +/-1
    near = 0.90
    plateau_frac = sum(1 for v in x if abs(v) >= near) / len(x)

    # Derivative statistics
    dx = [x[i + 1] - x[i] for i in range(len(x) - 1)]
    if not dx:
        return WaveResult("unknown", None, 0.0, "Degenerate signal")

    abs_dx = [abs(v) for v in dx]
    mean_abs_dx = sum(abs_dx) / len(abs_dx)

    # "Constant slope" score: triangle has many dx values close to median of |dx|
    sorted_abs = sorted(abs_dx)
    med = sorted_abs[len(sorted_abs) // 2]
    if med < 1e-6:
        med = 1e-6
    band = 0.35 * med
    const_slope_frac = sum(1 for v in abs_dx if abs(v - med) <= band) / len(abs_dx)

    # Roughness: count sign changes in derivative
    sign_changes = 0
    prev = dx[0]
    for d in dx[1:]:
        if (prev >= 0) != (d >= 0):
            sign_changes += 1
        prev = d
    sign_change_rate = sign_changes / max(1, len(dx))

    freq = estimate_frequency(samples, fs)

    # Decision logic (tuned for typical lab waveforms + ADC noise)
    if plateau_frac > 0.25:
        # Likely square
        confidence = min(1.0, 0.6 + 0.8 * (plateau_frac - 0.25))
        return WaveResult("square", freq, confidence, f"plateau_frac={plateau_frac:.2f}")

    # Triangle tends to have more constant-slope behavior
    if const_slope_frac > 0.38 and sign_change_rate < 0.20:
        confidence = min(1.0, 0.55 + 0.9 * (const_slope_frac - 0.38))
        return WaveResult("triangle", freq, confidence, f"const_slope_frac={const_slope_frac:.2f}, sign_change_rate={sign_change_rate:.2f}")

    # Sine tends to have higher sign-change rate and lower const-slope fraction
    if sign_change_rate >= 0.18:
        confidence = min(1.0, 0.45 + 0.8 * (sign_change_rate - 0.18))
        return WaveResult("sine", freq, confidence, f"sign_change_rate={sign_change_rate:.2f}, plateau_frac={plateau_frac:.2f}")

    return WaveResult("unknown", freq, 0.35, f"plateau_frac={plateau_frac:.2f}, const_slope_frac={const_slope_frac:.2f}, sign_change_rate={sign_change_rate:.2f}")
