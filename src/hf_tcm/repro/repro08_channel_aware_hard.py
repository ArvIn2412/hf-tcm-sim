"""REPRO-08 hard 8PSK front end with explicit public static-tap ISI feedback.

This receiver is a project-defined channel-aware baseline. It is deliberately
limited to a publicly configured, static complex channel; it does not estimate
or read hidden time-varying coefficients.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.encoder import TerminationPolicy
from hf_tcm.repro.finite_viterbi import ViterbiConfig, run_viterbi
from hf_tcm.repro.hamming_metric import hamming_metric_matrix
from hf_tcm.repro.hard_8psk_demodulator import inverse_phase_labels
from hf_tcm.repro.identifiers import MAPPING_ID

_PROFILE_ID = "repro08_public_static_channel_hard_v1"


def _readonly(values: object, dtype: np.dtype) -> NDArray[Any]:
    array = np.ascontiguousarray(values, dtype=dtype)
    return np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape)


@dataclass(frozen=True, slots=True)
class PublicStaticTap:
    """One receiver-known static complex channel tap with integer sample delay."""

    delay_samples: int
    coefficient: complex

    def __post_init__(self) -> None:
        if type(self.delay_samples) is not int or self.delay_samples < 0:
            raise ValueError("tap delay_samples must be a non-negative integer")
        coefficient = complex(self.coefficient)
        if not math.isfinite(coefficient.real) or not math.isfinite(coefficient.imag):
            raise ValueError("tap coefficient must be finite")
        object.__setattr__(self, "coefficient", coefficient)

    def to_dict(self) -> dict[str, Any]:
        return {
            "delay_samples": self.delay_samples,
            "coefficient": [float(self.coefficient.real), float(self.coefficient.imag)],
            "provenance": "explicit_receiver_public_configuration",
        }


@dataclass(frozen=True, slots=True)
class Repro08HardReceiverConfig:
    expected_symbol_count: int
    taps: tuple[PublicStaticTap, ...]
    initial_state: tuple[int, int] = (0, 0)
    amplitude: float = 1.0
    phase_offset_rad: float = 0.0
    phase_increment_rad: float = math.pi / 4.0
    traceback_depth: int = 20
    termination_policy: TerminationPolicy = "none"
    tie_break_policy: str = "numpy_argmin_lowest_phase"
    mapping_id: str = MAPPING_ID

    def __post_init__(self) -> None:
        if type(self.expected_symbol_count) is not int or self.expected_symbol_count < 1:
            raise ValueError("expected_symbol_count must be a positive integer")
        if not isinstance(self.taps, tuple) or not self.taps:
            raise ValueError("taps must be a nonempty tuple of PublicStaticTap")
        if any(not isinstance(tap, PublicStaticTap) for tap in self.taps):
            raise TypeError("each tap must be PublicStaticTap")
        if len({tap.delay_samples for tap in self.taps}) != len(self.taps):
            raise ValueError("tap delays must be unique")
        if max(tap.delay_samples for tap in self.taps) >= 8:
            raise ValueError("delays must be less than samples_per_symbol")
        if min(tap.delay_samples for tap in self.taps) != 0:
            raise ValueError("at least one zero-delay reference tap is required")
        if self.initial_state not in {(0, 0), (0, 1), (1, 0), (1, 1)}:
            raise ValueError("initial_state must be a valid two-bit Encoder A state")
        if isinstance(self.amplitude, bool) or not math.isfinite(float(self.amplitude)):
            raise ValueError("amplitude must be finite and positive")
        if self.amplitude <= 0:
            raise ValueError("amplitude must be finite and positive")
        if isinstance(self.phase_offset_rad, bool) or not math.isfinite(
            float(self.phase_offset_rad)
        ):
            raise ValueError("phase_offset_rad must be finite")
        if not math.isclose(self.phase_increment_rad, math.pi / 4.0, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError("phase_increment_rad must equal pi/4")
        if type(self.traceback_depth) is not int or self.traceback_depth < 1:
            raise ValueError("traceback_depth must be a positive integer")
        if self.termination_policy not in {"none", "zero_tail_2"}:
            raise ValueError("unsupported termination_policy")
        if self.tie_break_policy != "numpy_argmin_lowest_phase":
            raise ValueError("unsupported hard-demodulation tie break policy")
        if self.mapping_id != MAPPING_ID:
            raise ValueError("unsupported reconstructed phase mapping")
        object.__setattr__(self, "amplitude", float(self.amplitude))
        object.__setattr__(self, "phase_offset_rad", float(self.phase_offset_rad))

    @property
    def maximum_delay_samples(self) -> int:
        return max(tap.delay_samples for tap in self.taps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": _PROFILE_ID,
            "expected_symbol_count": self.expected_symbol_count,
            "taps": [tap.to_dict() for tap in self.taps],
            "initial_state": list(self.initial_state),
            "amplitude": self.amplitude,
            "phase_offset_rad": self.phase_offset_rad,
            "phase_increment_rad": self.phase_increment_rad,
            "traceback_depth": self.traceback_depth,
            "termination_policy": self.termination_policy,
            "tie_break_policy": self.tie_break_policy,
            "mapping_id": self.mapping_id,
            "channel_mode": "public_static_complex_taps",
            "decision_feedback": "previous_hard_phase_symbol",
        }


@dataclass(frozen=True, slots=True)
class Repro08HardReceiverResult:
    receiver_config: dict[str, Any]
    receiver_profile_id: str
    observation_sha256: str
    hard_phase_indices: NDArray[np.int8]
    hard_coded_triples: NDArray[np.int8]
    candidate_squared_distances: NDArray[np.float64]
    hamming_branch_metrics: NDArray[np.int8]
    decoded_edge_ids: NDArray[np.int16]
    decoded_information_pairs: NDArray[np.int8]
    decoded_information_bits: NDArray[np.int8]
    processed_sample_indices: NDArray[np.int64]
    unprocessed_sample_indices: NDArray[np.int64]
    decoder_mode: str
    traceback_depth: int
    mapping_id: str
    reproducibility_metadata: dict[str, Any]

    @property
    def processed_symbol_count(self) -> int:
        return int(self.hard_phase_indices.size)

    @property
    def processed_sample_count(self) -> int:
        return int(self.processed_sample_indices.size)

    @property
    def unprocessed_sample_count(self) -> int:
        return int(self.unprocessed_sample_indices.size)


def _symbol_for_sample(
    absolute_sample: int,
    current_symbol: int,
    frame_symbol_count: int,
    candidate: complex,
    previous_decisions: NDArray[np.complex128],
    samples_per_symbol: int,
) -> complex:
    source_sample = absolute_sample
    if source_sample < 0:
        return 0j
    source_symbol = source_sample // samples_per_symbol
    if source_symbol >= frame_symbol_count:
        return 0j
    if source_symbol > current_symbol:
        raise ValueError("static-tap predictor requested a future symbol")
    if source_symbol == current_symbol:
        return candidate
    return complex(previous_decisions[source_symbol])


def _candidate_distances(
    observation_samples: NDArray[np.complex128],
    symbol_index: int,
    previous_decisions: NDArray[np.complex128],
    config: Repro08HardReceiverConfig,
) -> NDArray[np.float64]:
    sps = 8
    frame_samples = config.expected_symbol_count * sps
    start = symbol_index * sps
    stop = (symbol_index + 1) * sps
    if symbol_index == config.expected_symbol_count - 1:
        stop = min(len(observation_samples), frame_samples + config.maximum_delay_samples)
    sample_indices = range(start, stop)
    phase_indices = np.arange(8, dtype=np.float64)
    hypotheses = config.amplitude * np.exp(
        1j * (config.phase_offset_rad + phase_indices * config.phase_increment_rad)
    )
    distances = np.zeros(8, dtype=np.float64)
    for absolute_sample in sample_indices:
        received = observation_samples[absolute_sample]
        for phase, current_symbol in enumerate(hypotheses):
            predicted = 0j
            for tap in config.taps:
                source_sample = absolute_sample - tap.delay_samples
                source_symbol_value = _symbol_for_sample(
                    source_sample,
                    symbol_index,
                    config.expected_symbol_count,
                    complex(current_symbol),
                    previous_decisions,
                    sps,
                )
                predicted += tap.coefficient * source_symbol_value
            residual = received - predicted
            distances[phase] += float(residual.real * residual.real + residual.imag * residual.imag)
    return distances


def run_channel_aware_hard_receiver(
    observation: ReceiverObservation,
    receiver_config: Repro08HardReceiverConfig,
) -> Repro08HardReceiverResult:
    """Use public static taps for hard phase decisions, then Hamming Viterbi."""
    if type(observation) is not ReceiverObservation:
        raise TypeError(
            "B1 accepts ReceiverObservation only; ChannelResult/EvaluationTruth forbidden"
        )
    if not isinstance(receiver_config, Repro08HardReceiverConfig):
        raise TypeError("receiver_config must be Repro08HardReceiverConfig")
    if observation.samples_per_symbol != 8:
        raise ValueError("B1 requires 8 samples per symbol")
    samples = np.asarray(observation.received_samples, dtype=np.complex128)
    if samples.ndim != 1 or samples.size == 0 or not np.all(np.isfinite(samples)):
        raise ValueError("received samples must be a nonempty finite complex vector")
    frame_samples = receiver_config.expected_symbol_count * 8
    max_tail = receiver_config.maximum_delay_samples
    if not frame_samples <= samples.size <= frame_samples + max_tail:
        raise ValueError(
            "received length must equal frame samples plus at most the configured channel tail"
        )
    indexes = np.arange(samples.size, dtype=np.int64)
    if not np.array_equal(observation.absolute_sample_index, indexes):
        raise ValueError("observation sample indices must be contiguous from zero")
    if not np.array_equal(observation.sample_symbol_index, indexes // 8) or not np.array_equal(
        observation.sample_local_index, indexes % 8
    ):
        raise ValueError("observation sample/symbol timing metadata is inconsistent")

    phase_symbols = receiver_config.amplitude * np.exp(
        1j
        * (
            receiver_config.phase_offset_rad
            + np.arange(8, dtype=np.float64) * receiver_config.phase_increment_rad
        )
    )
    previous_decisions = np.zeros(receiver_config.expected_symbol_count, dtype=np.complex128)
    hard_phases = np.empty(receiver_config.expected_symbol_count, dtype=np.int8)
    candidate_rows = np.empty((receiver_config.expected_symbol_count, 8), dtype=np.float64)
    for symbol_index in range(receiver_config.expected_symbol_count):
        distances = _candidate_distances(samples, symbol_index, previous_decisions, receiver_config)
        phase = int(np.argmin(distances))
        candidate_rows[symbol_index] = distances
        hard_phases[symbol_index] = phase
        previous_decisions[symbol_index] = phase_symbols[phase]

    labels = inverse_phase_labels()
    hard_triples = labels[hard_phases]
    branch_metrics = hamming_metric_matrix(hard_triples)
    decoded = run_viterbi(
        branch_metrics,
        ViterbiConfig(
            initial_state=receiver_config.initial_state,
            traceback_depth=receiver_config.traceback_depth,
            decoder_mode="finite_depth",
            expected_symbol_count=receiver_config.expected_symbol_count,
            termination_policy=receiver_config.termination_policy,
            trace_output_mode="compact",
        ),
    )
    payload_pairs = decoded.information_pairs
    tail_pair_count = 2 if receiver_config.termination_policy == "zero_tail_2" else 0
    payload_bits = (
        payload_pairs[:-tail_pair_count].reshape(-1)
        if tail_pair_count
        else payload_pairs.reshape(-1)
    )
    processed_count = samples.size
    processed_indices = np.arange(processed_count, dtype=np.int64)
    unprocessed_indices = np.arange(processed_count, samples.size, dtype=np.int64)
    arrays = (
        hard_phases,
        hard_triples,
        candidate_rows,
        branch_metrics,
        decoded.decoded_edge_ids,
        payload_bits,
    )
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(np.asarray(contiguous.shape, dtype=np.int64).tobytes())
        digest.update(contiguous.tobytes())
    return Repro08HardReceiverResult(
        receiver_config=receiver_config.to_dict(),
        receiver_profile_id=_PROFILE_ID,
        observation_sha256=observation.sha256,
        hard_phase_indices=_readonly(hard_phases, np.dtype(np.int8)),
        hard_coded_triples=_readonly(hard_triples, np.dtype(np.int8)),
        candidate_squared_distances=_readonly(candidate_rows, np.dtype(np.float64)),
        hamming_branch_metrics=_readonly(branch_metrics, np.dtype(np.int8)),
        decoded_edge_ids=_readonly(decoded.decoded_edge_ids, np.dtype(np.int16)),
        decoded_information_pairs=_readonly(payload_pairs, np.dtype(np.int8)),
        decoded_information_bits=_readonly(payload_bits, np.dtype(np.int8)),
        processed_sample_indices=_readonly(processed_indices, np.dtype(np.int64)),
        unprocessed_sample_indices=_readonly(unprocessed_indices, np.dtype(np.int64)),
        decoder_mode="finite_depth",
        traceback_depth=receiver_config.traceback_depth,
        mapping_id=receiver_config.mapping_id,
        reproducibility_metadata={
            "schema_version": "repro08-channel-aware-hard-v1",
            "observation_sha256": observation.sha256,
            "output_arrays_sha256": digest.hexdigest(),
            "channel_truth_used": False,
            "receiver_channel_information": "explicit_static_taps_only",
            "isi_method": "causal_previous_hard_symbol_decision_feedback",
            "frame_tail_policy": "last_decision_scores_available_zero_extended_tail",
            "decoder_mode": decoded.decoder_mode,
            "traceback_depth": decoded.traceback_depth,
            "decision_latency_transitions": receiver_config.traceback_depth - 1,
            "eta_is_not_visual_window": True,
        },
    )
