"""Literal algebraic transform from [A](5), not a complete paper-exact receiver."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

PHASE_STEP_RAD = np.pi / 4.0


def _phase_indices(values: object) -> NDArray[np.int64]:
    try:
        raw = np.asarray(values)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("b must be an integer in {0, ..., 7} or a 1-D array of them") from exc
    if (
        raw.ndim not in (0, 1)
        or np.issubdtype(raw.dtype, np.bool_)
        or not np.issubdtype(raw.dtype, np.integer)
    ):
        raise ValueError("b must be an integer in {0, ..., 7} or a 1-D array of them")
    indices = np.asarray(raw, dtype=np.int64)
    if indices.size == 0:
        raise ValueError("b must contain at least one phase index")
    if np.any((indices < 0) | (indices > 7)):
        raise ValueError("each b value must be in {0, ..., 7}")
    return indices


def _quadrature_coefficients(values: ArrayLike, *, name: str) -> NDArray[np.float64]:
    try:
        raw = np.asarray(values)
        if np.iscomplexobj(raw):
            raise ValueError
        coefficients = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must contain finite real coefficients") from exc
    if (
        coefficients.ndim not in (0, 1)
        or np.issubdtype(raw.dtype, np.bool_)
        or not np.all(np.isfinite(coefficients))
    ):
        raise ValueError(f"{name} must be a finite scalar or 1-D array")
    return coefficients


def iq_quadratures_from_index(
    b: object,
    mu1: ArrayLike,
    mu2: ArrayLike,
) -> NDArray[np.float64]:
    """Return the two quadratures specified by [A](5) for explicit ``b``.

    ``b`` is an integer from 0 through 7. For one ray, ``b``, ``mu1`` and
    ``mu2`` are scalars and the result has shape ``(2,)``. For multiple rays,
    they are equal-shaped 1-D arrays and the result has shape ``(L, 2)``.
    The last axis is ordered as the source's ``j=1`` then ``j=2`` quadrature.
    No mapping from coded bits or hypothesis IDs is performed.
    """
    indices = _phase_indices(b)
    first_coefficient = _quadrature_coefficients(mu1, name="mu1")
    second_coefficient = _quadrature_coefficients(mu2, name="mu2")
    if first_coefficient.shape != indices.shape:
        raise ValueError("mu1 shape must match b")
    if second_coefficient.shape != indices.shape:
        raise ValueError("mu2 shape must match b")

    phase = indices * PHASE_STEP_RAD
    with np.errstate(over="ignore", invalid="ignore"):
        first = first_coefficient * (-np.sin(phase))
        second = second_coefficient * np.cos(phase)
        result = np.stack((first, second), axis=-1)
    if not np.all(np.isfinite(result)):
        raise ValueError("quadrature transform produced non-finite values")
    return np.asarray(result, dtype=np.float64)
