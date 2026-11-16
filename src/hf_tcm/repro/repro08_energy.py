"""Explicit dimensionless REPRO-08 sample-domain energy convention.

This is not physical Eb/N0: it is energy per information bit in the discrete
ZOH waveform divided by complex sample-noise variance.
"""

from __future__ import annotations

import math


def discrete_energy_per_information_bit(
    *, samples_per_symbol: int, amplitude: float, information_bits_per_symbol: int = 2
) -> float:
    """Return sum_n |x[n]|^2 / payload bits for rectangular constant symbols."""
    if type(samples_per_symbol) is not int or samples_per_symbol <= 0:
        raise ValueError("samples_per_symbol must be positive")
    if type(information_bits_per_symbol) is not int or information_bits_per_symbol <= 0:
        raise ValueError("information_bits_per_symbol must be positive")
    if isinstance(amplitude, bool) or not math.isfinite(float(amplitude)) or amplitude <= 0:
        raise ValueError("amplitude must be positive and finite")
    return samples_per_symbol * float(amplitude) ** 2 / information_bits_per_symbol


def discrete_gamma_b_db(
    complex_noise_variance: float,
    *,
    samples_per_symbol: int,
    amplitude: float,
    information_bits_per_symbol: int = 2,
) -> float:
    """Compute 10log10(Eb,discrete / E|w|^2); not a physical SNR or Eb/N0."""
    if (
        isinstance(complex_noise_variance, bool)
        or not math.isfinite(float(complex_noise_variance))
        or complex_noise_variance <= 0
    ):
        raise ValueError("complex_noise_variance must be positive and finite")
    eb = discrete_energy_per_information_bit(
        samples_per_symbol=samples_per_symbol,
        amplitude=amplitude,
        information_bits_per_symbol=information_bits_per_symbol,
    )
    return 10.0 * math.log10(eb / float(complex_noise_variance))


def noise_variance_for_discrete_gamma_b_db(
    gamma_b_db: float,
    *,
    samples_per_symbol: int,
    amplitude: float,
    information_bits_per_symbol: int = 2,
) -> float:
    """Invert the discrete convention to complex per-sample noise variance."""
    if isinstance(gamma_b_db, bool) or not math.isfinite(float(gamma_b_db)):
        raise ValueError("gamma_b_db must be finite")
    eb = discrete_energy_per_information_bit(
        samples_per_symbol=samples_per_symbol,
        amplitude=amplitude,
        information_bits_per_symbol=information_bits_per_symbol,
    )
    return eb / (10.0 ** (float(gamma_b_db) / 10.0))
