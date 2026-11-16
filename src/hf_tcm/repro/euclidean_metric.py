"""Explicit Euclidean and squared-Euclidean branch metrics for REPRO-05."""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import NDArray

MetricProfile = Literal["euclidean", "squared_euclidean"]


def euclidean_metric_rows(
    observed: object, predictions: object, *, profile: MetricProfile
) -> NDArray[np.float64]:
    """Return one nonnegative metric per candidate; candidates are axis 1."""
    y = np.asarray(observed, dtype=np.complex128)
    yhat = np.asarray(predictions, dtype=np.complex128)
    if y.ndim != 2 or yhat.ndim != 3 or yhat.shape[0] != y.shape[0]:
        raise ValueError("observed must be (F,S) and predictions must be (F,E,S)")
    if yhat.shape[2] != y.shape[1] or y.shape[1] < 1 or y.shape[0] < 1:
        raise ValueError("observed and prediction sample dimensions must match and be nonempty")
    if profile not in {"euclidean", "squared_euclidean"}:
        raise ValueError("metric_profile must be euclidean or squared_euclidean")
    if not np.all(np.isfinite(y)) or not np.all(np.isfinite(yhat)):
        raise ValueError("metric operands must be finite")
    residual = y[:, None, :] - yhat
    # Scaling avoids overflow in the sum-of-squares for finite large operands.
    scale = np.max(np.abs(residual), axis=2)
    normalized = np.divide(
        residual,
        scale[:, :, None],
        out=np.zeros_like(residual),
        where=scale[:, :, None] != 0,
    )
    normalized_energy = np.sum(np.square(np.abs(normalized)), axis=2)
    with np.errstate(over="ignore", invalid="ignore"):
        squared = np.square(scale) * normalized_energy
    if profile == "euclidean":
        result = scale * np.sqrt(normalized_energy)
    else:
        result = squared
    if not np.all(np.isfinite(result)):
        raise ValueError("metric result overflowed and is non-finite")
    return np.asarray(result, dtype=np.float64)
