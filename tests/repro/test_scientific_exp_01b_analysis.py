from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import numpy as np

from scripts.analyze_energy_exp01b import (
    _expected_stream_seeds,
    _gain_plot_entry,
    analyze_scenario,
    crossing_gamma_db,
    paired_bootstrap_gain,
    recompute_trial_metrics,
)
from scripts.package_scientific_exp01b_audit import _make_manifest
from scripts.run_energy_exp01b import (
    _runtime_accounting,
    load_protocol,
    trial_spec,
    validate_seed_separation,
)

ROOT = Path(__file__).resolve().parents[2]


def test_gain_plot_does_not_present_partial_point_as_confirmed_estimate():
    partial = {
        "status": "PARTIAL",
        "gain_db": 4.0764,
        "bootstrap": {"confidence_interval_db": None, "valid_fraction": 0.8462},
        "crossings": {"joint": {"status": "BRACKETED"}, "b1": {"status": "BRACKETED"}},
    }

    value, interval, status = _gain_plot_entry(partial)

    assert value is None
    assert interval is None
    assert status == "insufficient_bootstrap"


def test_gain_plot_shows_only_estimates_with_valid_confidence_intervals():
    estimated = {
        "status": "ESTIMATED",
        "gain_db": 5.78,
        "bootstrap": {"confidence_interval_db": [5.39, 6.23]},
    }
    no_crossing = {
        "status": "NOT_ESTIMABLE",
        "gain_db": None,
        "crossings": {"joint": {"status": "BRACKETED"}, "b0": {"status": "NO_CROSSING"}},
    }

    assert _gain_plot_entry(estimated) == (5.78, (5.39, 6.23), None)
    assert _gain_plot_entry(no_crossing) == (None, None, "no_crossing")
    assert _gain_plot_entry(None) == (None, None, "unsupported")


def test_audit_manifest_counts_and_hashes_readme_but_excludes_itself():
    payload = [{"path": "trial/record.json", "size_bytes": 2, "sha256": "ab"}]

    manifest = _make_manifest(payload, b"readme")

    assert manifest["file_count"] == 3
    assert manifest["payload_file_count"] == 2
    assert manifest["files"][-1] == {
        "path": "README_FOR_CHATGPT.md",
        "size_bytes": 6,
        "sha256": "711a6108ba2ce6ca93dd47d6817f2361db10d8ab6eec89460b2dfc2c325efabe",
    }


def test_recompute_trial_metrics_uses_saved_bits_and_transmitted_samples():
    bits = np.asarray([0, 0, 1, 1], dtype=np.uint8)
    joint = np.asarray([0, 1, 1, 0], dtype=np.uint8)
    b0 = bits.copy()
    tx_samples = np.ones(16, dtype=np.complex128)
    arrays = {
        "information_bits": bits,
        "tx_samples": tx_samples,
        "noise_samples": np.ones(16, dtype=np.complex128),
        "coefficients": np.ones((1, 16), dtype=np.complex128),
        "joint_decoded_bits": joint,
        "b0_decoded_bits": b0,
    }
    record = {
        "amplitude": 1.0,
        "tx_energy": 16.0,
        "eb_d": 4.0,
        "bits": 4,
        "pairs": 2,
        "bit_errors": {"joint": 2, "b0": 0},
        "pair_errors": {"joint": 2, "b0": 0},
        "frame_errors": {"joint": 1, "b0": 0},
        "ber": {"joint": 0.5, "b0": 0.0},
        "ser": {"joint": 1.0, "b0": 0.0},
        "receiver_observation_hashes": {"joint": "same", "b0": "same"},
        "empirical_noise_power": 1.0,
        "empirical_path_powers": [1.0],
    }

    result = recompute_trial_metrics(record, arrays)

    assert result["tx_energy"] == 16.0
    assert result["eb_d"] == 4.0
    assert result["bit_errors"] == {"joint": 2, "b0": 0}
    assert result["pair_errors"] == {"joint": 2, "b0": 0}
    assert result["frame_errors"] == {"joint": 1, "b0": 0}


def test_recompute_trial_metrics_rejects_receiver_hash_mismatch():
    bits = np.zeros(4, dtype=np.uint8)
    arrays = {
        "information_bits": bits,
        "tx_samples": np.ones(16, dtype=np.complex128),
        "noise_samples": np.ones(16, dtype=np.complex128),
        "coefficients": np.ones((1, 16), dtype=np.complex128),
        "joint_decoded_bits": bits.copy(),
        "b0_decoded_bits": bits.copy(),
    }
    record = {
        "amplitude": 1.0,
        "tx_energy": 16.0,
        "eb_d": 4.0,
        "bits": 4,
        "pairs": 2,
        "bit_errors": {"joint": 0, "b0": 0},
        "pair_errors": {"joint": 0, "b0": 0},
        "frame_errors": {"joint": 0, "b0": 0},
        "ber": {"joint": 0.0, "b0": 0.0},
        "ser": {"joint": 0.0, "b0": 0.0},
        "receiver_observation_hashes": {"joint": "obs-a", "b0": "obs-b"},
        "empirical_noise_power": 1.0,
        "empirical_path_powers": [1.0],
    }

    try:
        recompute_trial_metrics(record, arrays)
    except ValueError as exc:
        assert "paired observation" in str(exc)
    else:
        raise AssertionError("hash mismatch must be rejected")


