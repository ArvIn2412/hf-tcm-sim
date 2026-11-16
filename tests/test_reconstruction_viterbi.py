from __future__ import annotations

import ast
import inspect
import math

import numpy as np
import pytest

from hf_tcm.coding.encoder import INITIAL_STATE, encode_step
from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.coding.trellis import STATES, build_trellis
from hf_tcm.decoding import reconstruction_viterbi


def _decode_args(metrics: np.ndarray) -> dict[str, object]:
    count = metrics.shape[0]
    return {
        "candidate_metrics": metrics,
        "hypotheses": HYPOTHESES,
        "initial_state": INITIAL_STATE,
        "sequence_mode": "new_independent_sequence",
        "profile": "reconstructed_offline",
        "edge_indices": tuple(range(count)),
        "symbol_indices": tuple(17 + index for index in range(count)),
        "estimator_time_indices": tuple(4 + index for index in range(count)),
    }


def _all_paths(length: int) -> list[tuple[int, ...]]:
    paths: list[tuple[int, ...]] = []

    def visit(state: tuple[int, int], prefix: tuple[int, ...]) -> None:
        if len(prefix) == length:
            paths.append(prefix)
            return
        for edge in HYPOTHESES:
            if edge.current_state == state:
                visit(edge.next_state, (*prefix, edge.hypothesis_id))

    visit(INITIAL_STATE, ())
    return paths


def _brute_force(metrics: np.ndarray) -> tuple[float, tuple[int, ...], tuple[int, int]]:
    candidates: list[tuple[float, int, tuple[int, ...], tuple[int, int]]] = []
    for path in _all_paths(metrics.shape[0]):
        states = validate_hypothesis_edge_path(path, initial_state=INITIAL_STATE)
        cost = sum(float(metrics[t, edge_id]) for t, edge_id in enumerate(path))
        candidates.append((cost, states[-1].next_state, path, states[-1].next_state))
    best_metric = min(candidate[0] for candidate in candidates)
    tied = [candidate for candidate in candidates if candidate[0] == best_metric]
    # The oracle's tie policy is final canonical state order, then the path
    # tuple as a test-only deterministic complete-path ordering.
    assert len(tied) == 1
    selected = min(tied, key=lambda candidate: (STATES.index(candidate[3]), candidate[2]))
    return selected[0], selected[2], selected[3]


def test_canonical_decoder_edges_are_the_m1_trellis() -> None:
    trellis = build_trellis()
    assert STATES == ((0, 0), (0, 1), (1, 0), (1, 1))
    assert len(HYPOTHESES) == len(trellis) == 16
    for edge_id, (edge, branch) in enumerate(zip(HYPOTHESES, trellis, strict=True)):
        assert edge.hypothesis_id == edge_id
        assert edge.current_state == branch.state
        assert edge.input_bits == branch.input_pair
        assert edge.output_bits == branch.output
        assert edge.next_state == branch.next_state
        assert encode_step(edge.input_bits, edge.current_state) == (
            edge.output_bits,
            edge.next_state,
        )


@pytest.mark.parametrize("length", [1, 2, 3, 4])
def test_full_trellis_dp_matches_independent_brute_force_without_ties(length: int) -> None:
    rows = np.arange(length, dtype=np.float64)[:, None]
    columns = np.arange(16, dtype=np.float64)[None, :]
    metrics = ((rows + 3.0) * (columns + 5.0) % 37.0) + columns * 0.001
    expected_metric, expected_path, expected_final = _brute_force(metrics)

    result = reconstruction_viterbi.decode_reconstruction_viterbi(**_decode_args(metrics))

    assert result.best_path_metric == expected_metric
    assert result.hypothesis_ids == expected_path
    assert result.final_state == expected_final
    selected = validate_hypothesis_edge_path(result.hypothesis_ids, initial_state=INITIAL_STATE)
    np.testing.assert_array_equal(
        np.asarray([edge.input_bits for edge in selected], dtype=np.int8), result.input_pairs
    )


def test_selected_edges_match_m1_and_result_shapes_and_clock_labels() -> None:
    metrics = np.full((4, 16), 9.0)
    for time_index, edge_id in enumerate((0, 1, 9, 13)):
        metrics[time_index, edge_id] = 0.0
    result = reconstruction_viterbi.decode_reconstruction_viterbi(**_decode_args(metrics))

    assert len(STATES) == 4
    assert len(HYPOTHESES) == 16
    assert tuple(result.hypothesis_ids) == (0, 1, 9, 13)
    assert result.input_pairs.shape == (4, 2)
    assert result.decoded_bits.shape == (8,)
    assert tuple(result.decoded_bits) == (0, 0, 0, 1, 0, 1, 0, 1)
    assert result.edge_indices == (0, 1, 2, 3)
    assert result.symbol_indices == (17, 18, 19, 20)
    assert result.estimator_time_indices == (4, 5, 6, 7)
    assert result.symbol_indices != result.estimator_time_indices
    assert result.state_path == ((0, 0), (0, 0), (1, 0), (1, 1), (1, 1))
    for edge in validate_hypothesis_edge_path(result.hypothesis_ids, initial_state=INITIAL_STATE):
        assert encode_step(edge.input_bits, edge.current_state) == (
            edge.output_bits,
            edge.next_state,
        )


