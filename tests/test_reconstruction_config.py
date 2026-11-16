"""Validation tests for the inactive reconstructed_offline config profile."""

from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.posterior import ALLOWED_HYPOTHESIS_TRANSITIONS
from hf_tcm.reconstruction_config import (
    ReconstructionConfigError,
    load_reconstructed_offline_config,
    validate_receiver_profile_mode,
    validate_reconstructed_offline_config,
)


def _synthetic_config() -> dict[str, object]:
    """Build explicit test-only values; none of these are research defaults."""
    transition_mask = ALLOWED_HYPOTHESIS_TRANSITIONS.astype(np.float64)
    transition_probabilities = transition_mask / transition_mask.sum(axis=1, keepdims=True)
    assumption_names = (
        "candidate_index_space",
        "candidate_count",
        "labeling",
        "transition_model",
        "initial_state",
        "initial_prior",
        "likelihood_type",
        "beta",
        "alpha_prime",
        "k_tilde",
        "mu0",
        "initial_estimates",
        "estimator_time_index",
        "estimator_time_rule",
        "timebase",
        "samples_per_symbol",
        "sample_rate_hz",
        "symbol_rate_hz",
        "symbol_origin_sample",
        "path_delays_samples",
        "path_count",
        "aggregate_observation_model",
        "prediction_combination",
        "beam_width",
        "decision_lag_symbols",
    )
    return {
        "schema_version": 1,
        "profile": "reconstructed_offline",
        "paper_exact": False,
        "receiver_enabled": False,
        "candidate_index_space": "m4_1_hypothesis_id",
        "candidate_count": 16,
        "labeling": {
            "name": "synthetic_test_labeling",
            "origin": "synthetic fixture; not an article convention",
            "bit_order": ["c2", "c1", "c0"],
            "output_to_b": [0, 1, 2, 3, 4, 5, 6, 7],
            "phase_offset_rad": 0.0,
        },
        "transition_model": {
            "name": "adr003_uniform_allowed_edges",
            "probabilities": transition_probabilities.tolist(),
        },
        "initial": {
            "state": [0, 0],
            "prior": [
                0.25 if hypothesis.current_state == (0, 0) else 0.0 for hypothesis in HYPOTHESES
            ],
        },
        "likelihood": {
            "kind": "exp_negative_beta_project_reconstruction_metric",
            "beta": 0.5,
        },
        "estimator": {
            "alpha_prime": 0.75,
            "k_tilde": [[0.1, -0.2], [0.3, 0.4]],
            "mu0": [[0.0, 0.0], [0.1, 0.0]],
            "initial_time_index": 0,
            "time_rule": "one_recursion_step_i_to_i_plus_1",
            "initial_estimates": {
                "fluctuating_iq": [[0.0, 0.0], [0.0, 0.0]],
                "full_iq": [[0.0, 0.0], [0.1, 0.0]],
            },
        },
        "timebase": {
            "name": "synthetic_test_timebase",
            "samples_per_symbol": 8,
            "sample_rate_hz": 8000.0,
            "symbol_rate_hz": 1000.0,
            "symbol_origin_sample": 0,
            "path_count": 2,
            "path_delays_samples": [0, 3],
        },
        "observation_model": {
            "kind": "aggregate_received_iq",
            "prediction_combination": "synthetic_sum_of_estimated_paths",
        },
        "search": {
            "beam_width": 4,
            "decision_lag_symbols": 20,
        },
        "assumption_provenance": {
            name: {
                "status": "proposed",
                "source": "synthetic test fixture",
                "note": "test-only explicit value; does not accept any ADR",
            }
            for name in assumption_names
        },
    }


def test_complete_profile_requires_explicit_metadata_and_stays_inactive() -> None:
    config = _synthetic_config()

    validated = validate_reconstructed_offline_config(config)

    assert validated["profile"] == "reconstructed_offline"
    assert validated["paper_exact"] is False
    assert validated["receiver_enabled"] is False
    assert validated["assumption_provenance"] == config["assumption_provenance"]


