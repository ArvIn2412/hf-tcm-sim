from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import pytest

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.evaluation.reconstruction_factorial_ablation import (
    FACTORIAL_ARMS,
    run_reconstruction_factorial_ablation,
)
from hf_tcm.receiver.paper_recursion import update_quadrature_estimates

ROOT = Path(__file__).resolve().parents[1]
BETA = 0.7
EXPECTED_PHASES = (0, 2, 4, 6, 2, 0, 6, 4, 1, 3, 5, 7, 3, 1, 7, 5)
RECEIVED = np.asarray(
    [complex((index - 7) / 20.0, ((index % 5) - 2) / 25.0) for index in range(16)],
    dtype=np.complex128,
)
INITIAL_STATE = np.asarray([0.42, 0.91], dtype=np.float64)


def _observed_iq(received: np.ndarray, symbol: int) -> np.ndarray:
    first = 8 * symbol
    return np.asarray(
        [
            [-float(received[index].imag), float(received[index].real)]
            for index in range(first, first + 8)
        ],
        dtype=np.float64,
    )


def _phase_prediction(coefficients: np.ndarray, phase: int) -> tuple[float, float]:
    angle = phase * math.pi / 4.0
    return (
        -float(coefficients[0]) * math.sin(angle),
        float(coefficients[1]) * math.cos(angle),
    )


def _manual_metric_row(received: np.ndarray, symbol: int, coefficients: np.ndarray) -> np.ndarray:
    observed = _observed_iq(received, symbol)
    return np.asarray(
        [
            math.fsum(
                (float(observed[sample, axis]) - _phase_prediction(coefficients, phase)[axis]) ** 2
                for sample in range(8)
                for axis in range(2)
            )
            for phase in EXPECTED_PHASES
        ],
        dtype=np.float64,
    )


def _manual_predictions(coefficients: np.ndarray) -> np.ndarray:
    return np.asarray(
        [_phase_prediction(coefficients, phase) for phase in EXPECTED_PHASES],
        dtype=np.float64,
    )


def _manual_posterior(prior: np.ndarray, metrics: np.ndarray) -> np.ndarray:
    minimum = min(float(value) for value in metrics[prior > 0.0])
    unnormalized = [
        float(prior[index]) * math.exp(-BETA * (float(metrics[index]) - minimum))
        if prior[index] > 0.0
        else 0.0
        for index in range(16)
    ]
    total = math.fsum(unnormalized)
    return np.asarray([value / total for value in unnormalized], dtype=np.float64)


def _manual_prior_and_transition() -> tuple[np.ndarray, np.ndarray]:
    first_prior = np.asarray(
        [1.0 / 4.0 if edge.current_state == (0, 0) else 0.0 for edge in HYPOTHESES],
        dtype=np.float64,
    )
    transition = np.zeros((16, 16), dtype=np.float64)
    for row, previous in enumerate(HYPOTHESES):
        allowed = [
            column
            for column, following in enumerate(HYPOTHESES)
            if previous.next_state == following.current_state
        ]
        for column in allowed:
            transition[row, column] = 1.0 / len(allowed)
    return first_prior, transition


def _manual_innovation(
    observed: np.ndarray, predicted: np.ndarray, posterior: np.ndarray
) -> np.ndarray:
    return np.asarray(
        [
            math.fsum(
                float(posterior[edge]) * (float(observed[axis]) - float(predicted[edge, axis]))
                for edge in range(16)
            )
            for axis in range(2)
        ],
        dtype=np.float64,
    )


def _assert_array(actual: np.ndarray, expected: np.ndarray, *, atol: float = 1e-12) -> None:
    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=atol)


