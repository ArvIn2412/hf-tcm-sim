"""Static and explicitly approximate AR(1) Rician fading coefficients."""

import math
from numbers import Real
from typing import Literal

import numpy as np
from numpy.typing import NDArray

FadingMode = Literal["static", "approximate_ar1"]


def _finite_real(value: float, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real number") from exc
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be a finite real number")
    return converted


def generate_rician_coefficients(
    length: int,
    *,
    average_power: float,
    k_factor: float,
    rng: np.random.Generator,
    mode: FadingMode = "static",
    correlation: float = 0.0,
    los_phase_rad: float = 0.0,
) -> NDArray[np.complex128]:
    """Generate Rician coefficients with explicit power, K, phase, and RNG.

    ``approximate_ar1`` correlates only the unit-power diffuse component:
    ``g[t] = rho*g[t-1] + sqrt(1-rho**2)*w[t]``. This is a configurable
    approximation, not the paper's unspecified Markov fading recursion.
    """
    if type(length) is not int or length < 1:
        raise ValueError("length must be a positive integer")
    if not isinstance(rng, np.random.Generator):
        raise ValueError("rng must be a numpy.random.Generator")
    power = _finite_real(average_power, name="average_power")
    k_value = _finite_real(k_factor, name="k_factor")
    rho = _finite_real(correlation, name="correlation")
    phase = _finite_real(los_phase_rad, name="los_phase_rad")
    if power <= 0.0:
        raise ValueError("average_power must be positive")
    if k_value < 0.0:
        raise ValueError("k_factor must be non-negative")
    if mode not in ("static", "approximate_ar1"):
        raise ValueError("mode must be 'static' or 'approximate_ar1'")
    if not 0.0 <= rho < 1.0:
        raise ValueError("correlation must be in [0, 1)")
    if mode == "static" and rho != 0.0:
        raise ValueError("correlation is used only with mode='approximate_ar1'")

    if mode == "static":
        diffuse = np.full(
            length,
            (rng.standard_normal() + 1j * rng.standard_normal()) / math.sqrt(2.0),
            dtype=np.complex128,
        )
    else:
        innovations = (rng.standard_normal(length) + 1j * rng.standard_normal(length)) / math.sqrt(
            2.0
        )
        diffuse = np.empty(length, dtype=np.complex128)
        diffuse[0] = innovations[0]
        innovation_scale = math.sqrt(1.0 - rho**2)
        for index in range(1, length):
            diffuse[index] = rho * diffuse[index - 1] + innovation_scale * innovations[index]

    los_scale = math.sqrt(k_value / (k_value + 1.0))
    diffuse_scale = math.sqrt(1.0 / (k_value + 1.0))
    los = los_scale * complex(math.cos(phase), math.sin(phase))
    coefficients = math.sqrt(power) * (los + diffuse_scale * diffuse)
    if not np.all(np.isfinite(coefficients)):
        raise ValueError("Rician coefficients are outside the supported numeric range")
    return np.asarray(coefficients, dtype=np.complex128)
