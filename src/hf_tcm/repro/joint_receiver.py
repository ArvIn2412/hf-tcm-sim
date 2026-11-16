"""Causal single-path joint Euclidean receiver for REPRO-05."""

from __future__ import annotations

import hashlib
import json
import platform
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.encoder import EDGE_ORDER_ID, encode, transition_table
from hf_tcm.repro.euclidean_metric import euclidean_metric_rows
from hf_tcm.repro.finite_viterbi import DecisionRecord, ViterbiConfig, run_viterbi
from hf_tcm.repro.identifiers import ENCODER_ID, MAPPING_ID, MAPPING_STATUS
from hf_tcm.repro.joint_estimator import update_complex_estimate
from hf_tcm.repro.joint_posterior import posterior_weights
from hf_tcm.repro.joint_receiver_config import JointReceiverConfig
from hf_tcm.repro.joint_viterbi import decode_joint_viterbi
from hf_tcm.repro.labeling import build_edge_mapping

JOINT_RECEIVER_PROFILE_ID = "repro05_causal_single_path_joint_euclidean_v1"
_EDGES = transition_table()


def _immutable(values: object, dtype: np.dtype | None = None) -> NDArray[Any]:
    owned = np.ascontiguousarray(values, dtype=dtype)
    return np.frombuffer(owned.tobytes(), dtype=owned.dtype).reshape(owned.shape)


@dataclass(frozen=True, slots=True)
class JointReceiverResult:
    receiver_config: dict[str, Any]
    observation_sha256: str
    config_sha256: str
    receiver_profile_id: str
    metric_profile: str
    encoder_id: str
    mapping_id: str
    mapping_status: str
    mapping_fingerprint: str
    edge_order_id: str
    candidate_edge_ids: NDArray[np.int16]
    candidate_source_states: NDArray[np.int8]
    candidate_target_states: NDArray[np.int8]
    candidate_input_pairs: NDArray[np.int8]
    candidate_coded_triples: NDArray[np.int8]
    candidate_phase_indices: NDArray[np.int8]
    candidate_symbols: NDArray[np.complex128]
    candidate_estimator_state_used: NDArray[np.complex128]
    sample_indices: NDArray[np.int64]
    sample_ranges: NDArray[np.int64]
    unprocessed_sample_indices: NDArray[np.int64]
    candidate_predictions: NDArray[np.complex128]
    metric_rows: NDArray[np.float64]
    posterior_weights: NDArray[np.float64]
    estimator_state_pre: NDArray[np.complex128]
    estimator_pre: NDArray[np.complex128]
    estimator_state_post: NDArray[np.complex128]
    estimator_post: NDArray[np.complex128]
    innovation: NDArray[np.complex128]
    viterbi_state_metrics: NDArray[np.float64]
    survivor_edge_ids: NDArray[np.int16]
    decoded_edge_ids: NDArray[np.int16]
    decoded_state_path: NDArray[np.int8]
    decoded_information_pairs: NDArray[np.int8]
    decoded_information_bits: NDArray[np.int8]
    decoded_frame_information_bits: NDArray[np.int8]
    final_state: tuple[int, int]
    final_path_metric: float
    traceback_mode: str
    decoder_depth: int | None
    diagnostics: dict[str, Any]
    reproducibility_metadata: dict[str, Any]
    result_sha256: str


def _validate_observation(observation: ReceiverObservation, config: JointReceiverConfig) -> None:
    if type(observation) is not ReceiverObservation:
        raise TypeError(
            "observation must be an exact REPRO-03 ReceiverObservation; truth is forbidden"
        )
    if observation.samples_per_symbol != 8:
        raise ValueError("REPRO-05 requires 8 samples per symbol")
    if "multipath" in observation.profile_id.lower():
        raise ValueError(
            "MULTIPATH_JOINT_RECEIVER_PARTIAL: delayed multipath requires a memory-aware ISI predictor"
        )
    arrays = (
        observation.received_samples,
        observation.absolute_sample_index,
        observation.sample_symbol_index,
        observation.sample_local_index,
    )
    if any(np.asarray(item).ndim != 1 for item in arrays):
        raise ValueError("ReceiverObservation arrays must be one-dimensional")
    if np.asarray(observation.received_samples).dtype != np.dtype(np.complex128):
        raise ValueError("received_samples must be complex128")
    if any(np.asarray(item).dtype != np.dtype(np.int64) for item in arrays[1:]):
        raise ValueError("observation timing metadata must be int64")
    length = len(observation.received_samples)
    if length == 0 or any(len(array) != length for array in arrays):
        raise ValueError("observation arrays must have equal nonzero lengths")
    indexes = np.arange(length, dtype=np.int64)
    if not np.array_equal(observation.absolute_sample_index, indexes):
        raise ValueError("absolute sample indices must be contiguous from zero")
    if not np.array_equal(observation.sample_symbol_index, indexes // 8) or not np.array_equal(
        observation.sample_local_index, indexes % 8
    ):
        raise ValueError("observation sample-to-symbol metadata is inconsistent")
    if not np.all(np.isfinite(observation.received_samples)):
        raise ValueError("received samples must be finite")
    required = config.expected_symbol_count * 8
    if length < required:
        raise ValueError(f"observation has {length} samples; expected at least {required}")


