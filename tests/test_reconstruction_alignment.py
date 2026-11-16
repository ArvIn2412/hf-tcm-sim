import numpy as np
import pytest

from hf_tcm.receiver.reconstruction_aggregate import sum_estimated_path_predictions
from hf_tcm.receiver.reconstruction_alignment import align_estimated_path_predictions


def test_zero_delay_preserves_segment_values_and_absolute_indices() -> None:
    segment = np.array([[1.0, 2.0], [3.0, 4.0]])
    aligned = align_estimated_path_predictions(
        path_segments=(segment,),
        segment_start_indices=(40,),
        delays_samples=(0,),
        frame_start_sample=40,
        frame_sample_count=2,
        edge_policy="zero_padding",
    )
    np.testing.assert_array_equal(aligned, segment[None, :, :])


def test_two_paths_with_different_delays_share_output_timeline() -> None:
    path_a = np.array([[1.0, 10.0], [2.0, 20.0]])
    path_b = np.array([[3.0, 30.0], [4.0, 40.0]])
    aligned = align_estimated_path_predictions(
        path_segments=(path_a, path_b),
        segment_start_indices=(100, 100),
        delays_samples=(0, 2),
        frame_start_sample=100,
        frame_sample_count=4,
        edge_policy="zero_padding",
    )
    np.testing.assert_array_equal(
        aligned,
        np.array(
            [
                [[1.0, 10.0], [2.0, 20.0], [0.0, 0.0], [0.0, 0.0]],
                [[0.0, 0.0], [0.0, 0.0], [3.0, 30.0], [4.0, 40.0]],
            ]
        ),
    )


def test_zero_padding_keeps_impulses_on_both_inclusive_frame_samples() -> None:
    segment = np.array([[1.0, -1.0], [0.0, 0.0], [0.0, 0.0], [2.0, -2.0], [0.0, 0.0]])
    aligned = align_estimated_path_predictions(
        path_segments=(segment,),
        segment_start_indices=(8,),
        delays_samples=(1,),
        frame_start_sample=9,
        frame_sample_count=4,
        edge_policy="zero_padding",
    )
    np.testing.assert_array_equal(
        aligned[0],
        np.array([[1.0, -1.0], [0.0, 0.0], [0.0, 0.0], [2.0, -2.0]]),
    )


def test_input_segment_is_cropped_to_explicit_output_frame() -> None:
    segment = np.array([[float(i), -float(i)] for i in range(7)])
    aligned = align_estimated_path_predictions(
        path_segments=(segment,),
        segment_start_indices=(98,),
        delays_samples=(0,),
        frame_start_sample=100,
        frame_sample_count=3,
        edge_policy="zero_padding",
    )
    np.testing.assert_array_equal(aligned[0], np.array([[2.0, -2.0], [3.0, -3.0], [4.0, -4.0]]))


