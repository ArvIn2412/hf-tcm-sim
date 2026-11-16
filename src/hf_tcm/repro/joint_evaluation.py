"""Evaluation-only bit/symbol comparison for completed joint receiver results."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.encoder import transition_table
from hf_tcm.repro.joint_receiver import JointReceiverResult
from hf_tcm.repro.receiver_evaluation import evaluate_separate_receiver
from hf_tcm.repro.separate_receiver import SeparateReceiverResult


@dataclass(frozen=True, slots=True)
class JointEvaluation:
    compared_information_bit_count: int
    bit_errors: int
    ber: float
    compared_symbol_count: int
    symbol_errors: int
    ser: float
    bit_error_positions: NDArray[np.int64]
    symbol_error_positions: NDArray[np.int64]
    evidence_scope: str = "single_frame_descriptive_only_not_statistical_evidence"


@dataclass(frozen=True, slots=True)
class DualReceiverComparison:
    observation_sha256: str
    compared_information_bit_count: int
    joint_bit_errors: int
    separate_bit_errors: int
    joint_ber: float
    separate_ber: float
    joint_ser: float
    separate_ser: float
    evidence_scope: str = "paired_single_frame_descriptive_only_not_statistical_evidence"


def evaluate_joint_receiver(
    result: JointReceiverResult,
    reference_information_bits: object,
    reference_phase_indices: object,
) -> JointEvaluation:
    if not isinstance(result, JointReceiverResult):
        raise TypeError("result must be JointReceiverResult")
    bits = np.asarray(reference_information_bits)
    phases = np.asarray(reference_phase_indices)
    if bits.ndim != 1 or bits.dtype.kind not in "iu" or np.any((bits != 0) & (bits != 1)):
        raise ValueError("reference_information_bits must be a binary integer vector")
    if phases.ndim != 1 or phases.dtype.kind not in "iu" or np.any((phases < 0) | (phases > 7)):
        raise ValueError("reference_phase_indices must be integer values in [0,7]")
    tail = 2 if result.receiver_config["termination_policy"] == "zero_tail_2" else 0
    symbol_count = len(result.decoded_information_pairs) - tail
    if len(bits) != symbol_count * 2 or len(phases) != symbol_count:
        raise ValueError("reference lengths must match payload after explicit tail exclusion")
    decoded = result.decoded_information_bits
    bit_errors = decoded != bits.astype(np.int8)
    phase_lookup = np.asarray(
        [4 * row[3][0] + 2 * row[3][1] + row[3][2] for row in transition_table()],
        dtype=np.int8,
    )
    decoded_phases = phase_lookup[result.decoded_edge_ids[:symbol_count]]
    symbol_errors = decoded_phases != phases.astype(np.int8)
    return JointEvaluation(
        compared_information_bit_count=len(bits),
        bit_errors=int(np.count_nonzero(bit_errors)),
        ber=float(np.mean(bit_errors)) if len(bits) else 0.0,
        compared_symbol_count=symbol_count,
        symbol_errors=int(np.count_nonzero(symbol_errors)),
        ser=float(np.mean(symbol_errors)) if symbol_count else 0.0,
        bit_error_positions=np.flatnonzero(bit_errors).astype(np.int64),
        symbol_error_positions=np.flatnonzero(symbol_errors).astype(np.int64),
    )


def compare_joint_and_separate(
    joint: JointReceiverResult,
    separate: SeparateReceiverResult,
    reference_information_bits: object,
    reference_phase_indices: object,
) -> DualReceiverComparison:
    """Compare two completed arms against one reference, after both decode."""
    if not isinstance(joint, JointReceiverResult) or not isinstance(
        separate, SeparateReceiverResult
    ):
        raise TypeError("comparison requires joint and separate receiver results")
    if joint.observation_sha256 != separate.observation_sha256:
        raise ValueError("receiver arms must use the exact same ReceiverObservation")
    joint_eval = evaluate_joint_receiver(joint, reference_information_bits, reference_phase_indices)
    separate_eval = evaluate_separate_receiver(
        separate, reference_information_bits, reference_phase_indices
    )
    if joint_eval.compared_information_bit_count != separate_eval.compared_information_bit_count:
        raise ValueError("receiver arms used different evaluation boundaries")
    return DualReceiverComparison(
        observation_sha256=joint.observation_sha256,
        compared_information_bit_count=joint_eval.compared_information_bit_count,
        joint_bit_errors=joint_eval.bit_errors,
        separate_bit_errors=separate_eval.bit_errors,
        joint_ber=joint_eval.ber,
        separate_ber=separate_eval.ber,
        joint_ser=joint_eval.ser,
        separate_ser=separate_eval.ser,
    )