def run_joint_receiver(
    observation: ReceiverObservation, receiver_config: JointReceiverConfig
) -> JointReceiverResult:
    """Decode directly from 16 edge-distance rows; no hard 8PSK demodulation stage."""
    if not isinstance(receiver_config, JointReceiverConfig):
        raise TypeError("receiver_config must be JointReceiverConfig")
    _validate_observation(observation, receiver_config)
    config = receiver_config
    started = time.perf_counter()
    count, offset = config.expected_symbol_count, config.timing_offset_samples
    used_count = 8 - offset
    samples = np.empty((count, used_count), dtype=np.complex128)
    ranges = np.empty((count, 2), dtype=np.int64)
    for k in range(count):
        start, stop = k * 8 + offset, (k + 1) * 8
        samples[k] = observation.received_samples[start:stop]
        ranges[k] = (start, stop - 1)
    sample_indices = np.concatenate(
        [np.arange(start, stop + 1, dtype=np.int64) for start, stop in ranges]
    )
    used_mask = np.zeros(len(observation.received_samples), dtype=bool)
    used_mask[sample_indices] = True
    unprocessed_indices = np.flatnonzero(~used_mask).astype(np.int64)

    edge_phases = np.empty(16, dtype=np.int8)
    for edge_id, _source, _pair, coded, _target in _EDGES:
        edge_phases[edge_id] = 4 * coded[0] + 2 * coded[1] + coded[2]
    candidate_edge_ids = np.arange(16, dtype=np.int16)
    candidate_source_states = np.asarray([edge[1] for edge in _EDGES], dtype=np.int8)
    candidate_input_pairs = np.asarray([edge[2] for edge in _EDGES], dtype=np.int8)
    candidate_coded_triples = np.asarray([edge[3] for edge in _EDGES], dtype=np.int8)
    candidate_target_states = np.asarray([edge[4] for edge in _EDGES], dtype=np.int8)
    symbols = config.amplitude * np.exp(
        1j * (config.phase_offset_rad + edge_phases.astype(np.float64) * config.phase_increment_rad)
    )
    waveform = np.broadcast_to(symbols[None, :, None], (count, 16, used_count)).copy()
    state_pre = np.empty(count, dtype=np.complex128)
    channel_pre = np.empty(count, dtype=np.complex128)
    state_post = np.empty(count, dtype=np.complex128)
    channel_post = np.empty(count, dtype=np.complex128)
    innovations = np.empty(count, dtype=np.complex128)
    metric_rows = np.empty((count, 16), dtype=np.float64)
    weights = np.empty((count, 16), dtype=np.float64)
    predictions = np.empty((count, 16, used_count), dtype=np.complex128)
    base = (
        complex(config.known_static_gain)
        if config.channel_mode == "known_static_complex_gain"
        else complex(config.mu0)
    )
    state = complex(config.initial_state_value)
    prediction_seconds = metric_seconds = posterior_estimator_seconds = 0.0
    for k in range(count):
        state_pre[k] = state
        channel = base + state
        channel_pre[k] = channel
        phase_start = time.perf_counter()
        predictions[k] = channel * waveform[k]
        prediction_seconds += time.perf_counter() - phase_start
        phase_start = time.perf_counter()
        metric_rows[k] = euclidean_metric_rows(
            samples[k : k + 1], predictions[k : k + 1], profile=config.metric_profile
        )[0]
        metric_seconds += time.perf_counter() - phase_start
        phase_start = time.perf_counter()
        weights[k] = posterior_weights(metric_rows[k], beta=config.beta)
        residuals = samples[k][None, :] - predictions[k]
        updated, innovations[k] = update_complex_estimate(
            state_pre=state,
            residuals=residuals,
            weights=weights[k],
            alpha_prime=config.alpha_prime,
            k_tilde=config.k_tilde,
            mu0=config.mu0,
        )
        if config.estimator_policy == "frozen":
            updated = state
        state = updated
        state_post[k] = state
        channel_post[k] = base + state
        posterior_estimator_seconds += time.perf_counter() - phase_start

    estimator_used_by_candidate = np.repeat(channel_pre[:, None], 16, axis=1)
    viterbi_started = time.perf_counter()
    if config.decoder_mode == "finite_depth":
        vit = run_viterbi(
            metric_rows,
            ViterbiConfig(
                initial_state=config.initial_state,
                traceback_depth=config.traceback_depth,
                decoder_mode="finite_depth",
                expected_symbol_count=config.expected_symbol_count,
                termination_policy=config.termination_policy,
                final_state_policy=config.final_state_policy,
                tie_break_policy=config.tie_break_policy,
                trace_output_mode=config.trace_output_mode,
            ),
        )
    else:
        vit = decode_joint_viterbi(
            metric_rows,
            initial_state=config.initial_state,
            termination_policy=config.termination_policy,
        )
    viterbi_seconds = time.perf_counter() - viterbi_started
    frame_bits = vit.information_pairs.reshape(-1)
    tail_bits = 4 if config.termination_policy == "zero_tail_2" else 0
    decoded_bits = frame_bits[:-tail_bits] if tail_bits else frame_bits
    if config.decoder_mode == "finite_depth":
        decision_records = vit.decisions
    else:
        decision_records = tuple(
            DecisionRecord(
                symbol_index=index,
                decision_available_at=count - 1,
                traceback_depth_used=count,
                edge_id=int(edge_id),
                input_pair=tuple(int(bit) for bit in vit.information_pairs[index]),
                source_state=tuple(int(bit) for bit in vit.state_path[index]),
                target_state=tuple(int(bit) for bit in vit.state_path[index + 1]),
                decoder_mode="full_frame",
                decision_policy="full_frame_terminal_survivor",
            )
            for index, edge_id in enumerate(vit.decoded_edge_ids)
        )
    decision_arrays = (
        np.asarray([row.symbol_index for row in decision_records], dtype=np.int64),
        np.asarray([row.decision_available_at for row in decision_records], dtype=np.int64),
        np.asarray([row.traceback_depth_used for row in decision_records], dtype=np.int64),
        np.asarray([row.edge_id for row in decision_records], dtype=np.int16),
        np.asarray([row.input_pair for row in decision_records], dtype=np.int8).reshape((-1, 2)),
        np.asarray([row.source_state for row in decision_records], dtype=np.int8).reshape((-1, 2)),
        np.asarray([row.target_state for row in decision_records], dtype=np.int8).reshape((-1, 2)),
    )
    arrays = (
        sample_indices,
        ranges,
        unprocessed_indices,
        candidate_edge_ids,
        candidate_source_states,
        candidate_target_states,
        candidate_input_pairs,
        candidate_coded_triples,
        edge_phases,
        symbols,
        estimator_used_by_candidate,
        predictions,
        metric_rows,
        weights,
        state_pre,
        channel_pre,
        state_post,
        channel_post,
        innovations,
        vit.state_metrics,
        vit.survivor_edge_ids,
        vit.decoded_edge_ids,
        vit.state_path,
        vit.information_pairs,
        decoded_bits,
        *decision_arrays,
    )
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(np.asarray(contiguous.shape, dtype=np.int64).tobytes())
        digest.update(contiguous.tobytes())
    config_canonical = json.dumps(config.to_dict(), sort_keys=True, separators=(",", ":"))
    config_hash = hashlib.sha256(config_canonical.encode("utf-8")).hexdigest()
    elapsed = time.perf_counter() - started
    array_bytes = int(sum(np.asarray(array).nbytes for array in arrays))
    metadata = {
        "schema_version": config.schema_version,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "observation_sha256": observation.sha256,
        "config_sha256": config_hash,
        "output_arrays_sha256": digest.hexdigest(),
        "wall_time_seconds": elapsed,
        "candidate_prediction_seconds": prediction_seconds,
        "metric_seconds": metric_seconds,
        "posterior_estimator_seconds": posterior_estimator_seconds,
        "viterbi_seconds": viterbi_seconds,
        "array_storage_bytes": array_bytes,
    }
    mapping_fingerprint = build_edge_mapping(
        encode(np.asarray([[0, 0]], dtype=np.int8))
    ).fingerprint

    return JointReceiverResult(
        receiver_config=config.to_dict(),
        observation_sha256=observation.sha256,
        config_sha256=config_hash,
        receiver_profile_id=JOINT_RECEIVER_PROFILE_ID,
        metric_profile=config.metric_profile,
        encoder_id=ENCODER_ID,
        mapping_id=MAPPING_ID,
        mapping_status=MAPPING_STATUS,
        mapping_fingerprint=mapping_fingerprint,
        edge_order_id=EDGE_ORDER_ID,
        candidate_edge_ids=_immutable(candidate_edge_ids, np.dtype(np.int16)),
        candidate_source_states=_immutable(candidate_source_states, np.dtype(np.int8)),
        candidate_target_states=_immutable(candidate_target_states, np.dtype(np.int8)),
        candidate_input_pairs=_immutable(candidate_input_pairs, np.dtype(np.int8)),
        candidate_coded_triples=_immutable(candidate_coded_triples, np.dtype(np.int8)),
        candidate_phase_indices=_immutable(edge_phases, np.dtype(np.int8)),
        candidate_symbols=_immutable(symbols, np.dtype(np.complex128)),
        candidate_estimator_state_used=_immutable(
            estimator_used_by_candidate, np.dtype(np.complex128)
        ),
        sample_indices=_immutable(sample_indices, np.dtype(np.int64)),
        sample_ranges=_immutable(ranges, np.dtype(np.int64)),
        unprocessed_sample_indices=_immutable(unprocessed_indices, np.dtype(np.int64)),
        candidate_predictions=_immutable(predictions, np.dtype(np.complex128)),
        metric_rows=_immutable(metric_rows, np.dtype(np.float64)),
        posterior_weights=_immutable(weights, np.dtype(np.float64)),
        estimator_state_pre=_immutable(state_pre, np.dtype(np.complex128)),
        estimator_pre=_immutable(channel_pre, np.dtype(np.complex128)),
        estimator_state_post=_immutable(state_post, np.dtype(np.complex128)),
        estimator_post=_immutable(channel_post, np.dtype(np.complex128)),
        innovation=_immutable(innovations, np.dtype(np.complex128)),
        viterbi_state_metrics=_immutable(vit.state_metrics, np.dtype(np.float64)),
        survivor_edge_ids=_immutable(vit.survivor_edge_ids, np.dtype(np.int16)),
        decoded_edge_ids=_immutable(vit.decoded_edge_ids, np.dtype(np.int16)),
        decoded_state_path=_immutable(vit.state_path, np.dtype(np.int8)),
        decoded_information_pairs=_immutable(vit.information_pairs, np.dtype(np.int8)),
        decoded_information_bits=_immutable(decoded_bits, np.dtype(np.int8)),
        decoded_frame_information_bits=_immutable(frame_bits, np.dtype(np.int8)),
        final_state=vit.final_state,
        final_path_metric=vit.final_metric,
        traceback_mode=config.decoder_mode,
        decoder_depth=config.traceback_depth,
        diagnostics={
            "receiver_mode": "joint_euclidean_edge_metric_viterbi",
            "hard_demodulation_used": False,
            "estimator_policy": config.estimator_policy,
            "channel_mode": config.channel_mode,
            "posterior_semantics": "flat_prior_soft_edge_pseudo_posterior_project_reconstruction",
            "multipath_status": "MULTIPATH_JOINT_RECEIVER_PARTIAL",
            "full_frame_traceback": config.decoder_mode == "full_frame",
            "eta_claimed": config.decoder_mode == "finite_depth",
            "initial_state_policy": config.initial_state_policy,
            "final_state_policy": config.final_state_policy,
            "tie_break_policy": config.tie_break_policy,
            "trace_output_mode": config.trace_output_mode,
            "survivor_buffer_max_rows": getattr(vit, "survivor_buffer_max_rows", count),
            "terminal_survivor_state": list(getattr(vit, "survivor_final_state", vit.final_state)),
            "decision_records": [
                {
                    "symbol_index": row.symbol_index,
                    "decision_available_at": row.decision_available_at,
                    "traceback_depth_used": row.traceback_depth_used,
                    "edge_id": row.edge_id,
                    "input_pair": list(row.input_pair),
                    "source_state": list(row.source_state),
                    "target_state": list(row.target_state),
                    "decoder_mode": row.decoder_mode,
                    "decision_policy": row.decision_policy,
                }
                for row in decision_records
            ],
            "unprocessed_sample_count": int(len(unprocessed_indices)),
            "paper_exact": False,
            "receiver_enabled": False,
        },
        reproducibility_metadata=metadata,
        result_sha256=digest.hexdigest(),
    )
