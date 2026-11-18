"""REPRO-03 path coefficient profiles backed by an explicit Rician K convention."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from hf_tcm.channels.rician import generate_rician_coefficients
from hf_tcm.repro.channel_config import ChannelPathConfig


def generate_path_coefficients(
    length: int,
    path: ChannelPathConfig,
    *,
    fading_mode: str,
    correlation: float,
    seed: int,
    doppler_spread_hz: float = 0.0,
    sample_rate_hz: float = 0.0,
) -> NDArray[np.complex128]:
    """Generate one path from an isolated PCG64 stream.

    Rician K is the ratio between deterministic LOS power and diffuse power.
    The existing helper scales the sum to configured average path power.
    AR(1) is stationary filtered Gaussian correlation, not Jakes/Doppler.
    """
    if type(length) is not int or length < 1:
        raise ValueError("length must be a positive integer")
    if type(seed) is not int or not 0 <= seed <= (1 << 64) - 1:
        raise ValueError("seed must be an integer in [0, 2**64-1]")
    rng = np.random.Generator(np.random.PCG64(seed))
    if fading_mode == "constant":
        if path.constant_coefficient is None:
            raise ValueError("constant fading requires an explicit coefficient")
        return np.full(length, path.constant_coefficient, dtype=np.complex128)
    if fading_mode == "rician_doppler":
        diffuse = gaussian_doppler_process(
            length, doppler_spread_hz=doppler_spread_hz, sample_rate_hz=sample_rate_hz, rng=rng
        )
        regular_power, diffuse_power = rician_power_components(path)
        los = math.sqrt(regular_power) * complex(
            math.cos(path.los_phase_rad), math.sin(path.los_phase_rad)
        )
        result = los + math.sqrt(diffuse_power) * diffuse
        if not np.all(np.isfinite(result)):
            raise ValueError("generated fading coefficients must be finite")
        return np.asarray(result, dtype=np.complex128)
    if fading_mode not in {"rician_static", "rician_ar1"}:
        raise ValueError("unsupported fading_mode")
    mode = "static" if fading_mode == "rician_static" else "approximate_ar1"
    result = generate_rician_coefficients(
        length,
        average_power=path.average_power,
        k_factor=path.k_factor,
        rng=rng,
        mode=mode,
        correlation=correlation,
        los_phase_rad=path.los_phase_rad,
    )
    if not np.all(np.isfinite(result)):
        raise ValueError("generated fading coefficients must be finite")
    return np.asarray(result, dtype=np.complex128)


def rician_power_components(path: ChannelPathConfig) -> tuple[float, float]:
    """Return expected LOS and diffuse powers under the configured K factor."""
    total = float(path.average_power)
    k_value = float(path.k_factor)
    return total * k_value / (k_value + 1.0), total / (k_value + 1.0)


def rician_regular_component(path: ChannelPathConfig) -> complex:
    """Return deterministic LOS mean coefficient for the configured profile."""
    regular_power, _ = rician_power_components(path)
    return math.sqrt(regular_power) * complex(
        math.cos(path.los_phase_rad), math.sin(path.los_phase_rad)
    )


def gaussian_doppler_autocorrelation(lag_seconds: float, doppler_spread_hz: float) -> float:
    """Normalised autocorrelation of the Watterson diffuse component.

    ITU-R F.1487 defines the frequency spread as ``2 * sigma_f`` of a Gaussian
    Doppler spectrum, so ``R(tau) = exp(-2 pi^2 sigma_f^2 tau^2)``.
    """
    sigma_f = float(doppler_spread_hz) / 2.0
    return math.exp(-2.0 * math.pi**2 * sigma_f**2 * float(lag_seconds) ** 2)


def gaussian_doppler_process(
    length: int,
    *,
    doppler_spread_hz: float,
    sample_rate_hz: float,
    rng: np.random.Generator,
) -> NDArray[np.complex128]:
    """Unit-power complex Gaussian process with a Gaussian Doppler spectrum.

    The spectrum is shaped in the frequency domain on a coarse grid of at least
    32 points per Hz of spread (fading is far slower than the sample rate),
    padded by several correlation times to avoid circular wrap, and linearly
    interpolated to the sample grid.
    """
    if type(length) is not int or length < 1:
        raise ValueError("length must be a positive integer")
    spread = float(doppler_spread_hz)
    rate = float(sample_rate_hz)
    if not (math.isfinite(spread) and math.isfinite(rate)) or spread <= 0 or rate <= 0:
        raise ValueError("doppler spread and sample rate must be positive")
    if spread >= rate / 8.0:
        raise ValueError("doppler spread must be below the symbol rate")
    sigma_f = spread / 2.0
    decimation = max(1, int(rate // (64.0 * sigma_f)))
    coarse_rate = rate / decimation
    coarse_length = length // decimation + 2
    padding = int(math.ceil(4.0 * coarse_rate / sigma_f))
    size = 1 << int(math.ceil(math.log2(coarse_length + padding)))
    frequencies = np.fft.fftfreq(size, d=1.0 / coarse_rate)
    shaping = np.exp(-(frequencies**2) / (4.0 * sigma_f**2))
    white = (rng.standard_normal(size) + 1j * rng.standard_normal(size)) / math.sqrt(2.0)
    coarse = np.fft.ifft(white * shaping) * size / math.sqrt(float(np.sum(shaping**2)))
    coarse = coarse[:coarse_length]
    if decimation == 1:
        return np.asarray(coarse[:length], dtype=np.complex128)
    positions = np.arange(length, dtype=np.float64) / decimation
    grid = np.arange(coarse_length, dtype=np.float64)
    fine = np.interp(positions, grid, coarse.real) + 1j * np.interp(positions, grid, coarse.imag)
    return np.asarray(fine, dtype=np.complex128)
