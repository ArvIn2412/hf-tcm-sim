"""Explicit noise generators for the REPRO-03 discrete complex-baseband model."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray


def generate_complex_noise(
    length: int,
    *,
    complex_variance: float,
    seed: int,
) -> NDArray[np.complex128]:
    """Generate independent circular sample-domain noise with E|w|²=variance.

    Thus I and Q are independent with variance ``complex_variance / 2``.
    This helper is not an Eb/N0 calibration and not article equations (8)-(10).
    """
    if type(length) is not int or length < 1:
        raise ValueError("length must be a positive integer")
    if isinstance(complex_variance, bool) or not isinstance(complex_variance, (int, float)):
        raise ValueError("complex_variance must be a finite non-negative real number")
    variance = float(complex_variance)
    if not math.isfinite(variance) or variance < 0.0:
        raise ValueError("complex_variance must be a finite non-negative real number")
    if type(seed) is not int or not 0 <= seed <= (1 << 64) - 1:
        raise ValueError("seed must be an integer in [0, 2**64-1]")
    if variance == 0.0:
        return np.zeros(length, dtype=np.complex128)
    rng = np.random.Generator(np.random.PCG64(seed))
    scale = math.sqrt(variance / 2.0)
    i_values = rng.standard_normal(length)
    q_values = rng.standard_normal(length)
    return np.asarray(scale * (i_values + 1j * q_values), dtype=np.complex128)
