from __future__ import annotations

import pytest

from hf_tcm.repro.scientific_exp03b_analysis import (
    aggregate_paired_trials,
    assess_gain_precision,
    estimate_paired_gain,
)
from scripts.analyze_scientific_exp03b import (
    _recount_system_trial_arrays,
    _validate_system_observation_pair,
)


def _records() -> list[dict]:
    rows = []
    for gamma, e_errors, h_errors, e_pairs, h_pairs in (
        (0.0, 20, 30, 10, 15),
        (1.0, 10, 20, 5, 10),
        (2.0, 1, 5, 1, 3),
    ):
        for _ in range(30):
            rows.append(
                {
                    "scenario": "awgn_direct",
                    "sweep": "amplitude_fixed_noise",
                    "phase": "confirmatory",
                    "gamma_db": gamma,
                    "bits": 100,
                    "pairs": 50,
                    "bit_errors": {"euclidean": e_errors, "hamming": h_errors},
                    "pair_errors": {"euclidean": e_pairs, "hamming": h_pairs},
                    "frame_errors": {"euclidean": 1, "hamming": 1},
                }
            )
    return rows


def test_paired_aggregation_reports_counts_and_cluster_intervals() -> None:
    points = aggregate_paired_trials(_records(), replicates=200, seed=19)

    assert len(points) == 3
    assert points[0]["bit_errors"] == {"euclidean": 600, "hamming": 900}
    assert points[0]["pair_errors"] == {"euclidean": 300, "hamming": 450}
    assert points[0]["paired_delta_ber"]["euclidean_minus_hamming"] == pytest.approx(-0.1)
    assert points[0]["bootstrap_95ci"]["replicates"] == 200
    assert points[0]["bootstrap_95ci"]["fer"]["euclidean"] == [1.0, 1.0]


def test_zero_observed_errors_are_reported_with_nonzero_uncertainty_bounds() -> None:
    rows = _records()
    for row in rows:
        row["bit_errors"] = {"euclidean": 0, "hamming": 0}
        row["pair_errors"] = {"euclidean": 0, "hamming": 0}
        row["frame_errors"] = {"euclidean": 0, "hamming": 0}

    point = aggregate_paired_trials(rows, replicates=100, seed=41)[0]

    uncertainty = point["zero_error_uncertainty"]["euclidean"]
    assert point["ber"]["euclidean"] == 0
    assert uncertainty["observed_bit_errors"] == 0
    assert 0 < uncertainty["iid_bit_ber_upper95_descriptive_only"] < 1
    assert 0 < uncertainty["independent_trial_fer_upper95"] < 1
    assert "not inferential for fading" in uncertainty["iid_bit_bound_warning"]


def test_paired_gain_uses_measured_brackets_without_extrapolation() -> None:
    estimate = estimate_paired_gain(
        _records(),
        target=0.05,
        euclidean_arm="euclidean",
        hamming_arm="hamming",
        replicates=300,
        seed=7,
    )

    assert estimate["observed"]["log_ber"]["euclidean"]["status"] == "BRACKETED"
    assert estimate["observed"]["log_ber"]["hamming"]["status"] == "EXACT_GRID_POINT"
    assert estimate["gain_db_log_ber"] is not None
    assert estimate["bootstrap"]["log_ber"]["valid_fraction"] == 1.0
    assert estimate["bootstrap"]["log_ber"]["gain_db_ci95"] is not None


def test_paired_validation_rejects_ser_counts_inconsistent_with_ber() -> None:
    rows = _records()
    rows[0]["pair_errors"]["euclidean"] = 0

    with pytest.raises(ValueError, match="counts disagree"):
        aggregate_paired_trials(rows, replicates=50)


def test_precision_assessment_applies_bracket_counts_and_interval_limits() -> None:
    rows = _records()
    points = aggregate_paired_trials(rows, replicates=200, seed=27)
    estimate = estimate_paired_gain(
        rows,
        target=0.05,
        euclidean_arm="euclidean",
        hamming_arm="hamming",
        replicates=200,
        seed=28,
    )
    criteria = {
        "per_arm_error_count_at_bracketing_points": {"0.05": 1},
        "max_95ci_half_width_ber": {"0.05": 1.0},
        "max_95ci_half_width_gain_db": {"0.05": 10.0},
        "minimum_valid_bootstrap_crossing_fraction": 0.5,
    }

    result = assess_gain_precision(
        estimate, points, target=0.05, arms=("euclidean", "hamming"), precision_criteria=criteria
    )

    assert result["status"] == "PRECISION_CRITERIA_MET"
    assert result["arm_checks"]["euclidean"]["bracket_points"]
    assert result["bootstrap_valid_fraction"] >= 0.5


def test_precision_assessment_does_not_call_unbracketed_target_precise() -> None:
    rows = _records()
    points = aggregate_paired_trials(rows, replicates=100, seed=37)
    estimate = estimate_paired_gain(
        rows,
        target=0.001,
        euclidean_arm="euclidean",
        hamming_arm="hamming",
        replicates=100,
        seed=38,
    )
    criteria = {
        "per_arm_error_count_at_bracketing_points": {"0.001": 1},
        "max_95ci_half_width_ber": {"0.001": 1.0},
        "max_95ci_half_width_gain_db": {"0.001": 10.0},
        "minimum_valid_bootstrap_crossing_fraction": 0.5,
    }

    result = assess_gain_precision(
        estimate, points, target=0.001, arms=("euclidean", "hamming"), precision_criteria=criteria
    )

    assert result["status"] == "TARGET_NOT_ESTIMABLE"
    assert any("target_not_bracketed" in reason for reason in result["reasons"])


def test_system_array_recount_recomputes_ber_pair_ser_and_fer() -> None:
    arrays = {
        "information_bits": [0, 1, 1, 0, 1, 1],
        "joint_decoded_bits": [0, 1, 0, 0, 1, 0],
        "b0_decoded_bits": [1, 1, 1, 0, 0, 1],
    }
    record = {
        "bits": 6,
        "pairs": 3,
        "bit_errors": {"joint": 2, "b0": 2},
        "pair_errors": {"joint": 2, "b0": 2},
        "frame_errors": {"joint": 1, "b0": 1},
    }

    result = _recount_system_trial_arrays(arrays, record)

    assert result["joint"] == {"bit_errors": 2, "pair_errors": 2, "frame_error": 1}
    assert result["b0"] == {"bit_errors": 2, "pair_errors": 2, "frame_error": 1}


def test_system_array_recount_rejects_sidecar_error_counts_that_do_not_match_bits() -> None:
    arrays = {
        "information_bits": [0, 1, 1, 0],
        "joint_decoded_bits": [1, 1, 1, 0],
    }
    record = {
        "bits": 4,
        "pairs": 2,
        "bit_errors": {"joint": 0},
        "pair_errors": {"joint": 0},
        "frame_errors": {"joint": 0},
    }

    with pytest.raises(ValueError, match="independent BER/SER/FER recount"):
        _recount_system_trial_arrays(arrays, record)


def test_full_system_receivers_must_reference_one_observation_hash() -> None:
    shared_hash = "a" * 64
    _validate_system_observation_pair(
        {
            "observation_sha256": shared_hash,
            "receiver_observation_hashes": {"joint": shared_hash, "b0": shared_hash},
        }
    )

    with pytest.raises(ValueError, match="observation hashes are not paired"):
        _validate_system_observation_pair(
            {
                "observation_sha256": shared_hash,
                "receiver_observation_hashes": {"joint": shared_hash, "b0": "b" * 64},
            }
        )
