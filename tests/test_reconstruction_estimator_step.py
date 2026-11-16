"""M4.7i/B3b-0 explicit single-beam estimator state-step tests."""

from __future__ import annotations

import numpy as np
import pytest

from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_estimator_step import advance_reconstruction_estimator_state


@pytest.mark.parametrize(
    ("alpha_prime", "expected_fluctuating", "expected_full"),
    [
        (0.0, [[10.5, -5.0]], [[12.0, -8.0]]),
        (1.0, [[12.5, -6.0]], [[14.0, -9.0]]),
    ],
)
def test_one_step_matches_hand_computed_recursion_for_alpha_boundaries(
    alpha_prime: float,
    expected_fluctuating: list[list[float]],
    expected_full: list[list[float]],
) -> None:
    state = ReconstructionEstimatorState([[2.0, -1.0]], [[20.0, 30.0]], time_index=6)

    result = advance_reconstruction_estimator_state(
        state,
        time_index=6,
        next_time_index=7,
        alpha_prime=alpha_prime,
        k_tilde=[[3.0, -2.0]],
        mu0=[[1.5, -3.0]],
        observed_iq=[8.0, 5.0],
        predicted_iq=[[6.0, 7.0], [4.0, 1.0]],
        posterior=[0.25, 0.75],
    )

    np.testing.assert_allclose(result.fluctuating_iq, expected_fluctuating)
    np.testing.assert_allclose(result.full_iq, expected_full)
    assert result.time_index == 7


def test_zero_gain_leaves_only_damped_fluctuating_estimate_plus_regular_component() -> None:
    state = ReconstructionEstimatorState([[2.0, -4.0]], [[0.0, 0.0]], time_index=1)

    result = advance_reconstruction_estimator_state(
        state,
        time_index=1,
        next_time_index=2,
        alpha_prime=0.5,
        k_tilde=[[0.0, 0.0]],
        mu0=[[0.5, 1.0]],
        observed_iq=[7.0, 9.0],
        predicted_iq=[[1.0, 2.0], [3.0, 4.0]],
        posterior=[0.4, 0.6],
    )

    np.testing.assert_allclose(result.fluctuating_iq, [[1.0, -2.0]])
    np.testing.assert_allclose(result.full_iq, [[1.5, -1.0]])


def test_zero_innovations_preserve_only_alpha_scaled_prior_and_mu0() -> None:
    state = ReconstructionEstimatorState([[4.0, -8.0]], [[11.0, 12.0]], time_index=-2)

    result = advance_reconstruction_estimator_state(
        state,
        time_index=-2,
        next_time_index=-1,
        alpha_prime=0.25,
        k_tilde=[[9.0, -7.0]],
        mu0=[[2.0, -3.0]],
        observed_iq=[2.0, 3.0],
        predicted_iq=[[2.0, 3.0], [2.0, 3.0]],
        posterior=[0.2, 0.8],
    )

    np.testing.assert_allclose(result.fluctuating_iq, [[1.0, -2.0]])
    np.testing.assert_allclose(result.full_iq, [[3.0, -5.0]])
    assert result.time_index == -1


def test_two_successive_steps_match_independent_hand_calculation_and_keep_old_state() -> None:
    first = ReconstructionEstimatorState([[1.0, -1.0]], [[9.0, 8.0]], time_index=4)

    second = advance_reconstruction_estimator_state(
        first,
        time_index=4,
        next_time_index=5,
        alpha_prime=0.5,
        k_tilde=[[2.0, 1.0]],
        mu0=[[0.5, -1.0]],
        observed_iq=[4.0, 6.0],
        predicted_iq=[[2.0, 1.0], [3.0, 4.0]],
        posterior=[0.25, 0.75],
    )
    third = advance_reconstruction_estimator_state(
        second,
        time_index=5,
        next_time_index=6,
        alpha_prime=0.5,
        k_tilde=[[2.0, 1.0]],
        mu0=[[0.5, -1.0]],
        observed_iq=[10.0, 10.0],
        predicted_iq=[[9.0, 8.0], [6.0, 9.0]],
        posterior=[0.6, 0.4],
    )

    np.testing.assert_allclose(first.fluctuating_iq, [[1.0, -1.0]])
    np.testing.assert_allclose(first.full_iq, [[9.0, 8.0]])
    np.testing.assert_allclose(second.fluctuating_iq, [[3.0, 2.25]])
    np.testing.assert_allclose(second.full_iq, [[3.5, 1.25]])
    np.testing.assert_allclose(third.fluctuating_iq, [[5.9, 2.725]])
    np.testing.assert_allclose(third.full_iq, [[6.4, 1.725]])
    assert (first.time_index, second.time_index, third.time_index) == (4, 5, 6)
    assert not np.shares_memory(first.fluctuating_iq, second.fluctuating_iq)


