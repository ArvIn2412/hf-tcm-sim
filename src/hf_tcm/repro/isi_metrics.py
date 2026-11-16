"""Branch costs for the REPRO-06B static-known multipath profile."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.augmented_trellis import AugmentedTrellis
from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.isi_predictor import predict_transition_samples
from hf_tcm.repro.multipath_receiver_config import MultipathReceiverConfig


def branch_sample_indices(
    symbol_index: int, frame_symbols: int, maximum_delay_samples: int
) -> NDArray[np.int64]:
    """Assign each 8-sample symbol block once and attach the D-sample tail to F-1."""
    if type(symbol_index) is not int or not 0 <= symbol_index < frame_symbols:
        raise ValueError("symbol_index must be inside the frame")
    start = symbol_index * 8
    stop = start + 8
    if symbol_index == frame_symbols - 1:
        stop += maximum_delay_samples
    return np.arange(start, stop, dtype=np.int64)


def build_branch_metric_row(
    observation: ReceiverObservation,
    symbol_index: int,
    trellis: AugmentedTrellis,
    config: MultipathReceiverConfig,
) -> NDArray[np.float64]:
    """Score every expanded transition against its complete predicted receive block."""
    if type(observation) is not ReceiverObservation:
        raise TypeError("observation must be ReceiverObservation; channel truth is forbidden")
    if observation.samples_per_symbol != 8:
        raise ValueError("REPRO-06B requires 8 samples per symbol")
    frame_length = config.expected_symbol_count * 8 + config.maximum_delay_samples
    received = np.asarray(observation.received_samples)
    if received.dtype != np.dtype(np.complex128) or received.ndim != 1:
        raise ValueError("received_samples must be a one-dimensional complex128 vector")
    if len(received) != frame_length:
        raise ValueError(f"observation length must equal {frame_length} for this delay profile")
    sample_indices = branch_sample_indices(
        symbol_index, config.expected_symbol_count, config.maximum_delay_samples
    )
    observed = received[sample_indices]
    predictions = np.empty((len(trellis.edges), len(sample_indices)), dtype=np.complex128)
    for edge in trellis.edges:
        predictions[edge.expanded_edge_id] = predict_transition_samples(
            edge,
            trellis,
            symbol_index=symbol_index,
            frame_symbols=config.expected_symbol_count,
            config=config,
            sample_indices=sample_indices,
        )
    row = _metric_values(observed, predictions, config.metric_profile)
    if not np.all(np.isfinite(row)) or np.any(row < 0):
        raise ValueError("computed branch metrics are not finite and nonnegative")
    return row


def build_branch_metric_matrix(
    observation: ReceiverObservation,
    trellis: AugmentedTrellis,
    config: MultipathReceiverConfig,
) -> NDArray[np.float64]:
    """Build all branch rows, reusing the time-invariant static-channel templates.

    Only warm-up and terminal rows need per-row prediction. In the interior, a
    static integer-delay ZOH channel depends on the expanded node's phase history
    and current edge, not on the absolute symbol index.
    """
    if type(observation) is not ReceiverObservation:
        raise TypeError("observation must be ReceiverObservation; channel truth is forbidden")
    expected = config.expected_symbol_count * 8 + config.maximum_delay_samples
    received = np.asarray(observation.received_samples)
    if observation.samples_per_symbol != 8 or received.dtype != np.dtype(np.complex128):
        raise ValueError("observation must use eight complex128 samples per symbol")
    if received.shape != (expected,):
        raise ValueError(f"observation length must equal {expected} for this delay profile")
    count, edges = config.expected_symbol_count, len(trellis.edges)
    rows = np.empty((count, edges), dtype=np.float64)
    memory = trellis.memory_symbols
    interior = memory < count - 1
    template: NDArray[np.complex128] | None = None
    if interior:
        symbol = memory
        indices = np.arange(symbol * 8, symbol * 8 + 8, dtype=np.int64)
        template = np.empty((edges, 8), dtype=np.complex128)
        for edge in trellis.edges:
            template[edge.expanded_edge_id] = predict_transition_samples(
                edge,
                trellis,
                symbol_index=symbol,
                frame_symbols=count,
                config=config,
                sample_indices=indices,
            )
    for symbol in range(count):
        indices = branch_sample_indices(symbol, count, config.maximum_delay_samples)
        observed = received[indices]
        if template is not None and memory <= symbol < count - 1:
            predictions = template
        else:
            predictions = np.empty((edges, len(indices)), dtype=np.complex128)
            for edge in trellis.edges:
                predictions[edge.expanded_edge_id] = predict_transition_samples(
                    edge,
                    trellis,
                    symbol_index=symbol,
                    frame_symbols=count,
                    config=config,
                    sample_indices=indices,
                )
        rows[symbol] = _metric_values(observed, predictions, config.metric_profile)
    if not np.all(np.isfinite(rows)) or np.any(rows < 0):
        raise ValueError("computed branch metrics are not finite and nonnegative")
    return rows


def _metric_values(
    observed: NDArray[np.complex128],
    predictions: NDArray[np.complex128],
    metric_profile: str,
) -> NDArray[np.float64]:
    residual = observed[None, :] - predictions
    squared = np.sum(residual.real * residual.real + residual.imag * residual.imag, axis=1)
    if metric_profile == "euclidean":
        return np.sqrt(squared, dtype=np.float64)
    return np.asarray(squared, dtype=np.float64)
