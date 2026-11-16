"""Single-beam explicit-operand step for reconstruction estimator state."""

from __future__ import annotations

from numbers import Integral

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.receiver.paper_recursion import update_quadrature_estimates
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState

FloatArray = NDArray[np.float64]


def _array_with_shape(value: ArrayLike, *, name: str, shape: tuple[int, ...]) -> FloatArray:
    try:
        array = np.asarray(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must have shape {shape}") from exc
    if array.shape != shape:
        raise ValueError(f"{name} must have shape {shape}")
    return array


def advance_reconstruction_estimator_state(
    state: ReconstructionEstimatorState,
    *,
    time_index: int,
    next_time_index: int,
    alpha_prime: float,
    k_tilde: ArrayLike,
    mu0: ArrayLike,
    observed_iq: ArrayLike,
    predicted_iq: ArrayLike,
    posterior: ArrayLike,
) -> ReconstructionEstimatorState:
    """Advance one ``L=1`` snapshot by delegating to the [A](1) kernel.

    The state and beam coefficient parameters use ``(1, 2)``. Explicit
    single-beam operands use the shapes accepted by ``paper_recursion.py``:
    ``observed_iq=(2,)``, ``predicted_iq=(M, 2)``, ``posterior=(M,)``.
    This adapter adds the beam axis required by the kernel's batched ``L``
    form and returns its new fluctuating and full estimates at
    ``next_time_index``. It performs no estimator arithmetic itself.
    """
    for name, value in (
        ("time_index", time_index),
        ("next_time_index", next_time_index),
    ):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
            raise ValueError(f"{name} must be an integer absolute index")
    current_index = int(time_index)
    successor_index = int(next_time_index)
    if current_index != state.time_index:
        raise ValueError("time_index must match state time_index")
    if successor_index != current_index + 1:
        raise ValueError("next_time_index must equal time_index + 1")

    if state.fluctuating_iq.shape != (1, 2) or state.full_iq.shape != (1, 2):
        raise ValueError("state estimates must have shape (1, 2) for this L=1 adapter")

    gain = _array_with_shape(k_tilde, name="k_tilde", shape=(1, 2))
    regular = _array_with_shape(mu0, name="mu0", shape=(1, 2))
    observation = _array_with_shape(observed_iq, name="observed_iq", shape=(2,))

    try:
        predictions = np.asarray(predicted_iq)
        weights = np.asarray(posterior)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("predicted_iq and posterior must be numeric arrays") from exc
    if predictions.ndim != 2 or predictions.shape[1:] != (2,):
        raise ValueError("predicted_iq must have shape (M, 2)")
    if weights.ndim != 1:
        raise ValueError("posterior must have shape (M,) for one beam")
    if predictions.shape[0] != weights.shape[0]:
        raise ValueError("predicted_iq hypothesis dimension must match posterior")

    fluctuating, full = update_quadrature_estimates(
        previous_fluctuating=state.fluctuating_iq,
        alpha_prime=alpha_prime,
        k_tilde=gain,
        posterior=weights[np.newaxis, :],
        observed_iq=observation[np.newaxis, :],
        predicted_iq=predictions[np.newaxis, :, :],
        mu0=regular,
    )
    return ReconstructionEstimatorState(
        fluctuating_iq=fluctuating,
        full_iq=full,
        time_index=successor_index,
    )
