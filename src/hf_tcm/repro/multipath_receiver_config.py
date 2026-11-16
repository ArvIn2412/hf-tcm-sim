"""Validated public receiver settings for the REPRO-06B ISI-aware decoder."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Literal

from hf_tcm.repro.encoder import TerminationPolicy
from hf_tcm.repro.identifiers import ENCODER_ID, MAPPING_ID

MULTIPATH_RECEIVER_SCHEMA = "repro06b-multipath-joint-v1"
MAX_CHANNEL_MEMORY_SYMBOLS = 2
MAX_EXPANDED_STATES = 256
MAX_EXPANDED_EDGES = 2048


@dataclass(frozen=True, slots=True)
class MultipathPathConfig:
    """Receiver-known static path delay and complex gain."""

    delay_samples: int
    gain: complex

    def __post_init__(self) -> None:
        if type(self.delay_samples) is not int or self.delay_samples < 0:
            raise ValueError("delay_samples must be a non-negative integer")
        gain = complex(self.gain)
        if not math.isfinite(gain.real) or not math.isfinite(gain.imag):
            raise ValueError("path gain must be a finite complex number")
        object.__setattr__(self, "gain", gain)

    def to_dict(self) -> dict[str, Any]:
        return {
            "delay_samples": self.delay_samples,
            "gain": [float(self.gain.real), float(self.gain.imag)],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> MultipathPathConfig:
        if not isinstance(value, dict) or set(value) != {"delay_samples", "gain"}:
            raise ValueError("each path requires only delay_samples and gain")
        gain = value["gain"]
        if not isinstance(gain, (list, tuple)) or len(gain) != 2:
            raise ValueError("path gain must be encoded as [real, imag]")
        try:
            return cls(value["delay_samples"], complex(float(gain[0]), float(gain[1])))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid static multipath entry") from exc


@dataclass(frozen=True, slots=True)
class MultipathReceiverConfig:
    """Exact receiver-known static channel and decoder configuration.

    The channel values are supplied to the receiver as public CSI. No generated
    coefficients, noise realization, or EvaluationTruth object is accepted.
    """

    expected_symbol_count: int
    paths: tuple[MultipathPathConfig, ...]
    initial_state: tuple[int, int] = (0, 0)
    termination_policy: TerminationPolicy = "none"
    metric_profile: Literal["euclidean", "squared_euclidean"] = "squared_euclidean"
    decoder_mode: Literal["full_frame", "finite_depth"] = "full_frame"
    traceback_depth: int | None = None
    final_state_policy: Literal["free", "known_terminated"] = "free"
    tie_break_policy: str = "canonical_first_edge_then_state_order"
    trace_output_mode: Literal["compact", "full"] = "compact"
    diagnostic_symbol_index: int = 0
    amplitude: float = 1.0
    phase_offset_rad: float = 0.0
    phase_increment_rad: float = math.pi / 4.0
    samples_per_symbol: int = 8
    timing_offset_samples: int = 0
    channel_mode: Literal["known_public_static"] = "known_public_static"
    isi_mode: Literal["augmented_trellis"] = "augmented_trellis"
    estimator_profile: Literal["known_static", "adaptive_rician_survivor_v1"] = "known_static"
    encoder_id: str = ENCODER_ID
    mapping_id: str = MAPPING_ID
    profile_id: str = "repro06b_known_static_isi_project_v1"
    schema_version: str = MULTIPATH_RECEIVER_SCHEMA

    def __post_init__(self) -> None:
        if type(self.expected_symbol_count) is not int or self.expected_symbol_count < 1:
            raise ValueError("expected_symbol_count must be a positive integer")
        if (
            not isinstance(self.paths, tuple)
            or not self.paths
            or any(not isinstance(path, MultipathPathConfig) for path in self.paths)
        ):
            raise ValueError("paths must be a nonempty tuple of MultipathPathConfig")
        if self.estimator_profile != "known_static":
            raise ValueError(
                "adaptive Rician multipath is unavailable until survivor-specific estimation is verified"
            )
        if self.channel_mode != "known_public_static":
            raise ValueError("only channel_mode='known_public_static' is implemented")
        if self.isi_mode != "augmented_trellis":
            raise ValueError("only isi_mode='augmented_trellis' is implemented")
        if self.encoder_id != ENCODER_ID or self.mapping_id != MAPPING_ID:
            raise ValueError("REPRO-06B supports Encoder A and the configured REPRO-02 mapping")
        if self.schema_version != MULTIPATH_RECEIVER_SCHEMA:
            raise ValueError("unsupported REPRO-06B receiver schema")
        if (
            not isinstance(self.initial_state, tuple)
            or len(self.initial_state) != 2
            or any(type(bit) is not int or bit not in (0, 1) for bit in self.initial_state)
        ):
            raise ValueError("initial_state must be a binary pair")
        if self.termination_policy not in {"none", "zero_tail_2"}:
            raise ValueError("unsupported termination_policy")
        if self.termination_policy == "zero_tail_2" and self.expected_symbol_count < 3:
            raise ValueError("zero_tail_2 requires at least three frame symbols")
        if self.metric_profile not in {"euclidean", "squared_euclidean"}:
            raise ValueError("unsupported metric_profile")
        if self.decoder_mode not in {"full_frame", "finite_depth"}:
            raise ValueError("decoder_mode must be full_frame or finite_depth")
        if self.decoder_mode == "finite_depth":
            if type(self.traceback_depth) is not int or self.traceback_depth < 1:
                raise ValueError("finite_depth mode requires positive traceback_depth")
        elif self.traceback_depth is not None:
            raise ValueError("full_frame mode requires traceback_depth=None")
        if self.final_state_policy not in {"free", "known_terminated"}:
            raise ValueError("unsupported final_state_policy")
        if (
            self.final_state_policy == "known_terminated"
            and self.termination_policy != "zero_tail_2"
        ):
            raise ValueError("known_terminated requires zero_tail_2 termination")
        if self.tie_break_policy != "canonical_first_edge_then_state_order":
            raise ValueError("unsupported tie_break_policy")
        if self.trace_output_mode not in {"compact", "full"}:
            raise ValueError("trace_output_mode must be compact or full")
        if (
            type(self.diagnostic_symbol_index) is not int
            or not 0 <= self.diagnostic_symbol_index < self.expected_symbol_count
        ):
            raise ValueError("diagnostic_symbol_index must be inside the frame")
        if self.samples_per_symbol != 8:
            raise ValueError("samples_per_symbol must equal 8")
        if type(self.timing_offset_samples) is not int or self.timing_offset_samples != 0:
            raise ValueError("ISI-aware profile currently requires timing_offset_samples=0")
        numeric = (self.amplitude, self.phase_offset_rad, self.phase_increment_rad)
        if any(isinstance(value, bool) or not math.isfinite(float(value)) for value in numeric):
            raise ValueError("modulation parameters must be finite")
        if self.amplitude <= 0:
            raise ValueError("amplitude must be positive")
        if not math.isclose(self.phase_increment_rad, math.pi / 4, rel_tol=0, abs_tol=1e-15):
            raise ValueError("phase_increment_rad must equal pi/4")
        if not isinstance(self.profile_id, str) or not self.profile_id.strip():
            raise ValueError("profile_id must be a nonempty string")
        if self.channel_memory_symbols > MAX_CHANNEL_MEMORY_SYMBOLS:
            raise ValueError("channel delay requires more than 2 previous symbols")

    @property
    def maximum_delay_samples(self) -> int:
        return max(path.delay_samples for path in self.paths)

    @property
    def channel_memory_symbols(self) -> int:
        return (self.maximum_delay_samples + self.samples_per_symbol - 1) // self.samples_per_symbol

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["paths"] = [path.to_dict() for path in self.paths]
        result["initial_state"] = list(self.initial_state)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MultipathReceiverConfig:
        if not isinstance(data, dict):
            raise ValueError("receiver config must be a JSON object")
        extra = set(data) - set(cls.__dataclass_fields__)
        if extra:
            raise ValueError(f"unexpected receiver config field: {sorted(extra)[0]}")
        values = dict(data)
        if "paths" in values:
            values["paths"] = tuple(
                item
                if isinstance(item, MultipathPathConfig)
                else MultipathPathConfig.from_dict(item)
                for item in values["paths"]
            )
        if "initial_state" in values:
            values["initial_state"] = tuple(values["initial_state"])
        try:
            return cls(**values)
        except TypeError as exc:
            raise ValueError(f"invalid REPRO-06B receiver config: {exc}") from exc

    @classmethod
    def from_json(cls, text: str) -> MultipathReceiverConfig:
        try:
            return cls.from_dict(json.loads(text))
        except json.JSONDecodeError as exc:
            raise ValueError("receiver config is not valid JSON") from exc
