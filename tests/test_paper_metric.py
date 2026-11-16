"""M4.6 tests for the isolated scalar metric in [A], equation (2)."""

import numpy as np
import pytest

from hf_tcm.decoding.paper_metric import compute_paper_metric


def _one_frame_inputs(
    observed: list[np.ndarray],
    predicted: list[np.ndarray],
    sample_indices: list[np.ndarray],
    sample_bounds: list[tuple[int, int]],
) -> dict[str, object]:
    return {
        "r": 4,
        "eta": 0,
        "f_indices": [4],
        "observed_iq": [observed],
        "predicted_iq": [predicted],
        "sample_indices": [sample_indices],
        "sample_bounds": sample_bounds,
    }


def test_matching_observations_and_predictions_have_zero_metric() -> None:
    values = np.array([[1.0, -2.0], [3.0, 4.0]])
    parameters = _one_frame_inputs([values], [values.copy()], [np.array([10, 11])], [(10, 11)])

    assert compute_paper_metric(**parameters) == 0.0  # type: ignore[arg-type]


def test_single_unit_residual_contributes_one_square() -> None:
    parameters = _one_frame_inputs(
        [np.array([[1.0, 0.0]])],
        [np.zeros((1, 2))],
        [np.array([0])],
        [(0, 0)],
    )

    assert compute_paper_metric(**parameters) == 1.0  # type: ignore[arg-type]


def test_both_quadratures_are_squared_and_summed() -> None:
    parameters = _one_frame_inputs(
        [np.array([[3.0, 4.0]])],
        [np.zeros((1, 2))],
        [np.array([2])],
        [(2, 2)],
    )

    assert compute_paper_metric(**parameters) == 25.0  # type: ignore[arg-type]


def test_multiple_beams_allow_different_inclusive_sample_segments() -> None:
    parameters = _one_frame_inputs(
        [np.array([[1.0, 2.0]]), np.array([[3.0, 0.0], [0.0, 4.0]])],
        [np.zeros((1, 2)), np.zeros((2, 2))],
        [np.array([10]), np.array([-2, -1])],
        [(10, 10), (-2, -1)],
    )

    assert compute_paper_metric(**parameters) == 30.0  # type: ignore[arg-type]


def test_inclusive_sample_bounds_include_both_endpoints() -> None:
    parameters = _one_frame_inputs(
        [np.array([[1.0, 0.0], [0.0, 2.0], [3.0, 0.0]])],
        [np.zeros((3, 2))],
        [np.array([5, 6, 7])],
        [(5, 7)],
    )

    # i=5 and i=7 contribute too: 1^2 + 2^2 + 3^2.
    assert compute_paper_metric(**parameters) == 14.0  # type: ignore[arg-type]


def test_eta_zero_uses_exactly_one_inclusive_symbol_position() -> None:
    parameters = _one_frame_inputs(
        [np.array([[2.0, 0.0]])],
        [np.zeros((1, 2))],
        [np.array([0])],
        [(0, 0)],
    )

    assert compute_paper_metric(**parameters) == 4.0  # type: ignore[arg-type]


def test_eta_twenty_uses_twenty_one_inclusive_symbol_positions() -> None:
    f_indices = np.arange(80, 101)
    observed = [[np.array([[1.0, 0.0]])] for _ in f_indices]
    predicted = [[np.zeros((1, 2))] for _ in f_indices]
    sample_indices = [[np.array([1])] for _ in f_indices]

    result = compute_paper_metric(
        r=100,
        eta=20,
        f_indices=f_indices,
        observed_iq=observed,
        predicted_iq=predicted,
        sample_indices=sample_indices,
        sample_bounds=[(1, 1)],
    )

    assert result == 21.0


def test_permuting_beam_summation_order_preserves_metric() -> None:
    observed = [
        np.array([[1.0e8, 0.0]]),
        np.array([[1.0, 0.0]]),
        np.array([[1.0, 0.0]]),
        np.array([[1.0, 0.0]]),
        np.array([[1.0, 0.0]]),
    ]
    predicted = [np.zeros_like(values) for values in observed]
    indices = [np.array([index]) for index in range(5)]
    bounds = [(index, index) for index in range(5)]
    forward = _one_frame_inputs(observed, predicted, indices, bounds)
    reverse = _one_frame_inputs(
        list(reversed(observed)),
        list(reversed(predicted)),
        list(reversed(indices)),
        list(reversed(bounds)),
    )

    forward_result = compute_paper_metric(**forward)  # type: ignore[arg-type]
    reverse_result = compute_paper_metric(**reverse)  # type: ignore[arg-type]
    assert forward_result == reverse_result == 1.0e16 + 4.0


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"f_indices": [3, 5]}, "f_indices"),
        ({"sample_indices": [[np.array([5, 7])]]}, "sample_indices"),
        ({"sample_indices": [[np.array([5.0, 6.0, 7.0])]]}, "sample_indices"),
        ({"sample_bounds": [(7, 5)]}, "sample_bounds"),
        ({"sample_bounds": [(5,)]}, "sample_bounds"),
        ({"observed_iq": [[np.array([1.0, 2.0])]]}, "observed_iq"),
        ({"predicted_iq": [[np.zeros((2, 2))]]}, "shape"),
        ({"sample_indices": []}, "sample_indices"),
        ({"eta": True}, "eta"),
    ],
)
def test_rejects_invalid_indices_bounds_and_shapes(
    overrides: dict[str, object], message: str
) -> None:
    parameters = _one_frame_inputs(
        [np.zeros((3, 2))],
        [np.zeros((3, 2))],
        [np.array([5, 6, 7])],
        [(5, 7)],
    )
    parameters.update(overrides)

    with pytest.raises(ValueError, match=message):
        compute_paper_metric(**parameters)  # type: ignore[arg-type]


def test_rejects_non_finite_observations_and_predictions() -> None:
    parameters = _one_frame_inputs(
        [np.array([[np.inf, 0.0]])],
        [np.zeros((1, 2))],
        [np.array([0])],
        [(0, 0)],
    )

    with pytest.raises(ValueError, match="finite"):
        compute_paper_metric(**parameters)  # type: ignore[arg-type]


def test_rejects_non_integral_r_and_sample_bounds() -> None:
    parameters = _one_frame_inputs(
        [np.zeros((1, 2))],
        [np.zeros((1, 2))],
        [np.array([0])],
        [(0, 0)],
    )
    parameters["r"] = 4.0
    with pytest.raises(ValueError, match="r"):
        compute_paper_metric(**parameters)  # type: ignore[arg-type]
