"""Strict BER and coded-symbol SER utilities for post-decode evaluation.

Reference data belongs to this evaluation layer. Receiver modules must not
import these functions or receive reference bits through receiver results.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.encoder import INITIAL_STATE, encode
from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.receiver.reconstruction_labeling import (
    ASSUMED_NATURAL_BINARY,
    OUTPUT_BIT_ORDER,
    output_bits_to_phase_index,
)

IntArray = NDArray[np.int64]


def _integer_vector(values: ArrayLike, *, name: str) -> IntArray:
    try:
        raw = np.asarray(values)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a one-dimensional integer sequence") from exc
    if raw.ndim != 1 or raw.dtype.kind not in "iub":
        raise ValueError(f"{name} must be a one-dimensional integer sequence")
    try:
        return np.asarray(raw, dtype=np.int64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} contains values outside the supported integer range") from exc


def _bits(values: ArrayLike, *, name: str) -> IntArray:
    result = _integer_vector(values, name=name)
    if result.size == 0 or np.any((result != 0) & (result != 1)):
        raise ValueError(f"{name} must contain one or more bits in {{0, 1}}")
    return result


def _symbols(values: ArrayLike, *, name: str) -> IntArray:
    result = _integer_vector(values, name=name)
    if result.size == 0 or np.any((result < 0) | (result > 7)):
        raise ValueError(f"{name} must contain one or more 8PSK indices in [0, 7]")
    return result


@dataclass(frozen=True, slots=True)
class ErrorCounts:
    """Primary pooled counts for one or more complete rate-2/3 runs."""

    bit_errors: int
    total_bits: int
    symbol_errors: int
    total_symbols: int

    def __post_init__(self) -> None:
        values = (self.bit_errors, self.total_bits, self.symbol_errors, self.total_symbols)
        if any(type(value) is not int for value in values):
            raise ValueError("error counts and denominators must be integers")
        if self.total_bits <= 0 or self.total_symbols <= 0:
            raise ValueError("error-count denominators must be positive")
        if self.total_bits != 2 * self.total_symbols:
            raise ValueError("rate-2/3 runs require exactly two information bits per symbol")
        if not 0 <= self.bit_errors <= self.total_bits:
            raise ValueError("bit_errors must be between zero and total_bits")
        if not 0 <= self.symbol_errors <= self.total_symbols:
            raise ValueError("symbol_errors must be between zero and total_symbols")


@dataclass(frozen=True, slots=True)
class ErrorAggregate:
    """Pooled counts together with the original per-run counts."""

    run_counts: tuple[ErrorCounts, ...]
    counts: ErrorCounts

    def __post_init__(self) -> None:
        if not self.run_counts or any(not isinstance(run, ErrorCounts) for run in self.run_counts):
            raise ValueError("run_counts must retain at least one ErrorCounts record")
        expected = ErrorCounts(
            bit_errors=sum(run.bit_errors for run in self.run_counts),
            total_bits=sum(run.total_bits for run in self.run_counts),
            symbol_errors=sum(run.symbol_errors for run in self.run_counts),
            total_symbols=sum(run.total_symbols for run in self.run_counts),
        )
        if self.counts != expected:
            raise ValueError("pooled counts must equal the sum of retained per-run counts")


@dataclass(frozen=True, slots=True)
class ErrorRates:
    """Pooled point estimates computed from primary error counts."""

    ber: float
    ser: float


@dataclass(frozen=True, slots=True)
class ErrorEvaluation:
    """Counts and pooled ratios for one complete independent sequence."""

    counts: ErrorCounts

    @property
    def ber(self) -> float:
        return calculate_ber_ser(self.counts).ber

    @property
    def ser(self) -> float:
        return calculate_ber_ser(self.counts).ser


def count_bit_errors(
    reference_information_bits: ArrayLike, decoded_information_bits: ArrayLike
) -> int:
    """Count exact-position information-bit disagreements; never trim lengths."""
    reference = _bits(reference_information_bits, name="reference_information_bits")
    decoded = _bits(decoded_information_bits, name="decoded_information_bits")
    if reference.shape != decoded.shape:
        raise ValueError("reference and decoded information-bit lengths must match exactly")
    return int(np.count_nonzero(reference != decoded))


def count_symbol_errors(
    reference_symbol_indices: ArrayLike, decoded_symbol_indices: ArrayLike
) -> int:
    """Count exact-position coded 8PSK symbol-index disagreements."""
    reference = _symbols(reference_symbol_indices, name="reference_symbol_indices")
    decoded = _symbols(decoded_symbol_indices, name="decoded_symbol_indices")
    if reference.shape != decoded.shape:
        raise ValueError("reference and decoded symbol lengths must match exactly")
    return int(np.count_nonzero(reference != decoded))


def evaluate_run(
    reference_information_bits: ArrayLike,
    decoded_information_bits: ArrayLike,
    reference_symbol_indices: ArrayLike,
    decoded_symbol_indices: ArrayLike,
) -> ErrorEvaluation:
    """Evaluate one independent sequence with strict 2F-bit/F-symbol lengths."""
    reference_bits = _bits(reference_information_bits, name="reference_information_bits")
    decoded_bits = _bits(decoded_information_bits, name="decoded_information_bits")
    reference_symbols = _symbols(reference_symbol_indices, name="reference_symbol_indices")
    decoded_symbols = _symbols(decoded_symbol_indices, name="decoded_symbol_indices")
    if reference_bits.shape != decoded_bits.shape:
        raise ValueError("reference and decoded information-bit lengths must match exactly")
    if reference_symbols.shape != decoded_symbols.shape:
        raise ValueError("reference and decoded symbol lengths must match exactly")
    if reference_bits.size != 2 * reference_symbols.size:
        raise ValueError("a rate-2/3 sequence requires 2F information bits and F symbols")
    return ErrorEvaluation(
        ErrorCounts(
            bit_errors=int(np.count_nonzero(reference_bits != decoded_bits)),
            total_bits=int(reference_bits.size),
            symbol_errors=int(np.count_nonzero(reference_symbols != decoded_symbols)),
            total_symbols=int(reference_symbols.size),
        )
    )


def aggregate_error_counts(
    runs: Iterable[ErrorCounts | ErrorEvaluation],
) -> ErrorAggregate:
    """Pool counts while retaining each run's counts; never average run ratios."""
    materialized = tuple(run.counts if isinstance(run, ErrorEvaluation) else run for run in runs)
    if not materialized or any(not isinstance(run, ErrorCounts) for run in materialized):
        raise ValueError("runs must contain at least one ErrorCounts or ErrorEvaluation")
    pooled = ErrorCounts(
        bit_errors=sum(run.bit_errors for run in materialized),
        total_bits=sum(run.total_bits for run in materialized),
        symbol_errors=sum(run.symbol_errors for run in materialized),
        total_symbols=sum(run.total_symbols for run in materialized),
    )
    return ErrorAggregate(run_counts=materialized, counts=pooled)