def test_decoder_chooses_valid_global_path_over_independent_row_argmins() -> None:
    metrics = np.full((2, 16), 50.0)
    metrics[0, :4] = (0.2, 0.0, 0.3, 0.4)
    metrics[1, 0] = 0.0  # Best local edge, but it starts at (0,0), unreachable after edge 1.
    metrics[1, 8:12] = 1.0  # Edges reachable after edge 1 start at (1,0).

    result = reconstruction_viterbi.decode_reconstruction_viterbi(**_decode_args(metrics))

    assert int(np.argmin(metrics[0])) == 1
    assert int(np.argmin(metrics[1])) == 0
    assert result.hypothesis_ids == (0, 0)
    assert result.best_path_metric == pytest.approx(0.2)
    assert result.state_path[-1] == (0, 0)


def test_contiguous_symbols_across_reporting_frame_boundary_do_not_reset() -> None:
    metrics = np.full((3, 16), 20.0)
    metrics[0, 1] = 0.0  # (0,0) -> (1,0)
    metrics[1, 9] = 0.0  # Continue from (1,0) -> (1,1)
    metrics[2, 13] = 0.0  # Continue from (1,1) -> (1,1)
    args = _decode_args(metrics)
    args["symbol_indices"] = (100, 101, 102)
    args["edge_indices"] = (40, 41, 42)
    args["estimator_time_indices"] = (7, 8, 9)

    result = reconstruction_viterbi.decode_reconstruction_viterbi(**args)

    # The reporting split between symbols 100 and 101 is not an input to the
    # decoder and therefore cannot trigger an implicit state reset.
    assert result.hypothesis_ids == (1, 9, 13)
    assert result.state_path == ((0, 0), (1, 0), (1, 1), (1, 1))


def test_zero_cost_ties_use_minimum_edge_id_and_canonical_final_state() -> None:
    metrics = np.zeros((3, 16), dtype=np.float64)
    result = reconstruction_viterbi.decode_reconstruction_viterbi(**_decode_args(metrics))

    assert result.final_state == STATES[0]
    assert result.hypothesis_ids == (0, 0, 0)
    assert result.best_path_metric == 0.0
    assert result.predecessor_hypothesis_ids[0, STATES.index((0, 0))] == 0
    assert result.predecessor_hypothesis_ids[0, STATES.index((1, 0))] == 1
    assert result.predecessor_hypothesis_ids[0, STATES.index((0, 1))] == -1
    assert result.predecessor_hypothesis_ids[0, STATES.index((1, 1))] == -1
    assert math.isinf(result.survivor_metrics[0, STATES.index((0, 1))])


def test_exact_survivor_tie_uses_smallest_canonical_hypothesis_id() -> None:
    metrics = np.full((1, 16), 100.0)
    metrics[0, 0] = metrics[0, 2] = 2.0  # Both edges enter state (0,0).
    metrics[0, 1] = metrics[0, 3] = 3.0  # Both edges enter state (1,0).
    result = reconstruction_viterbi.decode_reconstruction_viterbi(**_decode_args(metrics))

    assert result.predecessor_hypothesis_ids[0, STATES.index((0, 0))] == 0
    assert result.predecessor_hypothesis_ids[0, STATES.index((1, 0))] == 1


def test_zero_and_large_finite_costs_and_free_final_state() -> None:
    zero = np.zeros((1, 16))
    assert (
        reconstruction_viterbi.decode_reconstruction_viterbi(**_decode_args(zero)).best_path_metric
        == 0.0
    )

    large = np.full((2, 16), 1.0e300)
    result = reconstruction_viterbi.decode_reconstruction_viterbi(**_decode_args(large))
    assert result.best_path_metric == 2.0e300

    free_end = np.full((1, 16), 5.0)
    free_end[0, 1] = 0.0
    free_result = reconstruction_viterbi.decode_reconstruction_viterbi(**_decode_args(free_end))
    assert free_result.final_state == (1, 0)


def test_repeated_output_bits_do_not_merge_distinct_trellis_edges() -> None:
    assert HYPOTHESES[1].output_bits == HYPOTHESES[4].output_bits
    assert HYPOTHESES[1].current_state != HYPOTHESES[4].current_state
    metrics = np.full((2, 16), 50.0)
    metrics[0, 1] = 0.0
    metrics[1, 8:12] = 0.0
    result = reconstruction_viterbi.decode_reconstruction_viterbi(**_decode_args(metrics))
    assert result.hypothesis_ids[0] == 1
    assert result.hypothesis_ids[1] in range(8, 12)


