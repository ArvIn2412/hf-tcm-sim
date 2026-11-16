"""Truth-isolated static-CSI joint Euclidean MLSE over an ISI-expanded trellis."""

from __future__ import annotations

import hashlib
import json
import platform
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.augmented_trellis import AugmentedTrellis, build_augmented_trellis
from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.expanded_viterbi import (
    ExpandedDecisionRecord,
    ExpandedViterbiConfig,
    run_expanded_viterbi,
)
from hf_tcm.repro.identifiers import ENCODER_ID, MAPPING_ID, MAPPING_STATUS
from hf_tcm.repro.isi_metrics import branch_sample_indices, build_branch_metric_matrix
from hf_tcm.repro.isi_predictor import predict_transition_samples
from hf_tcm.repro.multipath_receiver_config import MultipathReceiverConfig

MULTIPATH_RECEIVER_PROFILE_ID = "repro06b_static_known_isi_joint_mlse_v1"


def _readonly(values: object, dtype: np.dtype | None = None) -> NDArray[Any]:
    array = np.ascontiguousarray(values, dtype=dtype)
    return np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape)


@dataclass(frozen=True, slots=True)
class MultipathJointReceiverResult:
    receiver_config: dict[str, Any]
    observation_sha256: str
    config_sha256: str
    result_sha256: str
    receiver_profile_id: str
    metric_profile: str
    encoder_id: str
    mapping_id: str
    mapping_status: str
    trellis_state_count: int
    trellis_edge_count: int
    channel_memory_symbols: int
    expanded_nodes: tuple[dict[str, Any], ...]
    expanded_edges: tuple[dict[str, Any], ...]
    sample_indices: NDArray[np.int64]
    sample_ranges: NDArray[np.int64]
    branch_metric_rows: NDArray[np.float64]
    diagnostic_symbol_index: int
    diagnostic_sample_indices: NDArray[np.int64]
    diagnostic_candidate_predictions: NDArray[np.complex128]
    survivor_state_metrics: NDArray[np.float64]
    survivor_expanded_edge_ids: NDArray[np.int32]
    decision_base_edge_ids: NDArray[np.int16]
    decoded_edge_ids: NDArray[np.int16]
    decoded_state_path: NDArray[np.int8]
    decoded_information_pairs: NDArray[np.int8]
    decoded_information_bits: NDArray[np.int8]
    decisions: tuple[ExpandedDecisionRecord, ...]
    final_state: tuple[int, int]
    terminal_survivor_node_id: int
    final_path_metric: float
    decoder_mode: str
    traceback_depth: int | None
    survivor_buffer_max_rows: int
    diagnostics: dict[str, Any]
    reproducibility_metadata: dict[str, Any]


def _validate_observation(
    observation: ReceiverObservation, config: MultipathReceiverConfig
) -> None:
    if type(observation) is not ReceiverObservation:
        raise TypeError("observation must be ReceiverObservation; ChannelResult/truth is forbidden")
    if observation.samples_per_symbol != 8:
        raise ValueError("REPRO-06B requires exactly 8 samples per symbol")
    arrays = (
        observation.received_samples,
        observation.absolute_sample_index,
        observation.sample_symbol_index,
        observation.sample_local_index,
    )
    if any(np.asarray(array).ndim != 1 for array in arrays):
        raise ValueError("ReceiverObservation arrays must be one-dimensional")
    if np.asarray(observation.received_samples).dtype != np.dtype(np.complex128):
        raise ValueError("received_samples must use complex128")
    if any(np.asarray(array).dtype != np.dtype(np.int64) for array in arrays[1:]):
        raise ValueError("ReceiverObservation timing arrays must use int64")
    expected_length = config.expected_symbol_count * 8 + config.maximum_delay_samples
    if len(observation.received_samples) != expected_length or any(
        len(array) != expected_length for array in arrays[1:]
    ):
        raise ValueError(f"observation length must be exactly {expected_length} samples")
    indices = np.arange(expected_length, dtype=np.int64)
    if not np.array_equal(observation.absolute_sample_index, indices):
        raise ValueError("absolute sample indices must be contiguous from zero")
    if not np.array_equal(observation.sample_symbol_index, indices // 8) or not np.array_equal(
        observation.sample_local_index, indices % 8
    ):
        raise ValueError("observation sample timing metadata is inconsistent")
    if not np.all(np.isfinite(observation.received_samples)):
        raise ValueError("received samples must be finite")
    if observation.boundary_policy != "zero_extension":
        raise ValueError("REPRO-06B requires the REPRO-03 zero_extension boundary policy")


