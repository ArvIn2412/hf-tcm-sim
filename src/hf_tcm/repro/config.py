"""Strict configuration for the REPRO-02 transmitter."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from numbers import Real
from typing import Any

from hf_tcm.repro.identifiers import ENCODER_ID, MAPPING_ID

SCHEMA_VERSION = "repro02-transmitter-v1"
MAX_FRAME_SYMBOLS = 1_000_000
SOURCE_MODES = {"manual", "pattern", "seeded_random"}
PATTERN_IDS = {"all_zeros", "all_ones", "alternating", "repeat"}
TERMINATION_POLICIES = {"none", "zero_tail_2"}


def _integer(value: object, *, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _finite_real(value: object, *, name: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return result


@dataclass(frozen=True, slots=True)
class TransmitterConfig:
    """Frozen, explicit inputs for an Encoder A transmitter run."""

    source_mode: str
    frame_symbols: int
    manual_bits: str | None = None
    pattern_id: str | None = None
    repeat_pattern: str | None = None
    seed: int | None = None
    rng_algorithm: str = "PCG64"
    initial_state: tuple[int, int] = (0, 0)
    termination_policy: str = "none"
    encoder_id: str = ENCODER_ID
    mapping_id: str = MAPPING_ID
    amplitude: float = 1.0
    phase_offset_rad: float = 0.0
    phase_increment_rad: float = math.pi / 4.0
    samples_per_symbol: int = 8

    def __post_init__(self) -> None:
        if self.source_mode not in SOURCE_MODES:
            raise ValueError("source_mode must be manual, pattern, or seeded_random")
        if self.rng_algorithm != "PCG64":
            raise ValueError("rng_algorithm must be the explicitly supported 'PCG64'")
        frame_symbols = _integer(self.frame_symbols, name="frame_symbols", minimum=1)
        if frame_symbols > MAX_FRAME_SYMBOLS:
            raise ValueError(f"frame_symbols must be <= {MAX_FRAME_SYMBOLS}")
        if self.termination_policy not in TERMINATION_POLICIES:
            raise ValueError("termination_policy must be 'none' or 'zero_tail_2'")
        if self.encoder_id != ENCODER_ID:
            raise ValueError(
                f"encoder_id must be {ENCODER_ID!r}; Encoder B is not implemented here"
            )
        if self.mapping_id != MAPPING_ID:
            raise ValueError(f"mapping_id must be {MAPPING_ID!r}")
        if self.samples_per_symbol != 8:
            raise ValueError("samples_per_symbol must equal 8 for the S1-aligned profile")
        if not math.isclose(
            _finite_real(self.phase_increment_rad, name="phase_increment_rad"),
            math.pi / 4.0,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError("phase_increment_rad must equal the source increment pi/4")
        _finite_real(self.amplitude, name="amplitude", minimum=0.0)
        if self.amplitude == 0.0:
            raise ValueError("amplitude must be positive")
        _finite_real(self.phase_offset_rad, name="phase_offset_rad")
        if (
            not isinstance(self.initial_state, tuple)
            or len(self.initial_state) != 2
            or any(type(bit) is not int or bit not in (0, 1) for bit in self.initial_state)
        ):
            raise ValueError("initial_state must be a pair of integer bits")

        if self.source_mode == "manual":
            if not isinstance(self.manual_bits, str):
                raise ValueError("manual_bits is required for manual source_mode")
            if any(bit not in "01" for bit in self.manual_bits):
                raise ValueError("manual_bits must contain only characters 0 and 1")
            if len(self.manual_bits) % 2:
                raise ValueError("manual_bits must contain an even number of bits")
            if len(self.manual_bits) != 2 * frame_symbols:
                raise ValueError("manual_bits length must equal 2*frame_symbols")
            if (
                self.pattern_id is not None
                or self.repeat_pattern is not None
                or self.seed is not None
            ):
                raise ValueError("manual mode cannot also define pattern or seed fields")
        elif self.source_mode == "pattern":
            if self.pattern_id not in PATTERN_IDS:
                raise ValueError(f"pattern_id must be one of {sorted(PATTERN_IDS)}")
            if self.pattern_id == "repeat":
                if not isinstance(self.repeat_pattern, str) or not self.repeat_pattern:
                    raise ValueError("repeat_pattern is required for repeat pattern_id")
                if any(bit not in "01" for bit in self.repeat_pattern):
                    raise ValueError("repeat_pattern must contain only characters 0 and 1")
            elif self.repeat_pattern is not None:
                raise ValueError("repeat_pattern is only valid with pattern_id='repeat'")
            if self.manual_bits is not None or self.seed is not None:
                raise ValueError("pattern mode cannot also define manual_bits or seed")
        else:
            if self.seed is None:
                raise ValueError("seed is required for seeded_random source_mode")
            _integer(self.seed, name="seed", minimum=0)
            if self.seed > (1 << 64) - 1:
                raise ValueError("seed must be <= 2**64-1")
            if (
                self.manual_bits is not None
                or self.pattern_id is not None
                or self.repeat_pattern is not None
            ):
                raise ValueError("seeded_random mode cannot define manual or pattern fields")

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> TransmitterConfig:
        """Parse one strict JSON-compatible configuration object."""
        if not isinstance(values, dict):
            raise ValueError("configuration must be a JSON object")
        allowed = set(cls.__dataclass_fields__) | {"schema_version"}
        unexpected = set(values) - allowed
        if unexpected:
            raise ValueError(f"unexpected configuration field: {sorted(unexpected)[0]}")
        version = values.get("schema_version", SCHEMA_VERSION)
        if version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        data = {key: value for key, value in values.items() if key != "schema_version"}
        if "source_mode" not in data or "frame_symbols" not in data:
            raise ValueError("source_mode and frame_symbols are required")
        if isinstance(data.get("initial_state"), list):
            data["initial_state"] = tuple(data["initial_state"])
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValueError(f"invalid configuration fields: {exc}") from exc

    @classmethod
    def from_json(cls, text: str) -> TransmitterConfig:
        import json

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("configuration is not valid JSON") from exc
        return cls.from_dict(parsed)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["schema_version"] = SCHEMA_VERSION
        result["initial_state"] = list(self.initial_state)
        return result
