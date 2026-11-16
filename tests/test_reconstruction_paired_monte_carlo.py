from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest
from test_matched_m2_b5_experiment import _configuration

from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.evaluation.reconstruction_paired_monte_carlo import (
    PairedMonteCarloConfig,
    load_paired_monte_carlo_config,
    run_paired_monte_carlo,
    validate_paired_monte_carlo_config,
)


def _config_mapping(*, runs: int = 3, symbols: int = 4) -> dict[str, object]:
    profile = _configuration(0.75, origin=23, initial_time=41)
    profile["estimator"]["alpha_prime"] = 0.85
    profile["estimator"]["k_tilde"] = [[0.35, -0.2]]
    profile["estimator"]["mu0"] = [[0.0, 0.0]]
    profile["estimator"]["initial_estimates"] = {
        "fluctuating_iq": [[0.42, 0.91]],
        "full_iq": [[0.42, 0.91]],
    }
    return {
        "experiment_id": "m5f-test",
        "number_of_independent_runs": runs,
        "symbols_per_run": symbols,
        "real_channel_gain": 0.75,
        "sigma_squared": 0.08,
        "data_rng_master_seed": 1201,
        "noise_rng_master_seed": 1202,
        "bootstrap_seed": 1203,
        "bootstrap_replicates": 80,
        "confidence_level": 0.95,
        "beta": 0.7,
        "initial_fluctuating_iq": [0.42, 0.91],
        "initial_full_iq": [0.42, 0.91],
        "alpha_prime_c": 0.85,
        "k_tilde_c": [0.35, -0.2],
        "mu0_c": [0.0, 0.0],
        "absolute_sample_origin": 23,
        "absolute_symbol_origin": 5,
        "initial_estimator_time_index": 41,
        "reconstruction_profile": "reconstructed_offline",
        "receiver_profile_version": "B5c/B5d plus M5e paired diagnostic API",
        "profile_provenance": "test template derived from explicit ADR contracts",
        "reconstruction_configuration": profile,
    }


def test_config_requires_explicit_profile_and_recursion_decomposition() -> None:
    config = validate_paired_monte_carlo_config(_config_mapping())
    assert isinstance(config, PairedMonteCarloConfig)
    assert config.number_of_independent_runs == 3
    invalid = _config_mapping()
    invalid["initial_full_iq"] = [0.5, 0.9]
    with pytest.raises(ValueError, match="full_iq"):
        validate_paired_monte_carlo_config(invalid)
    invalid = _config_mapping()
    invalid["mu0_c"] = [0.01, 0.0]
    invalid["reconstruction_configuration"]["estimator"]["mu0"] = [[0.01, 0.0]]
    with pytest.raises(ValueError, match="B stays frozen"):
        validate_paired_monte_carlo_config(invalid)


def test_checked_in_experiment_configuration_is_explicit_and_validated() -> None:
    path = Path(__file__).parents[1] / "configs/m5f_paired_monte_carlo.json"
    config = load_paired_monte_carlo_config(path)
    assert config.number_of_independent_runs == 12
    assert config.symbols_per_run == 32
    assert config.bootstrap_replicates == 2000
    assert config.reconstruction_profile == "reconstructed_offline"


def test_small_runs_are_paired_raw_count_records_with_separate_rng_streams() -> None:
    result = run_paired_monte_carlo(validate_paired_monte_carlo_config(_config_mapping()))
    assert len(result.runs) == 3
    assert len({run.run_id for run in result.runs}) == 3
    assert len({run.data_seed for run in result.runs}) == 3
    assert len({run.noise_seed for run in result.runs}) == 3
    for run in result.runs:
        assert run.b_counts.total_bits == run.c_counts.total_bits == 8
        assert run.b_counts.total_symbols == run.c_counts.total_symbols == 4
        assert len(run.b_decoded_information_bits) == len(run.c_decoded_information_bits) == 8
        assert len(run.b_hypothesis_path) == len(run.c_hypothesis_path) == 4
        validate_hypothesis_edge_path(run.b_hypothesis_path, initial_state=(0, 0))
        validate_hypothesis_edge_path(run.c_hypothesis_path, initial_state=(0, 0))
        assert run.received_sha256
        assert run.b_received_sha256 == run.c_received_sha256 == run.received_sha256
        assert run.initial_fluctuating_iq == run.initial_full_iq == (0.42, 0.91)
        assert run.absolute_symbol_indices == (5, 6, 7, 8)
        assert run.estimator_time_indices == (41, 42, 43, 44)
        assert len(run.absolute_sample_indices) == 32
        assert run.b_state_unchanged
        assert run.c_state_changed
        assert np.isfinite(run.c_final_deviation_from_initial)
        assert run.status == "complete"
    assert result.bootstrap.bootstrap_replicates == 80
    assert result.bootstrap.bootstrap_seed == 1203
    assert not result.bootstrap.resample_indices.flags.writeable
    assert result.point_estimates == result.bootstrap.point_estimates


def test_same_seeds_reproduce_run_hashes_counts_and_bootstrap() -> None:
    config = validate_paired_monte_carlo_config(_config_mapping(runs=4, symbols=6))
    first = run_paired_monte_carlo(config)
    repeated = run_paired_monte_carlo(config)
    assert tuple(run.received_sha256 for run in first.runs) == tuple(
        run.received_sha256 for run in repeated.runs
    )
    assert tuple((run.b_counts, run.c_counts) for run in first.runs) == tuple(
        (run.b_counts, run.c_counts) for run in repeated.runs
    )
    assert np.array_equal(first.bootstrap.resample_indices, repeated.bootstrap.resample_indices)
    assert np.array_equal(
        first.bootstrap.replicate_estimates, repeated.bootstrap.replicate_estimates
    )


def test_run_record_has_reference_and_truth_outside_receiver_api(monkeypatch) -> None:
    import hf_tcm.evaluation.reconstruction_adaptive_diagnostics as diagnostics

    original = diagnostics.run_reconstruction_posterior_estimator_sequence
    calls: list[dict[str, object]] = []

    def capture(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(diagnostics, "run_reconstruction_posterior_estimator_sequence", capture)
    run_paired_monte_carlo(validate_paired_monte_carlo_config(_config_mapping(runs=2, symbols=2)))
    assert len(calls) == 6  # 2 runs × (A, B, C)
    for call in calls:
        assert "reference_information_bits" not in call
        assert "real_channel_gain" not in call
        assert "ChannelTruth" not in call
    path = Path(__file__).parents[1] / "src/hf_tcm/evaluation/reconstruction_paired_monte_carlo.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    identifiers = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "ChannelTruth" not in identifiers


@pytest.mark.parametrize(
    "field,value",
    [
        ("number_of_independent_runs", 0),
        ("symbols_per_run", 0),
        ("real_channel_gain", 0.0),
        ("sigma_squared", float("nan")),
        ("data_rng_master_seed", -1),
        ("bootstrap_replicates", 0),
        ("confidence_level", 1.0),
        ("beta", 0.0),
        ("initial_fluctuating_iq", [True, False]),
        ("reconstruction_profile", "source_faithful"),
    ],
)
def test_invalid_experiment_configuration_is_rejected(field: str, value: object) -> None:
    data = _config_mapping()
    data[field] = value
    with pytest.raises(ValueError):
        validate_paired_monte_carlo_config(data)


def test_data_and_noise_master_seeds_must_be_separate() -> None:
    data = _config_mapping()
    data["noise_rng_master_seed"] = data["data_rng_master_seed"]
    with pytest.raises(ValueError, match="separate RNG streams"):
        validate_paired_monte_carlo_config(data)
