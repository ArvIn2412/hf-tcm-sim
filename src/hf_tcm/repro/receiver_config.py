"""Strict configuration for the REPRO-04 separate receiver."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Literal

from hf_tcm.repro.encoder import TerminationPolicy
from hf_tcm.repro.identifiers import ENCODER_ID, MAPPING_ID

RECEIVER_SCHEMA_VERSION = "repro04-separate-receiver-v1"


@dataclass(frozen=True, slots=True)
class ReceiverFrontEndConfig:
    """Nominal constellation or explicitly receiver-known static complex gain."""

    mode: Literal["fixed_nominal", "known_static_complex_gain"] = "fixed_nominal"
    amplitude: float = 1.0
    phase_offset_rad: float = 0.0
    known_static_gain: complex = 1 + 0j

    def __post_init__(self) -> None:
        if self.mode not in {"fixed_nominal", "known_static_complex_gain"}:
            raise ValueError("front-end mode must be fixed_nominal or known_static_complex_gain")
        if (
            isinstance(self.amplitude, bool)
            or not math.isfinite(float(self.amplitude))
            or self.amplitude <= 0
        ):
            raise ValueError("amplitude must be finite and positive")
        if isinstance(self.phase_offset_rad, bool) or not math.isfinite(
            float(self.phase_offset_rad)
        ):
            raise ValueError("phase_offset_rad must be finite")
        gain = complex(self.known_static_gain)
        if not math.isfinite(gain.real) or not math.isfinite(gain.imag) or abs(gain) == 0:
            raise ValueError("known_static_gain must be finite and nonzero")
        if self.mode == "fixed_nominal" and gain != 1 + 0j:
            raise ValueError("fixed_nominal front end does not accept a configured channel gain")
        object.__setattr__(self, "amplitude", float(self.amplitude))
        object.__setattr__(self, "phase_offset_rad", float(self.phase_offset_rad))
        object.__setattr__(self, "known_static_gain", gain)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "amplitude": self.amplitude,
            "phase_offset_rad": self.phase_offset_rad,
            "known_static_gain": [self.known_static_gain.real, self.known_static_gain.imag],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReceiverFrontEndConfig:
        if not isinstance(data, dict) or set(data) - set(cls.__dataclass_fields__):
            raise ValueError("invalid receiver front-end fields")
        values = dict(data)
        gain = values.get("known_static_gain", [1.0, 0.0])
        if not isinstance(gain, (list, tuple)) or len(gain) != 2:
            raise ValueError("known_static_gain must be [real, imag]")
        values["known_static_gain"] = complex(float(gain[0]), float(gain[1]))
        return cls(**values)


@dataclass(frozen=True, slots=True)
class SeparateReceiverConfig:
    expected_symbol_count: int
    initial_state: tuple[int, int] = (0, 0)
    termination_policy: TerminationPolicy = "none"
    timing_offset_samples: int = 0
    front_end: ReceiverFrontEndConfig = ReceiverFrontEndConfig()
    encoder_id: str = ENCODER_ID
    mapping_id: str = MAPPING_ID
    tie_policy: str = "canonical_first_edge_then_state_order"
    decoder_mode: Literal["full_frame", "finite_depth"] = "full_frame"
    traceback_depth: int | None = None
    initial_state_policy: Literal["configured"] = "configured"
    final_state_policy: Literal["auto", "free", "known_terminated"] = "auto"
    tie_break_policy: str = "canonical_first_edge_then_state_order"
    trace_output_mode: Literal["compact", "full"] = "full"
    phase_increment_rad: float = math.pi / 4.0
    schema_version: str = RECEIVER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.expected_symbol_count) is not int or self.expected_symbol_count < 1:
            raise ValueError("expected_symbol_count must be a positive integer")
        if (
            not isinstance(self.initial_state, tuple)
            or len(self.initial_state) != 2
            or any(type(bit) is not int or bit not in (0, 1) for bit in self.initial_state)
        ):
            raise ValueError("initial_state must be a pair of binary integers")
        if self.termination_policy not in {"none", "zero_tail_2"}:
            raise ValueError("termination_policy must be none or zero_tail_2")
        if self.termination_policy == "zero_tail_2" and self.expected_symbol_count < 3:
            raise ValueError("zero_tail_2 requires at least one payload and two tail symbols")
        if type(self.timing_offset_samples) is not int or not 0 <= self.timing_offset_samples < 8:
            raise ValueError("timing_offset_samples must be an integer in [0,7]")
        if not isinstance(self.front_end, ReceiverFrontEndConfig):
            raise ValueError("front_end must be ReceiverFrontEndConfig")
        if self.encoder_id != ENCODER_ID or self.mapping_id != MAPPING_ID:
            raise ValueError("receiver supports only Encoder A and the ADR-002 project mapping")
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
        if not math.isclose(self.phase_increment_rad, math.pi / 4, rel_tol=0, abs_tol=1e-15):
            raise ValueError("phase_increment_rad must equal pi/4")
        if self.schema_version != RECEIVER_SCHEMA_VERSION:
            raise ValueError("unsupported REPRO-04 schema version")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "expected_symbol_count": self.expected_symbol_count,
            "initial_state": list(self.initial_state),
            "termination_policy": self.termination_policy,
            "timing_offset_samples": self.timing_offset_samples,
            "front_end": self.front_end.to_dict(),
            "encoder_id": self.encoder_id,
            "mapping_id": self.mapping_id,
            "tie_policy": self.tie_policy,
            "decoder_mode": self.decoder_mode,
            "traceback_depth": self.traceback_depth,
            "initial_state_policy": self.initial_state_policy,
            "final_state_policy": self.final_state_policy,
            "tie_break_policy": self.tie_break_policy,
            "trace_output_mode": self.trace_output_mode,
            "phase_increment_rad": self.phase_increment_rad,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SeparateReceiverConfig:
        if not isinstance(data, dict) or set(data) - set(cls.__dataclass_fields__):
            raise ValueError("invalid separate receiver config fields")
        values = dict(data)
        values["initial_state"] = tuple(values.get("initial_state", (0, 0)))
        values["front_end"] = ReceiverFrontEndConfig.from_dict(values.get("front_end", {}))
        return cls(**values)

    @classmethod
    def from_json(cls, text: str) -> SeparateReceiverConfig:
        try:
            return cls.from_dict(json.loads(text))
        except json.JSONDecodeError as exc:
            raise ValueError("receiver configuration is not valid JSON") from exc

    @classmethod
    def article_oriented(
        cls, *, expected_symbol_count: int, **kwargs: Any
    ) -> SeparateReceiverConfig:
        """Build the explicit project convention eta=20 (transitions, not source-confirmed internals)."""
        kwargs.setdefault("trace_output_mode", "compact")
        return cls(
            expected_symbol_count=expected_symbol_count,
            decoder_mode="finite_depth",
            traceback_depth=20,
            **kwargs,
        )
