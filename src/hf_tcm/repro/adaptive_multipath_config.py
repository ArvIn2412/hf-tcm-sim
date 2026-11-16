"""Strict, truth-free configuration for REPRO-06C adaptive multipath decoding."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Literal

from hf_tcm.repro.encoder import TerminationPolicy
from hf_tcm.repro.identifiers import ENCODER_ID, MAPPING_ID

SCHEMA = "repro06c-survivor-adaptive-v1"
ChannelMode = Literal["unknown_static", "slow_fading_rician_ar1", "rician_ar1"]


@dataclass(frozen=True, slots=True)
class AdaptivePathConfig:
    delay_samples: int
    prior_mean: complex | None = None
    prior_variance: float | None = None
    average_power: float | None = None
    k_factor: float | None = None
    los_phase_rad: float = 0.0

    def __post_init__(self) -> None:
        if type(self.delay_samples) is not int or self.delay_samples < 0:
            raise ValueError("delay_samples must be a non-negative integer")
        if self.prior_mean is not None:
            mean = complex(self.prior_mean)
            if not math.isfinite(mean.real) or not math.isfinite(mean.imag):
                raise ValueError("prior_mean must be finite")
            object.__setattr__(self, "prior_mean", mean)
        static = self.prior_mean is not None or self.prior_variance is not None
        rician = self.average_power is not None or self.k_factor is not None
        if static == rician:
            raise ValueError(
                "provide either prior_mean and prior_variance or Rician public parameters"
            )
        if static:
            if self.prior_mean is None or self.prior_variance is None:
                raise ValueError("unknown-static paths require prior_mean and prior_variance")
            if not math.isfinite(self.prior_variance) or self.prior_variance <= 0:
                raise ValueError("prior_variance must be positive and finite")
        else:
            if self.average_power is None or self.k_factor is None:
                raise ValueError("Rician public parameters require average_power and k_factor")
            if not math.isfinite(self.average_power) or self.average_power <= 0:
                raise ValueError("average_power must be positive and finite")
            if not math.isfinite(self.k_factor) or self.k_factor < 0:
                raise ValueError("k_factor must be non-negative and finite")
            if not math.isfinite(self.los_phase_rad):
                raise ValueError("los_phase_rad must be finite")

    @property
    def public_mean(self) -> complex:
        if self.average_power is None or self.k_factor is None:
            return complex(self.prior_mean or 0j)
        return math.sqrt(self.average_power * self.k_factor / (self.k_factor + 1)) * complex(
            math.cos(self.los_phase_rad), math.sin(self.los_phase_rad)
        )

    @property
    def diffuse_variance(self) -> float:
        if self.average_power is None or self.k_factor is None:
            return float(self.prior_variance or 0.0)
        return self.average_power / (self.k_factor + 1)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.prior_mean is not None:
            result["prior_mean"] = [self.prior_mean.real, self.prior_mean.imag]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdaptivePathConfig:
        if not isinstance(data, dict) or set(data) - set(cls.__dataclass_fields__):
            raise ValueError("invalid adaptive path config fields")
        values = dict(data)
        mean = values.get("prior_mean")
        if isinstance(mean, (list, tuple)) and len(mean) == 2:
            values["prior_mean"] = complex(float(mean[0]), float(mean[1]))
        return cls(**values)


@dataclass(frozen=True, slots=True)
class AdaptiveMultipathReceiverConfig:
    expected_symbol_count: int
    paths: tuple[AdaptivePathConfig, ...]
    channel_mode: ChannelMode
    observation_noise_variance: float
    correlation: float = 1.0
    forgetting_factor: float = 1.0
    covariance_floor: float = 1e-12
    numerical_tolerance: float = 1e-10
    metric_profile: Literal["euclidean", "squared_euclidean"] = "squared_euclidean"
    decoder_mode: Literal["full_frame", "finite_depth"] = "finite_depth"
    traceback_depth: int | None = 20
    initial_state: tuple[int, int] = (0, 0)
    termination_policy: TerminationPolicy = "none"
    amplitude: float = 1.0
    phase_offset_rad: float = 0.0
    phase_increment_rad: float = math.pi / 4
    samples_per_symbol: int = 8
    trace_output_mode: Literal["compact", "full"] = "compact"
    encoder_id: str = ENCODER_ID
    mapping_id: str = MAPPING_ID
    profile_id: str = "repro06c_adaptive_multipath_psp_v1"
    schema_version: str = SCHEMA

    def __post_init__(self) -> None:
        if type(self.expected_symbol_count) is not int or self.expected_symbol_count < 1:
            raise ValueError("expected_symbol_count must be a positive integer")
        if (
            not isinstance(self.paths, tuple)
            or not self.paths
            or any(not isinstance(path, AdaptivePathConfig) for path in self.paths)
        ):
            raise ValueError("paths must be a nonempty tuple of AdaptivePathConfig")
        if self.channel_mode not in {"unknown_static", "slow_fading_rician_ar1", "rician_ar1"}:
            raise ValueError("unsupported channel_mode")
        if any(
            (path.average_power is None) != (self.channel_mode == "unknown_static")
            for path in self.paths
        ):
            raise ValueError("path priors must match the selected channel_mode")
        if (
            type(self.observation_noise_variance) not in (float, int)
            or not math.isfinite(self.observation_noise_variance)
            or self.observation_noise_variance < 0
        ):
            raise ValueError("observation_noise_variance must be finite and non-negative")
        if not 0 <= self.correlation <= 1 or (
            self.channel_mode != "unknown_static" and self.correlation >= 1
        ):
            raise ValueError("rho must be in [0, 1) for AR(1) profiles")
        if self.channel_mode == "slow_fading_rician_ar1" and self.correlation < 0.98:
            raise ValueError("slow_fading_rician_ar1 requires rho >= 0.98")
        for name, value in (
            ("forgetting_factor", self.forgetting_factor),
            ("covariance_floor", self.covariance_floor),
            ("numerical_tolerance", self.numerical_tolerance),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        if self.forgetting_factor > 1:
            raise ValueError("forgetting_factor must be <= 1")
        if self.metric_profile not in {"euclidean", "squared_euclidean"}:
            raise ValueError("unsupported metric_profile")
        if self.decoder_mode == "finite_depth":
            if type(self.traceback_depth) is not int or self.traceback_depth < 1:
                raise ValueError("finite_depth requires positive traceback_depth")
        elif self.decoder_mode != "full_frame" or self.traceback_depth is not None:
            raise ValueError("full_frame requires traceback_depth=None")
        if self.initial_state not in {(0, 0), (1, 0), (0, 1), (1, 1)}:
            raise ValueError("invalid Encoder A initial_state")
        if self.termination_policy not in {"none", "zero_tail_2"}:
            raise ValueError("unsupported termination_policy")
        if self.samples_per_symbol != 8 or not math.isclose(
            self.phase_increment_rad, math.pi / 4, abs_tol=1e-15
        ):
            raise ValueError("REPRO-06C requires 8 samples/symbol and phase increment pi/4")
        if (
            not math.isfinite(self.amplitude)
            or self.amplitude <= 0
            or not math.isfinite(self.phase_offset_rad)
        ):
            raise ValueError("modulation parameters must be finite with positive amplitude")
        if self.trace_output_mode not in {"compact", "full"}:
            raise ValueError("trace_output_mode must be compact or full")
        if self.encoder_id != ENCODER_ID or self.mapping_id != MAPPING_ID:
            raise ValueError("REPRO-06C requires Encoder A and the REPRO-02 mapping")
        if self.schema_version != SCHEMA:
            raise ValueError("unsupported REPRO-06C schema")
        if (max(path.delay_samples for path in self.paths) + 7) // 8 > 2:
            raise ValueError("channel delay requires more than 2 previous symbols")

    @property
    def delays_samples(self) -> tuple[int, ...]:
        return tuple(path.delay_samples for path in self.paths)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["paths"] = [path.to_dict() for path in self.paths]
        result["initial_state"] = list(self.initial_state)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdaptiveMultipathReceiverConfig:
        if not isinstance(data, dict):
            raise ValueError("receiver config must be a JSON object")
        extra = set(data) - set(cls.__dataclass_fields__)
        if extra:
            raise ValueError(f"unexpected adaptive receiver config field: {sorted(extra)[0]}")
        values = dict(data)
        if "paths" in values:
            values["paths"] = tuple(
                p if isinstance(p, AdaptivePathConfig) else AdaptivePathConfig.from_dict(p)
                for p in values["paths"]
            )
        if "initial_state" in values:
            values["initial_state"] = tuple(values["initial_state"])
        return cls(**values)

    @classmethod
    def from_json(cls, text: str) -> AdaptiveMultipathReceiverConfig:
        try:
            return cls.from_dict(json.loads(text))
        except json.JSONDecodeError as exc:
            raise ValueError("receiver config is not valid JSON") from exc
