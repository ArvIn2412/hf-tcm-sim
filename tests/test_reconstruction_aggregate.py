import inspect

import numpy as np
import pytest

from hf_tcm.channels.multipath import ChannelTruth
from hf_tcm.receiver.reconstruction_aggregate import (
    compute_project_reconstruction_metric,
    sum_estimated_path_predictions,
)


def test_one_beam_prediction_keeps_sample_and_iq_axes() -> None:
    paths = np.array([[[1.0, -2.0], [3.5, 4.0]]])
    before = paths.copy()

    aggregate = sum_estimated_path_predictions(paths)

    np.testing.assert_array_equal(aggregate, paths[0])
    np.testing.assert_array_equal(paths, before)


def test_multiple_beams_sum_componentwise_without_alignment() -> None:
    paths = np.array(
        [
            [[1.0, 2.0], [3.0, 4.0]],
            [[5.0, 6.0], [7.0, 8.0]],
        ]
    )
    np.testing.assert_array_equal(
        sum_estimated_path_predictions(paths),
        np.array([[6.0, 8.0], [10.0, 12.0]]),
    )


def test_project_metric_is_zero_for_identical_aggregate_iq() -> None:
    samples = np.array([[1.0, -2.0], [0.25, 7.0]])
    assert compute_project_reconstruction_metric(samples, samples) == 0.0


def test_project_metric_matches_hand_computed_squared_residuals() -> None:
    received = np.array([[1.0, 2.0], [3.0, 4.0]])
    predicted = np.array([[0.0, 0.0], [2.0, 2.0]])
    assert compute_project_reconstruction_metric(received, predicted) == 10.0


def test_metric_is_invariant_to_beam_order() -> None:
    paths = np.array(
        [
            [[1e16, 2.0]],
            [[1.0, 3.0]],
            [[-1e16, 4.0]],
        ]
    )
    first = sum_estimated_path_predictions(paths)
    second = sum_estimated_path_predictions(paths[::-1])
    np.testing.assert_array_equal(first, second)
    np.testing.assert_array_equal(first, np.array([[1.0, 9.0]]))


@pytest.mark.parametrize(
    "paths",
    [
        np.empty((0, 2, 2)),
        np.empty((1, 0, 2)),
        np.empty((1, 2, 1)),
        np.empty((2, 3)),
        np.zeros((1, 2, 2, 1)),
    ],
)
def test_path_prediction_rejects_empty_or_wrong_shapes(paths: np.ndarray) -> None:
    with pytest.raises(ValueError):
        sum_estimated_path_predictions(paths)


@pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
def test_path_prediction_rejects_non_finite_values(bad_value: float) -> None:
    paths = np.zeros((1, 1, 2))
    paths[0, 0, 0] = bad_value
    with pytest.raises(ValueError, match="finite"):
        sum_estimated_path_predictions(paths)


def test_path_prediction_rejects_non_finite_sum() -> None:
    paths = np.full((2, 1, 2), np.finfo(np.float64).max)
    with pytest.raises(ValueError, match="range"):
        sum_estimated_path_predictions(paths)


@pytest.mark.parametrize(
    ("received", "predicted"),
    [
        (np.zeros((0, 2)), np.zeros((0, 2))),
        (np.zeros((2, 2)), np.zeros((1, 2))),
        (np.zeros((2, 2)), np.zeros((2, 1))),
        (np.zeros((2,)), np.zeros((2,))),
        (np.zeros((1, 2, 2)), np.zeros((1, 2, 2))),
    ],
)
def test_project_metric_rejects_empty_or_mismatched_shapes(
    received: np.ndarray, predicted: np.ndarray
) -> None:
    with pytest.raises(ValueError):
        compute_project_reconstruction_metric(received, predicted)


@pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
def test_project_metric_rejects_non_finite_inputs(bad_value: float) -> None:
    for argument in ("received", "predicted"):
        received = np.zeros((1, 2))
        predicted = np.zeros((1, 2))
        target = received if argument == "received" else predicted
        target[0, 0] = bad_value
        with pytest.raises(ValueError, match="finite"):
            compute_project_reconstruction_metric(received, predicted)


def test_project_metric_rejects_overflowing_residual_or_square() -> None:
    maximum = np.finfo(np.float64).max
    with pytest.raises(ValueError, match="residual|range"):
        compute_project_reconstruction_metric(
            np.array([[maximum, 0.0]]), np.array([[-maximum, 0.0]])
        )


def test_project_metric_does_not_mutate_input_arrays() -> None:
    received = np.array([[4.0, 5.0], [6.0, 7.0]])
    predicted = np.array([[1.0, 2.0], [3.0, 4.0]])
    received_before = received.copy()
    predicted_before = predicted.copy()
    assert compute_project_reconstruction_metric(received, predicted) == 36.0
    np.testing.assert_array_equal(received, received_before)
    np.testing.assert_array_equal(predicted, predicted_before)


def test_truth_and_metadata_are_outside_the_explicit_function_inputs() -> None:
    fixed_received = np.array([[2.0, 3.0]])
    fixed_prediction = np.array([[1.0, 1.0]])
    truth_a = ChannelTruth(
        path_delays=(0,),
        average_powers=(1.0,),
        k_factors=(0.0,),
        coefficients=np.array([[1.0 + 0.0j]]),
        fading_mode="static",
        correlation=0.0,
        model_profile="unrelated-a",
    )
    truth_b = ChannelTruth(
        path_delays=(17, 23),
        average_powers=(0.1, 0.9),
        k_factors=(3.0, 8.0),
        coefficients=np.array([[8.0 + 2.0j, -3.0 + 1.0j]]),
        fading_mode="approximate_ar1",
        correlation=0.8,
        model_profile="unrelated-b",
    )
    assert truth_a != truth_b
    assert compute_project_reconstruction_metric(fixed_received, fixed_prediction) == 5.0
    assert compute_project_reconstruction_metric(fixed_received, fixed_prediction) == 5.0
    assert "truth" not in inspect.signature(sum_estimated_path_predictions).parameters
    assert "truth" not in inspect.signature(compute_project_reconstruction_metric).parameters


def test_metric_uses_stable_sum_for_many_small_residual_squares() -> None:
    residual = 1e-8
    count = 20_000
    received = np.full((count, 2), residual)
    predicted = np.zeros((count, 2))
    expected = float(count * 2) * residual**2
    result = compute_project_reconstruction_metric(received, predicted)
    assert result == pytest.approx(expected, rel=1e-15)
