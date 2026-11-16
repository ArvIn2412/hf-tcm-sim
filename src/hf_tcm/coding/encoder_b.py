"""Standalone source-derived encoder/trellis preview for Chapter 4 Code 2.

This module implements only the convolutional encoder defined by the printed
generator matrix and Table 4.2. It does not define an 8PSK receiver or Viterbi
contract for this 16-state source variant.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import product

InputPairB = tuple[int, int]
OutputTripleB = tuple[int, int, int]
StateB = tuple[int, int, int, int]  # register cells (1, 3, 2, 4)
INITIAL_STATE_B: StateB = (0, 0, 0, 0)
INPUT_PAIRS_B: tuple[InputPairB, ...] = ((0, 0), (1, 0), (0, 1), (1, 1))
STATES_B: tuple[StateB, ...] = tuple(product((0, 1), repeat=4))
MAX_INFORMATION_BITS_B = 256


@dataclass(frozen=True, slots=True)
class EncoderBBranch:
    """One Code 2 edge, with the source-named manipulation parameter B."""

    branch_id: int
    state_id: int
    state: StateB
    input_pair: InputPairB
    encoded_bits: OutputTripleB
    next_state: StateB
    manipulation_parameter: int


@dataclass(frozen=True, slots=True)
class EncoderBResult:
    """Encoded bit groups and all encoder states for one preview sequence."""

    initial_state: StateB
    states: tuple[StateB, ...]
    encoded_bits: tuple[OutputTripleB, ...]
    manipulation_parameters: tuple[int, ...]
    branch_ids: tuple[int, ...]


def _validated_bits(values: Iterable[int]) -> tuple[int, ...]:
    try:
        bits = tuple(values)
    except TypeError as exc:
        raise ValueError("bits must be an iterable of integer 0/1 values") from exc
    if not 2 <= len(bits) <= MAX_INFORMATION_BITS_B or len(bits) % 2:
        raise ValueError("bits must contain 2..256 bits in complete 2-bit groups")
    if any(type(bit) is not int or bit not in (0, 1) for bit in bits):
        raise ValueError("bits must contain only integer 0/1 values")
    return bits


def _state(values: Sequence[int] | Iterable[int]) -> StateB:
    try:
        state = tuple(values)
    except TypeError as exc:
        raise ValueError("state must contain four integer bits") from exc
    if len(state) != 4 or any(type(bit) is not int or bit not in (0, 1) for bit in state):
        raise ValueError("state must contain four integer bits")
    return state  # type: ignore[return-value]


def state_id_b(state: Iterable[int]) -> int:
    """Return the Table 4.2 state Y for registers ordered `(1,3,2,4)`."""
    cells = _state(state)
    return sum(bit << shift for bit, shift in zip(cells, (3, 2, 1, 0), strict=True))


def state_b_from_id(state_id: int) -> StateB:
    if type(state_id) is not int or not 0 <= state_id < 16:
        raise ValueError("initial_state_id must be in 0..15")
    return tuple((state_id >> shift) & 1 for shift in (3, 2, 1, 0))  # type: ignore[return-value]


def encode_step_b(input_pair: Iterable[int], state: Iterable[int]) -> EncoderBBranch:
    """Apply G=[[D²+D,1,0],[1,D²,D]] with source `(C2,C1,C0)` order."""
    try:
        pair = tuple(input_pair)
    except TypeError as exc:
        raise ValueError("input_pair must contain two integer bits") from exc
    if len(pair) != 2 or any(type(bit) is not int or bit not in (0, 1) for bit in pair):
        raise ValueError("input_pair must contain two integer bits")
    x0, x1 = pair
    cells = _state(state)
    cell1, cell3, cell2, cell4 = cells
    output: OutputTripleB = (x1 ^ cell1 ^ cell2, x0 ^ cell4, cell3)
    next_state: StateB = (x0, x1, cell1, cell3)
    state_id = state_id_b(cells)
    # Table 4.2 enumerates inputs 00, 10, 01, 11; X0 is the low-order bit.
    input_id = x0 + 2 * x1
    manipulation_parameter = int("".join(str(bit) for bit in output), 2)
    return EncoderBBranch(
        branch_id=4 * state_id + input_id,
        state_id=state_id,
        state=cells,
        input_pair=(x0, x1),
        encoded_bits=output,
        next_state=next_state,
        manipulation_parameter=manipulation_parameter,
    )


def encode_b(
    information_bits: Iterable[int], *, initial_state: Iterable[int] = INITIAL_STATE_B
) -> EncoderBResult:
    """Encode complete 2-bit groups; no padding or truncation is performed."""
    bits = _validated_bits(information_bits)
    current = _state(initial_state)
    start = current
    states = [current]
    outputs: list[OutputTripleB] = []
    parameters: list[int] = []
    branch_ids: list[int] = []
    for offset in range(0, len(bits), 2):
        branch = encode_step_b(bits[offset : offset + 2], current)
        outputs.append(branch.encoded_bits)
        parameters.append(branch.manipulation_parameter)
        branch_ids.append(branch.branch_id)
        current = branch.next_state
        states.append(current)
    return EncoderBResult(
        initial_state=start,
        states=tuple(states),
        encoded_bits=tuple(outputs),
        manipulation_parameters=tuple(parameters),
        branch_ids=tuple(branch_ids),
    )


def build_trellis_b() -> tuple[EncoderBBranch, ...]:
    """Enumerate the 16 states × four inputs in the source Table 4.2 order."""
    return tuple(
        encode_step_b(input_pair, state) for state in STATES_B for input_pair in INPUT_PAIRS_B
    )
