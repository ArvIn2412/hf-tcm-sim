"""Strict serialized configuration for the REPRO-05 joint receiver."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Literal

from hf_tcm.repro.encoder import TerminationPolicy
from hf_tcm.repro.identifiers import ENCODER_ID, MAPPING_ID

JOINT_RECEIVER_SCHEMA_VERSION = "repro05-joint-receiver-v1"
EstimatorPolicy = Literal["frozen", "adaptive_project_v1"]
ChannelMode = Literal["nominal", "known_static_complex_gain"]


@dataclass(frozen=True, slots=True)
class JointReceiverConfig:
    expected_symbol_count: int
    initial_state: tuple[int, int] = (0, 0)
    termination_policy: TerminationPolicy = "none"
    timing_offset_samples: int = 0
    metric_profile: Literal["euclidean", "squared_euclidean"] = "squared_euclidean"
    estimator_policy: EstimatorPolicy = "frozen"
    initial_state_value: complex = 0j
    mu0: complex = 1 + 0j
    alpha_prime: float = 1.0
    k_tilde: float = 0.0
    beta: float = 1.0
    amplitude: float = 1.0
    phase_offset_rad: float = 0.0
    phase_increment_rad: float = math.pi / 4.0
    channel_mode: ChannelMode = "nominal"
    known_static_gain: complex = 1 + 0j
    encoder_id: str = ENCODER_ID
    mapping_id: str = MAPPING_ID
    tie_policy: str = "canonical_first_edge_then_state_order"
    decoder_mode: Literal["full_frame", "finite_depth"] = "full_frame"
    traceback_depth: int | None = None
    initial_state_policy: Literal["configured"] = "configured"
    final_state_policy: Literal["auto", "free", "known_terminated"] = "auto"
    tie_break_policy: str = "canonical_first_edge_then_state_order"
    trace_output_mode: Literal["compact", "full"] = "full"
    schema_version: str = JOINT_RECEIVER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.expected_symbol_count) is not int or self.expected_symbol_count < 1:
            raise ValueError("expected_symbol_count must be a positive integer")
        if (
            not isinstance(self.initial_state, tuple)
            or len(self.initial_state) != 2
            or any(type(bit) is not int or bit not in (0, 1) for bit in self.initial_state)
        ):
            raise ValueError("initial_state must be a binary pair")
        if self.termination_policy not in {"none", "zero_tail_2"}:
            raise ValueError("termination_policy must be none or zero_tail_2")
        if self.termination_policy == "zero_tail_2" and self.expected_symbol_count < 3:
            raise ValueError("zero_tail_2 requires at least one payload and two tail symbols")
        if type(self.timing_offset_samples) is not int or not 0 <= self.timing_offset_samples < 8:
            raise ValueError("timing_offset_samples must be in [0,7]")
        if self.metric_profile not in {"euclidean", "squared_euclidean"}:
            raise ValueError("metric_profile must be euclidean or squared_euclidean")
        if self.estimator_policy not in {"frozen", "adaptive_project_v1"}:
            raise ValueError("unsupported estimator_policy")
        if self.channel_mode not in {"nominal", "known_static_complex_gain"}:
            raise ValueError("unsupported channel_mode")
        numeric = {
            "alpha_prime": self.alpha_prime,
            "k_tilde": self.k_tilde,
            "beta": self.beta,
            "amplitude": self.amplitude,
            "phase_offset_rad": self.phase_offset_rad,
            "phase_increment_rad": self.phase_increment_rad,
        }
        if any(isinstance(v, bool) or not math.isfinite(float(v)) for v in numeric.values()):
            raise ValueError("receiver numeric parameters must be finite")
        if self.amplitude <= 0 or self.beta < 0:
            raise ValueError("amplitude must be positive and beta nonnegative")
        if self.estimator_policy == "frozen" and (self.k_tilde != 0.0 or self.alpha_prime != 1.0):
            raise ValueError("frozen estimator requires alpha_prime=1 and k_tilde=0")
        if not math.isclose(self.phase_increment_rad, math.pi / 4, rel_tol=0, abs_tol=1e-15):
            raise ValueError("phase_increment_rad must equal pi/4")
        if self.encoder_id != ENCODER_ID or self.mapping_id != MAPPING_ID:
            raise ValueError("REPRO-05 supports Encoder A with the ADR-002 project mapping")
        if self.tie_policy != "canonical_first_edge_then_state_order":
            raise ValueError("unsupported tie_policy")
        if self.decoder_mode not in {"full_frame", "finite_depth"}:
            raise ValueError("decoder_mode must be full_frame or finite_depth")
        if self.decoder_mode == "finite_depth" and (
            type(self.traceback_depth) is not int or self.traceback_depth < 1
        ):
            raise ValueError("finite_depth mode requires a positive traceback_depth")
        if self.decoder_mode == "full_frame" and self.traceback_depth is not None:
            raise ValueError("full_frame mode requires traceback_depth=None")
        if self.decoder_mode == "full_frame" and self.trace_output_mode != "full":
            raise ValueError("full_frame mode always records full diagnostics")
        if self.initial_state_policy != "configured":
            raise ValueError("only configured initial_state_policy is supported")
        if self.final_state_policy not in {"auto", "free", "known_terminated"}:
            raise ValueError("unsupported final_state_policy")
        if (
            self.final_state_policy == "known_terminated"
            and self.termination_policy != "zero_tail_2"
        ):
            raise ValueError("known_terminated requires termination_policy='zero_tail_2'")
        if self.tie_break_policy != self.tie_policy:
            raise ValueError("tie_break_policy must match the established canonical tie policy")
        if self.trace_output_mode not in {"compact", "full"}:
            raise ValueError("trace_output_mode must be compact or full")
        if self.schema_version != JOINT_RECEIVER_SCHEMA_VERSION:
            raise ValueError("unsupported joint receiver schema version")
        for name, value in (
            ("initial_state_value", self.initial_state_value),
            ("mu0", self.mu0),
            ("known_static_gain", self.known_static_gain),
        ):
            number = complex(value)
            if not math.isfinite(number.real) or not math.isfinite(number.imag):
                raise ValueError(f"{name} must be finite")
        if self.channel_mode == "known_static_complex_gain" and abs(self.known_static_gain) == 0:
            raise ValueError("known_static_gain must be nonzero")

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__}
        for name in ("initial_state_value", "mu0", "known_static_gain"):
            number = complex(result[name])
            result[name] = [number.real, number.imag]
        result["initial_state"] = list(self.initial_state)
        return result

    @classmethod
    def article_oriented(cls, *, expected_symbol_count: int, **kwargs: Any) -> JointReceiverConfig:
        """Build the explicit project convention eta=20 (transitions, not source-confirmed internals)."""
        kwargs.setdefault("trace_output_mode", "compact")
        return cls(
            expected_symbol_count=expected_symbol_count,
            decoder_mode="finite_depth",
            traceback_depth=20,
            **kwargs,
        )

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> JointReceiverConfig:
        if not isinstance(values, dict):
            raise ValueError("receiver config must be a JSON object")
        extra = set(values) - set(cls.__dataclass_fields__)
        if extra:
            raise ValueError(f"unexpected joint receiver field: {sorted(extra)[0]}")
        data = dict(values)
        if "initial_state" in data:
            data["initial_state"] = tuple(data["initial_state"])
        for name in ("initial_state_value", "mu0", "known_static_gain"):
            if name in data:
                pair = data[name]
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    raise ValueError(f"{name} must be encoded as [real, imag]")
                data[name] = complex(float(pair[0]), float(pair[1]))
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValueError(f"invalid joint receiver config: {exc}") from exc

    @classmethod
    def from_json(cls, text: str) -> JointReceiverConfig:
        try:
            return cls.from_dict(json.loads(text))
        except json.JSONDecodeError as exc:
            raise ValueError("receiver config is not valid JSON") from exc
