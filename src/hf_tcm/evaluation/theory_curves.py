"""Analytic reference curves for the discrete Eb/N0 convention.

Energy convention of the project (ZOH, 8 samples per symbol, complex AWGN with
variance ``sigma^2`` per sample, see ADR-015):

* ``Es = sum_n |x[n]|^2 = 8 A^2`` — energy of one 8PSK element;
* ``N0 = sigma^2`` — one-sided noise spectral density for unit sample spacing;
  the 8-sample matched filter (sum/average) gives the per-symbol SNR
  ``|A|^2 / (sigma^2 / 8) = Es / N0``;
* TCM R=2/3 with 8PSK carries 2 information bits per element, so
  ``Eb = Es / 2`` and ``gamma_b,d = Eb / sigma^2`` *is* ``Eb/N0``.

The functions below give textbook references used to validate that claim
(``hf_tcm.evaluation.ebn0_validation``) and to annotate BER plots.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
from numpy.typing import NDArray

INFORMATION_BITS_PER_TCM_SYMBOL = 2
SAMPLES_PER_SYMBOL = 8


def db_to_linear(value_db: float) -> float:
    return 10.0 ** (float(value_db) / 10.0)


def q_function(x: float) -> float:
    """Gaussian tail probability Q(x) = P(N(0,1) > x)."""
    return 0.5 * math.erfc(float(x) / math.sqrt(2.0))


def es_n0_from_amplitude(amplitude: float, noise_complex_variance: float) -> float:
    """Linear Es/N0 of one 8-sample element under the project convention."""
    if amplitude <= 0 or noise_complex_variance <= 0:
        raise ValueError("amplitude and noise variance must be positive")
    return SAMPLES_PER_SYMBOL * amplitude**2 / noise_complex_variance


def mpsk_symbol_error_probability(es_n0: float, order: int = 8, points: int = 4001) -> float:
    """Exact M-PSK SER in AWGN (Craig's integral), linear ``es_n0``.

    ``P_s = (1/pi) * int_0^{(M-1)pi/M} exp(-Es/N0 * sin^2(pi/M) / sin^2(t)) dt``
    """
    if order < 2 or es_n0 < 0:
        raise ValueError("order must be >= 2 and es_n0 non-negative")
    upper = (order - 1) * math.pi / order
    theta = np.linspace(1e-12, upper, points)
    integrand = np.exp(-es_n0 * math.sin(math.pi / order) ** 2 / np.sin(theta) ** 2)
    return float(np.trapezoid(integrand, theta) / math.pi)


def mpsk_symbol_error_approximation(es_n0: float, order: int = 8) -> float:
    """High-SNR nearest-neighbour approximation ``2 Q(sqrt(2 Es/N0) sin(pi/M))``."""
    return 2.0 * q_function(math.sqrt(2.0 * es_n0) * math.sin(math.pi / order))


def qpsk_bit_error_probability(eb_n0: float) -> float:
    """Uncoded Gray QPSK/BPSK BER ``Q(sqrt(2 Eb/N0))`` — same 2 bits/element rate."""
    return q_function(math.sqrt(2.0 * eb_n0))


def tcm4_8psk_dominant_term_ber(eb_n0: float) -> float:
    """Dominant-term estimate for the 4-state 8PSK TCM with soft decisions.

    The free distance of the 4-state Ungerboeck code is set by parallel
    transitions (antipodal points, d^2 = 4 Es). A parallel error flips the
    uncoded information bit only, i.e. one of two bits:
    ``Pb ~ 1/2 * Q(sqrt(d^2 / (2 N0))) = 1/2 * Q(sqrt(4 Eb/N0))``.
    Asymptotic (high Eb/N0) reference only; it ignores other error events.
    """
    return 0.5 * q_function(math.sqrt(4.0 * eb_n0))


def reference_table(eb_n0_db: Iterable[float]) -> list[dict[str, float]]:
    """Reference values on an Eb/N0 grid (dB) for plots and reports."""
    rows = []
    for value in eb_n0_db:
        eb_n0 = db_to_linear(value)
        es_n0_8psk_uncoded = 2.0 * eb_n0  # same element energy, 2 info bits/element
        rows.append(
            {
                "eb_n0_db": float(value),
                "qpsk_uncoded_ber": qpsk_bit_error_probability(eb_n0),
                "tcm4_8psk_soft_dominant_ber": tcm4_8psk_dominant_term_ber(eb_n0),
                "8psk_ser_at_same_element_energy": mpsk_symbol_error_probability(
                    es_n0_8psk_uncoded
                ),
            }
        )
    return rows


def wilson_interval(errors: int, trials: int, z: float = 1.959963984540054) -> NDArray[np.float64]:
    """Wilson score interval for a binomial proportion."""
    if trials <= 0 or not 0 <= errors <= trials:
        raise ValueError("invalid binomial counts")
    p = errors / trials
    denominator = 1.0 + z**2 / trials
    centre = (p + z**2 / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2)) / denominator
    return np.asarray([max(0.0, centre - half), min(1.0, centre + half)], dtype=np.float64)
