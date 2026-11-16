"""Causal project-reconstructed complex single-path estimator."""

from __future__ import annotations

import math

import numpy as np


def update_complex_estimate(
    *,
    state_pre: complex,
    residuals: object,
    weights: object,
    alpha_prime: float,
    k_tilde: float,
    mu0: complex,
) -> tuple[complex, complex]:
    """Update fluctuation state from weighted edge residuals averaged per symbol.

    Returns ``(state_post, innovation)``.  This is a complex-baseband project
    reconstruction of the source recursion, not an author-exact A(1) equation.
    """
    residual = np.asarray(residuals, dtype=np.complex128)
    probability = np.asarray(weights, dtype=np.float64)
    if residual.ndim != 2 or residual.shape[0] < 1 or residual.shape[1] < 1:
        raise ValueError("residuals must have shape (E,S) with E,S >= 1")
    if probability.shape != (residual.shape[0],) or not np.all(np.isfinite(probability)):
        raise ValueError("weights must match the residual candidate dimension")
    if np.any(probability < 0) or not math.isclose(float(probability.sum()), 1.0, abs_tol=1e-12):
        raise ValueError("weights must be nonnegative and sum to one")
    if not np.all(np.isfinite(residual)):
        raise ValueError("residuals must be finite")
    for name, value in (("alpha_prime", alpha_prime), ("k_tilde", k_tilde)):
        if isinstance(value, bool) or not math.isfinite(float(value)):
            raise ValueError(f"{name} must be finite")
    offset = complex(mu0)
    state = complex(state_pre)
    if not all(math.isfinite(v) for v in (offset.real, offset.imag, state.real, state.imag)):
        raise ValueError("estimator states must be finite")
    innovation = complex(np.dot(probability, residual.mean(axis=1)))
    post = float(alpha_prime) * state + float(k_tilde) * innovation
    if not all(math.isfinite(v) for v in (post.real, post.imag, innovation.real, innovation.imag)):
        raise ValueError("estimator update produced a non-finite value")
    return post, innovation