def test_four_factorial_arms_are_the_frozen_historical_policies() -> None:
    assert tuple(FACTORIAL_ARMS) == ("B", "A", "K", "C")
    assert FACTORIAL_ARMS["B"].alpha_prime == 1.0
    assert FACTORIAL_ARMS["B"].k_tilde == (0.0, 0.0)
    assert FACTORIAL_ARMS["A"].alpha_prime == 0.85
    assert FACTORIAL_ARMS["A"].k_tilde == (0.0, 0.0)
    assert FACTORIAL_ARMS["K"].alpha_prime == 1.0
    assert FACTORIAL_ARMS["K"].k_tilde == (0.35, -0.2)
    assert FACTORIAL_ARMS["C"].alpha_prime == 0.85
    assert FACTORIAL_ARMS["C"].k_tilde == (0.35, -0.2)


def test_first_symbol_is_shared_and_state_factorial_decomposition_is_additive() -> None:
    result = run_reconstruction_factorial_ablation(received=RECEIVED)
    arms = result.arms
    _assert_array(result.initial_state.full_iq[0], INITIAL_STATE, atol=0.0)
    _assert_array(result.initial_state.fluctuating_iq[0], INITIAL_STATE, atol=0.0)
    assert result.invariant_status == "first_symbol_shared_invariants_passed"
    assert all(arms[name].sequence_result.symbol_count == 2 for name in ("B", "A", "K", "C"))

    first_metrics = [arms[name].first_metrics for name in ("B", "A", "K", "C")]
    first_posteriors = [arms[name].first_posterior for name in ("B", "A", "K", "C")]
    for row in first_metrics[1:]:
        _assert_array(row, first_metrics[0], atol=0.0)
    for row in first_posteriors[1:]:
        _assert_array(row, first_posteriors[0], atol=0.0)
    _assert_array(
        arms["B"].first_metrics,
        _manual_metric_row(RECEIVED, 0, INITIAL_STATE),
    )

    first_step = arms["B"].sequence_result.history[0].b4c_result
    expected_innovation = _manual_innovation(
        first_step.observed_iq,
        first_step.predicted_iq,
        first_step.posterior,
    )
    _assert_array(arms["B"].first_innovation_iq, expected_innovation)

    alpha_delta = (0.85 - 1.0) * INITIAL_STATE
    correction_delta = np.asarray([0.35, -0.2]) * expected_innovation
    total_delta = alpha_delta + correction_delta
    _assert_array(result.delta_alpha_iq, alpha_delta)
    _assert_array(result.delta_k_iq, correction_delta)
    _assert_array(result.delta_combined_iq, total_delta)

    first_fluctuating = {
        name: arms[name].first_post_state.fluctuating_iq[0] for name in ("B", "A", "K", "C")
    }
    _assert_array(first_fluctuating["A"] - first_fluctuating["B"], alpha_delta)
    _assert_array(first_fluctuating["K"] - first_fluctuating["B"], correction_delta)
    _assert_array(first_fluctuating["C"] - first_fluctuating["B"], total_delta)
    _assert_array(
        first_fluctuating["C"]
        - first_fluctuating["A"]
        - first_fluctuating["K"]
        + first_fluctuating["B"],
        np.zeros(2),
    )