def _trellis_json(trellis: AugmentedTrellis) -> tuple[tuple[dict, ...], tuple[dict, ...]]:
    nodes = tuple(
        {
            "node_id": node.node_id,
            "encoder_state": list(node.encoder_state),
            "previous_phase_history": list(node.phase_history),
        }
        for node in trellis.nodes
    )
    edges = tuple(
        {
            "expanded_edge_id": edge.expanded_edge_id,
            "source_node_id": edge.source_node_id,
            "target_node_id": edge.target_node_id,
            "base_edge_id": edge.base_edge_id,
            "input_pair": list(edge.input_pair),
            "coded_triple": list(edge.coded_triple),
            "phase_index": edge.phase_index,
        }
        for edge in trellis.edges
    )
    return nodes, edges


def run_multipath_joint_receiver(
    observation: ReceiverObservation, config: MultipathReceiverConfig
) -> MultipathJointReceiverResult:
    """Run static-known channel MLSE from observation and explicit public CSI only."""
    if not isinstance(config, MultipathReceiverConfig):
        raise TypeError("config must be MultipathReceiverConfig")
    _validate_observation(observation, config)
    started = time.perf_counter()
    trellis = build_augmented_trellis(
        config.initial_state,
        tuple(path.delay_samples for path in config.paths),
        samples_per_symbol=config.samples_per_symbol,
    )
    row_count, edge_count = config.expected_symbol_count, trellis.edge_count
    metric_started = time.perf_counter()
    metrics = build_branch_metric_matrix(observation, trellis, config)
    metric_seconds = time.perf_counter() - metric_started
    ranges = np.empty((row_count, 2), dtype=np.int64)
    prediction_seconds = 0.0
    diagnostic_indices = branch_sample_indices(
        config.diagnostic_symbol_index, row_count, config.maximum_delay_samples
    )
    diagnostic_predictions = np.empty((edge_count, len(diagnostic_indices)), dtype=np.complex128)
    for symbol_index in range(row_count):
        indices = branch_sample_indices(symbol_index, row_count, config.maximum_delay_samples)
        ranges[symbol_index] = (int(indices[0]), int(indices[-1]))
        if symbol_index == config.diagnostic_symbol_index:
            prediction_started = time.perf_counter()
            for edge in trellis.edges:
                diagnostic_predictions[edge.expanded_edge_id] = predict_transition_samples(
                    edge,
                    trellis,
                    symbol_index=symbol_index,
                    frame_symbols=row_count,
                    config=config,
                    sample_indices=indices,
                )
            prediction_seconds += time.perf_counter() - prediction_started
    scored_indices = np.arange(len(observation.received_samples), dtype=np.int64)
    if not np.array_equal(scored_indices, np.arange(len(observation.received_samples))):
        raise RuntimeError("branch windows did not score every received sample exactly once")

    terminal_nodes = (
        tuple(node.node_id for node in trellis.nodes if node.encoder_state == (0, 0))
        if config.final_state_policy == "known_terminated"
        else ()
    )
    forced_tail = ((0, 0), (0, 0)) if config.termination_policy == "zero_tail_2" else ()
    viterbi_started = time.perf_counter()
    vit = run_expanded_viterbi(
        metrics,
        trellis,
        ExpandedViterbiConfig(
            decoder_mode=config.decoder_mode,
            traceback_depth=config.traceback_depth,
            expected_symbol_count=row_count,
            forced_tail_input_pairs=forced_tail,
            terminal_node_ids=terminal_nodes,
            tie_break_policy=config.tie_break_policy,
            trace_output_mode=config.trace_output_mode,
        ),
    )
    viterbi_seconds = time.perf_counter() - viterbi_started
    nodes_json, edges_json = _trellis_json(trellis)
    config_snapshot = config.to_dict()
    config_hash = hashlib.sha256(
        json.dumps(config_snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    arrays = (
        scored_indices,
        ranges,
        metrics,
        diagnostic_indices,
        diagnostic_predictions,
        vit.state_metrics,
        vit.survivor_expanded_edge_ids,
        vit.decision_base_edge_ids,
        vit.decoded_edge_ids,
        vit.decoded_state_path,
        vit.information_pairs,
        vit.decoded_information_bits,
    )
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(np.asarray(contiguous.shape, dtype=np.int64).tobytes())
        digest.update(contiguous.tobytes())
    elapsed = time.perf_counter() - started
    metadata = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "observation_sha256": observation.sha256,
        "config_sha256": config_hash,
        "result_arrays_sha256": digest.hexdigest(),
        "wall_time_seconds": elapsed,
        "branch_metric_seconds": metric_seconds,
        "diagnostic_prediction_seconds": prediction_seconds,
        "expanded_viterbi_seconds": viterbi_seconds,
        "result_array_bytes": int(sum(np.asarray(array).nbytes for array in arrays)),
    }
    diagnostics = {
        "channel_mode": config.channel_mode,
        "isi_mode": config.isi_mode,
        "estimator_profile": config.estimator_profile,
        "adaptive_rician_multipath_status": "UNAVAILABLE_NOT_IMPLEMENTED",
        "scored_sample_count": int(len(scored_indices)),
        "tail_sample_indices": list(range(row_count * 8, len(observation.received_samples))),
        "tail_samples_assigned_to_symbol": row_count - 1,
        "receiver_truth_fields_used": [],
        "finite_depth_decisions_are_overlapping_survivor_decisions": (
            config.decoder_mode == "finite_depth"
        ),
        "decision_records": [
            {
                "symbol_index": row.symbol_index,
                "decision_available_at": row.decision_available_at,
                "traceback_depth_used": row.traceback_depth_used,
                "expanded_edge_id": row.expanded_edge_id,
                "base_edge_id": row.base_edge_id,
                "input_pair": list(row.input_pair),
                "encoder_source_state": list(row.encoder_source_state),
                "encoder_target_state": list(row.encoder_target_state),
                "source_node_id": row.source_node_id,
                "target_node_id": row.target_node_id,
                "source_phase_history": list(row.source_phase_history),
                "target_phase_history": list(row.target_phase_history),
                "decision_policy": row.decision_policy,
            }
            for row in vit.decisions
        ],
        "survivor_buffer_max_rows": vit.survivor_buffer_max_rows,
        "paper_exact": False,
        "receiver_enabled": False,
    }
    return MultipathJointReceiverResult(
        receiver_config=config_snapshot,
        observation_sha256=observation.sha256,
        config_sha256=config_hash,
        result_sha256=digest.hexdigest(),
        receiver_profile_id=MULTIPATH_RECEIVER_PROFILE_ID,
        metric_profile=config.metric_profile,
        encoder_id=ENCODER_ID,
        mapping_id=MAPPING_ID,
        mapping_status=MAPPING_STATUS,
        trellis_state_count=trellis.state_count,
        trellis_edge_count=trellis.edge_count,
        channel_memory_symbols=trellis.memory_symbols,
        expanded_nodes=nodes_json,
        expanded_edges=edges_json,
        sample_indices=_readonly(scored_indices, np.dtype(np.int64)),
        sample_ranges=_readonly(ranges, np.dtype(np.int64)),
        branch_metric_rows=_readonly(metrics, np.dtype(np.float64)),
        diagnostic_symbol_index=config.diagnostic_symbol_index,
        diagnostic_sample_indices=_readonly(diagnostic_indices, np.dtype(np.int64)),
        diagnostic_candidate_predictions=_readonly(diagnostic_predictions, np.dtype(np.complex128)),
        survivor_state_metrics=_readonly(vit.state_metrics, np.dtype(np.float64)),
        survivor_expanded_edge_ids=_readonly(vit.survivor_expanded_edge_ids, np.dtype(np.int32)),
        decision_base_edge_ids=_readonly(vit.decision_base_edge_ids, np.dtype(np.int16)),
        decoded_edge_ids=_readonly(vit.decoded_edge_ids, np.dtype(np.int16)),
        decoded_state_path=_readonly(vit.decoded_state_path, np.dtype(np.int8)),
        decoded_information_pairs=_readonly(vit.information_pairs, np.dtype(np.int8)),
        decoded_information_bits=_readonly(vit.decoded_information_bits, np.dtype(np.int8)),
        decisions=vit.decisions,
        final_state=tuple(int(bit) for bit in vit.decoded_state_path[-1]),
        terminal_survivor_node_id=vit.terminal_survivor_node_id,
        final_path_metric=vit.survivor_final_metric,
        decoder_mode=vit.decoder_mode,
        traceback_depth=vit.traceback_depth,
        survivor_buffer_max_rows=vit.survivor_buffer_max_rows,
        diagnostics=diagnostics,
        reproducibility_metadata=metadata,
    )
