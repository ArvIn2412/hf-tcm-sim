"""Complex circular AWGN for normalized symbol-rate experiments."""

import math
from numbers import Real

import numpy as np
from numpy.typing import NDArray


def _positive_real(value: float, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite positive real number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite positive real number") from exc
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be a finite positive real number")
    return result


def awgn_noise_variance(
    ebn0_db: float,
    *,
    bits_per_symbol: float = 2.0,
    energy_per_symbol: float = 1.0,
) -> float:
    """Return complex noise power ``N0 = Es / (k * 10**(Eb/N0/10))``."""
    if isinstance(ebn0_db, bool) or not isinstance(ebn0_db, Real):
        raise ValueError("ebn0_db must be a finite real number")
    ebn0 = float(ebn0_db)
    if not math.isfinite(ebn0):
        raise ValueError("ebn0_db must be a finite real number")
    bits = _positive_real(bits_per_symbol, name="bits_per_symbol")
    energy = _positive_real(energy_per_symbol, name="energy_per_symbol")
    try:
        gamma_b = 10.0 ** (ebn0 / 10.0)
    except OverflowError as exc:
        raise ValueError("ebn0_db is outside the supported numeric range") from exc
    if gamma_b == 0.0 or not math.isfinite(gamma_b):
        raise ValueError("ebn0_db is outside the supported numeric range")
    n0 = energy / (bits * gamma_b)
    if not math.isfinite(n0) or n0 <= 0.0:
        raise ValueError("ebn0_db produces an unsupported noise variance")
    return n0


def add_awgn(
    samples: NDArray[np.complexfloating],
    ebn0_db: float,
    *,
    rng: np.random.Generator,
    bits_per_symbol: float = 2.0,
    energy_per_symbol: float = 1.0,
) -> NDArray[np.complex128]:
    """Add reproducible circular complex AWGN to a 1-D symbol sequence.

    The real and imaginary noise components each have variance ``N0/2``.
    A generator must be supplied so the random stream is always explicit.
    """
    if not isinstance(rng, np.random.Generator):
        raise ValueError("rng must be a numpy.random.Generator")
    try:
        signal = np.asarray(samples, dtype=np.complex128)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("samples must be a finite 1-D numeric array") from exc
    if signal.ndim != 1 or not np.all(np.isfinite(signal)):
        raise ValueError("samples must be a finite 1-D numeric array")
    n0 = awgn_noise_variance(
        ebn0_db,
        bits_per_symbol=bits_per_symbol,
        energy_per_symbol=energy_per_symbol,
    )
    scale = math.sqrt(n0 / 2.0)
    noise = scale * (rng.standard_normal(signal.shape) + 1j * rng.standard_normal(signal.shape))
    return np.asarray(signal + noise, dtype=np.complex128)
