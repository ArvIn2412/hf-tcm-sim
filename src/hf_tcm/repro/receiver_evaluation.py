"""Evaluation-only comparison of a completed receiver output with references."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.separate_receiver import SeparateReceiverResult


@dataclass(frozen=True, slots=True)
class ReceiverEvaluation:
    compared_information_bit_count: int
    bit_errors: int
    ber: float
    compared_symbol_count: int
    symbol_errors: int
    ser: float
    bit_error_positions: NDArray[np.int64]
    symbol_error_positions: NDArray[np.int64]
    reference_phase_indices: NDArray[np.int8]
    evidence_scope: str


def evaluate_separate_receiver(
    receiver_result: SeparateReceiverResult,
    reference_information_bits: object,
    reference_phase_indices: object,
) -> ReceiverEvaluation:
    if not isinstance(receiver_result, SeparateReceiverResult):
        raise TypeError("receiver_result must be SeparateReceiverResult")
    ref_bits = np.asarray(reference_information_bits)
    ref_phase = np.asarray(reference_phase_indices)
    if (
        ref_bits.ndim != 1
        or ref_bits.dtype.kind not in "iu"
        or np.any((ref_bits != 0) & (ref_bits != 1))
    ):
        raise ValueError("reference_information_bits must be a binary integer vector")
    if (
        ref_phase.ndim != 1
        or ref_phase.dtype.kind not in "iu"
        or np.any(ref_phase < 0)
        or np.any(ref_phase > 7)
    ):
        raise ValueError("reference_phase_indices must be an integer vector in [0,7]")
    tail = 2 if receiver_result.receiver_config["termination_policy"] == "zero_tail_2" else 0
    payload_symbols = len(receiver_result.decoded_information_pairs) - tail
    if len(ref_bits) != payload_symbols * 2 or len(ref_phase) != payload_symbols:
        raise ValueError(
            "reference lengths must match the decoded payload after explicit tail exclusion"
        )
    decoded_bits = receiver_result.decoded_information_bits
    bit_errors_mask = decoded_bits != ref_bits.astype(np.int8)
    phase_decisions = receiver_result.hard_phase_indices[:payload_symbols]
    symbol_errors_mask = phase_decisions != ref_phase.astype(np.int8)
    return ReceiverEvaluation(
        compared_information_bit_count=len(ref_bits),
        bit_errors=int(np.count_nonzero(bit_errors_mask)),
        ber=float(np.mean(bit_errors_mask)),
        compared_symbol_count=payload_symbols,
        symbol_errors=int(np.count_nonzero(symbol_errors_mask)),
        ser=float(np.mean(symbol_errors_mask)),
        bit_error_positions=np.flatnonzero(bit_errors_mask).astype(np.int64),
        symbol_error_positions=np.flatnonzero(symbol_errors_mask).astype(np.int64),
        reference_phase_indices=np.frombuffer(
            np.asarray(ref_phase, dtype=np.int8).tobytes(), dtype=np.int8
        ),
        evidence_scope="single_frame_descriptive_only_not_statistical_evidence",
    )
