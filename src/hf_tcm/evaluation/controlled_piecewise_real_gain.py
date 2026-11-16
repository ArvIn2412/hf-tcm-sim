"""Deterministic evaluation-side adapter for the proposed M10 gain profiles.

This module applies a caller-supplied symbol gain schedule and noise vector. It
does not create RNG streams, expose channel truth to a receiver, or modify any
existing channel or receiver contract.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
from numpy.typing import NDArray

GainSchedule = NDArray[np.float64]
ComplexSamples = NDArray[np.complex128]

FRAME_SYMBOLS: Final = 256
SAMPLES_PER_SYMBOL: Final = 8
SWITCH_SYMBOL_INDEX: Final = 128
SWITCH_SAMPLE_INDEX: Final = SWITCH_SYMBOL_INDEX * SAMPLES_PER_SYMBOL
NOMINAL_GAIN: Final = 0.75
LOW_GAIN: Final = 0.60
HIGH_GAIN: Final = math.sqrt(2.0 * NOMINAL_GAIN**2 - LOW_GAIN**2)
PROFILE_IDS: Final = ("P0_CONSTANT", "P1_HIGH_TO_LOW", "P2_LOW_TO_HIGH")


def _finite_complex_vector(value: object, *, name: str) -> ComplexSamples:
    try:
        raw = np.asarray(value)
        if raw.ndim != 1 or raw.dtype.kind not in "iufc":
            raise ValueError
        result = np.asarray(raw, dtype=np.complex128)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite one-dimensional numeric vector") from exc
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite one-dimensional numeric vector")
    return result


def build_gain_schedule(profile_id: str) -> GainSchedule:
    """Return one immutable 256-symbol gain schedule for P0, P1, or P2."""
    if profile_id not in PROFILE_IDS:
        raise ValueError(f"unknown gain profile: {profile_id!r}")
    if profile_id == "P0_CONSTANT":
        gains = np.full(FRAME_SYMBOLS, NOMINAL_GAIN, dtype=np.float64)
    elif profile_id == "P1_HIGH_TO_LOW":
        gains = np.empty(FRAME_SYMBOLS, dtype=np.float64)
        gains[:SWITCH_SYMBOL_INDEX] = HIGH_GAIN
        gains[SWITCH_SYMBOL_INDEX:] = LOW_GAIN
    else:
        gains = np.empty(FRAME_SYMBOLS, dtype=np.float64)
        gains[:SWITCH_SYMBOL_INDEX] = LOW_GAIN
        gains[SWITCH_SYMBOL_INDEX:] = HIGH_GAIN
    if not np.all(np.isfinite(gains)) or np.any(gains <= 0.0):
        raise ValueError("gain schedule must contain only finite positive real values")
    return np.frombuffer(gains.tobytes(), dtype=np.float64)


def apply_symbol_gain_schedule(
    waveform_samples: object,
    noise_samples: object,
    gains_by_symbol: object,
    *,
    samples_per_symbol: int = SAMPLES_PER_SYMBOL,
) -> ComplexSamples:
    """Apply ``a[floor(n/sps)] * x[n] + w[n]`` without generating randomness."""
    if type(samples_per_symbol) is not int or samples_per_symbol < 1:
        raise ValueError("samples_per_symbol must be a positive integer")
    waveform = _finite_complex_vector(waveform_samples, name="waveform_samples")
    noise = _finite_complex_vector(noise_samples, name="noise_samples")
    try:
        raw_gains = np.asarray(gains_by_symbol)
        if raw_gains.ndim != 1 or raw_gains.dtype.kind not in "iuf":
            raise ValueError
        gains = np.asarray(raw_gains, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("gains_by_symbol must be a finite real vector") from exc
    if not np.all(np.isfinite(gains)) or np.any(gains <= 0.0):
        raise ValueError("gains_by_symbol must contain only finite positive real values")
    if waveform.shape != noise.shape:
        raise ValueError("waveform_samples and noise_samples must have identical shapes")
    if waveform.size == 0 or waveform.size % samples_per_symbol != 0:
        raise ValueError("sample vectors must contain complete nonempty symbols")
    symbol_count = waveform.size // samples_per_symbol
    if gains.shape != (symbol_count,):
        raise ValueError("gains_by_symbol must contain exactly one gain per complete symbol")
    sample_gains = np.repeat(gains, samples_per_symbol)
    received = np.asarray(sample_gains * waveform + noise, dtype=np.complex128, order="C")
    if not np.all(np.isfinite(received)):
        raise FloatingPointError("controlled gain channel produced non-finite received samples")
    received.setflags(write=False)
    return received


def generate_controlled_gain_received(
    waveform_samples: object, noise_samples: object, profile_id: str
) -> ComplexSamples:
    """Apply an exact M10a profile to explicit waveform/noise operands."""
    gains = build_gain_schedule(profile_id)
    return apply_symbol_gain_schedule(waveform_samples, noise_samples, gains)
