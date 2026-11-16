"""Evaluation-only BER/SER adapter for completed REPRO-06B results."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.encoder import transition_table
from hf_tcm.repro.multipath_joint_receiver import MultipathJointReceiverResult


@dataclass(frozen=True, slots=True)
class MultipathReceiverEvaluation:
    compared_information_bit_count: int
    bit_errors: int
    ber: float
    compared_symbol_count: int
    symbol_errors: int
    ser: float
    bit_error_positions: NDArray[np.int64]
    symbol_error_positions: NDArray[np.int64]
    reference_phase_indices: NDArray[np.int8]
    evidence_scope: str = "single_frame_descriptive_only_not_statistical_evidence"


def evaluate_multipath_receiver(
    receiver_result: MultipathJointReceiverResult,
    reference_information_bits: object,
    reference_phase_indices: object,
) -> MultipathReceiverEvaluation:
    """Compare a completed decode with references; references never enter decisions."""
    if not isinstance(receiver_result, MultipathJointReceiverResult):
        raise TypeError("receiver_result must be MultipathJointReceiverResult")
    bits = np.asarray(reference_information_bits)
    phases = np.asarray(reference_phase_indices)
    if bits.ndim != 1 or bits.dtype.kind not in "iu" or np.any((bits != 0) & (bits != 1)):
        raise ValueError("reference_information_bits must be a binary integer vector")
    if phases.ndim != 1 or phases.dtype.kind not in "iu" or np.any((phases < 0) | (phases > 7)):
        raise ValueError("reference_phase_indices must be integer values in [0,7]")
    tail = 2 if receiver_result.receiver_config["termination_policy"] == "zero_tail_2" else 0
    payload_symbols = len(receiver_result.decoded_information_pairs) - tail
    if len(bits) != payload_symbols * 2 or len(phases) != payload_symbols:
        raise ValueError("reference lengths must match payload after explicit tail exclusion")
    decoded_bits = receiver_result.decoded_information_bits[: payload_symbols * 2]
    bit_mask = decoded_bits != bits.astype(np.int8)
    phase_by_edge = np.asarray(
        [4 * edge[3][0] + 2 * edge[3][1] + edge[3][2] for edge in transition_table()],
        dtype=np.int8,
    )
    decoded_phases = phase_by_edge[receiver_result.decoded_edge_ids[:payload_symbols]]
    symbol_mask = decoded_phases != phases.astype(np.int8)
    return MultipathReceiverEvaluation(
        compared_information_bit_count=len(bits),
        bit_errors=int(np.count_nonzero(bit_mask)),
        ber=float(np.mean(bit_mask)) if len(bit_mask) else 0.0,
        compared_symbol_count=payload_symbols,
        symbol_errors=int(np.count_nonzero(symbol_mask)),
        ser=float(np.mean(symbol_mask)) if len(symbol_mask) else 0.0,
        bit_error_positions=np.flatnonzero(bit_mask).astype(np.int64),
        symbol_error_positions=np.flatnonzero(symbol_mask).astype(np.int64),
        reference_phase_indices=np.frombuffer(phases.astype(np.int8).tobytes(), dtype=np.int8),
    )
