from __future__ import annotations

import json

import pytest

from hf_tcm.repro.paired_experiment import (
    ExperimentConfig,
    PairedTrialResult,
    run_paired_experiment,
    run_paired_trial,
    verify_experiment,
)
from hf_tcm.repro.paired_experiment_plots import write_experiment_plots


def test_real_identity_trial_pairs_two_receivers_on_same_observation() -> None:
    config = ExperimentConfig(
        experiment_id="identity_unit_pair",
        frame_symbols=32,
        noise_variances=(0.0,),
        trials_per_point=1,
        root_seed=123,
        output_dir="unused",
        run_level="smoke",
        channel_profile="identity",
        path_delays_samples=(0,),
        path_powers=(1.0,),
        rician_k_factors=(0.0,),
        los_phases_rad=(0.0,),
        diagnostics_level="summary_only",
    )
    result = run_paired_trial(config, 0, 0)
    row = result.record
    assert row["status"] == "completed"
    assert row["joint_observation_sha256"] == row["separate_observation_sha256"]
    assert row["compared_bits"] == row["compared_bits_separate"] == 64
    assert row["joint_bit_errors"] == row["separate_bit_errors"] == 0
    assert row["joint_pair_symbol_errors"] == row["separate_pair_symbol_errors"] == 0
    assert row["traceback_depth"] == 20
    assert "EvaluationTruth" not in row


def test_known_static_multipath_control_uses_public_06b_receiver_profile() -> None:
    config = ExperimentConfig(
        experiment_id="static_isi_control_pair",
        frame_symbols=32,
        noise_variances=(0.0,),
        trials_per_point=1,
        root_seed=321,
        output_dir="unused",
        run_level="smoke",
        channel_profile="known_static_multipath",
        diagnostics_level="summary_only",
    )
    row = run_paired_trial(config, 0, 0).record
    assert row["joint_receiver_kind"] == "known_static_06b_control"
    assert row["joint_receiver_profile_id"] == "repro06b_static_known_isi_joint_mlse_v1"
    assert row["joint_observation_sha256"] == row["separate_observation_sha256"]
    assert row["traceback_depth"] == 20


@pytest.mark.parametrize(
    ("profile", "delays", "powers", "k_factors", "rho"),
    [
        ("static_single_path", (0,), (1.0,), (0.0,), 0.98),
        ("rician_single_path", (0,), (1.0,), (4.0,), 0.98),
        ("unknown_static_multipath", (0, 3), (1.0, 0.25), (4.0, 1.0), 0.98),
        ("slow_fading_multipath", (0, 3), (1.0, 0.25), (4.0, 1.0), 0.995),
    ],
)
def test_supported_channel_profiles_run_as_paired_smokes(
    profile, delays, powers, k_factors, rho
) -> None:
    config = ExperimentConfig(
        experiment_id=f"{profile}_smoke",
        frame_symbols=32,
        noise_variances=(0.0,),
        trials_per_point=1,
        root_seed=44,
        output_dir="unused",
        run_level="smoke",
        channel_profile=profile,
        path_delays_samples=delays,
        path_powers=powers,
        rician_k_factors=k_factors,
        los_phases_rad=tuple(0.0 for _ in delays),
        fading_correlation=rho,
        diagnostics_level="summary_only",
    )
    row = run_paired_trial(config, 0, 0).record
    assert row["status"] == "completed"
    assert row["joint_observation_sha256"] == row["separate_observation_sha256"]


