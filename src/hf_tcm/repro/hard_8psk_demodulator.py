"""Independent hard 8PSK nearest-hypothesis stage."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.receiver_config import ReceiverFrontEndConfig


@dataclass(frozen=True, slots=True)
class HardDemodulation:
    phase_indices: NDArray[np.int8]
    coded_triples: NDArray[np.int8]
    squared_distances: NDArray[np.float64]
    hypothesis_symbols: NDArray[np.complex128]
    symbol_observations: NDArray[np.complex128]


def inverse_phase_labels() -> NDArray[np.int8]:
    """Return the bijective project ADR-002 inverse: b -> (c2,c1,c0)."""
    return np.asarray(
        [[index >> 2, (index >> 1) & 1, index & 1] for index in range(8)], dtype=np.int8
    )


def demodulate_hard_8psk(
    observation_blocks: NDArray[np.complex128],
    config: ReceiverFrontEndConfig,
    *,
    phase_increment_rad: float = math.pi / 4.0,
) -> HardDemodulation:
    blocks = np.asarray(observation_blocks, dtype=np.complex128)
    if blocks.ndim != 2 or blocks.shape[0] < 1 or blocks.shape[1] < 1:
        raise ValueError("observation_blocks must have shape (symbols, samples_per_symbol_used)")
    if not np.all(np.isfinite(blocks)):
        raise ValueError("observation blocks must be finite")
    if not isinstance(config, ReceiverFrontEndConfig):
        raise TypeError("config must be ReceiverFrontEndConfig")
    if not math.isclose(phase_increment_rad, math.pi / 4, rel_tol=0, abs_tol=1e-15):
        raise ValueError("phase increment must equal pi/4")
    gain = config.known_static_gain if config.mode == "known_static_complex_gain" else 1 + 0j
    indices = np.arange(8, dtype=np.float64)
    hypotheses = (
        gain
        * config.amplitude
        * np.exp(1j * (config.phase_offset_rad + indices * phase_increment_rad))
    )
    # This algebra is exactly the per-sample Euclidean sum for a constant symbol.
    sums = blocks.sum(axis=1)
    energy = np.square(np.abs(blocks)).sum(axis=1)
    distances = energy[:, None] + blocks.shape[1] * np.square(np.abs(hypotheses))[None, :]
    distances -= 2.0 * np.real(sums[:, None] * np.conjugate(hypotheses)[None, :])
    np.maximum(distances, 0.0, out=distances)
    decisions = np.argmin(distances, axis=1).astype(np.int8)
    labels = inverse_phase_labels()
    return HardDemodulation(
        phase_indices=decisions,
        coded_triples=labels[decisions].copy(),
        squared_distances=distances,
        hypothesis_symbols=hypotheses,
        symbol_observations=sums / blocks.shape[1],
    )
