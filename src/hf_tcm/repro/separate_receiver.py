"""REPRO-04 hard 8PSK plus Hamming-metric Encoder A receiver."""

from __future__ import annotations

import hashlib
import platform
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.encoder import EDGE_ORDER_ID
from hf_tcm.repro.finite_viterbi import DecisionRecord, ViterbiConfig, run_viterbi
from hf_tcm.repro.hamming_metric import hamming_metric_matrix
from hf_tcm.repro.hamming_viterbi import decode_hamming_viterbi
from hf_tcm.repro.hard_8psk_demodulator import demodulate_hard_8psk
from hf_tcm.repro.receiver_config import SeparateReceiverConfig


def _readonly(values: object, dtype: np.dtype | None = None) -> NDArray[Any]:
    array = np.ascontiguousarray(values, dtype=dtype)
    return np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape)


@dataclass(frozen=True, slots=True)
class SeparateReceiverResult:
    receiver_config: dict[str, Any]
    observation_sha256: str
    processed_sample_ranges: NDArray[np.int64]
    processed_sample_indices: NDArray[np.int64]
    unprocessed_sample_indices: NDArray[np.int64]
    hard_phase_indices: NDArray[np.int8]
    hard_coded_triples: NDArray[np.int8]
    hard_symbol_squared_distances: NDArray[np.float64]
    hamming_branch_metrics: NDArray[np.int8]
    accumulated_state_metrics: NDArray[np.int64]
    survivor_edge_ids: NDArray[np.int16]
    decoded_edge_ids: NDArray[np.int16]
    decoded_state_path: NDArray[np.int8]
    decoded_information_pairs: NDArray[np.int8]
    decoded_information_bits: NDArray[np.int8]
    decoded_frame_information_bits: NDArray[np.int8]
    final_state: tuple[int, int]
    final_path_metric: int
    edge_order_id: str
    mapping_id: str
    mapping_status: str
    traceback_mode: str
    decoder_depth: int | None
    diagnostics: dict[str, Any]
    reproducibility_metadata: dict[str, Any]


