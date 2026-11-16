"""Exact static known-channel sample predictor for integer-delay ZOH paths."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.augmented_trellis import AugmentedTransition, AugmentedTrellis
from hf_tcm.repro.multipath_receiver_config import MultipathReceiverConfig


def _symbol(phase_index: int, config: MultipathReceiverConfig) -> complex:
    return complex(
        config.amplitude
        * np.exp(1j * (config.phase_offset_rad + phase_index * config.phase_increment_rad))
    )


def predict_transition_samples(
    transition: AugmentedTransition,
    trellis: AugmentedTrellis,
    *,
    symbol_index: int,
    frame_symbols: int,
    config: MultipathReceiverConfig,
    sample_indices: object,
) -> NDArray[np.complex128]:
    """Predict receiver samples for one edge and the edge's explicit phase history.

    `sample_indices` are absolute receive sample indices. Negative transmitter
    indices and source indices at/after the transmitted frame length use zero
    extension, matching REPRO-03.
    """
    if not isinstance(transition, AugmentedTransition) or not isinstance(trellis, AugmentedTrellis):
        raise TypeError("transition and trellis must be REPRO augmented-trellis values")
    if not isinstance(config, MultipathReceiverConfig):
        raise TypeError("config must be MultipathReceiverConfig")
    if type(symbol_index) is not int or not 0 <= symbol_index < frame_symbols:
        raise ValueError("symbol_index must lie inside the transmitted frame")
    if type(frame_symbols) is not int or frame_symbols != config.expected_symbol_count:
        raise ValueError("frame_symbols must match config.expected_symbol_count")
    if transition.source_node_id >= len(trellis.nodes):
        raise ValueError("transition source does not belong to trellis")
    source_node = trellis.nodes[transition.source_node_id]
    if len(source_node.phase_history) != config.channel_memory_symbols:
        raise ValueError("trellis history depth does not match configured channel memory")
    indices = np.asarray(sample_indices)
    if indices.ndim != 1 or indices.dtype.kind not in "iu":
        raise ValueError("sample_indices must be a one-dimensional integer vector")
    if np.any(indices < 0) or np.any(indices >= frame_symbols * 8 + config.maximum_delay_samples):
        raise ValueError("sample index is outside the complete receive frame")

    predicted = np.zeros(indices.shape, dtype=np.complex128)
    for path in config.paths:
        source_samples = indices.astype(np.int64, copy=False) - path.delay_samples
        in_frame = (source_samples >= 0) & (source_samples < frame_symbols * 8)
        if not np.any(in_frame):
            continue
        source_symbols = source_samples[in_frame] // 8
        path_values = np.empty(source_symbols.shape, dtype=np.complex128)
        for source_symbol in np.unique(source_symbols):
            if source_symbol == symbol_index:
                phase = transition.phase_index
            elif source_symbol < symbol_index:
                history_age = symbol_index - int(source_symbol)
                if history_age > len(source_node.phase_history):
                    raise ValueError("augmented trellis does not retain required symbol history")
                phase = source_node.phase_history[history_age - 1]
                if phase < 0:
                    continue
            else:
                # Source symbols after the current branch are outside the hypothesized prefix.
                continue
            mask = source_symbols == source_symbol
            path_values[mask] = _symbol(int(phase), config)
        # Entries sourced before frame time use zero-extension and therefore remain zero.
        for offset, source_symbol in enumerate(source_symbols):
            history_age = symbol_index - int(source_symbol)
            if source_symbol > symbol_index or (
                history_age > 0 and source_node.phase_history[history_age - 1] < 0
            ):
                path_values[offset] = 0.0j
        predicted[in_frame] += path.gain * path_values
    return predicted
