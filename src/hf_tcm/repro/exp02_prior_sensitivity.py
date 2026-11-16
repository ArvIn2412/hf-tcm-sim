"""Frozen, truth-free prior perturbations for the EXP-02 sensitivity study."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

PRIOR_VARIANTS = (
    "exact",
    "neutral",
    "amplitude_minus_10pct",
    "amplitude_plus_10pct",
    "phase_minus_15deg",
    "phase_plus_15deg",
)


def prior_means_for_variant(
    public_nominal_means: Sequence[complex], variant: str
) -> tuple[complex, ...]:
    """Return predetermined prior means from public profile parameters only.

    This function has no receiver-truth or observation parameter.  The exact
    values are the static channel profile's published nominal coefficients;
    amplitude and phase perturbations are relative to those fixed values.
    """
    if variant not in PRIOR_VARIANTS:
        raise ValueError(f"unknown prior variant: {variant}")
    means = tuple(complex(value) for value in public_nominal_means)
    if not means or any(not np.isfinite(value.real + value.imag) for value in means):
        raise ValueError("public nominal means must be nonempty and finite")
    if variant == "exact":
        return means
    if variant == "neutral":
        return (0j,) * len(means)
    if variant.startswith("amplitude_"):
        factor = 0.9 if variant.endswith("minus_10pct") else 1.1
        return tuple(value * factor for value in means)
    angle = math.radians(-15.0 if variant.endswith("minus_15deg") else 15.0)
    rotation = complex(math.cos(angle), math.sin(angle))
    return tuple(value * rotation for value in means)
