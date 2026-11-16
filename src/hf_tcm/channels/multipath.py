"""Configurable integer-delay Rician multipath channel with separate truth."""

import math
from dataclasses import dataclass
from numbers import Real

import numpy as np
from numpy.typing import NDArray

from hf_tcm.channels.rician import FadingMode, generate_rician_coefficients


@dataclass(frozen=True, slots=True)
class PathSpec:
    """One path with delay in samples and average power relative to Es=1."""

    delay_samples: int
    average_power: float
    k_factor: float
    los_phase_rad: float = 0.0

    def __post_init__(self) -> None:
        if type(self.delay_samples) is not int or self.delay_samples < 0:
            raise ValueError("delay_samples must be a non-negative integer")
        power = _real(self.average_power, name="average_power")
        k_value = _real(self.k_factor, name="k_factor")
        _real(self.los_phase_rad, name="los_phase_rad")
        if power <= 0.0:
            raise ValueError("average_power must be positive")
        if k_value < 0.0:
            raise ValueError("k_factor must be non-negative")


@dataclass(frozen=True, slots=True)
class MultipathConfig:
    """Path parameters and fading mode for an explicitly configured scenario."""

    paths: tuple[PathSpec, ...]
    fading_mode: FadingMode = "static"
    correlation: float = 0.0

    def __post_init__(self) -> None:
        paths = tuple(self.paths)
        object.__setattr__(self, "paths", paths)
        if not paths or any(not isinstance(path, PathSpec) for path in paths):
            raise ValueError("paths must contain at least one PathSpec")
        if self.fading_mode not in ("static", "approximate_ar1"):
            raise ValueError("fading_mode must be 'static' or 'approximate_ar1'")
        rho = _real(self.correlation, name="correlation")
        if not 0.0 <= rho < 1.0:
            raise ValueError("correlation must be in [0, 1)")
        if self.fading_mode == "static" and rho != 0.0:
            raise ValueError("correlation is used only with fading_mode='approximate_ar1'")

    @property
    def model_profile(self) -> str:
        """Return an explicit approximate model label for output metadata."""
        if self.fading_mode == "static":
            return "approximate_static_rician_multipath"
        return "approximate_ar1_rician_multipath"


@dataclass(frozen=True, slots=True)
class ChannelTruth:
    """Diagnostic-only channel coefficients and their configured parameters."""

    path_delays: tuple[int, ...]
    average_powers: tuple[float, ...]
    k_factors: tuple[float, ...]
    coefficients: NDArray[np.complex128]
    fading_mode: FadingMode
    correlation: float
    model_profile: str


@dataclass(frozen=True, slots=True)
class ChannelOutput:
    """Received samples and diagnostic truth kept as separate fields."""

    received: NDArray[np.complex128]
    truth: ChannelTruth


def _real(value: float, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real number") from exc
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be a finite real number")
    return converted


def apply_multipath(
    samples: NDArray[np.complexfloating],
    config: MultipathConfig,
    *,
    rng: np.random.Generator,
) -> ChannelOutput:
    """Apply ``sum_l h[l,t] * x[t-delay_l]`` with zero-padded delayed tails.

    AWGN is intentionally separate and can be added with the M2 channel
    function. ``truth`` is returned separately from samples for diagnostics.
    """
    if not isinstance(config, MultipathConfig):
        raise ValueError("config must be a MultipathConfig")
    if not isinstance(rng, np.random.Generator):
        raise ValueError("rng must be a numpy.random.Generator")
    try:
        signal = np.asarray(samples, dtype=np.complex128)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("samples must be a finite 1-D numeric array") from exc
    if signal.ndim != 1 or len(signal) == 0 or not np.all(np.isfinite(signal)):
        raise ValueError("samples must be a nonempty finite 1-D numeric array")

    output_length = len(signal) + max(path.delay_samples for path in config.paths)
    coefficients = np.vstack(
        [
            generate_rician_coefficients(
                output_length,
                average_power=path.average_power,
                k_factor=path.k_factor,
                rng=rng,
                mode=config.fading_mode,
                correlation=config.correlation,
                los_phase_rad=path.los_phase_rad,
            )
            for path in config.paths
        ]
    )
    received = np.zeros(output_length, dtype=np.complex128)
    for index, path in enumerate(config.paths):
        start = path.delay_samples
        end = start + len(signal)
        received[start:end] += coefficients[index, start:end] * signal
    truth = ChannelTruth(
        path_delays=tuple(path.delay_samples for path in config.paths),
        average_powers=tuple(path.average_power for path in config.paths),
        k_factors=tuple(path.k_factor for path in config.paths),
        coefficients=coefficients,
        fading_mode=config.fading_mode,
        correlation=config.correlation,
        model_profile=config.model_profile,
    )
    return ChannelOutput(received=received, truth=truth)
