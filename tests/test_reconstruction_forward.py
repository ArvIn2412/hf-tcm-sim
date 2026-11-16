import inspect
import math

import numpy as np
import pytest

from hf_tcm.receiver.reconstruction_aggregate import compute_project_reconstruction_metric
from hf_tcm.receiver.reconstruction_alignment import ZERO_PADDING
from hf_tcm.receiver.reconstruction_forward import (
    APPROXIMATE_RECTANGULAR_8SPS,
    RECTANGULAR_ZOH_RULE,
    predict_reconstructed_aggregate_iq,
)
from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER
from hf_tcm.reconstruction_config import (
    ReconstructionConfigError,
    validate_receiver_profile_mode,
)


def predict(
    bits: tuple[tuple[int, int, int], ...],
    coefficients: np.ndarray,
    delays: tuple[int, ...],
    *,
    origin: int = 0,
    frame_start: int = 0,
    frame_count: int = 8,
) -> np.ndarray:
    return predict_reconstructed_aggregate_iq(
        candidate_output_bits=bits,
        estimated_path_coefficients=coefficients,
        path_delays_samples=delays,
        symbol_origin_sample=origin,
        frame_start_sample=frame_start,
        frame_sample_count=frame_count,
        labeling_profile=ASSUMED_NATURAL_BINARY,
        bit_order=OUTPUT_BIT_ORDER,
        timebase_profile=APPROXIMATE_RECTANGULAR_8SPS,
        symbol_to_sample_rule=RECTANGULAR_ZOH_RULE,
        edge_policy=ZERO_PADDING,
    )


def test_single_path_forward_prediction_matches_manual_two_symbol_values() -> None:
    bits = ((0, 0, 0), (0, 0, 1))
    coefficients = np.array([[2.0, 3.0]])
    result = predict(bits, coefficients, (0,), frame_count=16)
    expected = np.repeat(
        np.array([[0.0, 3.0], [-math.sqrt(2.0), 3.0 * math.sqrt(2.0) / 2.0]]),
        8,
        axis=0,
    )
    np.testing.assert_allclose(result, expected, atol=1e-15)


def test_all_eight_phase_indices_follow_the_explicit_output_bit_mapping() -> None:
    bits = tuple((index >> 2 & 1, index >> 1 & 1, index & 1) for index in range(8))
    result = predict(bits, np.array([[1.0, 1.0]]), (0,), frame_count=64)
    phases = np.arange(8) * (math.pi / 4.0)
    expected_symbols = np.column_stack((-np.sin(phases), np.cos(phases)))
    np.testing.assert_allclose(result, np.repeat(expected_symbols, 8, axis=0), atol=1e-15)


def test_two_paths_combine_after_zero_and_nonzero_sample_delays() -> None:
    bits = ((0, 0, 0), (0, 1, 0))
    coefficients = np.array([[1.0, 0.0], [0.0, 2.0]])
    result = predict(bits, coefficients, (0, 2), frame_count=18)
    first_path = np.zeros((18, 2))
    first_path[:16] = np.repeat(np.array([[0.0, 0.0], [-1.0, 0.0]]), 8, axis=0)
    second_path = np.repeat(np.array([[0.0, 2.0], [0.0, 0.0]]), 8, axis=0)
    expected = first_path.copy()
    expected[2:18] += second_path
    np.testing.assert_allclose(result, expected, atol=1e-15)


def test_zero_padding_places_first_and_last_symbols_on_explicit_frame_edges() -> None:
    result = predict(
        ((0, 0, 0), (0, 0, 1)),
        np.array([[1.0, 1.0]]),
        (0,),
        origin=10,
        frame_start=10,
        frame_count=16,
    )
    np.testing.assert_array_equal(result[:8], np.tile([0.0, 1.0], (8, 1)))
    np.testing.assert_allclose(
        result[8:], np.tile([-math.sqrt(2.0) / 2.0, math.sqrt(2.0) / 2.0], (8, 1)), atol=1e-15
    )


def test_delay_padding_and_both_frame_crops_use_absolute_sample_indices() -> None:
    # Symbol 0 starts at sample 10, has 8 samples, and is shifted to 12..19.
    # The output frame 15..22 keeps the symbol-0 tail and symbol-1 head only.
    result = predict(
        ((0, 0, 0), (0, 0, 1)),
        np.array([[1.0, 1.0]]),
        (2,),
        origin=10,
        frame_start=15,
        frame_count=8,
    )
    expected = np.vstack(
        (
            np.tile([0.0, 1.0], (5, 1)),
            np.tile([-math.sqrt(2.0) / 2.0, math.sqrt(2.0) / 2.0], (3, 1)),
        )
    )
    np.testing.assert_allclose(result, expected, atol=1e-15)


def test_project_metric_is_zero_on_match_and_known_for_perturbation() -> None:
    prediction = predict(((0, 0, 1),), np.array([[0.0, 1.0]]), (0,), frame_count=8)
    assert compute_project_reconstruction_metric(prediction, prediction) == 0.0
    received = prediction.copy()
    received[3, 0] += 2.0
    assert compute_project_reconstruction_metric(received, prediction) == 4.0


