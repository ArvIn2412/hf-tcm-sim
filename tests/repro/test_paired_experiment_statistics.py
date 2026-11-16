from __future__ import annotations

import pytest

from hf_tcm.repro.paired_experiment import (
    ExperimentConfig,
    aggregate_trials,
    derive_trial_seeds,
    paired_cluster_bootstrap,
)


def test_seed_derivation_is_deterministic_domain_separated_and_trial_specific() -> None:
    first = derive_trial_seeds(1234, "pilot", 0, 4)
    assert first == derive_trial_seeds(1234, "pilot", 0, 4)
    assert len({first.bits, first.fading, first.noise}) == 3
    assert first != derive_trial_seeds(1234, "pilot", 0, 5)
    assert first != derive_trial_seeds(1234, "pilot", 1, 4)


def test_aggregate_uses_ratio_of_sums_and_delta_is_joint_minus_separate() -> None:
    records = [
        {
            "status": "completed",
            "joint_bit_errors": 2,
            "separate_bit_errors": 0,
            "compared_bits": 10,
            "compared_bits_separate": 10,
            "joint_pair_symbol_errors": 1,
            "separate_pair_symbol_errors": 0,
            "joint_phase_symbol_errors": 1,
            "separate_phase_symbol_errors": 0,
            "compared_symbols": 5,
        },
        {
            "status": "completed",
            "joint_bit_errors": 0,
            "separate_bit_errors": 1,
            "compared_bits": 30,
            "compared_bits_separate": 30,
            "joint_pair_symbol_errors": 0,
            "separate_pair_symbol_errors": 1,
            "joint_phase_symbol_errors": 0,
            "separate_phase_symbol_errors": 1,
            "compared_symbols": 15,
        },
    ]
    stats = aggregate_trials(records)
    assert stats["joint_ber"] == pytest.approx(2 / 40)
    assert stats["separate_ber"] == pytest.approx(1 / 40)
    assert stats["delta_ber_joint_minus_separate"] == pytest.approx(1 / 40)
    assert stats["total_compared_bits"] == 40
    assert stats["completed_trials"] == 2


def test_cluster_bootstrap_is_reproducible_and_handles_zero_differences() -> None:
    records = [
        {
            "status": "completed",
            "joint_bit_errors": e,
            "separate_bit_errors": e,
            "compared_bits": 100,
            "compared_bits_separate": 100,
            "joint_pair_symbol_errors": s,
            "separate_pair_symbol_errors": s,
            "joint_phase_symbol_errors": s,
            "separate_phase_symbol_errors": s,
            "compared_symbols": 50,
        }
        for e, s in ((0, 0), (1, 1), (2, 2), (0, 0))
    ]
    first = paired_cluster_bootstrap(records, confidence_level=0.95, replicates=1000, seed=99)
    second = paired_cluster_bootstrap(records, confidence_level=0.95, replicates=1000, seed=99)
    assert first == second
    assert first["delta_ber_ci"] == [0.0, 0.0]
    assert first["resampling_unit"] == "paired_trial"


def test_bootstrap_reports_no_interval_for_one_independent_trial() -> None:
    row = {
        "status": "completed",
        "joint_bit_errors": 0,
        "separate_bit_errors": 1,
        "compared_bits": 20,
        "compared_bits_separate": 20,
        "joint_pair_symbol_errors": 0,
        "separate_pair_symbol_errors": 1,
        "joint_phase_symbol_errors": 0,
        "separate_phase_symbol_errors": 1,
        "compared_symbols": 10,
    }
    result = paired_cluster_bootstrap([row], confidence_level=0.95, replicates=1000, seed=4)
    assert result["status"] == "exploratory_too_few_independent_trials"
    assert result["delta_ber_ci"] is None


def test_aggregate_excludes_failed_trials_and_weights_unequal_frame_lengths() -> None:
    rows = [
        {
            "status": "completed",
            "joint_bit_errors": 1,
            "separate_bit_errors": 2,
            "compared_bits": 10,
            "compared_bits_separate": 10,
            "compared_symbols": 5,
            "joint_pair_symbol_errors": 1,
            "separate_pair_symbol_errors": 2,
            "joint_phase_symbol_errors": 1,
            "separate_phase_symbol_errors": 2,
        },
        {
            "status": "completed",
            "joint_bit_errors": 0,
            "separate_bit_errors": 2,
            "compared_bits": 30,
            "compared_bits_separate": 30,
            "compared_symbols": 15,
            "joint_pair_symbol_errors": 0,
            "separate_pair_symbol_errors": 2,
            "joint_phase_symbol_errors": 0,
            "separate_phase_symbol_errors": 2,
        },
        {"status": "failed", "error_message": "excluded"},
    ]
    stats = aggregate_trials(rows)
    assert stats["completed_trials"] == 2
    assert stats["joint_ber"] == pytest.approx(1 / 40)
    assert stats["separate_ber"] == pytest.approx(4 / 40)


def test_config_rejects_ambiguous_physical_snr_and_invalid_pilot_size(tmp_path) -> None:
    with pytest.raises(ValueError, match="sample-domain"):
        ExperimentConfig(
            experiment_id="bad",
            frame_symbols=256,
            noise_variances=(0.01,),
            trials_per_point=20,
            root_seed=1,
            output_dir=str(tmp_path),
            snr_convention="ebn0_db",
        )
    with pytest.raises(ValueError, match="at least 20"):
        ExperimentConfig(
            experiment_id="bad",
            frame_symbols=256,
            noise_variances=(0.01,),
            trials_per_point=2,
            root_seed=1,
            output_dir=str(tmp_path),
        )
