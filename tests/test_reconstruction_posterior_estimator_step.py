import inspect
from dataclasses import replace

import numpy as np
import pytest

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.receiver import reconstruction_posterior_estimator_step as integration
from hf_tcm.receiver.iq_prediction import iq_quadratures_from_index
from hf_tcm.receiver.reconstruction_alignment import ZERO_PADDING
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_forward import (
    APPROXIMATE_RECTANGULAR_8SPS,
    RECTANGULAR_ZOH_RULE,
)
from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER
from hf_tcm.receiver.reconstruction_observation import (
    ADR012_IQ_RULE,
    ADR012_PROFILE,
    ADR012_PROFILE_ID,
    ADR012_WAVEFORM_RULE,
)
from hf_tcm.receiver.reconstruction_posterior import build_initial_reconstruction_prior


def _inputs(
    *,
    received: np.ndarray,
    state: ReconstructionEstimatorState,
    symbol: int = 0,
    origin: int = 0,
    estimator_time: int | None = None,
) -> dict[str, object]:
    start = origin + symbol * 8
    return {
        "received": received,
        "absolute_sample_indices": np.arange(start, start + received.size),
        "received_start_sample": start,
        "symbol_origin_sample": origin,
        "target_symbol_index": symbol,
        "state": state,
        "time_index": state.time_index if estimator_time is None else estimator_time,
        "edge_mode": "first_edge",
        "initial_prior": build_initial_reconstruction_prior(initial_state=(0, 0)),
        "previous_posterior": None,
        "beta": 0.7,
        "alpha_prime": 0.6,
        "k_tilde": np.array([[0.4, 0.3]]),
        "mu0": np.array([[0.2, -0.1]]),
        "prediction_data_cutoff_sample": start - 1,
        "posterior_data_cutoff_sample": start + 7,
        "profile": ADR012_PROFILE,
        "adr_profile": ADR012_PROFILE_ID,
        "path_count": 1,
        "path_delays_samples": (0,),
        "samples_per_symbol": 8,
        "iq_rule": ADR012_IQ_RULE,
        "waveform_rule": ADR012_WAVEFORM_RULE,
        "labeling_profile": ASSUMED_NATURAL_BINARY,
        "bit_order": OUTPUT_BIT_ORDER,
        "timebase_profile": APPROXIMATE_RECTANGULAR_8SPS,
        "symbol_to_sample_rule": RECTANGULAR_ZOH_RULE,
        "edge_policy": ZERO_PADDING,
    }


def _received_for_phase(b: int, coefficient: float = 1.0) -> np.ndarray:
    iq = iq_quadratures_from_index(b, coefficient, coefficient)
    sample = iq[1] - 1j * iq[0]
    return np.full(8, sample, dtype=np.complex128)


def _hand_initial(prior: np.ndarray, metrics: np.ndarray, beta: float) -> np.ndarray:
    likelihood = np.exp(-beta * (metrics - np.min(metrics)))
    weighted = prior * likelihood
    return weighted / np.sum(weighted)


def _hand_transition(previous: np.ndarray, metrics: np.ndarray, beta: float) -> np.ndarray:
    transition = np.zeros((16, 16), dtype=np.float64)
    for row, hypothesis in enumerate(HYPOTHESES):
        destinations = [
            column
            for column, candidate in enumerate(HYPOTHESES)
            if hypothesis.next_state == candidate.current_state
        ]
        for column in destinations:
            transition[row, column] = 1.0 / len(destinations)
    predicted = previous @ transition
    likelihood = np.exp(-beta * (metrics - np.min(metrics[predicted > 0.0])))
    weighted = predicted * likelihood
    return weighted / np.sum(weighted)


