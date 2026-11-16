"""Explicit information-bit sources for the REPRO transmitter."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.config import TransmitterConfig

IntArray = NDArray[np.int8]


def immutable_int8(values: object) -> IntArray:
    owned = np.array(values, dtype=np.int8, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=np.int8).reshape(owned.shape)


@dataclass(frozen=True, slots=True)
class InformationBits:
    information_bits: IntArray
    metadata: dict[str, Any]
    sha256: str


def generate_information_bits(config: TransmitterConfig) -> InformationBits:
    """Generate one exact-length bit vector without global RNG state."""
    count = 2 * config.frame_symbols
    metadata: dict[str, Any] = {
        "source_mode": config.source_mode,
        "frame_symbols": config.frame_symbols,
        "bit_count": count,
        "bit_order": "left-to-right input string; consecutive pairs (u0,u1)",
    }
    if config.source_mode == "manual":
        assert config.manual_bits is not None
        values = np.fromiter((int(bit) for bit in config.manual_bits), dtype=np.int8, count=count)
        metadata["source_id"] = "manual_bits_v1"
    elif config.source_mode == "pattern":
        pattern_id = config.pattern_id
        if pattern_id == "all_zeros":
            values = np.zeros(count, dtype=np.int8)
        elif pattern_id == "all_ones":
            values = np.ones(count, dtype=np.int8)
        elif pattern_id == "alternating":
            values = np.arange(count, dtype=np.int64).astype(np.int8) % 2
        else:
            assert config.repeat_pattern is not None
            seed = np.fromiter((int(bit) for bit in config.repeat_pattern), dtype=np.int8)
            values = np.resize(seed, count)
        metadata.update(
            {
                "source_id": f"pattern:{pattern_id}",
                "repeat_pattern": config.repeat_pattern,
            }
        )
    else:
        assert config.seed is not None
        generator = np.random.Generator(np.random.PCG64(config.seed))
        state_before = copy.deepcopy(generator.bit_generator.state)
        values = generator.integers(0, 2, size=count, dtype=np.int8)
        state_after = copy.deepcopy(generator.bit_generator.state)
        metadata.update(
            {
                "source_id": "numpy_seeded_pseudorandom_v1",
                "rng_algorithm": "PCG64",
                "rng_is_author_defined": False,
                "seed": config.seed,
                "numpy_version": np.__version__,
                "bit_generator_state_before": state_before,
                "bit_generator_state_after": state_after,
            }
        )

    bits = immutable_int8(values)
    digest = hashlib.sha256(bits.tobytes()).hexdigest()
    metadata["bits_sha256"] = digest
    return InformationBits(information_bits=bits, metadata=metadata, sha256=digest)
