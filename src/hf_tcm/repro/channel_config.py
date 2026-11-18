"""Strict REPRO-03 channel configuration; all unspecified article values stay explicit."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from numbers import Real
from typing import Any, Literal

CHANNEL_SCHEMA_VERSION = "repro03-channel-v1"
FADING_MODES = {"constant", "rician_static", "rician_ar1", "rician_doppler"}
NOISE_MODELS = {"none", "complex_awgn_sample_domain"}


def _finite(value: object, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    converted = float(value)
    if not math.isfinite(converted) or (minimum is not None and converted < minimum):
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return converted


def _seed(value: object, name: str) -> int:
    if type(value) is not int or not 0 <= value <= (1 << 64) - 1:
        raise ValueError(f"{name} must be an integer in [0, 2**64-1]")
    return value


@dataclass(frozen=True, slots=True)
class ChannelPathConfig:
    """One path: integer sample delay, average power, K and LOS phase."""

    delay_samples: int
    average_power: float
    k_factor: float
    los_phase_rad: float = 0.0
    constant_coefficient: complex | None = None

    def __post_init__(self) -> None:
        if type(self.delay_samples) is not int or self.delay_samples < 0:
            raise ValueError("delay_samples must be a non-negative integer sample delay")
        _finite(self.average_power, "average_power", minimum=0.0)
        if self.average_power == 0:
            raise ValueError("average_power must be positive")
        _finite(self.k_factor, "k_factor", minimum=0.0)
        _finite(self.los_phase_rad, "los_phase_rad")
        if self.constant_coefficient is not None:
            try:
                coefficient = complex(self.constant_coefficient)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("constant_coefficient must be a finite complex number") from exc
            if not math.isfinite(coefficient.real) or not math.isfinite(coefficient.imag):
                raise ValueError("constant_coefficient must be a finite complex number")
            if self.k_factor != 0.0:
                raise ValueError("constant-coefficient paths must set k_factor=0")
            if not math.isclose(
                abs(coefficient) ** 2,
                float(self.average_power),
                rel_tol=1e-12,
                abs_tol=1e-15,
            ):
                raise ValueError("average_power must equal |constant_coefficient|^2")
            object.__setattr__(self, "constant_coefficient", coefficient)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> ChannelPathConfig:
        if not isinstance(values, dict):
            raise ValueError("each path must be a JSON object")
        allowed = {field for field in cls.__dataclass_fields__}
        extra = set(values) - allowed
        if extra:
            raise ValueError(f"unexpected path field: {sorted(extra)[0]}")
        data = dict(values)
        coefficient = data.get("constant_coefficient")
        if coefficient is not None:
            if not isinstance(coefficient, (list, tuple)) or len(coefficient) != 2:
                raise ValueError("constant_coefficient must be [real, imag]")
            data["constant_coefficient"] = complex(float(coefficient[0]), float(coefficient[1]))
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValueError(f"invalid path configuration: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.constant_coefficient is not None:
            data["constant_coefficient"] = [
                float(self.constant_coefficient.real),
                float(self.constant_coefficient.imag),
            ]
        return data


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    """Versioned discrete complex-baseband channel configuration."""

    profile_id: str
    paths: tuple[ChannelPathConfig, ...]
    fading_mode: Literal["constant", "rician_static", "rician_ar1", "rician_doppler"]
    noise_model: Literal["none", "complex_awgn_sample_domain"]
    noise_complex_variance: float
    fading_seed: int
    noise_seed: int
    correlation: float = 0.0
    boundary_policy: Literal["zero_extension"] = "zero_extension"
    output_length_policy: Literal["tx_plus_max_delay"] = "tx_plus_max_delay"
    rng_algorithm: Literal["numpy.PCG64"] = "numpy.PCG64"
    reveal_noise_variance: bool = False
    schema_version: str = CHANNEL_SCHEMA_VERSION
    # Only for fading_mode="rician_doppler" (Watterson/ITU-R F.1487 Gaussian
    # Doppler spectrum). Two-sided spread 2*sigma_f in Hz; the sample rate is
    # 8 * symbol_rate_baud.
    doppler_spread_hz: float = 0.0
    symbol_rate_baud: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id.strip():
            raise ValueError("profile_id must be a nonempty string")
        paths = tuple(self.paths)
        object.__setattr__(self, "paths", paths)
        if not paths or any(not isinstance(path, ChannelPathConfig) for path in paths):
            raise ValueError("paths must contain at least one ChannelPathConfig")
        if self.fading_mode not in FADING_MODES:
            raise ValueError(f"fading_mode must be one of {sorted(FADING_MODES)}")
        if self.noise_model not in NOISE_MODELS:
            raise ValueError(f"noise_model must be one of {sorted(NOISE_MODELS)}")
        if self.fading_mode == "constant" and any(
            path.constant_coefficient is None for path in paths
        ):
            raise ValueError("constant fading mode requires constant_coefficient for every path")
        if self.fading_mode != "constant" and any(
            path.constant_coefficient is not None for path in paths
        ):
            raise ValueError("constant_coefficient is only valid with fading_mode='constant'")
        variance = _finite(self.noise_complex_variance, "noise_complex_variance", minimum=0.0)
        if self.noise_model == "none" and variance != 0.0:
            raise ValueError("noise_complex_variance must be 0 when noise_model='none'")
        if self.noise_model == "complex_awgn_sample_domain" and variance <= 0.0:
            raise ValueError("sample-domain AWGN requires positive complex variance")
        rho = _finite(self.correlation, "correlation", minimum=0.0)
        if self.fading_mode == "rician_ar1":
            if not 0.0 <= rho < 1.0:
                raise ValueError("AR(1) correlation must be in [0, 1)")
        elif rho != 0.0:
            raise ValueError("correlation is only valid for fading_mode='rician_ar1'")
        spread = _finite(self.doppler_spread_hz, "doppler_spread_hz", minimum=0.0)
        rate = _finite(self.symbol_rate_baud, "symbol_rate_baud", minimum=0.0)
        if self.fading_mode == "rician_doppler":
            if spread <= 0.0 or rate <= 0.0:
                raise ValueError(
                    "rician_doppler requires positive doppler_spread_hz and symbol_rate"
                )
            if spread >= rate:
                raise ValueError("doppler_spread_hz must be below the symbol rate")
        elif spread != 0.0 or rate != 0.0:
            raise ValueError("doppler parameters are only valid for fading_mode='rician_doppler'")
        _seed(self.fading_seed, "fading_seed")
        _seed(self.noise_seed, "noise_seed")
        if self.boundary_policy != "zero_extension":
            raise ValueError("boundary_policy must be 'zero_extension'")
        if self.output_length_policy != "tx_plus_max_delay":
            raise ValueError("output_length_policy must be 'tx_plus_max_delay'")
        if self.rng_algorithm != "numpy.PCG64":
            raise ValueError("rng_algorithm must be 'numpy.PCG64'")
        if type(self.reveal_noise_variance) is not bool:
            raise ValueError("reveal_noise_variance must be boolean")
        if self.schema_version != CHANNEL_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {CHANNEL_SCHEMA_VERSION!r}")

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> ChannelConfig:
        if not isinstance(values, dict):
            raise ValueError("channel config must be a JSON object")
        allowed = set(cls.__dataclass_fields__)
        extra = set(values) - allowed
        if extra:
            raise ValueError(f"unexpected channel config field: {sorted(extra)[0]}")
        data = dict(values)
        if "paths" in data and isinstance(data["paths"], list):
            data["paths"] = tuple(ChannelPathConfig.from_dict(item) for item in data["paths"])
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValueError(f"invalid channel configuration: {exc}") from exc

    @classmethod
    def from_json(cls, text: str) -> ChannelConfig:
        try:
            values = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("channel configuration is not valid JSON") from exc
        return cls.from_dict(values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "paths": [path.to_dict() for path in self.paths],
            "fading_mode": self.fading_mode,
            "correlation": self.correlation,
            "noise_model": self.noise_model,
            "noise_complex_variance": self.noise_complex_variance,
            "fading_seed": self.fading_seed,
            "noise_seed": self.noise_seed,
            "boundary_policy": self.boundary_policy,
            "output_length_policy": self.output_length_policy,
            "rng_algorithm": self.rng_algorithm,
            "reveal_noise_variance": self.reveal_noise_variance,
        } | (
            {
                "doppler_spread_hz": self.doppler_spread_hz,
                "symbol_rate_baud": self.symbol_rate_baud,
            }
            if self.fading_mode == "rician_doppler"
            else {}
        )


def identity_profile() -> ChannelConfig:
    """Engineering identity control, not a source-defined channel setting."""
    return ChannelConfig(
        profile_id="identity_project_v1",
        paths=(ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),),
        fading_mode="constant",
        noise_model="none",
        noise_complex_variance=0.0,
        fading_seed=1,
        noise_seed=2,
    )


def single_path_rician_awgn_profile() -> ChannelConfig:
    """Explicit project reconstruction settings; none of these are article defaults."""
    return ChannelConfig(
        profile_id="single_path_rician_awgn_project_v1",
        paths=(ChannelPathConfig(0, 1.0, 3.0, 0.0),),
        fading_mode="rician_ar1",
        correlation=0.98,
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=0.02,
        fading_seed=3001,
        noise_seed=4001,
    )


def multipath_rician_awgn_profile() -> ChannelConfig:
    """Two-ray integer-delay project reconstruction; not a validated HF propagation law."""
    return ChannelConfig(
        profile_id="multipath_rician_awgn_project_v1",
        paths=(
            ChannelPathConfig(0, 1.0, 4.0, 0.0),
            ChannelPathConfig(3, 0.25, 1.0, 0.7),
        ),
        fading_mode="rician_ar1",
        correlation=0.98,
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=0.02,
        fading_seed=3002,
        noise_seed=4002,
    )


def s1_structure_reconstruction_profile(
    *,
    paths: tuple[ChannelPathConfig, ...],
    fading_mode: Literal["constant", "rician_static", "rician_ar1"],
    noise_model: Literal["none", "complex_awgn_sample_domain"],
    noise_complex_variance: float,
    fading_seed: int,
    noise_seed: int,
    correlation: float = 0.0,
) -> ChannelConfig:
    """Use S1 structure with caller-supplied non-source numeric parameters."""
    return ChannelConfig(
        profile_id="s1_equation_structure_project_reconstruction_v1",
        paths=paths,
        fading_mode=fading_mode,
        correlation=correlation,
        noise_model=noise_model,
        noise_complex_variance=noise_complex_variance,
        fading_seed=fading_seed,
        noise_seed=noise_seed,
    )


# ITU-R F.1487 (formerly F.520) Doppler spreads for HF test channels. The ITU
# differential delays (0.5/1/2 ms) are NOT reproduced: the metric-isolation
# clean-tail combiner supports integer delays below 8 samples only, so the
# second path uses the project delay of 3 samples (3/8 element).
ITU_HF_DOPPLER_SPREAD_HZ = {"good": 0.1, "moderate": 0.5, "poor": 1.0, "flutter": 10.0}


def itu_hf_doppler_profile(
    condition: str,
    *,
    noise_complex_variance: float,
    fading_seed: int,
    noise_seed: int,
    symbol_rate_baud: float = 2400.0,
    second_path_delay_samples: int = 3,
) -> ChannelConfig:
    """Two equal-power Rayleigh paths with ITU HF Doppler spread (Watterson model)."""
    if condition not in ITU_HF_DOPPLER_SPREAD_HZ:
        raise ValueError(f"condition must be one of {sorted(ITU_HF_DOPPLER_SPREAD_HZ)}")
    return ChannelConfig(
        profile_id=f"itu_hf_{condition}_doppler_project_delay",
        paths=(
            ChannelPathConfig(0, 0.5, 0.0, 0.0),
            ChannelPathConfig(second_path_delay_samples, 0.5, 0.0, 0.0),
        ),
        fading_mode="rician_doppler",
        noise_model="complex_awgn_sample_domain" if noise_complex_variance > 0 else "none",
        noise_complex_variance=noise_complex_variance,
        fading_seed=fading_seed,
        noise_seed=noise_seed,
        reveal_noise_variance=True,
        doppler_spread_hz=ITU_HF_DOPPLER_SPREAD_HZ[condition],
        symbol_rate_baud=symbol_rate_baud,
    )
