import numpy as np
import pytest

from hf_tcm.coding.encoder import INITIAL_STATE, encode_step
from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.coding.posterior import ALLOWED_HYPOTHESIS_TRANSITIONS
from hf_tcm.coding.trellis import INPUT_PAIRS, STATES, build_trellis
from hf_tcm.receiver.reconstruction_labeling import (
    ASSUMED_NATURAL_BINARY,
    OUTPUT_BIT_ORDER,
    hypothesis_to_phase_index,
)
from hf_tcm.receiver.reconstruction_posterior import build_reconstruction_transition_matrix


def test_all_sixteen_hypotheses_match_m1_encoder_transitions_and_stable_order() -> None:
    branches = build_trellis()
    assert STATES == ((0, 0), (0, 1), (1, 0), (1, 1))
    assert INPUT_PAIRS == ((0, 0), (0, 1), (1, 0), (1, 1))
    assert len(branches) == len(HYPOTHESES) == 16
    for edge_id, (branch, hypothesis) in enumerate(zip(branches, HYPOTHESES, strict=True)):
        assert hypothesis.hypothesis_id == edge_id
        assert (hypothesis.current_state, hypothesis.input_bits) == (
            branch.state,
            branch.input_pair,
        )
        assert (hypothesis.output_bits, hypothesis.next_state) == (branch.output, branch.next_state)
        assert encode_step(hypothesis.input_bits, hypothesis.current_state) == (
            hypothesis.output_bits,
            hypothesis.next_state,
        )


def test_structural_adjacency_matches_posterior_mask_and_uniform_transition_order() -> None:
    expected = np.array(
        [
            [previous.next_state == following.current_state for following in HYPOTHESES]
            for previous in HYPOTHESES
        ],
        dtype=np.uint8,
    )
    np.testing.assert_array_equal(ALLOWED_HYPOTHESIS_TRANSITIONS, expected)
    probabilities = build_reconstruction_transition_matrix()
    assert probabilities.shape == (16, 16)
    np.testing.assert_array_equal(probabilities[expected == 0], 0.0)
    np.testing.assert_allclose(probabilities.sum(axis=1), np.ones(16), rtol=0.0, atol=1e-15)
    assert tuple(h.hypothesis_id for h in HYPOTHESES) == tuple(range(16))


def test_explicit_two_to_four_edge_paths_validate_and_recover_input_pairs() -> None:
    path_ids = (0, 1, 9, 13)
    path = validate_hypothesis_edge_path(path_ids, initial_state=INITIAL_STATE)
    assert tuple(edge.hypothesis_id for edge in path) == path_ids
    assert tuple(edge.input_bits for edge in path) == ((0, 0), (0, 1), (0, 1), (0, 1))
    assert all(left.next_state == right.current_state for left, right in zip(path, path[1:]))
    assert len(path[:2]) == 2
    assert len(path[:3]) == 3
    assert len(path) == 4
    # Two information bits are recovered directly from each selected edge.
    decoded_pairs = tuple(edge.input_bits for edge in path)
    assert tuple(bit for pair in decoded_pairs for bit in pair) == (0, 0, 0, 1, 0, 1, 0, 1)


@pytest.mark.parametrize(
    ("edge_ids", "initial_state", "message"),
    [
        ((0, 8), (0, 0), "structurally invalid"),
        ((1,), (0, 1), "first edge"),
        ((16,), (0, 0), "outside"),
        ((0, True), (0, 0), "integer edge IDs"),
        ((), (0, 0), "non-empty"),
    ],
)
def test_invalid_explicit_edge_paths_are_rejected(edge_ids, initial_state, message) -> None:
    with pytest.raises(ValueError, match=message):
        validate_hypothesis_edge_path(edge_ids, initial_state=initial_state)


def test_hypothesis_ids_are_metadata_not_phase_indices() -> None:
    edge = HYPOTHESES[8]
    phase = hypothesis_to_phase_index(
        edge,
        profile=ASSUMED_NATURAL_BINARY,
        bit_order=OUTPUT_BIT_ORDER,
    )
    assert edge.hypothesis_id == 8
    assert phase == 1
    assert edge.hypothesis_id != phase


def test_hand_cumulative_conditional_branch_cost_for_one_valid_path() -> None:
    path = validate_hypothesis_edge_path((0, 1, 9, 13), initial_state=(0, 0))
    candidate_costs = np.zeros((4, 16), dtype=np.float64)
    candidate_costs[0, 0] = 0.4
    candidate_costs[1, 1] = 1.2
    candidate_costs[2, 9] = 0.7
    candidate_costs[3, 13] = 0.3
    assert candidate_costs.shape == (4, 16)
    cumulative_cost = sum(
        candidate_costs[time, edge.hypothesis_id] for time, edge in enumerate(path)
    )
    assert cumulative_cost == pytest.approx(2.6)
    # Synthetic branch costs need no ChannelTruth or true transmitted bits.
    assert not np.any(~np.isfinite(candidate_costs))


def test_absolute_symbol_and_sample_formula_does_not_use_frame_local_index_as_absolute() -> None:
    symbol_origin_sample = 23
    frame_first_absolute_symbol = 4
    frame_local_symbol = 0
    absolute_symbol = frame_first_absolute_symbol + frame_local_symbol
    first_sample = symbol_origin_sample + 8 * absolute_symbol
    assert first_sample == 55
    assert tuple(range(first_sample, first_sample + 8)) == tuple(range(55, 63))
    assert first_sample - 1 == 54
    assert first_sample + 7 == 62
