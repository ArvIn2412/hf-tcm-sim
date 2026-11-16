from __future__ import annotations

import numpy as np
import pytest

from hf_tcm.evaluation.error_metrics import ErrorCounts
from hf_tcm.evaluation.paired_cluster_bootstrap import (
    PairedRunCounts,
    paired_cluster_bootstrap,
    summarize_paired_indices,
)


def _record(
    run_id: str,
    *,
    f: int,
    b_bits: int,
    c_bits: int,
    b_symbols: int,
    c_symbols: int,
) -> PairedRunCounts:
    return PairedRunCounts(
        run_id=run_id,
        b_counts=ErrorCounts(b_bits, 2 * f, b_symbols, f),
        c_counts=ErrorCounts(c_bits, 2 * f, c_symbols, f),
    )


def test_pooled_metrics_use_raw_counts_for_unequal_runs() -> None:
    records = (
        _record("r0", f=1, b_bits=0, c_bits=1, b_symbols=0, c_symbols=1),
        _record("r1", f=3, b_bits=3, c_bits=0, b_symbols=1, c_symbols=0),
    )
    summary = paired_cluster_bootstrap(
        records,
        bootstrap_replicates=200,
        confidence_level=0.95,
        bootstrap_seed=17,
    ).point_estimates
    assert summary.ber_b == pytest.approx(3 / 8)
    assert summary.ber_c == pytest.approx(1 / 8)
    assert summary.delta_ber == pytest.approx(-2 / 8)
    assert summary.ser_b == pytest.approx(1 / 4)
    assert summary.ser_c == pytest.approx(1 / 4)
    assert summary.delta_ser == 0.0
    assert summary.ber_b != pytest.approx((0.0 + 3 / 6) / 2)


def test_explicit_paired_indices_match_manual_pooled_calculation() -> None:
    records = (
        _record("r0", f=2, b_bits=0, c_bits=2, b_symbols=0, c_symbols=1),
        _record("r1", f=4, b_bits=2, c_bits=0, b_symbols=1, c_symbols=0),
    )
    result = summarize_paired_indices(records, np.asarray([1, 0], dtype=np.int64))
    assert result.selected_run_ids == ("r1", "r0")
    assert result.ber_b == pytest.approx(2 / 12)
    assert result.ber_c == pytest.approx(2 / 12)
    assert result.ser_b == pytest.approx(1 / 6)
    assert result.ser_c == pytest.approx(1 / 6)
    assert result.delta_ber == 0.0
    assert result.delta_ser == 0.0


def test_bootstrap_reuses_same_run_indices_for_b_and_c() -> None:
    records = (
        _record("r0", f=2, b_bits=0, c_bits=2, b_symbols=0, c_symbols=1),
        _record("r1", f=2, b_bits=2, c_bits=0, b_symbols=1, c_symbols=0),
        _record("r2", f=2, b_bits=1, c_bits=1, b_symbols=1, c_symbols=1),
    )
    result = paired_cluster_bootstrap(
        records,
        bootstrap_replicates=64,
        confidence_level=0.95,
        bootstrap_seed=1234,
    )
    assert result.resample_indices.shape == (64, 3)
    for row, selected in zip(result.resample_indices, result.resample_run_ids, strict=True):
        assert selected == tuple(records[int(index)].run_id for index in row)
    assert result.replicate_estimates.shape == (64, 6)


def test_equal_per_run_counts_make_every_paired_delta_replicate_zero() -> None:
    records = tuple(
        _record(f"r{i}", f=2, b_bits=i % 2, c_bits=i % 2, b_symbols=i % 2, c_symbols=i % 2)
        for i in range(4)
    )
    result = paired_cluster_bootstrap(
        records,
        bootstrap_replicates=100,
        confidence_level=0.95,
        bootstrap_seed=88,
    )
    assert np.array_equal(result.replicate_estimates[:, 2], np.zeros(100))
    assert np.array_equal(result.replicate_estimates[:, 5], np.zeros(100))


def test_single_cluster_bootstrap_ci_matches_exact_manual_rates() -> None:
    record = _record("single", f=1, b_bits=0, c_bits=1, b_symbols=0, c_symbols=1)
    result = paired_cluster_bootstrap(
        (record,),
        bootstrap_replicates=25,
        confidence_level=0.95,
        bootstrap_seed=5,
    )
    assert result.point_estimates.ber_b == 0.0
    assert result.point_estimates.ber_c == 0.5
    assert result.point_estimates.delta_ber == 0.5
    assert result.interval("ber_c").lower == result.interval("ber_c").upper == 0.5
    assert result.interval("delta_ser").lower == result.interval("delta_ser").upper == 1.0


