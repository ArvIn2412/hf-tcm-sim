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
