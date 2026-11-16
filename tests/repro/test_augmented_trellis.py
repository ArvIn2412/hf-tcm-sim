from __future__ import annotations

import pytest

from hf_tcm.repro.augmented_trellis import build_augmented_trellis
from hf_tcm.repro.multipath_receiver_config import (
    MultipathPathConfig,
    MultipathReceiverConfig,
)


def test_d3_trellis_contains_minimum_previous_phase_memory() -> None:
    trellis = build_augmented_trellis((0, 0), (0, 3))

    assert trellis.memory_symbols == 1
    assert trellis.state_count == 17
    assert trellis.edge_count == 68
    assert sum(edge.source_node_id == trellis.initial_node_id for edge in trellis.edges) == 4


def test_d0_trellis_reduces_to_encoder_a_four_state_sixteen_edge_graph() -> None:
    trellis = build_augmented_trellis((0, 0), (0,))

    assert trellis.memory_symbols == 0
    assert trellis.state_count == 4
    assert trellis.edge_count == 16


def test_each_expanded_transition_preserves_encoder_transition_and_history_shift() -> None:
    trellis = build_augmented_trellis((1, 1), (0, 3))

    for edge in trellis.edges:
        source = trellis.nodes[edge.source_node_id]
        target = trellis.nodes[edge.target_node_id]
        assert edge.source_state == source.encoder_state
        assert edge.target_state == target.encoder_state
        assert target.phase_history == (edge.phase_index,)


def test_delay_memory_beyond_configured_bound_is_rejected() -> None:
    with pytest.raises(ValueError, match="at most 2 previous symbols"):
        build_augmented_trellis((0, 0), (0, 17))


def test_trellis_enforces_expanded_graph_caps() -> None:
    with pytest.raises(ValueError, match="expanded trellis exceeds configured cap"):
        build_augmented_trellis((0, 0), (0, 3), max_edges=67)


def test_static_known_channel_config_round_trips_complex_gains() -> None:
    config = MultipathReceiverConfig(
        expected_symbol_count=32,
        paths=(
            MultipathPathConfig(0, 1 + 0j),
            MultipathPathConfig(3, 0.25 - 0.5j),
        ),
        decoder_mode="finite_depth",
        traceback_depth=20,
    )

    restored = MultipathReceiverConfig.from_dict(config.to_dict())
    assert restored == config
    assert restored.channel_memory_symbols == 1
    assert restored.to_dict()["paths"][1]["gain"] == [0.25, -0.5]


def test_unknown_rician_profile_is_explicitly_unavailable() -> None:
    with pytest.raises(ValueError, match="adaptive Rician multipath is unavailable"):
        MultipathReceiverConfig(
            expected_symbol_count=8,
            paths=(MultipathPathConfig(0, 1 + 0j),),
            estimator_profile="adaptive_rician_survivor_v1",
        )


def test_fractional_delay_is_never_rounded_during_json_config_parse() -> None:
    with pytest.raises(ValueError, match="invalid static multipath entry"):
        MultipathReceiverConfig.from_dict(
            {
                "expected_symbol_count": 8,
                "paths": [{"delay_samples": 3.5, "gain": [1, 0]}],
            }
        )
