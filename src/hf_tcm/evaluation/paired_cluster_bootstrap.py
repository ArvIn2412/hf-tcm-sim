"""Paired cluster-bootstrap summaries for independent coded-sequence runs."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Integral, Real

import numpy as np
from numpy.typing import NDArray

from hf_tcm.evaluation.error_metrics import (
    ErrorAggregate,
    ErrorCounts,
    aggregate_error_counts,
    calculate_ber_ser,
)

FloatArray = NDArray[np.float64]
IndexArray = NDArray[np.int64]
METRIC_NAMES = ("ber_b", "ber_c", "delta_ber", "ser_b", "ser_c", "delta_ser")
TOO_FEW_RUNS_THRESHOLD = 20
RARE_POOLED_ERROR_THRESHOLD = 20
STRONG_CLUSTER_IMBALANCE_RATIO = 2.0


def _immutable_array(values: NDArray, *, dtype: np.dtype) -> NDArray:
    owned = np.array(values, dtype=dtype, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=dtype).reshape(owned.shape)


def _integer(value: object, *, name: str, minimum: int) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer >= {minimum}")
    result = int(value)
    if result < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return result


@dataclass(frozen=True, slots=True)
class PairedRunCounts:
    """Raw B/C error counts for one independent complete TCM sequence."""

    run_id: str
    b_counts: ErrorCounts
    c_counts: ErrorCounts

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be a nonempty string")
        if not isinstance(self.b_counts, ErrorCounts) or not isinstance(self.c_counts, ErrorCounts):
            raise ValueError("B and C must each have an ErrorCounts record")
        if (
            self.b_counts.total_bits != self.c_counts.total_bits
            or self.b_counts.total_symbols != self.c_counts.total_symbols
        ):
            raise ValueError("paired B/C totals must be identical")
        object.__setattr__(self, "run_id", self.run_id.strip())


@dataclass(frozen=True, slots=True)
class PairedPointEstimates:
    """Pooled B/C rates and paired pooled differences from integer counts."""

    b_counts: ErrorCounts
    c_counts: ErrorCounts
    run_count: int
    ber_b: float
    ber_c: float
    delta_ber: float
    ser_b: float
    ser_c: float
    delta_ser: float


@dataclass(frozen=True, slots=True)
class PairedIndexSummary(PairedPointEstimates):
    """Pooled estimates for one explicit paired resample of run indices."""

    selected_run_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BootstrapInterval:
    metric: str
    lower: float
    upper: float


@dataclass(frozen=True, slots=True)
class PairedClusterBootstrapResult:
    """Read-only percentile intervals and auditable paired resampling indices."""

    point_estimates: PairedPointEstimates
    intervals: tuple[BootstrapInterval, ...]
    replicate_estimates: FloatArray
    resample_indices: IndexArray
    bootstrap_replicates: int
    confidence_level: float
    bootstrap_seed: int
    bit_generator: str
    quantile_method: str
    ordered_run_ids: tuple[str, ...]
    warning_flags: tuple[str, ...]

    def __post_init__(self) -> None:
        replicates = _immutable_array(self.replicate_estimates, dtype=np.dtype(np.float64))
        indices = _immutable_array(self.resample_indices, dtype=np.dtype(np.int64))
        if replicates.shape != (self.bootstrap_replicates, len(METRIC_NAMES)):
            raise ValueError("replicate_estimates must have shape (replicates, 6)")
        if indices.shape != (self.bootstrap_replicates, self.point_estimates.run_count):
            raise ValueError("resample_indices must have shape (replicates, run_count)")
        if (
            len(self.intervals) != len(METRIC_NAMES)
            or tuple(item.metric for item in self.intervals) != METRIC_NAMES
        ):
            raise ValueError("intervals must follow the canonical six-metric order")
        if not np.all(np.isfinite(replicates)):
            raise ValueError("bootstrap replicate estimates must be finite")
        object.__setattr__(self, "replicate_estimates", replicates)
        object.__setattr__(self, "resample_indices", indices)

    def interval(self, metric: str) -> BootstrapInterval:
        for interval in self.intervals:
            if interval.metric == metric:
                return interval
        raise ValueError(f"unknown metric {metric!r}")

    @property
    def resample_run_ids(self) -> tuple[tuple[str, ...], ...]:
        return tuple(
            tuple(self.ordered_run_ids[index] for index in row) for row in self.resample_indices
        )


def _validate_records(records: Sequence[PairedRunCounts]) -> tuple[PairedRunCounts, ...]:
    materialized = tuple(records)
    if not materialized:
        raise ValueError("at least one paired independent run is required")
    if any(not isinstance(record, PairedRunCounts) for record in materialized):
        raise ValueError("records must contain PairedRunCounts values")
    run_ids = tuple(record.run_id for record in materialized)
    if len(set(run_ids)) != len(run_ids):
        raise ValueError("run_id values must be unique")
    return materialized


def summarize_paired_indices(
    records: Sequence[PairedRunCounts], indices: NDArray[np.integer]
) -> PairedIndexSummary:
    """Pool paired raw counts for an explicit list of resampled run indices."""
    materialized = _validate_records(records)
    raw = np.asarray(indices)
    if raw.ndim != 1 or raw.size == 0 or raw.dtype.kind not in "iu":
        raise ValueError("indices must be a nonempty one-dimensional integer vector")
    if np.any(raw < 0) or np.any(raw >= len(materialized)):
        raise ValueError("resample indices are outside the ordered run record range")
    chosen = tuple(materialized[int(index)] for index in raw)
    b_aggregate: ErrorAggregate = aggregate_error_counts(record.b_counts for record in chosen)
    c_aggregate: ErrorAggregate = aggregate_error_counts(record.c_counts for record in chosen)
    b_rates = calculate_ber_ser(b_aggregate)
    c_rates = calculate_ber_ser(c_aggregate)
    return PairedIndexSummary(
        b_counts=b_aggregate.counts,
        c_counts=c_aggregate.counts,
        run_count=len(chosen),
        ber_b=b_rates.ber,
        ber_c=c_rates.ber,
        delta_ber=c_rates.ber - b_rates.ber,
        ser_b=b_rates.ser,
        ser_c=c_rates.ser,
        delta_ser=c_rates.ser - b_rates.ser,
        selected_run_ids=tuple(record.run_id for record in chosen),
    )


def _point_estimates(records: tuple[PairedRunCounts, ...]) -> PairedPointEstimates:
    summary = summarize_paired_indices(records, np.arange(len(records), dtype=np.int64))
    return PairedPointEstimates(
        b_counts=summary.b_counts,
        c_counts=summary.c_counts,
        run_count=summary.run_count,
        ber_b=summary.ber_b,
        ber_c=summary.ber_c,
        delta_ber=summary.delta_ber,
        ser_b=summary.ser_b,
        ser_c=summary.ser_c,
        delta_ser=summary.delta_ser,
    )


def _diagnostic_warnings(
    records: tuple[PairedRunCounts, ...], replicate_estimates: FloatArray
) -> tuple[str, ...]:
    flags: list[str] = []
    if len(records) < TOO_FEW_RUNS_THRESHOLD:
        flags.append("too_few_independent_runs")
    all_counts = tuple(count for record in records for count in (record.b_counts, record.c_counts))
    if all(count.bit_errors == 0 and count.symbol_errors == 0 for count in all_counts):
        flags.append("all_zero_errors")
    run_signatures = {
        (
            record.b_counts.total_bits,
            record.b_counts.total_symbols,
            record.b_counts.bit_errors,
            record.c_counts.bit_errors,
            record.b_counts.symbol_errors,
            record.c_counts.symbol_errors,
        )
        for record in records
    }
    if len(run_signatures) == 1:
        flags.append("all_runs_identical")
    pooled_errors = {
        "b_bits": sum(record.b_counts.bit_errors for record in records),
        "c_bits": sum(record.c_counts.bit_errors for record in records),
        "b_symbols": sum(record.b_counts.symbol_errors for record in records),
        "c_symbols": sum(record.c_counts.symbol_errors for record in records),
    }
    if any(error_count < RARE_POOLED_ERROR_THRESHOLD for error_count in pooled_errors.values()):
        flags.append("rare_error_count")
    denominators = np.asarray([record.b_counts.total_bits for record in records], dtype=np.float64)
    if float(np.max(denominators)) > STRONG_CLUSTER_IMBALANCE_RATIO * float(
        np.median(denominators)
    ):
        flags.append("strong_cluster_imbalance")
    if any(np.unique(replicate_estimates[:, index]).size <= 1 for index in range(6)):
        flags.append("degenerate_bootstrap_distribution")
    unreliable_flags = {
        "too_few_independent_runs",
        "all_runs_identical",
        "all_zero_errors",
        "rare_error_count",
        "strong_cluster_imbalance",
        "degenerate_bootstrap_distribution",
    }
    if unreliable_flags.intersection(flags):
        flags.append("bootstrap_interval_unreliable")
    return tuple(flags)


def paired_cluster_bootstrap(
    records: Sequence[PairedRunCounts],
    *,
    bootstrap_replicates: int,
    confidence_level: Real,
    bootstrap_seed: int,
) -> PairedClusterBootstrapResult:
    """Compute paired pooled percentile intervals by resampling whole runs.

    Uses a PCG64 generator and NumPy's `method="linear"` quantile convention.
    One resampled index vector is applied jointly to B and C for every replicate.
    """
    materialized = _validate_records(records)
    replicates = _integer(bootstrap_replicates, name="bootstrap_replicates", minimum=1)
    seed = _integer(bootstrap_seed, name="bootstrap_seed", minimum=0)
    if isinstance(confidence_level, (bool, np.bool_)) or not isinstance(confidence_level, Real):
        raise ValueError("confidence_level must be a finite real in (0, 1)")
    confidence = float(confidence_level)
    if not math.isfinite(confidence) or not 0.0 < confidence < 1.0:
        raise ValueError("confidence_level must be a finite real in (0, 1)")

    run_count = len(materialized)
    rng = np.random.Generator(np.random.PCG64(seed))
    indices = rng.integers(0, run_count, size=(replicates, run_count), dtype=np.int64)
    estimates = np.empty((replicates, len(METRIC_NAMES)), dtype=np.float64)
    for replicate_index, row in enumerate(indices):
        summary = summarize_paired_indices(materialized, row)
        estimates[replicate_index] = (
            summary.ber_b,
            summary.ber_c,
            summary.delta_ber,
            summary.ser_b,
            summary.ser_c,
            summary.delta_ser,
        )

    alpha = (1.0 - confidence) / 2.0
    bounds = np.quantile(estimates, [alpha, 1.0 - alpha], axis=0, method="linear")
    intervals = tuple(
        BootstrapInterval(metric, float(bounds[0, index]), float(bounds[1, index]))
        for index, metric in enumerate(METRIC_NAMES)
    )
    return PairedClusterBootstrapResult(
        point_estimates=_point_estimates(materialized),
        intervals=intervals,
        replicate_estimates=estimates,
        resample_indices=indices,
        bootstrap_replicates=replicates,
        confidence_level=confidence,
        bootstrap_seed=seed,
        bit_generator="PCG64",
        quantile_method="numpy.quantile(method='linear')",
        ordered_run_ids=tuple(record.run_id for record in materialized),
        warning_flags=_diagnostic_warnings(materialized, estimates),
    )