def test_variable_segment_lengths_are_supported_per_path() -> None:
    short = np.array([[5.0, -5.0]])
    long = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    aligned = align_estimated_path_predictions(
        path_segments=(short, long),
        segment_start_indices=(20, 21),
        delays_samples=(2, 0),
        frame_start_sample=20,
        frame_sample_count=4,
        edge_policy="zero_padding",
    )
    np.testing.assert_array_equal(
        aligned,
        np.array(
            [
                [[0.0, 0.0], [0.0, 0.0], [5.0, -5.0], [0.0, 0.0]],
                [[0.0, 0.0], [1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
            ]
        ),
    )


def test_alignment_indices_compose_with_b2a_aggregate_sum() -> None:
    path_a = np.array([[1.0, 2.0], [3.0, 4.0]])
    path_b = np.array([[5.0, 6.0], [7.0, 8.0]])
    aligned = align_estimated_path_predictions(
        path_segments=(path_a, path_b),
        segment_start_indices=(50, 49),
        delays_samples=(0, 1),
        frame_start_sample=50,
        frame_sample_count=2,
        edge_policy="zero_padding",
    )
    aggregate = sum_estimated_path_predictions(aligned)
    np.testing.assert_array_equal(aggregate, np.array([[6.0, 8.0], [10.0, 12.0]]))


def test_alignment_does_not_mutate_input_segments() -> None:
    first = np.array([[1.0, 2.0], [3.0, 4.0]])
    second = np.array([[5.0, 6.0]])
    snapshots = (first.copy(), second.copy())
    align_estimated_path_predictions(
        path_segments=(first, second),
        segment_start_indices=(0, 0),
        delays_samples=(1, 0),
        frame_start_sample=1,
        frame_sample_count=3,
        edge_policy="zero_padding",
    )
    np.testing.assert_array_equal(first, snapshots[0])
    np.testing.assert_array_equal(second, snapshots[1])


@pytest.mark.parametrize("delay", [-1, 1.5, True, np.bool_(False)])
def test_alignment_rejects_invalid_delays(delay: object) -> None:
    with pytest.raises(ValueError, match="delay"):
        align_estimated_path_predictions(
            path_segments=(np.zeros((1, 2)),),
            segment_start_indices=(0,),
            delays_samples=(delay,),  # type: ignore[arg-type]
            frame_start_sample=0,
            frame_sample_count=1,
            edge_policy="zero_padding",
        )


@pytest.mark.parametrize(
    ("segments", "starts", "delays", "frame_start", "frame_count", "policy"),
    [
        ((), (), (), 0, 1, "zero_padding"),
        ((np.zeros((1, 2)),), (), (0,), 0, 1, "zero_padding"),
        ((np.zeros((1, 2)),), (0,), (), 0, 1, "zero_padding"),
        ((np.zeros((0, 2)),), (0,), (0,), 0, 1, "zero_padding"),
        ((np.zeros((1, 3)),), (0,), (0,), 0, 1, "zero_padding"),
        ((np.zeros((1, 2, 1)),), (0,), (0,), 0, 1, "zero_padding"),
        ((np.zeros((1, 2)),), (0,), (0,), 0, 0, "zero_padding"),
        ((np.zeros((1, 2)),), (0,), (0,), 0.0, 1, "zero_padding"),
        ((np.zeros((1, 2)),), (0.0,), (0,), 0, 1, "zero_padding"),
        ((np.zeros((1, 2)),), (-1,), (0,), 0, 1, "zero_padding"),
        ((np.zeros((1, 2)),), (0,), (0,), -1, 1, "zero_padding"),
        ((np.zeros((1, 2)),), (0,), (0,), 0, 1, "truncate"),
    ],
)
def test_alignment_rejects_invalid_shapes_indices_and_edge_policy(
    segments: tuple[np.ndarray, ...],
    starts: tuple[object, ...],
    delays: tuple[object, ...],
    frame_start: object,
    frame_count: object,
    policy: str,
) -> None:
    with pytest.raises(ValueError):
        align_estimated_path_predictions(
            path_segments=segments,
            segment_start_indices=starts,  # type: ignore[arg-type]
            delays_samples=delays,  # type: ignore[arg-type]
            frame_start_sample=frame_start,  # type: ignore[arg-type]
            frame_sample_count=frame_count,  # type: ignore[arg-type]
            edge_policy=policy,
        )


@pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
def test_alignment_rejects_non_finite_segments(bad_value: float) -> None:
    segment = np.zeros((1, 2))
    segment[0, 0] = bad_value
    with pytest.raises(ValueError, match="finite"):
        align_estimated_path_predictions(
            path_segments=(segment,),
            segment_start_indices=(0,),
            delays_samples=(0,),
            frame_start_sample=0,
            frame_sample_count=1,
            edge_policy="zero_padding",
        )


def test_edge_policy_has_no_default() -> None:
    with pytest.raises(TypeError):
        align_estimated_path_predictions(
            path_segments=(np.zeros((1, 2)),),
            segment_start_indices=(0,),
            delays_samples=(0,),
            frame_start_sample=0,
            frame_sample_count=1,
        )  # type: ignore[call-arg]