def _hand_state_update(
    state: ReconstructionEstimatorState,
    observed: np.ndarray,
    predictions: np.ndarray,
    posterior: np.ndarray,
    alpha: float,
    gain: np.ndarray,
    regular: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    innovation = np.sum(posterior[:, None] * (observed - predictions), axis=0)
    fluctuating = alpha * state.fluctuating_iq[0] + gain[0] * innovation
    return fluctuating[None, :], (fluctuating + regular[0])[None, :]


def test_first_edge_posterior_has_no_transition_and_manual_update_matches() -> None:
    state = ReconstructionEstimatorState([[0.3, -0.2]], [[0.5, 0.4]], 31)
    received = _received_for_phase(3, 0.8)
    args = _inputs(received=received, state=state, symbol=4, origin=9, estimator_time=31)
    args.update(alpha_prime=0.0, k_tilde=np.array([[0.6, 0.25]]), mu0=np.array([[0.4, -0.3]]))
    result = integration.process_reconstruction_posterior_estimator_step(**args)

    prior = np.asarray(args["initial_prior"])
    expected_posterior = _hand_initial(prior, result.candidate_result.metrics, 0.7)
    np.testing.assert_allclose(result.posterior, expected_posterior, atol=1e-14, rtol=0.0)
    first_support = np.flatnonzero(prior)
    assert np.array_equal(np.flatnonzero(result.posterior), first_support)
    assert result.predicted_iq.shape == (16, 2)
    assert result.observed_iq.shape == (2,)
    np.testing.assert_allclose(result.observed_iq, [-received.imag.mean(), received.real.mean()])

    expected_fluctuating, expected_full = _hand_state_update(
        state,
        result.observed_iq,
        result.predicted_iq,
        expected_posterior,
        0.0,
        np.asarray(args["k_tilde"]),
        np.asarray(args["mu0"]),
    )
    assert not np.allclose(expected_fluctuating, 0.0)
    np.testing.assert_allclose(result.next_state.fluctuating_iq, expected_fluctuating)
    np.testing.assert_allclose(result.next_state.full_iq, expected_full)
    assert result.next_state.time_index == 32
    assert result.available_after_sample_index == 48
    assert result.prediction_data_cutoff_sample == 40
    assert result.next_usable_symbol_index == 5
    assert result.posterior_data_cutoff_sample == 48
    np.testing.assert_array_equal(state.fluctuating_iq, [[0.3, -0.2]])


def test_later_edge_uses_transition_before_current_metric_and_beta_is_explicit() -> None:
    state = ReconstructionEstimatorState([[0.7, -0.1]], [[0.9, 0.2]], 44)
    received = np.array([complex(0.2 * i - 0.4, 0.13 * i * i) for i in range(8)])
    previous = np.arange(1, 17, dtype=np.float64)
    previous /= previous.sum()
    args = _inputs(received=received, state=state, symbol=2, origin=17)
    args.update(
        edge_mode="later_edge",
        initial_prior=None,
        previous_posterior=previous,
        beta=1.3,
        alpha_prime=1.0,
        k_tilde=np.array([[0.0, 0.5]]),
        mu0=np.array([[0.25, 0.75]]),
        prediction_data_cutoff_sample=32,
        posterior_data_cutoff_sample=40,
    )
    first = integration.process_reconstruction_posterior_estimator_step(**args)
    expected = _hand_transition(previous, first.candidate_result.metrics, 1.3)
    np.testing.assert_allclose(first.posterior, expected, atol=1e-14, rtol=0.0)
    assert first.posterior_data_cutoff_sample == 40
    assert first.next_state.time_index == 45
    assert first.next_usable_symbol_index == 3

    args["beta"] = 0.15
    second = integration.process_reconstruction_posterior_estimator_step(**args)
    assert not np.allclose(first.posterior, second.posterior)


def test_two_consecutive_symbols_use_distinct_received_and_updated_prestate() -> None:
    state0 = ReconstructionEstimatorState([[0.0, 0.0]], [[0.4, 0.7]], 100)
    first_received = _received_for_phase(1, 0.4)
    first_args = _inputs(
        received=first_received, state=state0, symbol=3, origin=5, estimator_time=100
    )
    first = integration.process_reconstruction_posterior_estimator_step(**first_args)

    second_received = np.array([complex(-0.2 * k, 0.1 + 0.07 * k) for k in range(8)])
    second_args = _inputs(
        received=second_received,
        state=first.next_state,
        symbol=4,
        origin=5,
        estimator_time=101,
    )
    second_args.update(
        edge_mode="later_edge",
        initial_prior=None,
        previous_posterior=first.posterior,
        prediction_data_cutoff_sample=36,
        posterior_data_cutoff_sample=44,
    )
    second = integration.process_reconstruction_posterior_estimator_step(**second_args)
    np.testing.assert_array_equal(state0.full_iq, [[0.4, 0.7]])
    assert first.next_state is not second.next_state
    assert first.posterior is not second.posterior
    assert first.candidate_result.metrics.shape == second.candidate_result.metrics.shape == (16,)
    assert not np.array_equal(first.candidate_result.metrics, second.candidate_result.metrics)
    assert not np.allclose(first.posterior, second.posterior)
    assert second.prediction_data_cutoff_sample == 36
    assert second.available_after_sample_index == 44


@pytest.mark.parametrize(
    ("alpha", "gain", "received_phase"),
    [(0.0, 0.0, 2), (1.0, 0.0, 1), (1.0, 0.5, 5)],
)
def test_manual_recursion_handles_alpha_gain_and_innovations(alpha, gain, received_phase) -> None:
    state = ReconstructionEstimatorState([[0.2, -0.4]], [[0.3, 0.6]], 7)
    received = _received_for_phase(received_phase, 0.9)
    args = _inputs(received=received, state=state)
    args.update(
        alpha_prime=alpha,
        k_tilde=np.array([[gain, gain]]),
        mu0=np.array([[1.1, -0.7]]),
    )
    result = integration.process_reconstruction_posterior_estimator_step(**args)
    manual_fluctuating, manual_full = _hand_state_update(
        state,
        result.observed_iq,
        result.predicted_iq,
        result.posterior,
        alpha,
        np.array([[gain, gain]]),
        np.array([[1.1, -0.7]]),
    )
    np.testing.assert_allclose(result.next_state.fluctuating_iq, manual_fluctuating, atol=1e-14)
    np.testing.assert_allclose(result.next_state.full_iq, manual_full, atol=1e-14)
    if gain == 0.0:
        assert result.next_state.fluctuating_iq[0, 0] == pytest.approx(
            alpha * state.fluctuating_iq[0, 0]
        )


def test_zero_innovation_preserves_only_the_alpha_scaled_previous_fluctuation() -> None:
    state = ReconstructionEstimatorState([[0.6, -0.8]], [[0.0, 0.0]], 15)
    received = np.zeros(8, dtype=np.complex128)
    args = _inputs(received=received, state=state)
    args.update(
        alpha_prime=0.5,
        k_tilde=np.array([[2.0, -3.0]]),
        mu0=np.array([[0.2, 0.9]]),
    )
    result = integration.process_reconstruction_posterior_estimator_step(**args)
    np.testing.assert_array_equal(result.predicted_iq, np.zeros((16, 2)))
    np.testing.assert_array_equal(result.observed_iq, np.zeros(2))
    np.testing.assert_allclose(result.next_state.fluctuating_iq, [[0.3, -0.4]])
    np.testing.assert_allclose(result.next_state.full_iq, [[0.5, 0.5]])


def test_predictions_match_b4b_sample_predictions_and_duplicate_edges_align() -> None:
    state = ReconstructionEstimatorState([[0.2, 0.3]], [[0.75, 1.25]], 2)
    result = integration.process_reconstruction_posterior_estimator_step(
        **_inputs(received=_received_for_phase(4), state=state)
    )
    assert result.hypothesis_ids == tuple(range(16))
    for row, bits in enumerate(result.candidate_result.output_bits):
        phase = bits[0] * 4 + bits[1] * 2 + bits[2]
        assert result.candidate_result.phase_indices[row] == phase
        np.testing.assert_allclose(
            result.candidate_result.sample_predictions_iq[row],
            np.repeat(result.predicted_iq[row][None, :], 8, axis=0),
            rtol=1e-14,
            atol=1e-14,
        )
    for left in range(16):
        for right in range(left + 1, 16):
            if (
                result.candidate_result.output_bits[left]
                == result.candidate_result.output_bits[right]
            ):
                np.testing.assert_array_equal(result.predicted_iq[left], result.predicted_iq[right])


def test_future_samples_do_not_affect_current_step_and_invalid_cutoffs_fail() -> None:
    state = ReconstructionEstimatorState([[0.0, 0.0]], [[1.0, 1.0]], 0)
    current = _received_for_phase(6)
    original_current = current.copy()
    args = _inputs(received=current, state=state)
    baseline = integration.process_reconstruction_posterior_estimator_step(**args)
    future = np.concatenate((current, np.full(8, complex(np.nan, np.inf))))
    args_future = _inputs(received=future, state=state)
    contaminated_future = integration.process_reconstruction_posterior_estimator_step(**args_future)
    np.testing.assert_array_equal(
        baseline.candidate_result.metrics, contaminated_future.candidate_result.metrics
    )
    np.testing.assert_array_equal(baseline.posterior, contaminated_future.posterior)
    np.testing.assert_array_equal(
        baseline.next_state.full_iq, contaminated_future.next_state.full_iq
    )
    np.testing.assert_array_equal(current, original_current)

    args["prediction_data_cutoff_sample"] = 0
    with pytest.raises(ValueError, match="prediction_data_cutoff_sample"):
        integration.process_reconstruction_posterior_estimator_step(**args)


@pytest.mark.parametrize(
    ("received", "message"),
    [
        (np.zeros(7, dtype=np.complex128), "complete target symbol"),
        (np.array([0j] * 7 + [complex(np.nan, 0.0)]), "finite"),
        (np.array([0j] * 7 + [complex(0.0, np.inf)]), "finite"),
    ],
)
def test_incomplete_and_nonfinite_current_symbol_are_rejected(received, message) -> None:
    state = ReconstructionEstimatorState([[0.0, 0.0]], [[1.0, 1.0]], 0)
    args = _inputs(received=received, state=state)
    with pytest.raises(ValueError, match=message):
        integration.process_reconstruction_posterior_estimator_step(**args)


def test_rejects_wrong_edge_operands_clock_shapes_and_profile() -> None:
    state = ReconstructionEstimatorState([[0.0, 0.0]], [[1.0, 1.0]], 10)
    received = _received_for_phase(0)
    args = _inputs(received=received, state=state)
    args.update(edge_mode="later_edge", initial_prior=None, previous_posterior=None)
    with pytest.raises(ValueError, match="previous_posterior"):
        integration.process_reconstruction_posterior_estimator_step(**args)

    args = _inputs(received=received, state=state)
    args["time_index"] = 11
    with pytest.raises(ValueError, match="time_index"):
        integration.process_reconstruction_posterior_estimator_step(**args)

    args = _inputs(received=received, state=state)
    args["posterior_data_cutoff_sample"] = 6
    with pytest.raises(ValueError, match="posterior_data_cutoff_sample"):
        integration.process_reconstruction_posterior_estimator_step(**args)

    args = _inputs(received=received, state=state)
    args["beta"] = 0.0
    with pytest.raises(ValueError, match="beta"):
        integration.process_reconstruction_posterior_estimator_step(**args)

    args = _inputs(received=received, state=state)
    args["initial_prior"] = np.full(15, 1.0 / 15.0)
    with pytest.raises(ValueError, match=r"shape \(16,"):
        integration.process_reconstruction_posterior_estimator_step(**args)

    args = _inputs(received=received, state=state)
    args["k_tilde"] = np.ones((2, 2))
    with pytest.raises(ValueError, match="k_tilde.*shape"):
        integration.process_reconstruction_posterior_estimator_step(**args)


def test_rejects_wrong_candidate_order(monkeypatch) -> None:
    state = ReconstructionEstimatorState([[0.0, 0.0]], [[1.0, 1.0]], 0)
    received = _received_for_phase(2)
    args = _inputs(received=received, state=state)
    original = integration.generate_reconstruction_candidate_metrics

    def permuted(*call_args, **call_kwargs):
        candidate = original(*call_args, **call_kwargs)
        return replace(candidate, hypothesis_ids=tuple(reversed(candidate.hypothesis_ids)))

    monkeypatch.setattr(integration, "generate_reconstruction_candidate_metrics", permuted)
    with pytest.raises(ValueError, match="canonical HYPOTHESES order"):
        integration.process_reconstruction_posterior_estimator_step(**args)


def test_api_does_not_accept_truth_or_transmitted_symbol_operands() -> None:
    parameters = inspect.signature(
        integration.process_reconstruction_posterior_estimator_step
    ).parameters
    assert not {
        "truth",
        "channel_truth",
        "transmitted_bits",
        "true_b",
        "current_posterior",
    }.intersection(parameters)
