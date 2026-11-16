"""Evaluation-only BER and information-pair SER from one decoded bit sequence."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class InformationPairErrorMetrics:
    compared_bits: int
    bit_errors: int
    ber: float
    bit_error_positions: NDArray[np.int64]
    compared_pairs: int
    pair_errors: int
    pair_ser: float
    pair_error_positions: NDArray[np.int64]


def evaluate_information_pair_errors(
    reference_bits: object, decoded_bits: object
) -> InformationPairErrorMetrics:
    """Count BER and pair SER over the same payload bits and fixed two-bit grouping."""
    reference = _binary_vector(reference_bits, "reference_bits")
    decoded = _binary_vector(decoded_bits, "decoded_bits")
    if reference.shape != decoded.shape:
        raise ValueError("reference_bits and decoded_bits must have identical lengths")
    if reference.size % 2:
        raise ValueError("information bit sequences must contain complete two-bit pairs")

    bit_error_mask = reference != decoded
    pair_error_mask = bit_error_mask.reshape((-1, 2)).any(axis=1)
    bit_errors = int(np.count_nonzero(bit_error_mask))
    pair_errors = int(np.count_nonzero(pair_error_mask))
    if not pair_errors <= bit_errors <= 2 * pair_errors:
        raise RuntimeError("BER/pair-SER consistency invariant failed")

    return InformationPairErrorMetrics(
        compared_bits=int(reference.size),
        bit_errors=bit_errors,
        ber=float(bit_errors / reference.size) if reference.size else 0.0,
        bit_error_positions=np.flatnonzero(bit_error_mask).astype(np.int64),
        compared_pairs=int(pair_error_mask.size),
        pair_errors=pair_errors,
        pair_ser=float(pair_errors / pair_error_mask.size) if pair_error_mask.size else 0.0,
        pair_error_positions=np.flatnonzero(pair_error_mask).astype(np.int64),
    )


def _binary_vector(values: object, name: str) -> NDArray[np.int8]:
    array = np.asarray(values)
    if array.ndim != 1 or array.dtype.kind not in "iu":
        raise TypeError(f"{name} must be a one-dimensional integer bit vector")
    if np.any((array != 0) & (array != 1)):
        raise ValueError(f"{name} must contain only 0 and 1")
    return array.astype(np.int8, copy=False)