def test_zero_errors_emit_explicit_small_sample_and_degenerate_warnings() -> None:
    records = tuple(
        _record(f"r{i}", f=4, b_bits=0, c_bits=0, b_symbols=0, c_symbols=0) for i in range(5)
    )
    result = paired_cluster_bootstrap(
        records,
        bootstrap_replicates=80,
        confidence_level=0.95,
        bootstrap_seed=91,
    )
    assert result.point_estimates.ber_b == 0.0
    assert result.point_estimates.ber_c == 0.0
    assert result.interval("delta_ber").lower == result.interval("delta_ber").upper == 0.0
    assert {
        "too_few_independent_runs",
        "all_zero_errors",
        "all_runs_identical",
        "degenerate_bootstrap_distribution",
        "rare_error_count",
        "bootstrap_interval_unreliable",
    }.issubset(result.warning_flags)


def test_bootstrap_reproducible_and_different_seed_keeps_point_estimate() -> None:
    records = tuple(
        _record(
            f"r{i}",
            f=i + 1,
            b_bits=i % (2 * (i + 1) + 1),
            c_bits=(i + 1) % (2 * (i + 1) + 1),
            b_symbols=i % (i + 2),
            c_symbols=(i + 1) % (i + 2),
        )
        for i in range(5)
    )
    first = paired_cluster_bootstrap(
        records, bootstrap_replicates=100, confidence_level=0.95, bootstrap_seed=37
    )
    repeated = paired_cluster_bootstrap(
        records, bootstrap_replicates=100, confidence_level=0.95, bootstrap_seed=37
    )
    other = paired_cluster_bootstrap(
        records, bootstrap_replicates=100, confidence_level=0.95, bootstrap_seed=38
    )
    assert np.array_equal(first.resample_indices, repeated.resample_indices)
    assert np.array_equal(first.replicate_estimates, repeated.replicate_estimates)
    assert first.point_estimates == other.point_estimates
    assert not np.array_equal(first.resample_indices, other.resample_indices)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"bootstrap_replicates": 0, "confidence_level": 0.95, "bootstrap_seed": 1},
        {"bootstrap_replicates": 10, "confidence_level": 1.0, "bootstrap_seed": 1},
        {"bootstrap_replicates": 10, "confidence_level": float("nan"), "bootstrap_seed": 1},
        {"bootstrap_replicates": 10, "confidence_level": 0.95, "bootstrap_seed": -1},
    ],
)
def test_invalid_bootstrap_parameters_are_rejected(kwargs: dict[str, object]) -> None:
    records = (_record("r", f=1, b_bits=0, c_bits=0, b_symbols=0, c_symbols=0),)
    with pytest.raises(ValueError):
        paired_cluster_bootstrap(records, **kwargs)  # type: ignore[arg-type]


def test_zero_runs_duplicate_ids_and_invalid_count_pairs_are_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        paired_cluster_bootstrap(
            (), bootstrap_replicates=10, confidence_level=0.95, bootstrap_seed=1
        )
    duplicate = _record("same", f=1, b_bits=0, c_bits=0, b_symbols=0, c_symbols=0)
    with pytest.raises(ValueError, match="unique"):
        paired_cluster_bootstrap(
            (duplicate, duplicate),
            bootstrap_replicates=10,
            confidence_level=0.95,
            bootstrap_seed=1,
        )
    with pytest.raises(ValueError):
        ErrorCounts(bit_errors=-1, total_bits=2, symbol_errors=0, total_symbols=1)
    with pytest.raises(ValueError):
        ErrorCounts(bit_errors=3, total_bits=2, symbol_errors=0, total_symbols=1)
    with pytest.raises(ValueError, match="paired B/C totals"):
        PairedRunCounts(
            "mismatch",
            ErrorCounts(0, 2, 0, 1),
            ErrorCounts(0, 4, 0, 2),
        )


def test_explicit_indices_are_validated_and_inputs_are_not_mutated() -> None:
    records = (_record("r0", f=1, b_bits=0, c_bits=1, b_symbols=0, c_symbols=1),)
    indices = np.asarray([0, 0], dtype=np.int64)
    before = indices.copy()
    result = summarize_paired_indices(records, indices)
    assert np.array_equal(indices, before)
    assert result.ber_b == 0.0
    for invalid in (np.asarray([], dtype=np.int64), np.asarray([-1]), np.asarray([1])):
        with pytest.raises(ValueError):
            summarize_paired_indices(records, invalid)
