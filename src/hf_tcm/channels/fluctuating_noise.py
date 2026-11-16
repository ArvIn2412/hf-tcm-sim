"""Source-derived AR(1) quadrature noise process from equations (9)-(10)."""

import math
from numbers import Real

import numpy as np
from numpy.typing import NDArray


def fluctuating_noise_coefficients(n: int) -> tuple[float, float]:
    """Return ``alpha`` and ``sigma`` from article equations (10).

    ``n`` is the number of samples in one signal element. ``expm1`` keeps
    ``1 - exp(-8/n)`` accurate when ``n`` is large.
    """
    if type(n) is not int or n <= 0:
        raise ValueError("n must be a positive integer")
    try:
        n_float = float(n)
    except OverflowError as exc:
        raise ValueError("n is outside the supported numeric range") from exc
    if not math.isfinite(n_float):
        raise ValueError("n is outside the supported numeric range")

    alpha = math.exp(-4.0 / n_float)
    sigma = math.sqrt(2.0) * math.sqrt(-math.expm1(-8.0 / n_float)) / n_float
    if not math.isfinite(alpha) or not math.isfinite(sigma):
        raise ValueError("noise coefficients are outside the supported numeric range")
    return alpha, sigma


def _finite_real(value: float, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite real number")
    return result


def generate_fluctuating_noise(
    length: int,
    *,
    n: int,
    rng: np.random.Generator,
    initial_i: float = 0.0,
    initial_q: float = 0.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Generate the article's recursive noise quadratures as two real arrays.

    For each component ``xi`` the recurrence is ``xi[i+1] = alpha*xi[i] +
    sigma*z[i]`` with independent standard-normal innovations. The explicit
    project initial condition is ``I[0] = Q[0] = 0`` by default; equations
    (9)-(10) do not specify initial values. Nonzero finite initial values may
    be supplied for controlled experiments.

    Innovations for the I component are drawn first, followed by innovations
    for Q, from the supplied generator. This function implements only the
    quadrature processes in (9)-(10); it does not build the complete channel
    or the passband signal model.
    """
    if type(length) is not int or length < 1:
        raise ValueError("length must be a positive integer")
    if not isinstance(rng, np.random.Generator):
        raise ValueError("rng must be a numpy.random.Generator")
    i_initial = _finite_real(initial_i, name="initial_i")
    q_initial = _finite_real(initial_q, name="initial_q")
    alpha, sigma = fluctuating_noise_coefficients(n)

    i_innovations = rng.standard_normal(length - 1)
    q_innovations = rng.standard_normal(length - 1)
    in_phase = np.empty(length, dtype=np.float64)
    quadrature = np.empty(length, dtype=np.float64)
    in_phase[0] = i_initial
    quadrature[0] = q_initial

    for index in range(1, length):
        in_phase[index] = alpha * float(in_phase[index - 1]) + sigma * float(
            i_innovations[index - 1]
        )
        quadrature[index] = alpha * float(quadrature[index - 1]) + sigma * float(
            q_innovations[index - 1]
        )
        if not math.isfinite(float(in_phase[index])) or not math.isfinite(float(quadrature[index])):
            raise ValueError("generated noise is outside the supported numeric range")

    return in_phase, quadrature
