"""T-01: hand-checked convolutional encoder examples and input validation."""

import pytest

from hf_tcm.coding.encoder import encode, encode_step


def test_encode_matches_hand_calculated_sequence() -> None:
    inputs = [(1, 0), (0, 1), (1, 1), (0, 0)]

    assert encode(inputs) == [(1, 0, 0), (0, 1, 0), (1, 1, 1), (0, 1, 1)]


def test_encode_step_accepts_explicit_initial_memory() -> None:
    assert encode_step((1, 1), (1, 0)) == ((1, 1, 1), (1, 1))


@pytest.mark.parametrize("inputs", [[(0,)], [(0, 2)], [(0, False)], ["01"]])
def test_encode_rejects_invalid_input_pairs(inputs: list[object]) -> None:
    with pytest.raises(ValueError):
        encode(inputs)  # type: ignore[arg-type]


def test_encode_rejects_invalid_initial_state() -> None:
    with pytest.raises(ValueError, match="state"):
        encode([], initial_state=(0, 2))
