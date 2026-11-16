"""Independent synthetic checks; these curves are not performance evidence."""

from __future__ import annotations

import math

import numpy as np
import pytest

from hf_tcm.repro.energy_statistics import (
    aggregate_energy_records,
    analyze_energy_records,
    required_gamma_crossing,
)


def record(gamma: float, joint: int, b0: int, bits: int = 1_000_000) -> dict:
    return {
        "gamma_db": gamma,
        "bit_errors": {"joint": joint, "b0": b0},
        "pair_errors": {"joint": min(joint, bits // 2), "b0": min(b0, bits // 2)},
        "bits": bits,
        "pairs": bits // 2,
        "scenario": "synthetic",
        "sweep": "gamma",
        "phase": "test",
    }


def synthetic_records(trials: int = 25) -> list[dict]:
    return [
        record(gamma, joint, separate)
        for gamma, joint, separate in [(0, 10_000, 100_000), (2, 100, 10_000), (4, 1, 1)]
        for _ in range(trials)
    ]


def test_hand_calculated_synthetic_gain_is_one_point_five_db() -> None:
    result = analyze_energy_records(synthetic_records(), 0.001, replicates=40, seed=9)
    assert result["observed_crossing"] is True
    assert result["required_gamma_db"] == {"joint": 1.0, "separate": 2.5}
    assert result["gain_db"] == pytest.approx(1.5)
    assert result["bootstrap"]["confidence_interval_db"] == [1.5, 1.5]
    assert result["bootstrap"]["valid_fraction"] == 1


def test_aggregate_uses_ratio_of_sums_with_varying_denominators() -> None:
    result = aggregate_energy_records([record(0, 1, 2, 10), record(0, 1, 2, 100)])
    assert len(result) == 1
    assert result[0]["ber"]["joint"] == pytest.approx(2 / 110)
    assert result[0]["ser"]["b0"] == pytest.approx(4 / 55)
    assert result[0]["trials"] == 2


@pytest.mark.parametrize("target", [0.2, 0.0000001])
def test_no_extrapolation(target: float) -> None:
    points = aggregate_energy_records(synthetic_records())
    assert required_gamma_crossing(points, target)["status"] == "NO_CROSSING"


def test_floor_does_not_invent_crossing() -> None:
    records = [record(gamma, 2000, 3000) for gamma in (0, 2, 4)]
    result = analyze_energy_records(records, 0.001, replicates=20)
    assert result["observed_crossing"] is False
    assert result["gain_db"] is None
    assert result["bootstrap"]["confidence_interval_db"] is None
    assert result["bootstrap"]["valid_fraction"] == 0


def test_all_zero_and_zero_endpoint_have_no_logarithmic_crossing() -> None:
    points = aggregate_energy_records([record(0, 0, 100), record(2, 0, 0)])
    assert required_gamma_crossing(points, 0.001)["status"] == "ALL_ZERO_BER"
    assert required_gamma_crossing(points, 0.00001, "b0")["status"] == (
        "ZERO_BER_BRACKET_UNRESOLVED"
    )


def test_nonmonotonic_multiple_crossings_are_rejected() -> None:
    points = aggregate_energy_records(
        [record(0, 10000, 10000), record(2, 100, 100), record(4, 10000, 10000)]
    )
    crossing = required_gamma_crossing(points, 0.001)
    assert crossing["status"] == "AMBIGUOUS_MULTIPLE_CROSSINGS"
    assert crossing["required_gamma_db"] is None


def test_exact_grid_crossing_and_target_plateau() -> None:
    points = aggregate_energy_records([record(0, 10000, 10000), record(2, 1000, 1000)])
    assert required_gamma_crossing(points, 0.001)["required_gamma_db"] == 2
    points.append({**points[-1], "gamma_db": 4})
    assert required_gamma_crossing(points, 0.001)["status"] == "TARGET_PLATEAU"


def test_bootstrap_reproducible_and_records_order_independent() -> None:
    records = synthetic_records(5)
    records.extend([record(0, 20000, 50000), record(2, 200, 20000), record(4, 3, 5)])
    first = analyze_energy_records(records, 0.001, replicates=80, seed=91)
    second = analyze_energy_records(records, 0.001, replicates=80, seed=91)
    assert first == second
    assert first == analyze_energy_records(list(reversed(records)), 0.001, replicates=80, seed=91)
    assert first["bootstrap"]["confidence_interval_db"][0] < first["gain_db"]
    assert "LOW_TRIAL_COUNT" in first["flags"]


def test_bootstrap_matches_independent_scalar_ratio_of_sums_oracle() -> None:
    rows = [
        record(0, 100, 150, 1000),
        record(0, 450, 900, 9000),
        record(2, 1, 2, 1000),
        record(2, 9, 18, 9000),
    ]
    replicates, seed, target = 70, 123, 0.02
    indices = [
        np.random.default_rng(child).integers(2, size=(replicates, 2))
        for child in np.random.SeedSequence(seed).spawn(2)
    ]
    gains = []
    for replicate in range(replicates):
        crossings = []
        for arm in ("joint", "b0"):
            rates = []
            for point in range(2):
                sampled = [rows[2 * point + int(index)] for index in indices[point][replicate]]
                rates.append(
                    sum(row["bit_errors"][arm] for row in sampled)
                    / sum(row["bits"] for row in sampled)
                )
            crossings.append(2 * math.log10(target / rates[0]) / math.log10(rates[1] / rates[0]))
        gains.append(crossings[1] - crossings[0])
    expected = np.quantile(gains, [0.025, 0.975])
    actual = analyze_energy_records(rows, target, replicates=replicates, seed=seed)
    assert actual["bootstrap"]["valid_fraction"] == 1
    assert actual["bootstrap"]["confidence_interval_db"] == pytest.approx(expected)


def test_third_arm_is_preserved_and_can_be_selected() -> None:
    rows = synthetic_records()
    for row in rows:
        row["bit_errors"]["b1"] = row["bit_errors"]["b0"]
        row["pair_errors"]["b1"] = row["pair_errors"]["b0"]
    result = analyze_energy_records(rows, 0.001, arm="b1", replicates=20)
    assert result["separate_arm"] == "b1"
    assert result["gain_db"] == 1.5


def test_paired_bootstrap_preserves_identical_arms() -> None:
    records = [
        record(gamma, errors, errors)
        for gamma, base in [(0, 10000), (2, 100), (4, 1)]
        for errors in (base, 2 * base, 3 * base)
    ]
    result = analyze_energy_records(records, 0.001, replicates=100, seed=2)
    assert result["bootstrap"]["confidence_interval_db"] == [0, 0]


def test_partial_bootstrap_reports_conditional_quantiles_without_ci() -> None:
    records = [record(0, 10000, 10000)] * 4 + [record(2, 0, 0), record(2, 1000, 1000)]
    result = analyze_energy_records(records, 0.001, replicates=500, seed=7)
    bootstrap = result["bootstrap"]
    assert 0 < bootstrap["valid_fraction"] < 0.95
    assert bootstrap["status"] == "PARTIAL_VALID_CROSSINGS"
    assert bootstrap["confidence_interval_db"] is None
    assert bootstrap["conditional_quantiles_db"] == [0, 0]


@pytest.mark.parametrize("field,value", [("bits", 0), ("gamma_db", math.nan)])
def test_invalid_records_rejected(field: str, value: float) -> None:
    row = record(0, 10, 20)
    row[field] = value
    with pytest.raises(ValueError):
        aggregate_energy_records([row])


def test_mixed_context_and_excess_errors_rejected() -> None:
    row = record(0, 1, 2)
    with pytest.raises(ValueError, match="scenario"):
        aggregate_energy_records([row, {**row, "scenario": "different"}])
    with pytest.raises(ValueError, match="bit_errors"):
        aggregate_energy_records([record(0, 11, 2, 10)])
