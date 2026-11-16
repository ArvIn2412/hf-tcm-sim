from __future__ import annotations

import numpy as np

from hf_tcm.repro.augmented_trellis import AugmentedTransition, build_augmented_trellis
from hf_tcm.repro.isi_predictor import predict_transition_samples
from hf_tcm.repro.multipath_receiver_config import (
    MultipathPathConfig,
    MultipathReceiverConfig,
)


def _edge(trellis, source_node_id: int, base_edge_id: int) -> AugmentedTransition:
    return next(
        edge
        for edge in trellis.edges
        if edge.source_node_id == source_node_id and edge.base_edge_id == base_edge_id
    )


def _symbol(phase: int, config: MultipathReceiverConfig) -> complex:
    return config.amplitude * np.exp(
        1j * (config.phase_offset_rad + phase * config.phase_increment_rad)
    )


def test_d3_prediction_uses_previous_symbol_for_first_three_samples() -> None:
    config = MultipathReceiverConfig(
        expected_symbol_count=2,
        paths=(
            MultipathPathConfig(0, 1 + 0j),
            MultipathPathConfig(3, 0.5 + 0.25j),
        ),
    )
    trellis = build_augmented_trellis((0, 0), (0, 3))
    first = _edge(trellis, trellis.initial_node_id, 0)
    second = _edge(trellis, first.target_node_id, 1)

    predicted = predict_transition_samples(
        second,
        trellis,
        symbol_index=1,
        frame_symbols=2,
        config=config,
        sample_indices=np.arange(8, 16, dtype=np.int64),
    )
    previous_symbol = _symbol(first.phase_index, config)
    current_symbol = _symbol(second.phase_index, config)
    expected = np.array(
        [
            current_symbol + (0.5 + 0.25j) * previous_symbol,
            current_symbol + (0.5 + 0.25j) * previous_symbol,
            current_symbol + (0.5 + 0.25j) * previous_symbol,
            *([current_symbol * (1.5 + 0.25j)] * 5),
        ],
        dtype=np.complex128,
    )

    np.testing.assert_allclose(predicted, expected, rtol=0, atol=1e-14)


def test_zero_extension_at_frame_start_and_d3_final_tail() -> None:
    config = MultipathReceiverConfig(
        expected_symbol_count=1,
        paths=(
            MultipathPathConfig(0, 1 + 0j),
            MultipathPathConfig(3, 0.25 - 0.5j),
        ),
    )
    trellis = build_augmented_trellis((0, 0), (0, 3))
    edge = _edge(trellis, trellis.initial_node_id, 0)
    current = _symbol(edge.phase_index, config)
    block = predict_transition_samples(
        edge,
        trellis,
        symbol_index=0,
        frame_symbols=1,
        config=config,
        sample_indices=np.arange(8, dtype=np.int64),
    )
    tail = predict_transition_samples(
        edge,
        trellis,
        symbol_index=0,
        frame_symbols=1,
        config=config,
        sample_indices=np.arange(8, 11, dtype=np.int64),
    )

    expected_block = np.asarray([current] * 3 + [current * (1.25 - 0.5j)] * 5)
    np.testing.assert_allclose(block, expected_block, rtol=0, atol=1e-14)
    np.testing.assert_allclose(tail, np.full(3, (0.25 - 0.5j) * current), rtol=0, atol=1e-14)


def test_d0_prediction_is_the_public_static_complex_gain_times_zoh_symbol() -> None:
    config = MultipathReceiverConfig(
        expected_symbol_count=1,
        paths=(MultipathPathConfig(0, 0.3 + 0.7j),),
    )
    trellis = build_augmented_trellis((0, 0), (0,))
    edge = trellis.edges[0]
    actual = predict_transition_samples(
        edge,
        trellis,
        symbol_index=0,
        frame_symbols=1,
        config=config,
        sample_indices=np.arange(8, dtype=np.int64),
    )
    expected = np.full(8, (0.3 + 0.7j) * _symbol(edge.phase_index, config))
    np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-14)


def test_d9_prediction_uses_two_symbol_history_at_the_first_sample() -> None:
    config = MultipathReceiverConfig(
        expected_symbol_count=3,
        paths=(MultipathPathConfig(0, 1 + 0j), MultipathPathConfig(9, 0.2 + 0.1j)),
    )
    trellis = build_augmented_trellis((0, 0), (0, 9))
    first = _edge(trellis, trellis.initial_node_id, 0)
    second = _edge(trellis, first.target_node_id, 1)
    third = next(edge for edge in trellis.edges if edge.source_node_id == second.target_node_id)
    actual = predict_transition_samples(
        third,
        trellis,
        symbol_index=2,
        frame_symbols=3,
        config=config,
        sample_indices=np.arange(16, 24, dtype=np.int64),
    )
    current = _symbol(third.phase_index, config)
    previous = _symbol(second.phase_index, config)
    previous_two = _symbol(first.phase_index, config)
    expected = np.asarray(
        [
            current + (0.2 + 0.1j) * previous_two,
            *([current + (0.2 + 0.1j) * previous] * 7),
        ],
        dtype=np.complex128,
    )

    assert trellis.memory_symbols == 2
    np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-14)
