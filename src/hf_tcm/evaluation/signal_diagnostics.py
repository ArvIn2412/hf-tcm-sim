"""Pure sample-domain energy and covariance diagnostics.

These helpers measure explicit arrays. They do not assign physical units,
generate noise, or define an SNR convention.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray

ComplexVector = NDArray[np.complex128]
FloatVector = NDArray[np.float64]


def _complex_vector(values: ArrayLike, *, name: str) -> ComplexVector:
    try:
        raw = np.asarray(values)
        if not np.iscomplexobj(raw):
            raise ValueError
        result = np.asarray(raw, dtype=np.complex128)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite nonempty 1-D complex array") from exc
    if result.ndim != 1 or result.size == 0:
        raise ValueError(f"{name} must be a finite nonempty 1-D complex array")
    if not np.all(np.isfinite(result.real)) or not np.all(np.isfinite(result.imag)):
        raise ValueError(f"{name} must be a finite nonempty 1-D complex array")
    return result


def complex_sample_energy(samples: ArrayLike) -> float:
    """Return measured discrete energy ``sum(abs(samples)**2)`` in sample units."""
    values = _complex_vector(samples, name="samples")
    with np.errstate(over="ignore", invalid="ignore"):
        energy = float(np.sum(values.real**2 + values.imag**2, dtype=np.float64))
    if not math.isfinite(energy):
        raise ValueError("sample energy is outside the supported numeric range")
    return energy


def discrete_block_energies(samples: ArrayLike, *, samples_per_block: int) -> FloatVector:
    """Return exact sample-sum energies for complete equal-size blocks.

    The input length must be divisible by the explicitly supplied block size;
    no incomplete block is padded or discarded.
    """
    if type(samples_per_block) is not int or samples_per_block < 1:
        raise ValueError("samples_per_block must be a positive integer")
    values = _complex_vector(samples, name="samples")
    if values.size % samples_per_block:
        raise ValueError("samples length must be divisible by samples_per_block")
    blocks = values.reshape(-1, samples_per_block)
    with np.errstate(over="ignore", invalid="ignore"):
        energies = np.sum(blocks.real**2 + blocks.imag**2, axis=1, dtype=np.float64)
    if not np.all(np.isfinite(energies)):
        raise ValueError("block energy is outside the supported numeric range")
    result = np.array(energies, dtype=np.float64, copy=True)
    result.setflags(write=False)
    return result


def complex_sample_mean(samples: ArrayLike) -> complex:
    """Return the deterministic arithmetic mean of explicit complex samples."""
    values = _complex_vector(samples, name="samples")
    with np.errstate(over="ignore", invalid="ignore"):
        mean = complex(np.mean(values, dtype=np.complex128))
    if not math.isfinite(mean.real) or not math.isfinite(mean.imag):
        raise ValueError("sample mean is outside the supported numeric range")
    return mean


def empirical_component_powers(samples: ArrayLike) -> tuple[float, float, float]:
    """Return `(complex, real, imag)` mean-square powers about zero.

    These are measured powers, not centered sample variances and not estimates
    of a physical noise parameter.
    """
    values = _complex_vector(samples, name="samples")
    with np.errstate(over="ignore", invalid="ignore"):
        real_power = float(np.mean(values.real**2, dtype=np.float64))
        imag_power = float(np.mean(values.imag**2, dtype=np.float64))
        complex_power = real_power + imag_power
    result = (complex_power, real_power, imag_power)
    if not all(math.isfinite(value) for value in result):
        raise ValueError("empirical power is outside the supported numeric range")
    return result


def mean_complex_power_from_covariance(covariance: ArrayLike) -> float:
    """Return `E[|mean(n)|**2]` from an explicit complex covariance matrix.

    For an `N`-sample vector with covariance `C = E[(n-E[n])(n-E[n])^H]`,
    this computes `1^H C 1 / N**2`. It validates shape, finiteness, and
    Hermitian symmetry but makes no independence or distribution assumption.
    """
    try:
        matrix = np.asarray(covariance, dtype=np.complex128)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("covariance must be a finite nonempty square matrix") from exc
    if (
        matrix.ndim != 2
        or matrix.shape[0] == 0
        or matrix.shape[0] != matrix.shape[1]
        or not np.all(np.isfinite(matrix.real))
        or not np.all(np.isfinite(matrix.imag))
    ):
        raise ValueError("covariance must be a finite nonempty square matrix")
    if not np.array_equal(matrix, matrix.conjugate().T):
        raise ValueError("covariance must be Hermitian")
    count = matrix.shape[0]
    ones = np.ones(count, dtype=np.complex128)
    with np.errstate(over="ignore", invalid="ignore"):
        quadratic = np.vdot(ones, matrix @ ones) / (count * count)
    value = float(quadratic.real)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError("covariance implies an invalid mean complex power")
    return value