def test_accepted_adr012_observation_config_is_explicit_and_inactive() -> None:
    config = _synthetic_config()
    config["timebase"]["path_count"] = 1  # type: ignore[index]
    config["timebase"]["path_delays_samples"] = [0]  # type: ignore[index]
    config["estimator"]["k_tilde"] = [[0.1, -0.2]]  # type: ignore[index]
    config["estimator"]["mu0"] = [[0.0, 0.0]]  # type: ignore[index]
    config["estimator"]["initial_estimates"] = {  # type: ignore[index]
        "fluctuating_iq": [[0.0, 0.0]],
        "full_iq": [[0.0, 0.0]],
    }
    config["observation_model"] = {  # type: ignore[assignment]
        "kind": "adr012_l1_real_mean8",
        "prediction_combination": "explicit_project_prediction",
        "iq_rule": "(-Im(received), Re(received))",
        "sample_reduction": "arithmetic_mean_exactly_8",
        "waveform_rule": "rectangular_zoh",
    }

    validated = validate_reconstructed_offline_config(config)

    assert validated["observation_model"] == config["observation_model"]
    assert validated["receiver_enabled"] is False
    assert validated["paper_exact"] is False


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("iq_rule", "raw_re_im", "iq_rule"),
        ("sample_reduction", "select_one", "sample_reduction"),
        ("waveform_rule", "linear", "waveform_rule"),
    ],
)
def test_adr012_config_rejects_noncontract_observation_values(field, value, message) -> None:
    config = _synthetic_config()
    config["timebase"]["path_count"] = 1  # type: ignore[index]
    config["timebase"]["path_delays_samples"] = [0]  # type: ignore[index]
    config["estimator"]["k_tilde"] = [[0.1, -0.2]]  # type: ignore[index]
    config["estimator"]["mu0"] = [[0.0, 0.0]]  # type: ignore[index]
    config["estimator"]["initial_estimates"] = {  # type: ignore[index]
        "fluctuating_iq": [[0.0, 0.0]],
        "full_iq": [[0.0, 0.0]],
    }
    config["observation_model"] = {
        "kind": "adr012_l1_real_mean8",
        "prediction_combination": "explicit_project_prediction",
        "iq_rule": "(-Im(received), Re(received))",
        "sample_reduction": "arithmetic_mean_exactly_8",
        "waveform_rule": "rectangular_zoh",
    }  # type: ignore[assignment]
    config["observation_model"][field] = value  # type: ignore[index]

    with pytest.raises(ReconstructionConfigError, match=message):
        validate_reconstructed_offline_config(config)


@pytest.mark.parametrize(
    ("path", "expected_message"),
    [
        (("candidate_count",), "candidate_count"),
        (("labeling", "name"), "labeling.name"),
        (("labeling", "origin"), "labeling.origin"),
        (("transition_model", "probabilities"), "transition_model.probabilities"),
        (("initial", "state"), "initial.state"),
        (("initial", "prior"), "initial.prior"),
        (("likelihood", "kind"), "likelihood.kind"),
        (("likelihood", "beta"), "likelihood.beta"),
        (("estimator", "alpha_prime"), "estimator.alpha_prime"),
        (("estimator", "k_tilde"), "estimator.k_tilde"),
        (("estimator", "mu0"), "estimator.mu0"),
        (("estimator", "initial_estimates"), "estimator.initial_estimates"),
        (("estimator", "initial_time_index"), "estimator.initial_time_index"),
        (("estimator", "time_rule"), "estimator.time_rule"),
        (("timebase", "sample_rate_hz"), "timebase.sample_rate_hz"),
        (("timebase", "samples_per_symbol"), "timebase.samples_per_symbol"),
        (("timebase", "symbol_rate_hz"), "timebase.symbol_rate_hz"),
        (("timebase", "path_delays_samples"), "timebase.path_delays_samples"),
        (("observation_model", "kind"), "observation_model.kind"),
        (("search", "beam_width"), "search.beam_width"),
        (("search", "decision_lag_symbols"), "search.decision_lag_symbols"),
        (("assumption_provenance", "beta"), "assumption_provenance.beta"),
        (
            ("assumption_provenance", "estimator_time_rule"),
            "assumption_provenance.estimator_time_rule",
        ),
    ],
)
def test_missing_required_values_have_path_specific_errors(
    path: tuple[str, ...], expected_message: str
) -> None:
    config = _synthetic_config()
    target = config
    for key in path[:-1]:
        target = target[key]  # type: ignore[index, assignment]
    del target[path[-1]]  # type: ignore[index]

    with pytest.raises(ReconstructionConfigError, match=expected_message.replace(".", r"\.")):
        validate_reconstructed_offline_config(config)


@pytest.mark.parametrize(
    ("path", "value", "expected_message"),
    [
        (("profile",), "source_faithful", "profile"),
        (("candidate_count",), 15, "candidate_count"),
        (("paper_exact",), True, "paper_exact"),
        (("receiver_enabled",), True, "receiver_enabled"),
        (("likelihood", "beta"), 0.0, "beta"),
        (("likelihood", "beta"), -0.5, "beta"),
        (("likelihood", "beta"), float("nan"), "beta"),
        (("likelihood", "kind"), "gaussian", "likelihood.kind"),
        (("transition_model", "name"), "arbitrary", "transition_model.name"),
        (("initial", "state"), [0, 1], "ADR-004"),
        (("initial", "prior"), [1.0 / 16.0] * 16, "uniform on hypotheses"),
        (("estimator", "initial_time_index"), True, "initial_time_index"),
        (("estimator", "time_rule"), "per_frame", "time_rule"),
        (("search", "beam_width"), 0, "beam_width"),
        (("search", "decision_lag_symbols"), -1, "decision_lag_symbols"),
        (("observation_model", "kind"), "per_path_observations", "observation_model.kind"),
        (("labeling", "output_to_b"), [0, 1, 2, 3, 4, 5, 6, 6], "output_to_b"),
        (("timebase", "sample_rate_hz"), 16000.0, "must equal"),
        (("timebase", "path_delays_samples"), [0, -1], "path_delays_samples\\[1\\]"),
    ],
)
def test_rejects_forbidden_or_invalid_profile_values(
    path: tuple[str, ...], value: object, expected_message: str
) -> None:
    config = _synthetic_config()
    target = config
    for key in path[:-1]:
        target = target[key]  # type: ignore[index, assignment]
    target[path[-1]] = value  # type: ignore[index]

    with pytest.raises(ReconstructionConfigError, match=expected_message.replace(".", r"\.")):
        validate_reconstructed_offline_config(config)