def test_crossing_reports_log_and_linear_interpolation_without_extrapolation():
    points = [
        {"gamma_db": 0.0, "ber": {"joint": 0.2}},
        {"gamma_db": 1.0, "ber": {"joint": 0.08}},
        {"gamma_db": 2.0, "ber": {"joint": 0.02}},
    ]

    log_result = crossing_gamma_db(points, 0.05, "joint", "log10_ber")
    linear_result = crossing_gamma_db(points, 0.05, "joint", "linear_ber")
    outside_result = crossing_gamma_db(points, 0.005, "joint", "log10_ber")

    assert log_result["status"] == "BRACKETED"
    assert linear_result["status"] == "BRACKETED"
    assert log_result["gamma_db"] != linear_result["gamma_db"]
    assert outside_result["status"] == "NO_CROSSING"
    assert outside_result["gamma_db"] is None


def test_paired_bootstrap_resamples_whole_trials_and_returns_gain_interval():
    rows = []
    for point_index, gamma in enumerate((0.0, 1.0, 2.0)):
        joint_base, b0_base = ((200, 250), (70, 150), (10, 30))[point_index]
        for trial_index in range(16):
            delta = (trial_index % 5) - 2
            joint_errors = joint_base + delta
            b0_errors = b0_base + 2 * delta
            rows.append(
                {
                    "scenario": "static",
                    "sweep": "amplitude",
                    "phase": "confirmatory",
                    "gamma_db": gamma,
                    "point_index": point_index,
                    "trial_index": trial_index,
                    "bits": 1000,
                    "pairs": 500,
                    "eb_d": 1.0,
                    "bit_errors": {"joint": joint_errors, "b0": b0_errors},
                    "pair_errors": {
                        "joint": max(1, (joint_errors + 1) // 2),
                        "b0": max(1, (b0_errors + 1) // 2),
                    },
                    "frame_errors": {"joint": int(joint_errors > 0), "b0": int(b0_errors > 0)},
                    "runtime_seconds": {"joint": 1.0, "b0": 0.5},
                    "receiver_observation_hashes": {"joint": "paired", "b0": "paired"},
                }
            )

    result = paired_bootstrap_gain(
        rows,
        target_ber=0.05,
        separate_arm="b0",
        replicates=200,
        seed=404,
        interpolation="log10_ber",
    )

    assert result["observed_crossings"] is True
    assert result["gain_db"] > 0
    assert result["bootstrap"]["valid_fraction"] >= 0.95
    assert result["bootstrap"]["confidence_interval_db"] is not None


def test_frozen_independent_protocol_builds_supported_receiver_specs_and_fresh_seeds():
    protocol, _, _ = load_protocol()
    static_trial = trial_spec(protocol, "static", point_index=0, trial_index=0)
    rician_trial = trial_spec(protocol, "rician", point_index=24, trial_index=39)

    assert len(protocol["scenarios"]["static"]["gamma_db_grid"]) == 29
    assert len(protocol["scenarios"]["rician"]["gamma_db_grid"]) == 25
    assert static_trial.amplitude == 0.5
    assert static_trial.receiver_arms == ("joint", "b0", "b1")
    assert rician_trial.receiver_arms == ("joint", "b0")
    separation = validate_seed_separation(protocol, ROOT / "outputs/scientific_exp_01")
    assert separation["new_trial_count"] == 2160
    assert separation["overlap"] == 0


def test_empty_scenario_analysis_is_reported_partial_without_inventing_data():
    protocol, _, _ = load_protocol()
    analysis_root = ROOT / "tmp" / "exp01b-empty-analysis-test"
    analysis_root.mkdir(parents=True, exist_ok=True)

    result = analyze_scenario([], "rician", protocol, analysis_root)

    assert result["status"] == "PARTIAL"
    assert result["aggregate_points"] == []
    assert result["target_gain_analysis"] == {}
    assert result["plot_files"] == []
    (analysis_root / "rician_aggregates.csv").unlink()
    analysis_root.rmdir()


def test_independent_seed_audit_matches_backend_seed_derivation():
    protocol, _, _ = load_protocol()
    for scenario, point_index, trial_index in (("static", 0, 0), ("rician", 24, 39)):
        backend = trial_spec(protocol, scenario, point_index, trial_index)
        expected = _expected_stream_seeds(protocol, scenario, point_index, trial_index)
        assert expected == dict(zip(("bits", "fading", "noise"), backend.seeds, strict=True))


def test_runtime_budget_excludes_only_receiver_wall_suspend_outliers():
    root = ROOT / "tmp" / f"exp01b-runtime-test-{uuid4().hex}"
    base = root / "confirmatory" / "rician" / "amplitude"
    ordinary = base / "p00" / "t0000"
    stalled = base / "p00" / "t0001"
    ordinary.mkdir(parents=True)
    stalled.mkdir(parents=True)
    try:
        (ordinary / "record.json").write_text(
            '{"elapsed_seconds": 3.0, "runtime_seconds": {"joint": 2.7, "b0": 0.2}}',
            encoding="utf-8",
        )
        (stalled / "record.json").write_text(
            '{"elapsed_seconds": 203.0, "runtime_seconds": {"joint": 202.7, "b0": 0.2}}',
            encoding="utf-8",
        )

        result = _runtime_accounting(root, "rician")

        assert result["raw_recorded_wall_seconds"] == 206.0
        assert result["effective_compute_seconds"] == 6.0
        assert result["suspension_outlier_count"] == 1
        assert result["corrections"][0]["raw_elapsed_seconds"] == 203.0
    finally:
        for path in (stalled / "record.json", ordinary / "record.json"):
            path.unlink(missing_ok=True)
        stalled.rmdir()
        ordinary.rmdir()
        (base / "p00").rmdir()
        (base).rmdir()
        (root / "confirmatory" / "rician").rmdir()
        (root / "confirmatory").rmdir()
        root.rmdir()
