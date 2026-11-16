"""Rate-2/3 convolutional encoder for the explicitly scoped M1 baseline."""

from collections.abc import Iterable, Sequence

BitPair = tuple[int, int]
OutputTriple = tuple[int, int, int]
State = tuple[int, int]
INITIAL_STATE: State = (0, 0)


def _binary_pair(values: Sequence[int], *, name: str) -> BitPair:
    if len(values) != 2 or any(type(bit) is not int or bit not in (0, 1) for bit in values):
        raise ValueError(f"{name} must contain exactly two integer bits (0 or 1)")
    return values[0], values[1]


def _pair(values: Iterable[int], *, name: str) -> BitPair:
    try:
        materialized = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{name} must contain exactly two integer bits (0 or 1)") from exc
    return _binary_pair(materialized, name=name)


def encode_step(input_pair: Iterable[int], state: Iterable[int]) -> tuple[OutputTriple, State]:
    """Encode ``(u0, u1)`` using memory ``(u1[k-1], u1[k-2])``.

    The output order is ``(c2, c1, c0)`` as specified by the project model.
    """
    u0, u1 = _pair(input_pair, name="input_pair")
    previous_1, previous_2 = _pair(state, name="state")
    output = (u0, u1 ^ previous_2, previous_1)
    next_state = (u1, previous_1)
    return output, next_state


def encode(
    input_pairs: Iterable[Iterable[int]], *, initial_state: Iterable[int] = INITIAL_STATE
) -> list[OutputTriple]:
    """Encode input bit pairs without adding termination or tail bits."""
    state = _pair(initial_state, name="initial_state")
    outputs: list[OutputTriple] = []
    for input_pair in input_pairs:
        output, state = encode_step(input_pair, state)
        outputs.append(output)
    return outputs