@pytest.mark.parametrize(
    ("path", "value", "expected_message"),
    [
        (("initial", "state"), [0], "initial.state"),
        (("initial", "prior"), [0.5] * 16, "initial.prior"),
        (("estimator", "k_tilde"), [[1.0, 2.0]], "estimator.k_tilde"),
        (("estimator", "mu0"), [[1.0, 2.0, 3.0], [1.0, 2.0, 3.0]], "estimator.mu0"),
        (
            ("estimator", "initial_estimates", "fluctuating_iq"),
            [[0.0, 0.0]],
            "initial_estimates.fluctuating_iq",
        ),
        (("timebase", "path_delays_samples"), [0], "path_count"),
    ],
)
def test_rejects_inconsistent_vector_and_array_shapes(
    path: tuple[str, ...], value: object, expected_message: str
) -> None:
    config = _synthetic_config()
    target = config
    for key in path[:-1]:
        target = target[key]  # type: ignore[index, assignment]
    target[path[-1]] = value  # type: ignore[index]

    with pytest.raises(ReconstructionConfigError, match=expected_message.replace(".", r"\.")):
        validate_reconstructed_offline_config(config)


def test_rejects_transition_mass_on_structurally_forbidden_edge() -> None:
    config = _synthetic_config()
    matrix = config["transition_model"]["probabilities"]  # type: ignore[index]
    allowed = ALLOWED_HYPOTHESIS_TRANSITIONS
    source, target = np.argwhere(allowed == 0)[0]
    matrix[source][target] = 0.01
    allowed_targets = np.flatnonzero(allowed[source])
    matrix[source][allowed_targets[0]] -= 0.01

    with pytest.raises(ReconstructionConfigError, match="forbidden"):
        validate_reconstructed_offline_config(config)


def test_rejects_nonuniform_allowed_transition_probabilities() -> None:
    config = _synthetic_config()
    probabilities = config["transition_model"]["probabilities"]  # type: ignore[index]
    probabilities[0][0] += 0.1
    probabilities[0][1] -= 0.1

    with pytest.raises(ReconstructionConfigError, match="uniform on allowed edges"):
        validate_reconstructed_offline_config(config)


def test_rejects_transition_matrix_shape_and_non_stochastic_rows() -> None:
    config = _synthetic_config()
    matrix = config["transition_model"]["probabilities"]  # type: ignore[index]
    matrix.pop()
    with pytest.raises(ReconstructionConfigError, match=r"shape \(16, 16\)"):
        validate_reconstructed_offline_config(config)

    config = _synthetic_config()
    config["transition_model"]["probabilities"][0][0] += 0.1  # type: ignore[index]
    with pytest.raises(ReconstructionConfigError, match="sum to 1"):
        validate_reconstructed_offline_config(config)


def test_source_faithful_mode_rejects_reconstruction_settings() -> None:
    config = _synthetic_config()

    with pytest.raises(ReconstructionConfigError, match="source_faithful.*reconstruction"):
        validate_receiver_profile_mode(config, requested_mode="source_faithful")


def test_unknown_keys_are_rejected_instead_of_ignored() -> None:
    config = _synthetic_config()
    config["unreviewed_scientific_parameter"] = 1.0

    with pytest.raises(ReconstructionConfigError, match="unexpected.*unreviewed"):
        validate_reconstructed_offline_config(config)


def test_input_mapping_is_not_mutated_by_validation() -> None:
    config = _synthetic_config()
    original = copy.deepcopy(config)

    validate_reconstructed_offline_config(config)

    assert config == original


def test_json_loader_validates_without_activating_profile(tmp_path) -> None:
    path = tmp_path / "reconstructed.json"
    path.write_text(json.dumps(_synthetic_config()), encoding="utf-8")

    loaded = load_reconstructed_offline_config(path)

    assert loaded["profile"] == "reconstructed_offline"
    assert loaded["receiver_enabled"] is False


def test_json_loader_rejects_nonstandard_nan_values(tmp_path) -> None:
    path = tmp_path / "reconstructed.json"
    path.write_text('{"beta": NaN}', encoding="utf-8")

    with pytest.raises(ReconstructionConfigError, match="non-finite JSON constant"):
        load_reconstructed_offline_config(path)
