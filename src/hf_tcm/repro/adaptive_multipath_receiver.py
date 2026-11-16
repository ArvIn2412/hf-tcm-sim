"""Causal survivor-specific adaptive multipath TCM receiver (REPRO-06C)."""

from __future__ import annotations

import hashlib
import json
import platform
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.adaptive_multipath_config import AdaptiveMultipathReceiverConfig
from hf_tcm.repro.augmented_trellis import build_augmented_trellis
from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.expanded_viterbi import (
    ExpandedDecisionRecord,
    ExpandedViterbiConfig,
    run_expanded_viterbi,
)
from hf_tcm.repro.identifiers import MAPPING_STATUS
from hf_tcm.repro.isi_metrics import branch_sample_indices
from hf_tcm.repro.survivor_channel_estimator import (
    EstimatorState,
    build_delayed_regressor,
    initial_estimator_state,
    update_estimator_sample,
)


@dataclass(frozen=True, slots=True)
class AdaptiveMultipathReceiverResult:
    receiver_config: dict[str, Any]
    observation_sha256: str
    config_sha256: str
    result_sha256: str
    receiver_profile_id: str
    metric_profile: str
    trellis_state_count: int
    trellis_edge_count: int
    branch_metric_rows: NDArray[np.float64]
    survivor_path_metrics: NDArray[np.float64]
    estimator_mean_by_symbol_node: NDArray[np.complex128]
    estimator_covariance_diag_by_symbol_node: NDArray[np.float64]
    decoded_information_pairs: NDArray[np.int8]
    decoded_information_bits: NDArray[np.int8]
    decoded_edge_ids: NDArray[np.int16]
    decoded_state_path: NDArray[np.int8]
    decisions: tuple[ExpandedDecisionRecord, ...]
    decoder_mode: str
    traceback_depth: int | None
    survivor_buffer_max_rows: int
    final_path_metric: float
    diagnostics: dict[str, Any]
    reproducibility_metadata: dict[str, Any]