def test_prediction_is_invariant_to_path_order_with_coefficients_and_delays_reordered() -> None:
    bits = ((0, 0, 1), (1, 0, 0))
    coefficients = np.array([[1.0, 2.0], [-0.5, 3.0]])
    first = predict(bits, coefficients, (0, 3), frame_count=19)
    second = predict(bits, coefficients[::-1], (3, 0), frame_count=19)
    np.testing.assert_allclose(first, second, atol=1e-15)


def test_forward_prediction_does_not_mutate_explicit_inputs() -> None:
    coefficient_estimates = np.array([[1.25, -0.75], [2.5, 0.5]])
    bits = [(1, 0, 1), (0, 1, 0)]
    delays = [0, 2]
    original_coefficients = coefficient_estimates.copy()
    original_bits = list(bits)
    original_delays = list(delays)
    predict(tuple(bits), coefficient_estimates, tuple(delays), frame_count=18)
    np.testing.assert_array_equal(coefficient_estimates, original_coefficients)
    assert bits == original_bits
    assert delays == original_delays


def test_forward_api_has_no_truth_input_and_requires_explicit_conventions() -> None:
    parameters = inspect.signature(predict_reconstructed_aggregate_iq).parameters
    assert "truth" not in parameters
    assert "channel_truth" not in parameters
    for required in (
        "labeling_profile",
        "bit_order",
        "timebase_profile",
        "symbol_to_sample_rule",
        "edge_policy",
        "symbol_origin_sample",
        "frame_start_sample",
        "frame_sample_count",
    ):
        assert parameters[required].default is inspect.Parameter.empty


def test_reconstruction_config_remains_inactive_and_source_faithful_rejects_it() -> None:
    minimal_reconstruction_marker = {
        "profile": "reconstructed_offline",
        "receiver_enabled": False,
    }
    assert minimal_reconstruction_marker["receiver_enabled"] is False
    with pytest.raises(ReconstructionConfigError, match="source_faithful.*reconstruction"):
        validate_receiver_profile_mode(
            minimal_reconstruction_marker,
            requested_mode="source_faithful",
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"labeling_profile": "baseline_assumption"}, "labeling_profile"),
        ({"bit_order": ("c0", "c1", "c2")}, "bit_order"),
        ({"timebase_profile": "other"}, "timebase_profile"),
        ({"symbol_to_sample_rule": "linear"}, "symbol_to_sample_rule"),
        ({"edge_policy": "truncate"}, "edge_policy"),
    ],
)
def test_forward_rejects_unaccepted_conventions(overrides: dict[str, object], message: str) -> None:
    arguments: dict[str, object] = {
        "candidate_output_bits": ((0, 0, 0),),
        "estimated_path_coefficients": np.ones((1, 2)),
        "path_delays_samples": (0,),
        "symbol_origin_sample": 0,
        "frame_start_sample": 0,
        "frame_sample_count": 8,
        "labeling_profile": ASSUMED_NATURAL_BINARY,
        "bit_order": OUTPUT_BIT_ORDER,
        "timebase_profile": APPROXIMATE_RECTANGULAR_8SPS,
        "symbol_to_sample_rule": RECTANGULAR_ZOH_RULE,
        "edge_policy": ZERO_PADDING,
    }
    arguments.update(overrides)
    with pytest.raises(ValueError, match=message):
        predict_reconstructed_aggregate_iq(**arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("bits", "coefficients", "delays", "frame_count"),
    [
        ((), np.ones((1, 2)), (0,), 8),
        (((0, 0),), np.ones((1, 2)), (0,), 8),
        (((0, 0, 0),), np.ones((0, 2)), (), 8),
        (((0, 0, 0),), np.ones((1, 3)), (0,), 8),
        (((0, 0, 0),), np.ones((1, 2)), (-1,), 8),
        (((0, 0, 0),), np.ones((1, 2)), (0,), 0),
    ],
)
def test_forward_rejects_invalid_bits_coefficients_delays_and_frame(
    bits: tuple[tuple[int, ...], ...],
    coefficients: np.ndarray,
    delays: tuple[int, ...],
    frame_count: int,
) -> None:
    with pytest.raises(ValueError):
        predict_reconstructed_aggregate_iq(
            candidate_output_bits=bits,
            estimated_path_coefficients=coefficients,
            path_delays_samples=delays,
            symbol_origin_sample=0,
            frame_start_sample=0,
            frame_sample_count=frame_count,
            labeling_profile=ASSUMED_NATURAL_BINARY,
            bit_order=OUTPUT_BIT_ORDER,
            timebase_profile=APPROXIMATE_RECTANGULAR_8SPS,
            symbol_to_sample_rule=RECTANGULAR_ZOH_RULE,
            edge_policy=ZERO_PADDING,
        )


@pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
def test_forward_rejects_non_finite_coefficients(bad_value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        predict(
            ((0, 0, 0),),
            np.array([[bad_value, 1.0]]),
            (0,),
        )