def test_second_symbol_pre_states_predictions_and_metric_factorial_contrasts() -> None:
    result = run_reconstruction_factorial_ablation(received=RECEIVED)
    arms = result.arms
    for name in ("B", "A", "K", "C"):
        _assert_array(
            arms[name].second_pre_state.fluctuating_iq,
            arms[name].first_post_state.fluctuating_iq,
            atol=0.0,
        )
        _assert_array(
            arms[name].second_pre_state.full_iq,
            arms[name].first_post_state.full_iq,
            atol=0.0,
        )
        assert arms[name].second_symbol_index == 1
        assert arms[name].second_sample_window == tuple(range(8, 16))
        expected = _manual_metric_row(RECEIVED, 1, arms[name].second_pre_state.full_iq[0])
        _assert_array(arms[name].second_metrics, expected)
        _assert_array(
            arms[name].second_predictions_iq,
            _manual_predictions(arms[name].second_pre_state.full_iq[0]),
        )

    metrics = {name: arms[name].second_metrics for name in ("B", "A", "K", "C")}
    expected_alpha = metrics["A"] - metrics["B"]
    expected_k = metrics["K"] - metrics["B"]
    expected_combined = metrics["C"] - metrics["B"]
    expected_interaction = metrics["C"] - metrics["A"] - metrics["K"] + metrics["B"]
    _assert_array(result.metric_contrasts.alpha, expected_alpha)
    _assert_array(result.metric_contrasts.correction, expected_k)
    _assert_array(result.metric_contrasts.combined, expected_combined)
    _assert_array(result.metric_contrasts.interaction, expected_interaction)
    assert np.linalg.norm(expected_interaction) > 1e-8

    state_predictions = {
        name: _manual_predictions(arms[name].second_pre_state.full_iq[0])
        for name in ("B", "A", "K", "C")
    }
    expanded_interaction = np.asarray(
        [
            math.fsum(
                2.0
                * (
                    float(state_predictions["A"][edge, axis])
                    - float(state_predictions["B"][edge, axis])
                )
                * (
                    float(state_predictions["K"][edge, axis])
                    - float(state_predictions["B"][edge, axis])
                )
                for _sample in range(8)
                for axis in range(2)
            )
            for edge in range(16)
        ],
        dtype=np.float64,
    )
    _assert_array(result.metric_contrasts.interaction, expanded_interaction)


def test_actual_and_fixed_common_prior_posteriors_are_separately_audited() -> None:
    result = run_reconstruction_factorial_ablation(received=RECEIVED)
    prior, transition = _manual_prior_and_transition()
    assert result.transition_prior_api_status == "not exported; independently derived for audit"
    for name in ("B", "A", "K", "C"):
        arm = result.arms[name]
        expected_first = _manual_posterior(prior, arm.first_metrics)
        _assert_array(arm.first_posterior, expected_first, atol=1e-13)
        derived_q = np.asarray(
            [
                math.fsum(
                    float(expected_first[row]) * float(transition[row, col]) for row in range(16)
                )
                for col in range(16)
            ],
            dtype=np.float64,
        )
        expected_actual_second = _manual_posterior(derived_q, arm.second_metrics)
        _assert_array(arm.second_actual_posterior, expected_actual_second, atol=1e-13)
        assert math.fsum(float(value) for value in arm.second_actual_posterior) == pytest.approx(
            1.0, rel=0.0, abs=1e-13
        )
        assert arm.hypothesis_ids == tuple(range(16))
        assert arm.sequence_result.history[0].b4c_result.edge_mode == "first_edge"
        assert arm.sequence_result.history[1].b4c_result.edge_mode == "later_edge"
        _assert_array(
            arm.second_fixed_common_prior_posterior,
            _manual_posterior(np.full(16, 1.0 / 16.0), arm.second_metrics),
            atol=1e-13,
        )

    _assert_array(result.derived_transition_prior, derived_q, atol=1e-13)

    actual = {name: result.arms[name].second_actual_posterior for name in ("B", "A", "K", "C")}
    _assert_array(result.posterior_contrasts.actual.alpha, actual["A"] - actual["B"], atol=1e-13)
    _assert_array(
        result.posterior_contrasts.actual.correction, actual["K"] - actual["B"], atol=1e-13
    )
    _assert_array(result.posterior_contrasts.actual.combined, actual["C"] - actual["B"], atol=1e-13)
    _assert_array(
        result.posterior_contrasts.actual.interaction,
        actual["C"] - actual["A"] - actual["K"] + actual["B"],
        atol=1e-13,
    )
    common = {
        name: result.arms[name].second_fixed_common_prior_posterior for name in ("B", "A", "K", "C")
    }
    _assert_array(
        result.posterior_contrasts.fixed_common_prior.interaction,
        common["C"] - common["A"] - common["K"] + common["B"],
        atol=1e-13,
    )
    assert np.linalg.norm(actual["B"] - common["B"]) > 1e-8


