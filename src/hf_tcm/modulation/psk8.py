"""Normalized 8PSK constellation and baseline modulator/demodulator."""

import math
from collections.abc import Iterable
from numbers import Real

import numpy as np
from numpy.typing import NDArray

from hf_tcm.modulation.labeling import (
    BASELINE_ASSUMPTION,
    Label,
    index_to_label,
    label_to_index,
    normalize_label,
    validate_profile,
)


def _phase(phase_offset: float) -> float:
    if isinstance(phase_offset, bool) or not isinstance(phase_offset, Real):
        raise ValueError("phase_offset must be a finite real number")
    try:
        value = float(phase_offset)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("phase_offset must be a finite real number") from exc
    if not math.isfinite(value):
        raise ValueError("phase_offset must be a finite real number")
    return value


def constellation(phase_offset: float = 0.0) -> NDArray[np.complex128]:
    """Return ``exp(j * (2πm/8 + phase_offset))`` for indices 0 through 7."""
    phase = _phase(phase_offset)
    indices = np.arange(8, dtype=np.float64)
    return np.exp(1j * (2.0 * np.pi * indices / 8.0 + phase))


def modulate(
    labels: Iterable[Iterable[int]],
    *,
    phase_offset: float = 0.0,
    profile: str = BASELINE_ASSUMPTION,
) -> NDArray[np.complex128]:
    """Map labeled coded triples to normalized complex 8PSK symbols."""
    validate_profile(profile)
    points = constellation(phase_offset)
    indices = [label_to_index(normalize_label(label), profile=profile) for label in labels]
    return points[np.asarray(indices, dtype=np.intp)]


def demodulate(
    symbols: Iterable[complex],
    *,
    phase_offset: float = 0.0,
    profile: str = BASELINE_ASSUMPTION,
) -> list[Label]:
    """Map symbols to nearest 8PSK labels (hard decision)."""
    validate_profile(profile)
    points = constellation(phase_offset)
    received: list[complex] = []
    for symbol in symbols:
        if isinstance(symbol, bool) or not isinstance(symbol, (int, float, complex, np.number)):
            raise ValueError("symbols must be finite numeric values")
        value = complex(symbol)
        if not math.isfinite(value.real) or not math.isfinite(value.imag):
            raise ValueError("symbols must be finite numeric values")
        received.append(value)
    if not received:
        return []
    distances = np.abs(np.asarray(received, dtype=np.complex128)[:, None] - points[None, :])
    return [index_to_label(int(index), profile=profile) for index in np.argmin(distances, axis=1)]
