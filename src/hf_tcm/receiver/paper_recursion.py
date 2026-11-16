"""Isolated algebraic recursion from [A](1) for I/Q coefficient estimates.

This module implements the printed recursion only. It does not provide the
posterior, model coefficients, predictions, or initial conditions needed for a
complete paper-exact estimator.
"""

from __future__ import annotations

from numbers import Real

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def _finite_real_array(value: object, name: str) -> FloatArray:
    try:
        array = np.asarray(value)
        if np.iscomplexobj(array):
            raise ValueError
        result = np.asarray(array, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real numeric array") from exc
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def update_quadrature_estimates(
    *,
    previous_fluctuating: object,
    alpha_prime: Real,
    k_tilde: object,
    posterior: object,
    observed_iq: object,
    predicted_iq: object,
    mu0: object,
) -> tuple[FloatArray, FloatArray]:
    """Apply the printed [A](1)/[B](15) recursion to one or more beams.

    I and Q are the last-axis components in that order. A single beam uses
    ``(2,)`` coefficient/observation vectors, an ``(M,)`` posterior, and
    ``(M, 2)`` predictions. Multiple beams use ``(L, 2)``, ``(L, M)``, and
    ``(L, M, 2)`` respectively. Posterior rows are validated, never inferred
    or normalized by this function.

    Returns ``(new_fluctuating, full_estimate)`` where
    ``full_estimate = new_fluctuating + mu0``. The hypothesis count is the
    supplied prediction dimension; this function does not identify it with an
    author's ``theta`` indexing convention.
    """
    if isinstance(alpha_prime, (bool, np.bool_)) or not isinstance(alpha_prime, Real):
        raise ValueError("alpha_prime must be a finite real scalar")
    alpha = float(alpha_prime)
    if not np.isfinite(alpha):
        raise ValueError("alpha_prime must be a finite real scalar")

    previous = _finite_real_array(previous_fluctuating, "previous_fluctuating")
    gain = _finite_real_array(k_tilde, "k_tilde")
    weights = _finite_real_array(posterior, "posterior")
    observed = _finite_real_array(observed_iq, "observed_iq")
    predicted = _finite_real_array(predicted_iq, "predicted_iq")
    regular = _finite_real_array(mu0, "mu0")

    single_beam = previous.ndim == 1
    if single_beam:
        if previous.shape != (2,):
            raise ValueError("previous_fluctuating must have shape (2,) for one beam")
        if gain.shape != (2,):
            raise ValueError("k_tilde must have shape (2,) for one beam")
        if observed.shape != (2,):
            raise ValueError("observed_iq must have shape (2,) for one beam")
        if regular.shape != (2,):
            raise ValueError("mu0 must have shape (2,) for one beam")
        if weights.ndim != 1:
            raise ValueError("posterior must have shape (M,) for one beam")
        if predicted.ndim != 2 or predicted.shape[1:] != (2,):
            raise ValueError("predicted_iq must have shape (M, 2) for one beam")
        hypothesis_count = weights.shape[0]
        if predicted.shape[0] != hypothesis_count:
            raise ValueError("predicted_iq hypothesis dimension must match posterior")
    else:
        if previous.ndim != 2 or previous.shape[1:] != (2,) or previous.shape[0] == 0:
            raise ValueError("previous_fluctuating must have shape (L, 2) for multiple beams")
        beam_count = previous.shape[0]
        if gain.shape != (beam_count, 2):
            raise ValueError("k_tilde must have shape (L, 2) matching previous_fluctuating")
        if observed.shape != (beam_count, 2):
            raise ValueError("observed_iq must have shape (L, 2) matching previous_fluctuating")
        if regular.shape != (beam_count, 2):
            raise ValueError("mu0 must have shape (L, 2) matching previous_fluctuating")
        if weights.ndim != 2 or weights.shape[0] != beam_count:
            raise ValueError("posterior must have shape (L, M) matching the beam count")
        if predicted.ndim != 3 or predicted.shape[0] != beam_count or predicted.shape[2] != 2:
            raise ValueError("predicted_iq must have shape (L, M, 2)")
        hypothesis_count = weights.shape[1]
        if predicted.shape[1] != hypothesis_count:
            raise ValueError("predicted_iq hypothesis dimension must match posterior")

    if hypothesis_count == 0:
        raise ValueError("posterior must contain at least one hypothesis")
    if np.any(weights < 0.0):
        raise ValueError("posterior weights must be nonnegative")
    weight_sums = np.sum(weights, axis=-1)
    if not np.allclose(weight_sums, 1.0, rtol=0.0, atol=1e-10):
        raise ValueError("posterior weights must sum to 1 for each beam")

    posterior_axis = -2 if single_beam else -2
    with np.errstate(over="ignore", invalid="ignore"):
        residuals = observed[..., None, :] - predicted
        weighted_innovation = np.sum(weights[..., :, None] * residuals, axis=posterior_axis)
        new_fluctuating = alpha * previous + gain * weighted_innovation
        full_estimate = new_fluctuating + regular

    if not (
        np.all(np.isfinite(weighted_innovation))
        and np.all(np.isfinite(new_fluctuating))
        and np.all(np.isfinite(full_estimate))
    ):
        raise ValueError("recursion produced a non-finite estimate")
    return np.asarray(new_fluctuating, dtype=np.float64), np.asarray(
        full_estimate, dtype=np.float64
    )