@pytest.mark.parametrize(
    ("posterior", "predicted_iq", "message"),
    [
        ([0.2, 0.2], [[1.0, 1.0], [2.0, 2.0]], "sum to 1"),
        ([-0.1, 1.1], [[1.0, 1.0], [2.0, 2.0]], "nonnegative"),
        ([0.5, 0.5], [[1.0, 1.0]], "hypothesis dimension"),
    ],
)
def test_step_delegates_posterior_and_hypothesis_validation(
    posterior: list[float], predicted_iq: list[list[float]], message: str
) -> None:
    state = ReconstructionEstimatorState([[0.0, 0.0]], [[0.0, 0.0]], time_index=0)

    with pytest.raises(ValueError, match=message):
        advance_reconstruction_estimator_state(
            state,
            time_index=0,
            next_time_index=1,
            alpha_prime=1.0,
            k_tilde=[[1.0, 1.0]],
            mu0=[[0.0, 0.0]],
            observed_iq=[0.0, 0.0],
            predicted_iq=predicted_iq,
            posterior=posterior,
        )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"alpha_prime": float("nan")}, "alpha_prime must be a finite"),
        ({"k_tilde": [[float("inf"), 1.0]]}, "only finite values"),
        ({"mu0": [[0.0, float("nan")]]}, "only finite values"),
        ({"observed_iq": [float("nan"), 0.0]}, "only finite values"),
        ({"predicted_iq": [[float("inf"), 0.0]]}, "only finite values"),
        ({"posterior": [float("nan")]}, "only finite values"),
    ],
)
def test_step_delegates_finite_value_validation(changes: dict[str, object], message: str) -> None:
    state = ReconstructionEstimatorState([[0.0, 0.0]], [[0.0, 0.0]], time_index=0)
    operands: dict[str, object] = {
        "alpha_prime": 1.0,
        "k_tilde": [[1.0, 1.0]],
        "mu0": [[0.0, 0.0]],
        "observed_iq": [0.0, 0.0],
        "predicted_iq": [[0.0, 0.0]],
        "posterior": [1.0],
    }
    operands.update(changes)

    with pytest.raises(ValueError, match=message):
        advance_reconstruction_estimator_state(
            state,
            time_index=0,
            next_time_index=1,
            **operands,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("time_index", "next_time_index", "message"),
    [
        (1, 2, "state time_index"),
        (0, 2, r"next_time_index must equal time_index \+ 1"),
        (0, 1.0, "next_time_index must be an integer"),
    ],
)
def test_step_requires_matching_consecutive_absolute_indices(
    time_index: object, next_time_index: object, message: str
) -> None:
    state = ReconstructionEstimatorState([[0.0, 0.0]], [[0.0, 0.0]], time_index=0)

    with pytest.raises(ValueError, match=message):
        advance_reconstruction_estimator_state(
            state,
            time_index=time_index,  # type: ignore[arg-type]
            next_time_index=next_time_index,  # type: ignore[arg-type]
            alpha_prime=1.0,
            k_tilde=[[1.0, 1.0]],
            mu0=[[0.0, 0.0]],
            observed_iq=[0.0, 0.0],
            predicted_iq=[[0.0, 0.0]],
            posterior=[1.0],
        )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"k_tilde": [1.0, 1.0]}, r"k_tilde must have shape \(1, 2\)"),
        ({"mu0": [0.0, 0.0]}, r"mu0 must have shape \(1, 2\)"),
        ({"observed_iq": [[0.0, 0.0]]}, r"observed_iq must have shape \(2,\)"),
        ({"predicted_iq": [0.0, 0.0]}, r"predicted_iq must have shape \(M, 2\)"),
        ({"posterior": [[1.0]]}, r"posterior must have shape \(M,\)"),
    ],
)
def test_step_rejects_operands_outside_single_beam_api_shapes(
    changes: dict[str, object], message: str
) -> None:
    state = ReconstructionEstimatorState([[0.0, 0.0]], [[0.0, 0.0]], time_index=0)
    operands: dict[str, object] = {
        "alpha_prime": 1.0,
        "k_tilde": [[1.0, 1.0]],
        "mu0": [[0.0, 0.0]],
        "observed_iq": [0.0, 0.0],
        "predicted_iq": [[0.0, 0.0]],
        "posterior": [1.0],
    }
    operands.update(changes)

    with pytest.raises(ValueError, match=message):
        advance_reconstruction_estimator_state(
            state,
            time_index=0,
            next_time_index=1,
            **operands,  # type: ignore[arg-type]
        )


def test_step_rejects_state_with_more_than_one_beam() -> None:
    state = ReconstructionEstimatorState(
        [[0.0, 0.0], [0.0, 0.0]],
        [[0.0, 0.0], [0.0, 0.0]],
        time_index=0,
    )

    with pytest.raises(ValueError, match=r"state estimates must have shape \(1, 2\)"):
        advance_reconstruction_estimator_state(
            state,
            time_index=0,
            next_time_index=1,
            alpha_prime=1.0,
            k_tilde=[[1.0, 1.0]],
            mu0=[[0.0, 0.0]],
            observed_iq=[0.0, 0.0],
            predicted_iq=[[0.0, 0.0]],
            posterior=[1.0],
        )