def _validate_observation(observation: ReceiverObservation, config: SeparateReceiverConfig) -> None:
    if type(observation) is not ReceiverObservation:
        raise TypeError(
            "observation must be a REPRO-03 ReceiverObservation; ChannelResult/truth is forbidden"
        )
    if observation.samples_per_symbol != 8:
        raise ValueError("REPRO-04 requires 8 samples per symbol")
    arrays = (
        observation.received_samples,
        observation.absolute_sample_index,
        observation.sample_symbol_index,
        observation.sample_local_index,
    )
    if any(np.asarray(item).ndim != 1 for item in arrays):
        raise ValueError("ReceiverObservation arrays must be one-dimensional")
    if np.asarray(observation.received_samples).dtype != np.dtype(np.complex128):
        raise ValueError("received_samples must use the REPRO-03 complex128 representation")
    if any(np.asarray(item).dtype != np.dtype(np.int64) for item in arrays[1:]):
        raise ValueError("ReceiverObservation timing arrays must use int64")
    length = len(observation.received_samples)
    if length == 0 or any(len(array) != length for array in arrays):
        raise ValueError("ReceiverObservation arrays must have equal nonzero length")
    if not np.all(np.isfinite(observation.received_samples)):
        raise ValueError("received_samples must be finite")
    indices = np.arange(length, dtype=np.int64)
    if not np.array_equal(observation.absolute_sample_index, indices):
        raise ValueError("absolute_sample_index must be contiguous and begin at zero")
    if not np.array_equal(observation.sample_symbol_index, indices // 8):
        raise ValueError("sample_symbol_index is inconsistent with 8 samples per symbol")
    if not np.array_equal(observation.sample_local_index, indices % 8):
        raise ValueError("sample_local_index is inconsistent with 8-sample timing")
    required = config.expected_symbol_count * 8
    if length < required:
        raise ValueError(
            f"observation has {length} samples, fewer than expected_symbol_count requires ({required})"
        )


def run_separate_receiver(
    observation: ReceiverObservation, receiver_config: SeparateReceiverConfig
) -> SeparateReceiverResult:
    """Run hard 8PSK classification followed by independent Hamming Viterbi."""
    if not isinstance(receiver_config, SeparateReceiverConfig):
        raise TypeError("receiver_config must be SeparateReceiverConfig")
    _validate_observation(observation, receiver_config)
    started = time.perf_counter()
    sample_indices = np.arange(len(observation.received_samples), dtype=np.int64)
    blocks = np.empty(
        (receiver_config.expected_symbol_count, 8 - receiver_config.timing_offset_samples),
        dtype=np.complex128,
    )
    ranges = np.empty((receiver_config.expected_symbol_count, 2), dtype=np.int64)
    used_indices: list[NDArray[np.int64]] = []
    for symbol in range(receiver_config.expected_symbol_count):
        start = symbol * 8 + receiver_config.timing_offset_samples
        stop = (symbol + 1) * 8
        indexes = np.arange(start, stop, dtype=np.int64)
        used_indices.append(indexes)
        blocks[symbol] = observation.received_samples[indexes]
        ranges[symbol] = (start, stop - 1)
    processed = np.concatenate(used_indices)
    mask = np.ones(len(observation.received_samples), dtype=bool)
    mask[processed] = False
    demod_started = time.perf_counter()
    demod = demodulate_hard_8psk(blocks, receiver_config.front_end)
    demod_seconds = time.perf_counter() - demod_started
    metric_started = time.perf_counter()
    metrics = hamming_metric_matrix(demod.coded_triples)
    metric_seconds = time.perf_counter() - metric_started
    viterbi_started = time.perf_counter()
    if receiver_config.decoder_mode == "finite_depth":
        decoded = run_viterbi(
            metrics,
            ViterbiConfig(
                initial_state=receiver_config.initial_state,
                traceback_depth=receiver_config.traceback_depth,
                decoder_mode="finite_depth",
                expected_symbol_count=receiver_config.expected_symbol_count,
                termination_policy=receiver_config.termination_policy,
                final_state_policy=receiver_config.final_state_policy,
                tie_break_policy=receiver_config.tie_break_policy,
                trace_output_mode=receiver_config.trace_output_mode,
            ),
        )
    else:
        decoded = decode_hamming_viterbi(
            metrics,
            initial_state=receiver_config.initial_state,
            termination_policy=receiver_config.termination_policy,
        )
    viterbi_seconds = time.perf_counter() - viterbi_started
    elapsed = time.perf_counter() - started
    frame_information_bits = decoded.information_pairs.reshape(-1)
    tail_bit_count = 4 if receiver_config.termination_policy == "zero_tail_2" else 0
    payload_information_bits = (
        frame_information_bits[:-tail_bit_count] if tail_bit_count else frame_information_bits
    )
    if receiver_config.decoder_mode == "finite_depth":
        decision_records = decoded.decisions
    else:
        decision_records = tuple(
            DecisionRecord(
                symbol_index=index,
                decision_available_at=receiver_config.expected_symbol_count - 1,
                traceback_depth_used=receiver_config.expected_symbol_count,
                edge_id=int(edge_id),
                input_pair=tuple(int(bit) for bit in decoded.information_pairs[index]),
                source_state=tuple(int(bit) for bit in decoded.state_path[index]),
                target_state=tuple(int(bit) for bit in decoded.state_path[index + 1]),
                decoder_mode="full_frame",
                decision_policy="full_frame_terminal_survivor",
            )
            for index, edge_id in enumerate(decoded.decoded_edge_ids)
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
        ranges,
        processed,
        sample_indices[mask],
        demod.phase_indices,
        demod.coded_triples,
        demod.squared_distances,
        metrics,
        decoded.path_metrics,
        decoded.survivor_edge_ids,
        decoded.decoded_edge_ids,
        decoded.state_path,
        decoded.information_pairs,
        payload_information_bits,
        *decision_arrays,
    )
    output_digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        output_digest.update(str(contiguous.dtype).encode("ascii"))
        output_digest.update(np.asarray(contiguous.shape, dtype=np.int64).tobytes())
        output_digest.update(contiguous.tobytes())
    from hf_tcm.repro.identifiers import MAPPING_STATUS

    return SeparateReceiverResult(
        receiver_config=receiver_config.to_dict(),
        observation_sha256=observation.sha256,
        processed_sample_ranges=_readonly(ranges, np.dtype(np.int64)),
        processed_sample_indices=_readonly(processed, np.dtype(np.int64)),
        unprocessed_sample_indices=_readonly(sample_indices[mask], np.dtype(np.int64)),
        hard_phase_indices=_readonly(demod.phase_indices, np.dtype(np.int8)),
        hard_coded_triples=_readonly(demod.coded_triples, np.dtype(np.int8)),
        hard_symbol_squared_distances=_readonly(demod.squared_distances, np.dtype(np.float64)),
        hamming_branch_metrics=_readonly(metrics, np.dtype(np.int8)),
        accumulated_state_metrics=_readonly(decoded.path_metrics, np.dtype(np.int64)),
        survivor_edge_ids=_readonly(decoded.survivor_edge_ids, np.dtype(np.int16)),
        decoded_edge_ids=_readonly(decoded.decoded_edge_ids, np.dtype(np.int16)),
        decoded_state_path=_readonly(decoded.state_path, np.dtype(np.int8)),
        decoded_information_pairs=_readonly(decoded.information_pairs, np.dtype(np.int8)),
        decoded_information_bits=_readonly(payload_information_bits, np.dtype(np.int8)),
        decoded_frame_information_bits=_readonly(frame_information_bits, np.dtype(np.int8)),
        final_state=decoded.final_state,
        final_path_metric=decoded.final_metric,
        edge_order_id=EDGE_ORDER_ID,
        mapping_id=receiver_config.mapping_id,
        mapping_status=MAPPING_STATUS,
        traceback_mode=receiver_config.decoder_mode,
        decoder_depth=receiver_config.traceback_depth,
        diagnostics={
            "receiver_mode": "separate_hard_8psk_then_hamming_viterbi",
            "front_end_mode": receiver_config.front_end.mode,
            "processed_symbol_count": receiver_config.expected_symbol_count,
            "unprocessed_sample_count": int(np.count_nonzero(mask)),
            "timing_offset_samples": receiver_config.timing_offset_samples,
            "full_frame_traceback": receiver_config.decoder_mode == "full_frame",
            "eta_claimed": receiver_config.decoder_mode == "finite_depth",
            "initial_state_policy": receiver_config.initial_state_policy,
            "final_state_policy": receiver_config.final_state_policy,
            "tie_break_policy": receiver_config.tie_break_policy,
            "trace_output_mode": receiver_config.trace_output_mode,
            "survivor_buffer_max_rows": getattr(decoded, "survivor_buffer_max_rows", len(metrics)),
            "terminal_survivor_state": list(
                getattr(decoded, "survivor_final_state", decoded.final_state)
            ),
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
            "paper_exact": False,
            "receiver_enabled": False,
        },
        reproducibility_metadata={
            "schema_version": "repro04-separate-receiver-v1",
            "python": platform.python_version(),
            "numpy": np.__version__,
            "observation_sha256": observation.sha256,
            "output_arrays_sha256": output_digest.hexdigest(),
            "wall_time_seconds": elapsed,
            "demodulation_seconds": demod_seconds,
            "hamming_metric_seconds": metric_seconds,
            "viterbi_seconds": viterbi_seconds,
            "receiver_array_storage_bytes": int(sum(np.asarray(array).nbytes for array in arrays)),
            "deterministic_tie_policy": receiver_config.tie_policy,
        },
    )
