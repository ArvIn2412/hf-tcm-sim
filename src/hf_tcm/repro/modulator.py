"""Complex 8PSK modulation with explicit amplitude and phase origin."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.source_bits import immutable_int8

ComplexArray = NDArray[np.complex128]
FloatArray = NDArray[np.float64]


def _real(value: object, *, name: str, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        raise ValueError(f"{name} must be finite" + (" and positive" if positive else ""))
    return result


def _immutable(values: object, dtype: np.dtype) -> NDArray:
    owned = np.array(values, dtype=dtype, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=dtype).reshape(owned.shape)


@dataclass(frozen=True, slots=True)
class ModulationResult:
    phase_indices: NDArray[np.int8]
    phase_values_rad: FloatArray
    symbols: ComplexArray
    symbol_i: FloatArray
    symbol_q: FloatArray
    symbol_energies: FloatArray
    amplitude: float
    phase_offset_rad: float
    phase_increment_rad: float
    normalization_profile: str


def modulate(
    phase_indices: object,
    *,
    amplitude: float,
    phase_offset_rad: float,
    phase_increment_rad: float = math.pi / 4.0,
) -> ModulationResult:
    try:
        raw = np.asarray(phase_indices)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("phase_indices must be a nonempty integer vector") from exc
    if raw.ndim != 1 or raw.dtype.kind not in "iu" or len(raw) == 0:
        raise ValueError("phase_indices must be a nonempty integer vector")
    if np.any(raw < 0) or np.any(raw > 7):
        raise ValueError("phase_indices must be in the range 0 through 7")
    amp = _real(amplitude, name="amplitude", positive=True)
    offset = _real(phase_offset_rad, name="phase_offset_rad")
    increment = _real(phase_increment_rad, name="phase_increment_rad", positive=True)
    if not math.isclose(increment, math.pi / 4.0, rel_tol=0.0, abs_tol=1e-15):
        raise ValueError("phase_increment_rad must equal pi/4 in this profile")
    indices = np.asarray(raw, dtype=np.int8)
    phases = offset + indices.astype(np.float64) * increment
    symbols = amp * np.exp(1j * phases)
    energies = np.square(np.abs(symbols))
    return ModulationResult(
        phase_indices=immutable_int8(indices),
        phase_values_rad=_immutable(phases, np.dtype(np.float64)),
        symbols=_immutable(symbols, np.dtype(np.complex128)),
        symbol_i=_immutable(symbols.real, np.dtype(np.float64)),
        symbol_q=_immutable(symbols.imag, np.dtype(np.float64)),
        symbol_energies=_immutable(energies, np.dtype(np.float64)),
        amplitude=amp,
        phase_offset_rad=offset,
        phase_increment_rad=increment,
        normalization_profile="explicit_amplitude_no_implicit_normalization",
    )
