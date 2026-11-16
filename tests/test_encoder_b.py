"""Source-conformance tests for Chapter 4 Code 2, separate from encoder A."""

from __future__ import annotations

import itertools

import pytest

from hf_tcm.coding.encoder_b import (
    INITIAL_STATE_B,
    INPUT_PAIRS_B,
    STATES_B,
    build_trellis_b,
    encode_b,
    encode_step_b,
    state_id_b,
)


def _source_matrix_output(input_pair: tuple[int, int], state: tuple[int, int, int, int]):
    """Evaluate G=[[D²+D,1,0],[1,D²,D]] in (cell 1,3,2,4) order."""
    x0, x1 = input_pair
    cell1, cell3, cell2, cell4 = state
    return (x1 ^ cell1 ^ cell2, x0 ^ cell4, cell3)


def test_code_b_all_64_branches_match_source_generator_matrix_and_table_order() -> None:
    branches = build_trellis_b()

    assert len(STATES_B) == 16
    assert len(INPUT_PAIRS_B) == 4
    assert len(branches) == 64
    assert [branch.branch_id for branch in branches] == list(range(64))
    assert len({(branch.state, branch.input_pair) for branch in branches}) == 64
    for branch in branches:
        assert branch.encoded_bits == _source_matrix_output(branch.input_pair, branch.state)
        assert branch.manipulation_parameter == int("".join(map(str, branch.encoded_bits)), 2)
        cell1, cell3, _, _ = branch.state
        x0, x1 = branch.input_pair
        assert branch.next_state == (x0, x1, cell1, cell3)
        assert branch.branch_id == 4 * state_id_b(branch.state) + x0 + 2 * x1


def test_code_b_matches_rows_spanning_the_published_source_table() -> None:
    assert encode_step_b((0, 0), (0, 0, 0, 0)).encoded_bits == (0, 0, 0)
    assert encode_step_b((1, 0), (0, 0, 0, 0)).encoded_bits == (0, 1, 0)
    assert encode_step_b((0, 1), (0, 0, 0, 0)).encoded_bits == (1, 0, 0)
    assert encode_step_b((1, 1), (0, 0, 0, 0)).encoded_bits == (1, 1, 0)
    assert encode_step_b((0, 0), (1, 0, 0, 0)).encoded_bits == (1, 0, 0)
    assert encode_step_b((0, 0), (0, 1, 0, 0)).encoded_bits == (0, 0, 1)
    assert encode_step_b((0, 0), (0, 0, 0, 1)).encoded_bits == (0, 1, 0)


def test_code_b_reset_sequence_records_state_and_manipulation_parameter() -> None:
    result = encode_b((0, 0, 1, 0, 1, 1))

    assert result.initial_state == INITIAL_STATE_B == (0, 0, 0, 0)
    assert result.states == ((0, 0, 0, 0), (0, 0, 0, 0), (1, 0, 0, 0), (1, 1, 1, 0))
    assert result.encoded_bits == ((0, 0, 0), (0, 1, 0), (0, 1, 0))
    assert result.manipulation_parameters == (0, 2, 2)
    assert result.branch_ids == (0, 1, 35)


def test_code_b_accepts_explicit_preview_start_state() -> None:
    branch = encode_step_b((1, 1), (1, 0, 1, 0))
    assert branch.next_state == (1, 1, 1, 0)
    assert state_id_b(branch.next_state) == 14


@pytest.mark.parametrize(
    ("inputs", "state"),
    [((0,), (0, 0, 0, 0)), ((0, 2), (0, 0, 0, 0)), ((0, False), (0, 0, 0, 0)), ((0, 0), (0, 0, 0))],
)
def test_code_b_step_rejects_invalid_pair_or_state(inputs, state) -> None:
    with pytest.raises(ValueError):
        encode_step_b(inputs, state)


@pytest.mark.parametrize(
    "bits", [(), (1,), (0, 2), (0, False), (0, 1, 0), tuple(itertools.repeat(0, 258))]
)
def test_code_b_sequence_rejects_invalid_bits_or_unsafe_length(bits) -> None:
    with pytest.raises(ValueError):
        encode_b(bits)