def calculate_ber_ser(counts: ErrorCounts | ErrorAggregate) -> ErrorRates:
    """Calculate pooled BER/SER from raw counts and explicit denominators."""
    if isinstance(counts, ErrorAggregate):
        counts = counts.counts
    if not isinstance(counts, ErrorCounts):
        raise ValueError("counts must be an ErrorCounts or ErrorAggregate value")
    return ErrorRates(
        ber=counts.bit_errors / counts.total_bits,
        ser=counts.symbol_errors / counts.total_symbols,
    )


def encode_reference_symbol_indices(
    reference_information_bits: ArrayLike,
    *,
    profile: str,
    bit_order: Sequence[str],
) -> NDArray[np.int64]:
    """Encode evaluation-only reference bits and map M1 output triples to symbols."""
    bits = _bits(reference_information_bits, name="reference_information_bits")
    if bits.size % 2:
        raise ValueError("reference_information_bits must contain complete pairs")
    if profile != ASSUMED_NATURAL_BINARY or tuple(bit_order) != OUTPUT_BIT_ORDER:
        raise ValueError("explicit ADR-002 profile and output bit order are required")
    output_labels = encode(bits.reshape(-1, 2).tolist(), initial_state=INITIAL_STATE)
    indices = np.asarray(
        [
            output_bits_to_phase_index(label, profile=profile, bit_order=bit_order)
            for label in output_labels
        ],
        dtype=np.int64,
    )
    return np.frombuffer(indices.tobytes(), dtype=np.int64)


def decoded_path_symbol_indices(
    hypothesis_ids: Sequence[int],
    *,
    profile: str,
    bit_order: Sequence[str],
) -> NDArray[np.int64]:
    """Map validated decoded edge output bits to ADR-002 8PSK indices."""
    if profile != ASSUMED_NATURAL_BINARY or tuple(bit_order) != OUTPUT_BIT_ORDER:
        raise ValueError("explicit ADR-002 profile and output bit order are required")
    path = validate_hypothesis_edge_path(hypothesis_ids, initial_state=INITIAL_STATE)
    indices = np.asarray(
        [
            output_bits_to_phase_index(edge.output_bits, profile=profile, bit_order=bit_order)
            for edge in path
        ],
        dtype=np.int64,
    )
    return np.frombuffer(indices.tobytes(), dtype=np.int64)
