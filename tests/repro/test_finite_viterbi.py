from __future__ import annotations

import numpy as np
import pytest

from hf_tcm.repro.encoder import transition_table
from hf_tcm.repro.finite_viterbi import (
    FiniteDepthViterbiDecoder,
    ViterbiConfig,
    run_viterbi,
)
from hf_tcm.repro.finite_viterbi_plot_adapter import write_viterbi_comparison_plot
from hf_tcm.repro.hamming_viterbi import decode_hamming_viterbi
from hf_tcm.repro.joint_viterbi import decode_joint_viterbi


def _independent_best_edges(rows: np.ndarray, initial_state: tuple[int, int]) -> list[int]:
    """Exhaustive oracle for short fixtures; intentionally does not call Viterbi code."""
    states = ((0, 0), (1, 0), (0, 1), (1, 1))
    inputs = ((0, 0), (0, 1), (1, 0), (1, 1))
    candidates = [(0.0, initial_state, ())]
    for row in rows:
        next_candidates = []
        for cost, state, path in candidates:
            for state_index, source in enumerate(states):
                if source != state:
                    continue
                for input_index, pair in enumerate(inputs):
                    edge = state_index * 4 + input_index
                    target = (pair[1], state[0])
                    output = (pair[0], pair[1] ^ state[1], state[0])
                    del output
                    next_candidates.append((cost + float(row[edge]), target, path + (edge,)))
        candidates = next_candidates
    best = min(candidates, key=lambda item: (item[0], item[2]))
    return list(best[2])


def test_depth_two_emits_first_decision_at_second_row_and_flushes_tail() -> None:
    rows = np.full((4, 16), 9, dtype=np.int64)
    path = [0, 5, 10, 15]
    for time_index, edge_id in enumerate(path):
        rows[time_index, edge_id] = 0
    decoder = FiniteDepthViterbiDecoder(
        ViterbiConfig(initial_state=(0, 0), traceback_depth=2, expected_symbol_count=4)
    )
    emitted = []
    assert decoder.consume_metric_row(rows[0]) is None
    first = decoder.consume_metric_row(rows[1])
    assert first is not None
    assert (first.symbol_index, first.decision_available_at, first.traceback_depth_used) == (
        0,
        1,
        2,
    )
    emitted.append(first)
    for row in rows[2:]:
        decision = decoder.consume_metric_row(row)
        if decision is not None:
            emitted.append(decision)
    flushed = decoder.flush()
    decisions = emitted + list(flushed)
    assert [item.symbol_index for item in decisions] == list(range(4))
    assert len({item.symbol_index for item in decisions}) == 4
    assert decisions[-1].traceback_depth_used == 1
    result = decoder.result()
    assert result.decoder_mode == "finite_depth"


@pytest.mark.parametrize("frame_length", [1, 2, 20, 24])
def test_flush_returns_exactly_all_symbols_for_short_equal_and_long_frames(
    frame_length: int,
) -> None:
    rows = np.zeros((frame_length, 16), dtype=np.float64)
    result = run_viterbi(
        rows,
        ViterbiConfig(initial_state=(1, 0), traceback_depth=20, expected_symbol_count=frame_length),
    )
    assert result.decoded_edge_ids.shape == (frame_length,)
    assert result.information_pairs.shape == (frame_length, 2)
    assert len(result.decisions) == frame_length
    assert [item.symbol_index for item in result.decisions] == list(range(frame_length))
    if frame_length < 20:
        assert result.decisions[0].traceback_depth_used == frame_length
    elif frame_length == 20:
        assert result.decisions[0].traceback_depth_used == 20
    else:
        assert result.decisions[0].traceback_depth_used == 20


def test_streaming_survivor_storage_is_bounded_by_traceback_depth() -> None:
    decoder = FiniteDepthViterbiDecoder(
        ViterbiConfig(initial_state=(0, 0), traceback_depth=3, expected_symbol_count=500)
    )
    for _ in range(500):
        decoder.consume_metric_row(np.zeros(16, dtype=np.int8))
    assert decoder.survivor_buffer_rows <= 3
    assert decoder.survivor_buffer_rows == 3


def test_finite_depth_matches_independent_exhaustive_window_decisions() -> None:
    rows = np.asarray(
        [[((step + edge * 3) % 11) for edge in range(16)] for step in range(5)],
        dtype=np.int64,
    )
    result = run_viterbi(
        rows,
        ViterbiConfig(initial_state=(0, 0), traceback_depth=2, expected_symbol_count=5),
    )
    expected_first = _independent_best_edges(rows[:2], (0, 0))[0]
    assert int(result.decoded_edge_ids[0]) == expected_first
    assert result.decisions[0].decision_available_at == 1


def test_zero_tail_policy_forces_only_declared_tail_and_known_final_state() -> None:
    rows = np.zeros((5, 16), dtype=np.int8)
    result = run_viterbi(
        rows,
        ViterbiConfig(
            initial_state=(1, 1),
            traceback_depth=2,
            expected_symbol_count=5,
            termination_policy="zero_tail_2",
            final_state_policy="known_terminated",
        ),
    )
    assert result.final_state == (0, 0)
    assert result.information_pairs[-2:].tolist() == [[0, 0], [0, 0]]


def test_all_zero_costs_use_canonical_edge_and_state_tie_breaking() -> None:
    result = run_viterbi(
        np.zeros((4, 16), dtype=np.int8),
        ViterbiConfig(initial_state=(0, 0), traceback_depth=2, expected_symbol_count=4),
    )
    assert [decision.edge_id for decision in result.decisions] == [0, 0, 0, 0]
    assert result.information_pairs.tolist() == [[0, 0]] * 4


