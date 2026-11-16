"""Explicit one-path snapshot adapter for reconstruction forward coefficients."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

import numpy as np
from numpy.typing import NDArray

from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class ReconstructionForwardCoefficientSnapshot:
    """Immutable forward coefficients tagged with their estimator clock label."""

    estimated_path_coefficients: FloatArray
    estimator_time_index: int

    def __post_init__(self) -> None:
        if isinstance(self.estimator_time_index, (bool, np.bool_)) or not isinstance(
            self.estimator_time_index, Integral
        ):
            raise ValueError("estimator_time_index must be an integer absolute index")
        try:
            coefficients = np.asarray(self.estimated_path_coefficients)
            if np.iscomplexobj(coefficients):
                raise ValueError
            coefficients = np.asarray(coefficients, dtype=np.float64)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                "estimated_path_coefficients must be finite real shape (1, 2)"
            ) from exc
        if coefficients.shape != (1, 2) or not np.all(np.isfinite(coefficients)):
            raise ValueError("estimated_path_coefficients must be finite real shape (1, 2)")

        owned = np.array(coefficients, dtype=np.float64, order="C", copy=True)
        immutable = np.frombuffer(owned.tobytes(), dtype=np.float64).reshape((1, 2))
        object.__setattr__(self, "estimated_path_coefficients", immutable)
        object.__setattr__(self, "estimator_time_index", int(self.estimator_time_index))


def snapshot_full_iq_for_forward(
    state: ReconstructionEstimatorState,
    *,
    estimator_time_index: int,
) -> ReconstructionForwardCoefficientSnapshot:
    """Copy one-path ``full_iq`` for forward use without assigning frame time.

    The required clock label must match the state. It remains an estimator
    index; mapping it to sample/symbol indices or a forward frame is external.
    """
    if not isinstance(state, ReconstructionEstimatorState):
        raise ValueError("state must be a ReconstructionEstimatorState")
    if isinstance(estimator_time_index, (bool, np.bool_)) or not isinstance(
        estimator_time_index, Integral
    ):
        raise ValueError("estimator_time_index must be an integer absolute index")
    if state.fluctuating_iq.shape != (1, 2) or state.full_iq.shape != (1, 2):
        raise ValueError("state must contain exactly one path with shape (1, 2)")
    if int(estimator_time_index) != state.time_index:
        raise ValueError("estimator_time_index must match state.time_index")

    return ReconstructionForwardCoefficientSnapshot(
        estimated_path_coefficients=state.full_iq,
        estimator_time_index=int(estimator_time_index),
    )
