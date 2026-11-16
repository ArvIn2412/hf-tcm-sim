from __future__ import annotations

from itertools import product

import numpy as np

from hf_tcm.repro.augmented_trellis import AugmentedTrellis, build_augmented_trellis
from hf_tcm.repro.expanded_viterbi import (
    ExpandedViterbiConfig,
    ExpandedViterbiDecoder,
    run_expanded_viterbi,
)


def _exhaustive_path(trellis: AugmentedTrellis, costs: np.ndarray) -> tuple[int, ...]:
    best_cost = float("inf")
    best_edges: tuple[int, ...] | None = None
    outgoing = {
        node.node_id: tuple(edge for edge in trellis.edges if edge.source_node_id == node.node_id)
        for node in trellis.nodes
    }
    for chosen in product(range(4), repeat=len(costs)):
        node = trellis.initial_node_id
        path: list[int] = []
        total = 0.0
        valid = True
        for step, edge_index in enumerate(chosen):
            edges = outgoing[node]
            if edge_index >= len(edges):
                valid = False
                break
            edge = edges[edge_index]
            path.append(edge.expanded_edge_id)
            total += float(costs[step, edge.expanded_edge_id])
            node = edge.target_node_id
        if valid and total < best_cost:
            best_cost, best_edges = total, tuple(path)
    assert best_edges is not None
    return best_edges


def test_full_frame_expanded_viterbi_matches_exhaustive_short_frame() -> None:
    trellis = build_augmented_trellis((0, 0), (0, 3))
    costs = np.random.default_rng(61).uniform(0.01, 3, size=(4, trellis.edge_count))

    result = run_expanded_viterbi(
        costs,
        trellis,
        ExpandedViterbiConfig(
            decoder_mode="full_frame",
            traceback_depth=None,
            expected_symbol_count=4,
        ),
    )
    expected_path = _exhaustive_path(trellis, costs)

    assert tuple(record.expanded_edge_id for record in result.decisions) == expected_path
    assert result.information_pairs.tolist() == [
        list(trellis.edges[edge_id].input_pair) for edge_id in expected_path
    ]
    assert result.survivor_buffer_max_rows == 4


def test_finite_eta20_decision_latency_flush_and_bounded_ring() -> None:
    trellis = build_augmented_trellis((0, 0), (0, 3))
    rows = np.random.default_rng(4).uniform(0, 2, size=(27, trellis.edge_count))
    config = ExpandedViterbiConfig(
        decoder_mode="finite_depth",
        traceback_depth=20,
        expected_symbol_count=27,
    )
    decoder = ExpandedViterbiDecoder(trellis, config)
    ordinary = [record for row in rows if (record := decoder.consume_metric_row(row))]
    flushed = decoder.flush()
    result = decoder.result()

    assert ordinary[0].symbol_index == 0
    assert ordinary[0].decision_available_at == 19
    assert ordinary[0].traceback_depth_used == 20
    assert len(ordinary) == 8
    assert len(flushed) == 19
    assert [record.symbol_index for record in result.decisions] == list(range(27))
    assert result.survivor_buffer_max_rows == 20


def test_streaming_and_batch_finite_results_have_same_local_decisions() -> None:
    trellis = build_augmented_trellis((1, 0), (0, 3))
    rows = np.random.default_rng(20).uniform(0, 4, size=(11, trellis.edge_count))
    config = ExpandedViterbiConfig(
        decoder_mode="finite_depth",
        traceback_depth=3,
        expected_symbol_count=len(rows),
    )
    batch = run_expanded_viterbi(rows, trellis, config)
    decoder = ExpandedViterbiDecoder(trellis, config)
    decisions = [decoder.consume_metric_row(row) for row in rows]
    decisions = [record for record in decisions if record is not None]
    decisions.extend(decoder.flush())

    assert [record.expanded_edge_id for record in decisions] == [
        record.expanded_edge_id for record in batch.decisions
    ]
    assert [record.symbol_index for record in decisions] == list(range(len(rows)))


def test_short_frame_flush_uses_actual_traceback_depth_and_emits_every_symbol() -> None:
    trellis = build_augmented_trellis((0, 1), (0, 3))
    rows = np.zeros((3, trellis.edge_count), dtype=np.float64)
    result = run_expanded_viterbi(
        rows,
        trellis,
        ExpandedViterbiConfig(
            decoder_mode="finite_depth",
            traceback_depth=20,
            expected_symbol_count=3,
        ),
    )

    assert [decision.traceback_depth_used for decision in result.decisions] == [3, 2, 1]
    assert [decision.decision_policy for decision in result.decisions] == [
        "frame_flush",
        "frame_flush",
        "frame_flush",
    ]
    assert result.information_pairs.shape == (3, 2)


def test_exact_eta_frame_has_one_regular_decision_and_eta_minus_one_flush_records() -> None:
    trellis = build_augmented_trellis((0, 0), (0, 3))
    rows = np.random.default_rng(81).uniform(0, 1, size=(20, trellis.edge_count))
    decoder = ExpandedViterbiDecoder(
        trellis,
        ExpandedViterbiConfig(
            decoder_mode="finite_depth",
            traceback_depth=20,
            expected_symbol_count=20,
        ),
    )
    ordinary = [decoder.consume_metric_row(row) for row in rows]
    ordinary = [row for row in ordinary if row is not None]
    flushed = decoder.flush()

    assert len(ordinary) == 1
    assert (ordinary[0].symbol_index, ordinary[0].decision_available_at) == (0, 19)
    assert len(flushed) == 19
    assert [row.traceback_depth_used for row in flushed] == list(range(19, 0, -1))


def test_eta_one_and_two_emit_expected_decision_availability() -> None:
    trellis = build_augmented_trellis((0, 0), (0, 3))
    for depth in (1, 2):
        rows = np.random.default_rng(depth).uniform(0, 1, size=(5, trellis.edge_count))
        result = run_expanded_viterbi(
            rows,
            trellis,
            ExpandedViterbiConfig(
                decoder_mode="finite_depth",
                traceback_depth=depth,
                expected_symbol_count=5,
            ),
        )
        assert result.decisions[0].symbol_index == 0
        assert result.decisions[0].decision_available_at == depth - 1
        assert result.decisions[0].traceback_depth_used == depth


def test_zero_tail_constraints_use_public_inputs_and_terminal_encoder_state() -> None:
    trellis = build_augmented_trellis((0, 0), (0, 3))
    rows = np.random.default_rng(1).uniform(0, 1, size=(6, trellis.edge_count))
    result = run_expanded_viterbi(
        rows,
        trellis,
        ExpandedViterbiConfig(
            decoder_mode="full_frame",
            traceback_depth=None,
            expected_symbol_count=6,
            forced_tail_input_pairs=((0, 0), (0, 0)),
            terminal_node_ids=tuple(
                node.node_id for node in trellis.nodes if node.encoder_state == (0, 0)
            ),
        ),
    )

    assert result.information_pairs[-2:].tolist() == [[0, 0], [0, 0]]
    assert trellis.nodes[result.terminal_survivor_node_id].encoder_state == (0, 0)