def _validate_observation(
    observation: ReceiverObservation, config: AdaptiveMultipathReceiverConfig
) -> None:
    if type(observation) is not ReceiverObservation:
        raise TypeError(
            "observation must be ReceiverObservation; EvaluationTruth/ChannelResult are forbidden"
        )
    count = config.expected_symbol_count
    expected = count * 8 + max(config.delays_samples)
    arrays = (
        observation.received_samples,
        observation.absolute_sample_index,
        observation.sample_symbol_index,
        observation.sample_local_index,
    )
    if observation.samples_per_symbol != 8 or observation.boundary_policy != "zero_extension":
        raise ValueError("REPRO-06C requires 8 samples/symbol and zero_extension")
    if any(np.asarray(a).shape != (expected,) for a in arrays):
        raise ValueError(f"observation arrays must contain exactly {expected} samples")
    if np.asarray(observation.received_samples).dtype != np.complex128:
        raise ValueError("received_samples must use complex128")
    indices = np.arange(expected, dtype=np.int64)
    if not np.array_equal(observation.absolute_sample_index, indices):
        raise ValueError("absolute sample indices must be contiguous from zero")
    if not np.array_equal(observation.sample_symbol_index, indices // 8):
        raise ValueError("sample-to-symbol index metadata is inconsistent")
    if not np.array_equal(observation.sample_local_index, indices % 8):
        raise ValueError("local sample index metadata is inconsistent")
    if not np.all(np.isfinite(observation.received_samples)):
        raise ValueError("received_samples must be finite")


def run_adaptive_multipath_receiver(
    observation: ReceiverObservation,
    config: AdaptiveMultipathReceiverConfig,
) -> AdaptiveMultipathReceiverResult:
    """Decode using per-destination survivor filters and pre-update branch metrics.

    The candidate metric is computed from a no-observation forecast of the
    predecessor's channel state. For each destination, only its minimum-cost
    incoming edge is then measured/updated and transferred to that destination.
    This is a survivor-path approximation, not global joint ML over channel paths.
    """
    if not isinstance(config, AdaptiveMultipathReceiverConfig):
        raise TypeError("config must be AdaptiveMultipathReceiverConfig")
    _validate_observation(observation, config)
    started = time.perf_counter()
    trellis = build_augmented_trellis(config.initial_state, config.delays_samples)
    count, state_count, edge_count = (
        config.expected_symbol_count,
        trellis.state_count,
        trellis.edge_count,
    )
    received = np.asarray(observation.received_samples)
    path_metrics = np.full(state_count, np.inf, dtype=np.float64)
    path_metrics[trellis.initial_node_id] = 0.0
    bank: list[EstimatorState | None] = [None] * state_count
    bank[trellis.initial_node_id] = initial_estimator_state(config)
    rows = np.full((count, edge_count), np.inf, dtype=np.float64)
    means_history = np.full(
        (count, state_count, len(config.paths)), np.nan + 1j * np.nan, dtype=np.complex128
    )
    covariance_history = np.full((count, state_count, len(config.paths)), np.nan, dtype=np.float64)
    survivor_edges = np.full((count, state_count), -1, dtype=np.int32)
    path_metric_history = np.full((count, state_count), np.inf, dtype=np.float64)
    update_innovation_energy = np.zeros((count, state_count), dtype=np.float64)
    prediction_seconds = 0.0
    update_seconds = 0.0
    regressor_templates: dict[int, NDArray[np.complex128]] = {}
    if count > 3:
        template_indices = np.arange(16, 24, dtype=np.int64)
        for edge in trellis.edges:
            regressor_templates[edge.expanded_edge_id] = build_delayed_regressor(
                edge,
                trellis,
                symbol_index=2,
                frame_symbols=count,
                delays_samples=config.delays_samples,
                sample_indices=template_indices,
                amplitude=config.amplitude,
                phase_offset_rad=config.phase_offset_rad,
                phase_increment_rad=config.phase_increment_rad,
            )
    for symbol_index in range(count):
        indices = branch_sample_indices(symbol_index, count, max(config.delays_samples))
        # All branch scores use the exact pre-update state of their predecessor survivor.
        prediction_started = time.perf_counter()
        forecast_by_source: dict[int, NDArray[np.complex128]] = {}
        for node_id, state in enumerate(bank):
            if state is None or not np.isfinite(path_metrics[node_id]):
                continue
            forecast = np.empty((len(indices), len(config.paths)), dtype=np.complex128)
            mean = np.array(state.mean, copy=True)
            public_mean = np.asarray([path.public_mean for path in config.paths])
            for local, sample_index in enumerate(indices):
                if state.last_sample_index >= 0 or local > 0:
                    if config.channel_mode != "unknown_static":
                        mean = public_mean + config.correlation * (mean - public_mean)
                forecast[local] = mean
            forecast_by_source[node_id] = forecast
        for edge in trellis.edges:
            state = bank[edge.source_node_id]
            if state is None or not np.isfinite(path_metrics[edge.source_node_id]):
                continue
            regressors = regressor_templates.get(edge.expanded_edge_id)
            if regressors is None or len(indices) != 8:
                regressors = build_delayed_regressor(
                    edge,
                    trellis,
                    symbol_index=symbol_index,
                    frame_symbols=count,
                    delays_samples=config.delays_samples,
                    sample_indices=indices,
                    amplitude=config.amplitude,
                    phase_offset_rad=config.phase_offset_rad,
                    phase_increment_rad=config.phase_increment_rad,
                )
            predicted = np.sum(regressors * forecast_by_source[edge.source_node_id], axis=1)
            residual = received[indices] - predicted
            squared = float(np.vdot(residual, residual).real)
            rows[symbol_index, edge.expanded_edge_id] = (
                np.sqrt(squared) if config.metric_profile == "euclidean" else squared
            )
        prediction_seconds += time.perf_counter() - prediction_started
        next_metrics = np.full(state_count, np.inf, dtype=np.float64)
        predecessors = np.full(state_count, -1, dtype=np.int32)
        # Canonical edge order establishes deterministic ties by strict < comparison.
        for edge in trellis.edges:
            branch = rows[symbol_index, edge.expanded_edge_id]
            candidate = path_metrics[edge.source_node_id] + branch
            if candidate < next_metrics[edge.target_node_id]:
                next_metrics[edge.target_node_id] = candidate
                predecessors[edge.target_node_id] = edge.expanded_edge_id
        next_bank: list[EstimatorState | None] = [None] * state_count
        update_started = time.perf_counter()
        for target_node, edge_id in enumerate(predecessors):
            if edge_id < 0:
                continue
            edge = trellis.edges[int(edge_id)]
            source_filter = bank[edge.source_node_id]
            assert source_filter is not None
            x = regressor_templates.get(edge.expanded_edge_id)
            if x is None or len(indices) != 8:
                x = build_delayed_regressor(
                    edge,
                    trellis,
                    symbol_index=symbol_index,
                    frame_symbols=count,
                    delays_samples=config.delays_samples,
                    sample_indices=indices,
                    amplitude=config.amplitude,
                    phase_offset_rad=config.phase_offset_rad,
                    phase_increment_rad=config.phase_increment_rad,
                )
            # Use the selected destination branch's exact design, without changing branch costs.
            current = source_filter
            innovations = []
            for local, sample_index in enumerate(indices):
                current, innovation = update_estimator_sample(
                    current,
                    x[local],
                    complex(received[sample_index]),
                    config,
                    sample_index=int(sample_index),
                )
                innovations.append(innovation)
            updated = current
            innovation_energy = float(np.mean(np.abs(innovations) ** 2))
            next_bank[target_node] = EstimatorState(
                updated.mean, updated.covariance, updated.last_sample_index, target_node
            )
            means_history[symbol_index, target_node] = updated.mean
            covariance_history[symbol_index, target_node] = np.real(np.diag(updated.covariance))
            update_innovation_energy[symbol_index, target_node] = innovation_energy
            survivor_edges[symbol_index, target_node] = int(edge_id)
        path_metrics, bank = next_metrics, next_bank
        path_metric_history[symbol_index] = path_metrics
        update_seconds += time.perf_counter() - update_started
    terminal_nodes = (
        tuple(node.node_id for node in trellis.nodes if node.encoder_state == (0, 0))
        if config.termination_policy == "zero_tail_2"
        else ()
    )
    forced_tail = ((0, 0), (0, 0)) if config.termination_policy == "zero_tail_2" else ()
    vit = run_expanded_viterbi(
        rows,
        trellis,
        ExpandedViterbiConfig(
            decoder_mode=config.decoder_mode,
            traceback_depth=config.traceback_depth,
            expected_symbol_count=count,
            forced_tail_input_pairs=forced_tail,
            terminal_node_ids=terminal_nodes,
            trace_output_mode="compact",
        ),
    )
    # Diagnostic predictions are reconstructed only after decoding from the
    # pre-update estimates stored for each emitted local decision. They never
    # feed back into metrics, survivor selection, or estimator updates.
    emitted_prediction = np.full(received.shape, np.nan + 1j * np.nan, dtype=np.complex128)
    for decision in vit.decisions:
        indices = branch_sample_indices(decision.symbol_index, count, max(config.delays_samples))
        edge = trellis.edges[decision.expanded_edge_id]
        if decision.symbol_index == 0:
            pre_mean = initial_estimator_state(config).mean
        else:
            pre_mean = means_history[decision.symbol_index - 1, edge.source_node_id]
        if not np.all(np.isfinite(pre_mean)):
            continue
        regressors = build_delayed_regressor(
            edge,
            trellis,
            symbol_index=decision.symbol_index,
            frame_symbols=count,
            delays_samples=config.delays_samples,
            sample_indices=indices,
            amplitude=config.amplitude,
            phase_offset_rad=config.phase_offset_rad,
            phase_increment_rad=config.phase_increment_rad,
        )
        forecast = np.array(pre_mean, copy=True)
        public_mean = np.asarray([path.public_mean for path in config.paths])
        values = np.empty(len(indices), dtype=np.complex128)
        for local in range(len(indices)):
            if decision.symbol_index > 0 or local > 0:
                if config.channel_mode != "unknown_static":
                    forecast = public_mean + config.correlation * (forecast - public_mean)
            values[local] = regressors[local] @ forecast
        emitted_prediction[indices] = values
    config_snapshot = config.to_dict()
    config_hash = hashlib.sha256(
        json.dumps(config_snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    digest = hashlib.sha256()
    for array in (
        rows,
        path_metric_history,
        means_history,
        covariance_history,
        survivor_edges,
        update_innovation_energy,
        emitted_prediction,
        vit.information_pairs,
        vit.decoded_information_bits,
        vit.decoded_edge_ids,
        vit.decoded_state_path,
    ):
        data = np.ascontiguousarray(array)
        digest.update(str(data.dtype).encode())
        digest.update(np.asarray(data.shape, dtype=np.int64).tobytes())
        digest.update(data.tobytes())
    elapsed = time.perf_counter() - started
    return AdaptiveMultipathReceiverResult(
        receiver_config=config_snapshot,
        observation_sha256=observation.sha256,
        config_sha256=config_hash,
        result_sha256=digest.hexdigest(),
        receiver_profile_id=config.profile_id,
        metric_profile=config.metric_profile,
        trellis_state_count=state_count,
        trellis_edge_count=edge_count,
        branch_metric_rows=rows,
        survivor_path_metrics=path_metric_history,
        estimator_mean_by_symbol_node=means_history,
        estimator_covariance_diag_by_symbol_node=covariance_history,
        decoded_information_pairs=vit.information_pairs,
        decoded_information_bits=vit.decoded_information_bits,
        decoded_edge_ids=vit.decoded_edge_ids,
        decoded_state_path=vit.decoded_state_path,
        decisions=vit.decisions,
        decoder_mode=vit.decoder_mode,
        traceback_depth=vit.traceback_depth,
        survivor_buffer_max_rows=vit.survivor_buffer_max_rows,
        final_path_metric=vit.survivor_final_metric,
        diagnostics={
            "causal_order": "pre-update prediction -> metric -> winner selection -> winner-only sample updates",
            "innovation_energy_by_symbol_node": update_innovation_energy,
            "survivor_edges_by_symbol_node": survivor_edges,
            "predicted_samples_on_emitted_decisions": emitted_prediction,
            "frame_tail_samples_scored": max(config.delays_samples),
            "mapping_status": MAPPING_STATUS,
            "algorithm_status": "survivor-specific adaptive approximation; not global joint ML",
            "elapsed_seconds": elapsed,
            "candidate_prediction_seconds": prediction_seconds,
            "estimator_update_seconds": update_seconds,
            "expanded_trellis_states": state_count,
            "expanded_trellis_edges": edge_count,
        },
        reproducibility_metadata={
            "python": platform.python_version(),
            "numpy": np.__version__,
            "observation_sha256": observation.sha256,
            "config_sha256": config_hash,
            "result_arrays_sha256": digest.hexdigest(),
        },
    )
