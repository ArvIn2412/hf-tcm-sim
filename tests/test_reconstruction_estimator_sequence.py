from __future__ import annotations

import numpy as np
import pytest

from hf_tcm.receiver.reconstruction_estimator_sequence import (
    ReconstructionEstimatorStepOperands,
    run_reconstruction_estimator_sequence,
)
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState


def _step(
    index: int,
    *,
    alpha: float,
    gain: tuple[float, float],
    mu0: tuple[float, float],
    observed: tuple[float, float],
    predicted: tuple[tuple[float, float], ...],
    posterior: tuple[float, ...],
) -> ReconstructionEstimatorStepOperands:
    return ReconstructionEstimatorStepOperands(
        time_index=index,
        next_time_index=index + 1,
        alpha_prime=alpha,
        k_tilde=np.array([gain]),
        mu0=np.array([mu0]),
        observed_iq=np.array(observed),
        predicted_iq=np.array(predicted),
        posterior=np.array(posterior),
    )


def _manual_step(
    previous: np.ndarray, step: ReconstructionEstimatorStepOperands
) -> tuple[np.ndarray, np.ndarray]:
    innovation = np.sum(
        np.asarray(step.posterior)[:, None]
        * (np.asarray(step.observed_iq)[None, :] - np.asarray(step.predicted_iq)),
        axis=0,
    )
    fluctuating = step.alpha_prime * previous + np.asarray(step.k_tilde)[0] * innovation
    full = fluctuating + np.asarray(step.mu0)[0]
    return fluctuating, full


def test_two_steps_match_manual_recursion_and_keep_full_history() -> None:
    initial = ReconstructionEstimatorState([[1.0, -2.0]], [[11.0, 8.0]], time_index=4)
    first = _step(
        4,
        alpha=0.5,
        gain=(2.0, -1.0),
        mu0=(3.0, 5.0),
        observed=(4.0, 1.0),
        predicted=((1.0, 0.0), (0.0, -1.0)),
        posterior=(0.25, 0.75),
    )
    second = _step(
        5,
        alpha=0.25,
        gain=(0.5, 2.0),
        mu0=(-7.0, 6.0),
        observed=(2.0, 3.0),
        predicted=((1.0, 2.0), (3.0, 1.0)),
        posterior=(0.8, 0.2),
    )

    first_fluctuating, first_full = _manual_step(initial.fluctuating_iq[0], first)
    second_fluctuating, second_full = _manual_step(first_fluctuating, second)
    result = run_reconstruction_estimator_sequence(initial, (first, second), include_history=True)

    assert result.final_state.time_index == 6
    np.testing.assert_allclose(result.final_state.fluctuating_iq[0], second_fluctuating)
    np.testing.assert_allclose(result.final_state.full_iq[0], second_full)
    assert result.history is not None
    assert tuple(state.time_index for state in result.history) == (4, 5, 6)
    np.testing.assert_allclose(result.history[1].fluctuating_iq[0], first_fluctuating)
    np.testing.assert_allclose(result.history[1].full_iq[0], first_full)
    assert not result.history[2].fluctuating_iq.flags.writeable
    with pytest.raises(ValueError):
        result.history[1].full_iq[0, 0] = 100.0


def test_three_steps_with_zero_innovations_and_changing_mu0() -> None:
    initial = ReconstructionEstimatorState([[2.0, -3.0]], [[0.0, 0.0]], time_index=-2)
    steps = (
        _step(
            -2,
            alpha=0.0,
            gain=(9.0, 4.0),
            mu0=(5.0, 6.0),
            observed=(1.0, 2.0),
            predicted=((1.0, 2.0), (1.0, 2.0)),
            posterior=(0.5, 0.5),
        ),
        _step(
            -1,
            alpha=1.0,
            gain=(0.0, 7.0),
            mu0=(-2.0, 8.0),
            observed=(3.0, -1.0),
            predicted=((3.0, -1.0),),
            posterior=(1.0,),
        ),
        _step(
            0,
            alpha=0.5,
            gain=(1.0, 1.0),
            mu0=(10.0, -4.0),
            observed=(0.0, 0.0),
            predicted=((0.0, 0.0),),
            posterior=(1.0,),
        ),
    )

    expected_fluctuating = initial.fluctuating_iq[0].copy()
    expected_history = [expected_fluctuating.copy()]
    for step in steps:
        expected_fluctuating, _ = _manual_step(expected_fluctuating, step)
        expected_history.append(expected_fluctuating.copy())

    result = run_reconstruction_estimator_sequence(initial, steps, include_history=True)

    assert result.history is not None
    assert tuple(state.time_index for state in result.history) == (-2, -1, 0, 1)
    for state, expected in zip(result.history, expected_history, strict=True):
        np.testing.assert_allclose(state.fluctuating_iq[0], expected)
    # The second step must use the prior fluctuating estimate (zero), not the
    # previous full estimate (mu0=(5, 6)); its innovation is also zero.
    np.testing.assert_array_equal(result.history[2].fluctuating_iq, [[0.0, 0.0]])
    np.testing.assert_array_equal(result.history[2].full_iq, [[-2.0, 8.0]])


