"""Rectangular zero-order-hold samples for transmitted 8PSK symbols."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

import numpy as np
from numpy.typing import NDArray

ComplexArray = NDArray[np.complex128]
IndexArray = NDArray[np.int64]
FloatArray = NDArray[np.float64]


def _immutable(values: object, dtype: np.dtype) -> NDArray:
    owned = np.array(values, dtype=dtype, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=dtype).reshape(owned.shape)


@dataclass(frozen=True, slots=True)
class WaveformResult:
    tx_samples: ComplexArray
    absolute_sample_index: IndexArray
    symbol_index: IndexArray
    local_sample_index: IndexArray
    sample_tx_i: FloatArray
    sample_tx_q: FloatArray
    samples_per_symbol: int
    waveform_rule: str = "rectangular_zoh"


def rectangular_zoh(symbols: object, *, samples_per_symbol: int = 8) -> WaveformResult:
    try:
        values = np.asarray(symbols, dtype=np.complex128)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("symbols must be a nonempty finite complex vector") from exc
    if values.ndim != 1 or len(values) == 0:
        raise ValueError("symbols must be a nonempty finite complex vector")
    if not np.all(np.isfinite(values.real)) or not np.all(np.isfinite(values.imag)):
        raise ValueError("symbols must contain finite complex values")
    if isinstance(samples_per_symbol, bool) or not isinstance(samples_per_symbol, Integral):
        raise ValueError("samples_per_symbol must be a positive integer")
    sps = int(samples_per_symbol)
    if sps != 8:
        raise ValueError("samples_per_symbol must equal 8 for the S1-aligned profile")
    samples = np.repeat(values, sps)
    sample_count = len(samples)
    symbol_index = np.repeat(np.arange(len(values), dtype=np.int64), sps)
    local_index = np.tile(np.arange(sps, dtype=np.int64), len(values))
    return WaveformResult(
        tx_samples=_immutable(samples, np.dtype(np.complex128)),
        absolute_sample_index=_immutable(np.arange(sample_count), np.dtype(np.int64)),
        symbol_index=_immutable(symbol_index, np.dtype(np.int64)),
        local_sample_index=_immutable(local_index, np.dtype(np.int64)),
        sample_tx_i=_immutable(samples.real, np.dtype(np.float64)),
        sample_tx_q=_immutable(samples.imag, np.dtype(np.float64)),
        samples_per_symbol=sps,
    )