def test_resume_skips_valid_completed_trial_without_duplicate_aggregation(
    tmp_path, monkeypatch
) -> None:
    config = ExperimentConfig(
        experiment_id="resume_smoke",
        frame_symbols=32,
        noise_variances=(0.0,),
        trials_per_point=1,
        root_seed=9,
        output_dir=str(tmp_path),
        run_level="smoke",
        channel_profile="identity",
        path_delays_samples=(0,),
        path_powers=(1.0,),
        rician_k_factors=(0.0,),
        los_phases_rad=(0.0,),
        diagnostics_level="summary_only",
    )
    calls = 0

    def fake_trial(_config, point, trial):
        nonlocal calls
        calls += 1
        return PairedTrialResult(
            {
                "status": "completed",
                "experiment_id": config.experiment_id,
                "point_index": point,
                "trial_index": trial,
                "compared_bits": 64,
                "compared_bits_separate": 64,
                "joint_bit_errors": 1,
                "separate_bit_errors": 2,
                "compared_symbols": 32,
                "joint_pair_symbol_errors": 1,
                "separate_pair_symbol_errors": 2,
                "joint_phase_symbol_errors": 1,
                "separate_phase_symbol_errors": 2,
            }
        )

    monkeypatch.setattr("hf_tcm.repro.paired_experiment.run_paired_trial", fake_trial)
    first = run_paired_experiment(config, progress=False)
    second = run_paired_experiment(config, progress=False)
    assert calls == 1
    assert first["completed_trials"] == second["completed_trials"] == 1
    assert second["points"][0]["joint_bit_errors"] == 1
    assert verify_experiment(tmp_path / config.experiment_id)

    trial_path = tmp_path / config.experiment_id / "point_00" / "trial_0000" / "trial.json"
    record = json.loads(trial_path.read_text(encoding="utf-8"))
    record["joint_bit_errors"] = 7
    trial_path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        run_paired_experiment(config, progress=False)


def test_budget_stop_saves_only_completed_trials(tmp_path, monkeypatch) -> None:
    config = ExperimentConfig(
        experiment_id="budget_smoke",
        frame_symbols=32,
        noise_variances=(0.0, 0.1),
        trials_per_point=1,
        root_seed=10,
        output_dir=str(tmp_path),
        run_level="smoke",
        channel_profile="identity",
        path_delays_samples=(0,),
        path_powers=(1.0,),
        rician_k_factors=(0.0,),
        los_phases_rad=(0.0,),
        max_trials=1,
        diagnostics_level="summary_only",
    )

    def fake_trial(_config, point, trial):
        return PairedTrialResult(
            {
                "status": "completed",
                "experiment_id": config.experiment_id,
                "point_index": point,
                "trial_index": trial,
                "compared_bits": 64,
                "compared_bits_separate": 64,
                "joint_bit_errors": 0,
                "separate_bit_errors": 0,
                "compared_symbols": 32,
                "joint_pair_symbol_errors": 0,
                "separate_pair_symbol_errors": 0,
                "joint_phase_symbol_errors": 0,
                "separate_phase_symbol_errors": 0,
            }
        )

    monkeypatch.setattr("hf_tcm.repro.paired_experiment.run_paired_trial", fake_trial)
    result = run_paired_experiment(config, progress=False)
    assert result["status"] == "incomplete"
    assert result["completed_trials"] == 1
    assert result["stop_reason"] == "max_trials_budget"


def test_plots_are_built_from_measured_rows_and_keep_zero_ber_zero(tmp_path) -> None:
    point = {
        "completed_trials": 2,
        "noise_variance_complex_per_sample": 0.05,
        "joint_ber": 0.0,
        "separate_ber": 0.1,
        "joint_pair_ser": 0.0,
        "separate_pair_ser": 0.2,
        "delta_ber_joint_minus_separate": -0.1,
        "confidence_intervals": {"delta_ber_ci": [-0.2, 0.0]},
    }
    summary = {"points": [point]}
    records = [
        {
            "status": "completed",
            "point_index": 0,
            "trial_index": 0,
            "joint_bit_errors": 0,
            "separate_bit_errors": 1,
            "joint_seconds": 1.0,
            "separate_seconds": 0.1,
        }
    ]
    paths = write_experiment_plots(summary, records, tmp_path)
    assert len(paths) == 6
    ber_svg = (tmp_path / "01_ber_vs_noise_variance.svg").read_text(encoding="utf-8")
    assert "0 (виміряно)" in ber_svg
    assert "0.000001" not in ber_svg


def test_manifest_rejects_unsafe_relative_path_before_reading(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"files":{"../outside":"bad"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe path"):
        verify_experiment(tmp_path)