@pytest.mark.parametrize(
    "steps",
    [
        (
            _step(
                3,
                alpha=1,
                gain=(1, 1),
                mu0=(0, 0),
                observed=(0, 0),
                predicted=((0, 0),),
                posterior=(1,),
            ),
        ),
        (
            _step(
                2,
                alpha=1,
                gain=(1, 1),
                mu0=(0, 0),
                observed=(0, 0),
                predicted=((0, 0),),
                posterior=(1,),
            ),
            _step(
                2,
                alpha=1,
                gain=(1, 1),
                mu0=(0, 0),
                observed=(0, 0),
                predicted=((0, 0),),
                posterior=(1,),
            ),
        ),
        (
            _step(
                2,
                alpha=1,
                gain=(1, 1),
                mu0=(0, 0),
                observed=(0, 0),
                predicted=((0, 0),),
                posterior=(1,),
            ),
            _step(
                4,
                alpha=1,
                gain=(1, 1),
                mu0=(0, 0),
                observed=(0, 0),
                predicted=((0, 0),),
                posterior=(1,),
            ),
        ),
        (
            _step(
                3,
                alpha=1,
                gain=(1, 1),
                mu0=(0, 0),
                observed=(0, 0),
                predicted=((0, 0),),
                posterior=(1,),
            ),
            _step(
                2,
                alpha=1,
                gain=(1, 1),
                mu0=(0, 0),
                observed=(0, 0),
                predicted=((0, 0),),
                posterior=(1,),
            ),
        ),
    ],
    ids=("starts-after-initial", "repeated-index", "skipped-index", "reordered-index"),
)
def test_noncontiguous_or_reordered_clock_is_rejected(
    steps: tuple[ReconstructionEstimatorStepOperands, ...],
) -> None:
    initial = ReconstructionEstimatorState([[0.0, 0.0]], [[0.0, 0.0]], time_index=2)
    with pytest.raises(ValueError):
        run_reconstruction_estimator_sequence(initial, steps)


def test_independent_runs_reset_from_initial_state_and_are_deterministic() -> None:
    initial = ReconstructionEstimatorState([[1.0, 2.0]], [[8.0, 9.0]], time_index=7)
    original_fluctuating = initial.fluctuating_iq.copy()
    original_full = initial.full_iq.copy()
    steps = (
        _step(
            7,
            alpha=0.6,
            gain=(1.2, 0.8),
            mu0=(4.0, -3.0),
            observed=(5.0, 2.0),
            predicted=((0.0, 1.0), (3.0, 4.0)),
            posterior=(0.3, 0.7),
        ),
    )

    first_run = run_reconstruction_estimator_sequence(initial, steps, include_history=True)
    second_run = run_reconstruction_estimator_sequence(initial, steps, include_history=True)

    np.testing.assert_array_equal(initial.fluctuating_iq, original_fluctuating)
    np.testing.assert_array_equal(initial.full_iq, original_full)
    np.testing.assert_array_equal(
        first_run.final_state.fluctuating_iq, second_run.final_state.fluctuating_iq
    )
    np.testing.assert_array_equal(first_run.final_state.full_iq, second_run.final_state.full_iq)
    assert first_run.final_state is not second_run.final_state
    assert first_run.history is not None and second_run.history is not None
    assert first_run.history[0] is initial
    assert second_run.history[0] is initial
    assert all(
        a is not b for a, b in zip(first_run.history[1:], second_run.history[1:], strict=True)
    )


def test_history_is_optional_and_empty_sequence_returns_initial_state() -> None:
    initial = ReconstructionEstimatorState([[1.0, 2.0]], [[3.0, 4.0]], time_index=12)

    without_history = run_reconstruction_estimator_sequence(initial, ())
    with_history = run_reconstruction_estimator_sequence(initial, (), include_history=True)

    assert without_history.final_state is initial
    assert without_history.history is None
    assert with_history.final_state is initial
    assert with_history.history == (initial,)
