from __future__ import annotations

import math

import numpy as np
import pytest

from hf_tcm.evaluation.reconstruction_update_intervention import (
    run_reconstruction_update_intervention,
)

EXPECTED_PHASES = (0, 2, 4, 6, 2, 0, 6, 4, 1, 3, 5, 7, 3, 1, 7, 5)
POSTERIOR = np.full(16, 1.0 / 16.0, dtype=np.float64)
MU0 = np.asarray([0.31, -0.23], dtype=np.float64)
PRE_FLUCTUATING = np.asarray([0.42, -0.91], dtype=np.float64)
CURRENT_PREDICTIONS = np.asarray(
    [[(index - 7.5) / 10.0, (7.5 - index) / 25.0] for index in range(16)],
    dtype=np.float64,
)
NEXT_RECEIVED_IQ = np.asarray(
    [[(index % 4 - 1.5) / 3.0, (index % 5 - 2.0) / 4.0] for index in range(8)],
    dtype=np.float64,
)
PRIOR = np.asarray([index + 1 for index in range(16)], dtype=np.float64) / 136.0


def _manual_update(
    *,
    previous: np.ndarray,
    alpha: float,
    gain: np.ndarray,
    posterior: np.ndarray,
    observation: np.ndarray,
    predictions: np.ndarray,
    mu0: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    innovation = np.asarray(
        [
            math.fsum(
                float(posterior[index])
                * (float(observation[axis]) - float(predictions[index, axis]))
                for index in range(16)
            )
            for axis in range(2)
        ],
        dtype=np.float64,
    )
    updated = np.asarray(
        [
            float(alpha) * float(previous[axis]) + float(gain[axis]) * float(innovation[axis])
            for axis in range(2)
        ],
        dtype=np.float64,
    )
    return innovation, updated, updated + mu0


def _manual_predictions(coefficients: np.ndarray) -> np.ndarray:
    rows = []
    for phase_index in EXPECTED_PHASES:
        angle = phase_index * math.pi / 4.0
        rows.append(
            [
                -float(coefficients[0]) * math.sin(angle),
                float(coefficients[1]) * math.cos(angle),
            ]
        )
    return np.asarray(rows, dtype=np.float64)


def _manual_metrics(received: np.ndarray, predictions: np.ndarray) -> np.ndarray:
    return np.asarray(
        [
            math.fsum(
                (float(received[sample, axis]) - float(prediction[axis])) ** 2
                for sample in range(8)
                for axis in range(2)
            )
            for prediction in predictions
        ],
        dtype=np.float64,
    )


def _manual_posterior(prior: np.ndarray, metrics: np.ndarray, beta: float) -> np.ndarray:
    offset = float(np.min(metrics))
    weights = [
        float(prior[index]) * math.exp(-beta * (float(metrics[index]) - offset))
        for index in range(16)
    ]
    normalizer = math.fsum(weights)
    return np.asarray([weight / normalizer for weight in weights], dtype=np.float64)


def _run(
    observation: np.ndarray,
    *,
    alpha: float = 0.85,
    gain: tuple[float, float] = (0.35, -0.2),
    previous: np.ndarray = PRE_FLUCTUATING,
) -> object:
    predictions = CURRENT_PREDICTIONS.copy()
    if np.array_equal(observation, np.zeros(2, dtype=np.float64)):
        predictions.fill(0.0)
    return run_reconstruction_update_intervention(
        pre_fluctuating_iq=previous,
        mu0=MU0,
        alpha_prime=alpha,
        k_tilde=gain,
        current_observed_iq=observation,
        current_predicted_iq=predictions,
        current_posterior=POSTERIOR,
        next_received_iq_samples=NEXT_RECEIVED_IQ,
        fixed_prior=PRIOR,
        beta=0.7,
    )


@pytest.mark.parametrize(
    "observation",
    [
        np.asarray([0.0, 0.0]),  # zero innovation by matching all predictions
        np.asarray([1.0, 0.0]),  # positive first quadrature innovation
        np.asarray([-1.0, 0.0]),  # negative first quadrature innovation
        np.asarray([0.0, 0.8]),  # second quadrature innovation
        np.asarray([0.7, -0.6]),  # both quadratures
    ],
)
def test_intervention_matches_independent_scalar_recursion_and_prediction_oracle(
    observation: np.ndarray,
) -> None:
    result = _run(observation)
    current_predictions = (
        np.zeros((16, 2)) if np.array_equal(observation, [0.0, 0.0]) else CURRENT_PREDICTIONS
    )
    innovation, expected_fluctuating, expected_full = _manual_update(
        previous=PRE_FLUCTUATING,
        alpha=0.85,
        gain=np.asarray([0.35, -0.2]),
        posterior=POSTERIOR,
        observation=observation,
        predictions=current_predictions,
        mu0=MU0,
    )

    assert result.hypothesis_ids == tuple(range(16))
    assert result.phase_indices == EXPECTED_PHASES
    assert result.derived_weighted_innovation_iq == pytest.approx(innovation, rel=0.0, abs=1e-14)
    assert result.after_state.fluctuating_iq[0] == pytest.approx(
        expected_fluctuating, rel=0.0, abs=1e-14
    )
    assert result.after_state.full_iq[0] == pytest.approx(expected_full, rel=0.0, abs=1e-14)
    assert result.before_predictions_iq == pytest.approx(
        _manual_predictions(PRE_FLUCTUATING + MU0), rel=0.0, abs=1e-14
    )
    assert result.after_predictions_iq == pytest.approx(
        _manual_predictions(expected_full), rel=0.0, abs=1e-14
    )

    delta_coefficients = expected_full - (PRE_FLUCTUATING + MU0)
    expected_delta_predictions = np.asarray(
        [
            [
                -float(delta_coefficients[0]) * math.sin(index * math.pi / 4.0),
                float(delta_coefficients[1]) * math.cos(index * math.pi / 4.0),
            ]
            for index in EXPECTED_PHASES
        ]
    )
    assert result.delta_predictions_iq == pytest.approx(
        expected_delta_predictions, rel=0.0, abs=1e-14
    )
    assert result.before_metrics == pytest.approx(
        _manual_metrics(NEXT_RECEIVED_IQ, _manual_predictions(PRE_FLUCTUATING + MU0)),
        rel=0.0,
        abs=1e-13,
    )
    assert result.after_metrics == pytest.approx(
        _manual_metrics(NEXT_RECEIVED_IQ, _manual_predictions(expected_full)),
        rel=0.0,
        abs=1e-13,
    )

    # Independent quadratic-residual identity: ΔF = -2 r·ΔU + ||ΔU||² per sample.
    expected_metric_delta = np.asarray(
        [
            math.fsum(
                -2.0
                * (
                    float(NEXT_RECEIVED_IQ[sample, axis])
                    - float(result.before_predictions_iq[row, axis])
                )
                * float(result.delta_predictions_iq[row, axis])
                + float(result.delta_predictions_iq[row, axis]) ** 2
                for sample in range(8)
                for axis in range(2)
            )
            for row in range(16)
        ]
    )
    assert result.delta_metrics == pytest.approx(expected_metric_delta, rel=0.0, abs=1e-12)


def test_frozen_policy_has_zero_correction_and_unchanged_next_metrics() -> None:
    result = _run(np.asarray([0.7, -0.6]), alpha=1.0, gain=(0.0, 0.0))
    assert result.after_state.full_iq == pytest.approx(
        result.before_state.full_iq, rel=0.0, abs=0.0
    )
    assert result.delta_predictions_iq == pytest.approx(np.zeros((16, 2)), rel=0.0, abs=0.0)
    assert result.delta_metrics == pytest.approx(np.zeros(16), rel=0.0, abs=0.0)
    assert result.posterior_after == pytest.approx(result.posterior_before, rel=0.0, abs=1e-14)


def test_fixed_prior_posterior_sensitivity_is_normalized_and_ordered() -> None:
    result = _run(np.asarray([0.7, -0.6]))
    expected_before = _manual_posterior(PRIOR, result.before_metrics, 0.7)
    expected_after = _manual_posterior(PRIOR, result.after_metrics, 0.7)
    assert result.posterior_before == pytest.approx(expected_before, rel=0.0, abs=1e-13)
    assert result.posterior_after == pytest.approx(expected_after, rel=0.0, abs=1e-13)
    assert math.fsum(float(value) for value in result.posterior_before) == pytest.approx(
        1.0, rel=0.0, abs=1e-13
    )
    assert math.fsum(float(value) for value in result.posterior_after) == pytest.approx(
        1.0, rel=0.0, abs=1e-13
    )
    assert np.linalg.norm(result.posterior_after - result.posterior_before) > 1e-8


def test_symbol_estimator_and_absolute_sample_clocks_remain_explicit() -> None:
    result = run_reconstruction_update_intervention(
        pre_fluctuating_iq=PRE_FLUCTUATING,
        mu0=MU0,
        alpha_prime=0.85,
        k_tilde=(0.35, -0.2),
        current_observed_iq=(0.7, -0.6),
        current_predicted_iq=CURRENT_PREDICTIONS,
        current_posterior=POSTERIOR,
        next_received_iq_samples=NEXT_RECEIVED_IQ,
        fixed_prior=PRIOR,
        beta=0.7,
        symbol_index=4,
        estimator_time_index=9,
        symbol_origin_sample=13,
    )
    assert result.symbol_index == 4
    assert result.estimator_time_index == 9
    assert result.before_state.time_index == 9
    assert result.after_state.time_index == 10
    assert result.prediction_cutoff_sample == 44
    assert result.observation_cutoff_sample == 52
    assert result.next_metric_sample_window == tuple(range(53, 61))


def test_intervention_rejects_noncanonical_hypothesis_order_and_nonfinite_values() -> None:
    with pytest.raises(ValueError, match="canonical"):
        run_reconstruction_update_intervention(
            pre_fluctuating_iq=PRE_FLUCTUATING,
            mu0=MU0,
            alpha_prime=0.85,
            k_tilde=(0.35, -0.2),
            current_observed_iq=(0.1, -0.2),
            current_predicted_iq=CURRENT_PREDICTIONS,
            current_posterior=POSTERIOR,
            next_received_iq_samples=NEXT_RECEIVED_IQ,
            fixed_prior=PRIOR,
            beta=0.7,
            hypothesis_ids=tuple(reversed(range(16))),
        )

    with pytest.raises(ValueError, match="finite"):
        _run(np.asarray([float("nan"), 0.0]))


def test_intervention_snapshots_are_immutable_and_inputs_are_unchanged() -> None:
    observation = np.asarray([0.7, -0.6])
    before = (
        PRE_FLUCTUATING.copy(),
        MU0.copy(),
        CURRENT_PREDICTIONS.copy(),
        NEXT_RECEIVED_IQ.copy(),
    )
    result = _run(observation)
    assert PRE_FLUCTUATING == pytest.approx(before[0], rel=0.0, abs=0.0)
    assert MU0 == pytest.approx(before[1], rel=0.0, abs=0.0)
    assert CURRENT_PREDICTIONS == pytest.approx(before[2], rel=0.0, abs=0.0)
    assert NEXT_RECEIVED_IQ == pytest.approx(before[3], rel=0.0, abs=0.0)
    with pytest.raises(ValueError):
        result.delta_metrics[0] = 0.0


def test_evaluation_adapter_has_no_reference_truth_or_stochastic_inputs() -> None:
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / (
        "src/hf_tcm/evaluation/reconstruction_update_intervention.py"
    )
    source = path.read_text(encoding="utf-8")
    for forbidden in ("reference_bits", "ChannelTruth", "true_gain", "default_rng", "SeedSequence"):
        assert forbidden not in source
