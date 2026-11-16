"""Explicit immutable state container for project reconstruction estimates."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _immutable_iq_matrix(value: ArrayLike, *, name: str) -> FloatArray:
    try:
        raw = np.asarray(value)
        if np.iscomplexobj(raw):
            raise ValueError
        array = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real array with shape (L, 2)") from exc
    if array.ndim != 2 or array.shape[0] == 0 or array.shape[1] != 2:
        raise ValueError(f"{name} must have shape (L, 2) with at least one beam")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")

    owned = np.array(array, dtype=np.float64, order="C", copy=True)
    # An immutable bytes buffer prevents callers from re-enabling write access.
    return np.frombuffer(owned.tobytes(), dtype=np.float64).reshape(owned.shape)


@dataclass(frozen=True, slots=True)
class ReconstructionEstimatorState:
    """Snapshot of per-beam I/Q estimates at one explicit absolute index.

    This container stores values only. It does not calculate predictions,
    posteriors, coefficient updates, or a successor state.
    """

    fluctuating_iq: FloatArray
    full_iq: FloatArray
    time_index: int

    def __post_init__(self) -> None:
        if isinstance(self.time_index, (bool, np.bool_)) or not isinstance(
            self.time_index, Integral
        ):
            raise ValueError("time_index must be an integer absolute index")

        fluctuating = _immutable_iq_matrix(self.fluctuating_iq, name="fluctuating_iq")
        full = _immutable_iq_matrix(self.full_iq, name="full_iq")
        if full.shape != fluctuating.shape:
            raise ValueError("full_iq and fluctuating_iq must have matching shape")

        object.__setattr__(self, "fluctuating_iq", fluctuating)
        object.__setattr__(self, "full_iq", full)
        object.__setattr__(self, "time_index", int(self.time_index))