def test_zero_innovation_control_separates_alpha_decay_from_correction() -> None:
    observed = np.asarray([0.2, -0.4])
    predicted = np.repeat(observed[np.newaxis, :], 16, axis=0)
    posterior = np.full(16, 1.0 / 16.0)
    previous = INITIAL_STATE.copy()
    mu0 = np.zeros(2)
    actual = {}
    for name, arm in FACTORIAL_ARMS.items():
        updated, _ = update_quadrature_estimates(
            previous_fluctuating=previous,
            alpha_prime=arm.alpha_prime,
            k_tilde=arm.k_tilde,
            posterior=posterior,
            observed_iq=observed,
            predicted_iq=predicted,
            mu0=mu0,
        )
        actual[name] = updated
    _assert_array(actual["B"], previous, atol=0.0)
    _assert_array(actual["A"], 0.85 * previous, atol=1e-14)
    _assert_array(actual["K"], previous, atol=0.0)
    _assert_array(actual["C"], 0.85 * previous, atol=1e-14)


def test_nonzero_absolute_sample_origin_and_input_immutability() -> None:
    received_copy = RECEIVED.copy()
    result = run_reconstruction_factorial_ablation(
        received=RECEIVED,
        symbol_origin_sample=13,
        initial_estimator_time_index=7,
    )
    assert RECEIVED == pytest.approx(received_copy, rel=0.0, abs=0.0)
    for name in ("B", "A", "K", "C"):
        history = result.arms[name].sequence_result.history
        assert history[0].first_sample_index == 13
        assert history[0].last_sample_index == 20
        assert history[1].first_sample_index == 21
        assert history[1].last_sample_index == 28
        assert history[0].estimator_time_index == 7
        assert history[1].estimator_time_index == 8
        assert history[0].b4c_result.candidate_result.prediction_cutoff_sample_index == 12
        assert history[0].b4c_result.candidate_result.metric_available_after_sample_index == 20
        assert history[1].b4c_result.candidate_result.prediction_cutoff_sample_index == 20
        assert history[1].b4c_result.candidate_result.metric_available_after_sample_index == 28
        assert result.arms[name].second_sample_window == tuple(range(21, 29))
        with pytest.raises(ValueError):
            result.arms[name].first_metrics[0] = -1.0


def test_second_symbol_samples_cannot_change_frozen_first_symbol_history() -> None:
    original = run_reconstruction_factorial_ablation(received=RECEIVED)
    altered_received = RECEIVED.copy()
    altered_received[8:] += np.asarray(
        [complex(index / 50.0, -index / 70.0) for index in range(8)],
        dtype=np.complex128,
    )
    altered = run_reconstruction_factorial_ablation(received=altered_received)
    for name in ("B", "A", "K", "C"):
        _assert_array(original.arms[name].first_metrics, altered.arms[name].first_metrics, atol=0.0)
        _assert_array(
            original.arms[name].first_posterior, altered.arms[name].first_posterior, atol=0.0
        )


def test_factorial_adapter_has_no_truth_reference_or_random_inputs() -> None:
    path = ROOT / "src/hf_tcm/evaluation/reconstruction_factorial_ablation.py"
    source = path.read_text(encoding="utf-8")
    for forbidden in (
        "reference_bits",
        "ChannelTruth",
        "default_rng",
        "SeedSequence",
        "monte_carlo",
    ):
        assert forbidden not in source
    assert "run_reconstruction_posterior_estimator_sequence" in source


def test_factorial_received_fixture_is_a_fixed_two_symbol_buffer() -> None:
    assert RECEIVED.shape == (16,)
    assert np.iscomplexobj(RECEIVED)
    assert hashlib.sha256(RECEIVED.tobytes()).hexdigest() == (
        "59663708e2b8c9c7003a605aece3b7fd28d7c0afa42e22c6b0d670e6068d0331"
    )