def test_nearly_equal_large_float_costs_remain_finite_and_ordered() -> None:
    rows = np.full((4, 16), 1.0e12 + 0.25, dtype=np.float64)
    rows[:, 0] = 1.0e12
    result = run_viterbi(
        rows,
        ViterbiConfig(initial_state=(0, 0), traceback_depth=2, expected_symbol_count=4),
    )
    assert result.final_metric == pytest.approx(4.0e12)
    assert np.all(np.isfinite(result.state_metrics))


def test_full_frame_reference_mode_and_validation() -> None:
    rows = np.zeros((3, 16), dtype=np.int8)
    result = run_viterbi(
        rows,
        ViterbiConfig(initial_state=(0, 0), decoder_mode="full_frame", expected_symbol_count=3),
    )
    assert result.decoder_mode == "full_frame"
    assert len(result.decisions) == 3
    with pytest.raises(ValueError, match="finite and nonnegative"):
        run_viterbi(
            np.asarray([[np.nan] * 16]),
            ViterbiConfig(initial_state=(0, 0), traceback_depth=1),
        )


def test_shared_full_frame_engine_matches_legacy_integer_and_float_decoders() -> None:
    rng = np.random.default_rng(20261106)
    initial = (1, 0)
    integer_rows = rng.integers(0, 4, size=(17, 16), dtype=np.int8)
    float_rows = rng.random((17, 16)) * 3.0
    common = dict(
        initial_state=initial,
        decoder_mode="full_frame",
        expected_symbol_count=17,
        trace_output_mode="full",
    )
    integer = run_viterbi(integer_rows, ViterbiConfig(**common))
    legacy_integer = decode_hamming_viterbi(
        integer_rows, initial_state=initial, termination_policy="none"
    )
    np.testing.assert_array_equal(integer.decoded_edge_ids, legacy_integer.decoded_edge_ids)
    floating = run_viterbi(float_rows, ViterbiConfig(**common))
    legacy_float = decode_joint_viterbi(float_rows, initial_state=initial)
    np.testing.assert_array_equal(floating.decoded_edge_ids, legacy_float.decoded_edge_ids)
    reachable = legacy_float.state_metrics < np.finfo(np.float64).max / 16
    np.testing.assert_array_equal(np.isfinite(floating.state_metrics), reachable)
    np.testing.assert_allclose(
        floating.state_metrics[reachable], legacy_float.state_metrics[reachable]
    )


@pytest.mark.parametrize("depth", [1, 2, 20])
def test_streaming_and_batch_finite_depth_agree_on_decisions(depth: int) -> None:
    rows = np.asarray([[(k + 2 * edge) % 7 for edge in range(16)] for k in range(31)])
    config = ViterbiConfig(
        initial_state=(0, 1),
        traceback_depth=depth,
        expected_symbol_count=len(rows),
    )
    batch = run_viterbi(rows, config)
    decoder = FiniteDepthViterbiDecoder(config)
    streaming = []
    for row in rows:
        decision = decoder.consume_metric_row(row)
        if decision is not None:
            streaming.append(decision)
    streaming.extend(decoder.flush())
    assert [decision.edge_id for decision in streaming] == [
        decision.edge_id for decision in batch.decisions
    ]
    assert [decision.symbol_index for decision in streaming] == list(range(len(rows)))


def test_output_edge_and_state_paths_encode_the_emitted_information_pairs() -> None:
    rows = np.random.default_rng(0).integers(0, 5, size=(30, 16))
    result = run_viterbi(
        rows,
        ViterbiConfig(initial_state=(0, 0), traceback_depth=3, expected_symbol_count=30),
    )
    table = transition_table()
    state = (0, 0)
    for step, pair_array in enumerate(result.information_pairs):
        pair = tuple(int(bit) for bit in pair_array)
        edge = int(result.decoded_edge_ids[step])
        assert table[edge][1] == state
        assert table[edge][2] == pair
        assert tuple(int(bit) for bit in result.state_path[step]) == state
        state = table[edge][4]
        assert tuple(int(bit) for bit in result.state_path[step + 1]) == state


def test_short_depth_can_differ_from_full_frame_without_claiming_quality() -> None:
    rows = np.random.default_rng(1).integers(0, 5, size=(30, 16))
    finite = run_viterbi(
        rows,
        ViterbiConfig(initial_state=(0, 0), traceback_depth=2, expected_symbol_count=30),
    )
    full = run_viterbi(
        rows,
        ViterbiConfig(
            initial_state=(0, 0),
            decoder_mode="full_frame",
            expected_symbol_count=30,
            trace_output_mode="compact",
        ),
    )
    assert np.count_nonzero(np.any(finite.information_pairs != full.information_pairs, axis=1)) > 0


def test_actual_full_vs_finite_plot_records_path_differences_and_latency(tmp_path) -> None:
    rows = np.random.default_rng(1).integers(0, 5, size=(30, 16))
    finite = run_viterbi(
        rows,
        ViterbiConfig(initial_state=(0, 0), traceback_depth=2, expected_symbol_count=30),
    )
    full = run_viterbi(
        rows,
        ViterbiConfig(
            initial_state=(0, 0),
            decoder_mode="full_frame",
            expected_symbol_count=30,
        ),
    )
    path = write_viterbi_comparison_plot(
        full,
        finite,
        rows,
        metric_profile="test_integer_cost",
        output_path=tmp_path / "comparison.svg",
    )
    content = path.read_text(encoding="utf-8")
    assert "Повнокадрове та обмежене декодування Вітербі" in content
    assert "Затримка рішення" in content or "затримка" in content.lower()
    assert "позиції відмінних бітів" in content
    assert "test_integer_cost" in content
