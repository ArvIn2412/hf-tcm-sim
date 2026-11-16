"""Stable soft edge weights (project pseudo-posterior, not HMM marginals)."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray


def posterior_weights(metrics: object, *, beta: float) -> NDArray[np.float64]:
    values = np.asarray(metrics, dtype=np.float64)
    if values.ndim != 1 or values.size != 16:
        raise ValueError("metrics must be a vector of 16 candidate values")
    if not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError("metrics must be finite and nonnegative")
    if isinstance(beta, bool) or not math.isfinite(float(beta)) or beta < 0:
        raise ValueError("beta must be finite and nonnegative")
    # Subtracting the minimum is equivalent to log-sum-exp normalization and
    # preserves the flat, explicit project prior over the 16 edge candidates.
    with np.errstate(over="ignore", invalid="ignore"):
        log_weights = -float(beta) * (values - float(np.min(values)))
    log_weights -= float(np.max(log_weights))
    weights = np.exp(log_weights)
    denominator = float(np.sum(weights))
    if not math.isfinite(denominator) or denominator <= 0:
        raise ValueError("posterior normalization is degenerate")
    return weights / denominator