@pytest.mark.parametrize(
    ("metrics", "message"),
    [
        (np.zeros((2, 15)), r"shape \(F, 16\)"),
        (np.array([[-1.0] * 16]), "non-negative"),
        (np.array([[math.nan] + [0.0] * 15]), "finite"),
        (np.array([[math.inf] + [0.0] * 15]), "finite"),
    ],
)
def test_invalid_branch_costs_are_rejected(metrics: np.ndarray, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        reconstruction_viterbi.decode_reconstruction_viterbi(**_decode_args(metrics))


def test_cost_shape_nonempty_initial_state_and_canonical_hypotheses_are_required() -> None:
    for invalid in (np.zeros((0, 16)), np.zeros((2, 16, 1)), np.zeros((16,))):
        with pytest.raises(ValueError):
            reconstruction_viterbi.decode_reconstruction_viterbi(**_decode_args(invalid))

    valid = _decode_args(np.zeros((1, 16)))
    invalid_initial = dict(valid, initial_state=(0, 1))
    with pytest.raises(ValueError, match="initial_state"):
        reconstruction_viterbi.decode_reconstruction_viterbi(**invalid_initial)

    invalid_order = dict(valid, hypotheses=tuple(reversed(HYPOTHESES)))
    with pytest.raises(ValueError, match="canonical"):
        reconstruction_viterbi.decode_reconstruction_viterbi(**invalid_order)

    with pytest.raises(ValueError, match="continuation"):
        reconstruction_viterbi.decode_reconstruction_viterbi(
            **dict(valid, sequence_mode="continuation")
        )
    with pytest.raises(ValueError, match="reconstructed_offline"):
        reconstruction_viterbi.decode_reconstruction_viterbi(
            **dict(valid, profile="source_faithful")
        )


@pytest.mark.parametrize(
    ("field", "labels", "message"),
    [
        ("edge_indices", (0, 2), "consecutive"),
        ("symbol_indices", (17, 19), "consecutive"),
        ("estimator_time_indices", (4, 6), "consecutive"),
        ("symbol_indices", (17,), "length"),
    ],
)
def test_time_label_lengths_and_continuity_are_validated(field, labels, message) -> None:
    args = _decode_args(np.zeros((2, 16)))
    args[field] = labels
    with pytest.raises(ValueError, match=message):
        reconstruction_viterbi.decode_reconstruction_viterbi(**args)


def test_accumulated_cost_overflow_is_rejected() -> None:
    metrics = np.full((2, 16), np.finfo(np.float64).max)
    with pytest.raises(ValueError, match="overflow"):
        reconstruction_viterbi.decode_reconstruction_viterbi(**_decode_args(metrics))


def test_result_and_input_are_immutable_and_repeated_calls_are_deterministic() -> None:
    metrics = np.arange(64, dtype=np.float64).reshape(4, 16)
    original = metrics.copy()
    args = _decode_args(metrics)
    first = reconstruction_viterbi.decode_reconstruction_viterbi(**args)
    second = reconstruction_viterbi.decode_reconstruction_viterbi(**args)

    np.testing.assert_array_equal(metrics, original)
    assert first.hypothesis_ids == second.hypothesis_ids
    assert first.best_path_metric == second.best_path_metric
    np.testing.assert_array_equal(first.decoded_bits, second.decoded_bits)
    with pytest.raises(ValueError):
        first.decoded_bits[0] = 1
    with pytest.raises(ValueError):
        first.survivor_metrics[0, 0] = 4.0


def test_traceback_cost_and_final_state_match_selected_path() -> None:
    metrics = np.arange(48, dtype=np.float64).reshape(3, 16) / 7.0
    result = reconstruction_viterbi.decode_reconstruction_viterbi(**_decode_args(metrics))
    path = validate_hypothesis_edge_path(result.hypothesis_ids, initial_state=INITIAL_STATE)
    manual_cost = sum(float(metrics[t, edge.hypothesis_id]) for t, edge in enumerate(path))

    assert len(path) == metrics.shape[0]
    assert result.state_path[0] == INITIAL_STATE
    assert result.state_path[-1] == result.final_state
    assert result.best_path_metric == manual_cost
    np.testing.assert_array_equal(
        np.asarray([edge.input_bits for edge in path], dtype=np.int8), result.input_pairs
    )
    assert result.decoded_bits.shape == (2 * metrics.shape[0],)


def test_public_decoder_has_no_truth_or_m3_truth_operands() -> None:
    parameters = inspect.signature(reconstruction_viterbi.decode_reconstruction_viterbi).parameters
    assert not any("truth" in name.lower() or "channel" in name.lower() for name in parameters)
    syntax_tree = ast.parse(inspect.getsource(reconstruction_viterbi))
    identifiers = {node.id for node in ast.walk(syntax_tree) if isinstance(node, ast.Name)}
    identifiers.update(
        node.attr for node in ast.walk(syntax_tree) if isinstance(node, ast.Attribute)
    )
    imports = {
        alias.name
        for node in ast.walk(syntax_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module or "" for node in ast.walk(syntax_tree) if isinstance(node, ast.ImportFrom)
    )
    assert not any("truth" in name.lower() for name in identifiers)
    assert "ChannelTruth" not in identifiers
    assert "ChannelOutput" not in identifiers
    assert not any("hf_tcm.channel" in module for module in imports)


def test_brute_force_enumeration_is_independent_and_has_expected_path_count() -> None:
    assert len(_all_paths(1)) == 4
    assert len(_all_paths(2)) == 16
    assert len(_all_paths(3)) == 64
    assert len(_all_paths(4)) == 256
