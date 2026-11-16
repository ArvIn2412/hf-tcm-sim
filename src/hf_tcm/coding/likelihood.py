"""Isolated log-likelihood component transcribed from [B], equation (7)."""

import math
from numbers import Real

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _residual_array(values: ArrayLike, *, name: str) -> NDArray[np.float64]:
    try:
        residuals = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must contain numeric values") from exc
    if residuals.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if residuals.size == 0:
        raise ValueError(f"{name} must contain at least one sample")
    if not np.all(np.isfinite(residuals)):
        raise ValueError(f"{name} must contain only finite values")
    return residuals


def _finite_coefficient(value: Real) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("coefficient_c must be a finite real number")
    try:
        coefficient = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("coefficient_c must be a finite real number") from exc
    if not math.isfinite(coefficient):
        raise ValueError("coefficient_c must be a finite real number")
    return coefficient


def log_likelihood_component(
    residual_i: ArrayLike,
    residual_q: ArrayLike,
    *,
    coefficient_c: Real,
) -> float:
    """Compute only ``C * sum_k hypot(r_I[k], r_Q[k])`` from [B](7).

    Both residual arrays and ``coefficient_c`` must be supplied explicitly.
    ``math.hypot`` avoids intermediate overflow while forming each I/Q norm;
    ``math.fsum`` limits accumulation error across samples. This returns the
    exponent argument only, not ``exp(...)``, the complete ``V`` factor, or a
    likelihood for [A]. The source does not establish the sign or numerical
    value of ``C``, so either sign is preserved without interpretation.
    """
    in_phase = _residual_array(residual_i, name="residual_i")
    quadrature = _residual_array(residual_q, name="residual_q")
    coefficient = _finite_coefficient(coefficient_c)
    if in_phase.shape != quadrature.shape:
        raise ValueError("residual_i and residual_q must have the same shape")
    if coefficient == 0.0:
        return 0.0

    try:
        norm_sum = math.fsum(
            math.hypot(float(i_value), float(q_value))
            for i_value, q_value in zip(in_phase, quadrature, strict=True)
        )
    except OverflowError as exc:
        raise ValueError("quadrature norm sum is outside the supported numeric range") from exc

    result = coefficient * norm_sum
    if not math.isfinite(result):
        raise ValueError("log-likelihood component is outside the supported numeric range")
    return result
