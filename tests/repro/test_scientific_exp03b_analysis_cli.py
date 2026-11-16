import scripts.analyze_scientific_exp03b as analysis
from hf_tcm.repro.scientific_exp03b_analysis import assess_gain_precision


def test_analysis_reads_frozen_bootstrap_resamples_key():
    protocol = {"analysis": {"bootstrap_seed_root": 833101, "bootstrap_resamples": 5000}}

    assert analysis._analysis_bootstrap_settings(protocol) == (833101, 5000)


def test_system_precision_schema_is_normalized_without_inventing_ber_width():
    protocol = {
        "system_comparison": {
            "targets_ber": [0.05],
            "precision_criteria": {
                "minimum_errors_per_arm_at_target_bracket": 200,
                "max_95ci_half_width_gain_db": {"0.05": 0.5},
                "minimum_valid_bootstrap_crossing_fraction": 0.95,
            },
        }
    }

    criteria = analysis._analysis_precision_criteria(protocol, "system_comparison")
    estimate = {
        "observed": {
            "log_ber": {
                "euclidean": {"status": "BRACKETED", "bracket_db": [0.0, 1.0]},
                "hamming": {"status": "BRACKETED", "bracket_db": [0.0, 1.0]},
            }
        },
        "bootstrap": {"log_ber": {"valid_fraction": 0.99, "gain_db_ci95": [0.2, 0.4]}},
        "gain_db_log_ber": 0.3,
    }
    points = [
        {
            "gamma_db": gamma,
            "ber": {"joint": 0.05, "b0": 0.052},
            "bit_errors": {"joint": 250, "b0": 260},
            "bootstrap_95ci": {"ber": {"joint": [0.04, 0.06], "b0": [0.04, 0.06]}},
        }
        for gamma in (0.0, 1.0)
    ]

    assert criteria["per_arm_error_count_at_bracketing_points"] == {"0.05": 200}
    assert "max_95ci_half_width_ber" not in criteria
    result = assess_gain_precision(
        estimate,
        points,
        target=0.05,
        arms=("joint", "b0"),
        estimate_arms=("euclidean", "hamming"),
        precision_criteria=criteria,
    )
    assert result["status"] == "PRECISION_CRITERIA_MET"
    assert result["maximum_ber_ci95_half_width"] is None


def test_figure_content_check_uses_downsampled_pixels_and_detects_blank_images():
    import numpy as np

    blank = np.zeros((620, 940, 3), dtype=np.uint8)
    chart = blank.copy()
    chart[::20, :, :] = (255, 255, 255)
    chart[:, ::20, :] = (10, 120, 180)

    assert analysis._visible_rgb_values(blank) == 1
    assert analysis._visible_rgb_values(chart) > 1


def test_system_energy_points_use_frozen_grid_not_measured_float_artifacts():
    protocol = {"system_comparison": {"energy_grid_gamma_db": {"awgn": [0.0, 0.5, 1.0]}}}

    assert analysis._system_grid_gamma(protocol, "awgn", 1, 0.5, 0.5, 0.500000000000001) == 0.5

    try:
        analysis._system_grid_gamma(protocol, "awgn", 1, 0.5, 0.5, 0.51)
    except ValueError as error:
        assert "measured energy" in str(error)
    else:
        raise AssertionError("out-of-grid measured energy must be rejected")


def test_system_trial_ids_are_rebuilt_from_frozen_point_and_trial_indices():
    assert analysis._system_trial_id("awgn", 14, 99) == "confirmatory-awgn-p14-t0099"
