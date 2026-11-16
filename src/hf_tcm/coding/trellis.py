"""Four-state trellis derived from the M1 convolutional encoder."""

from dataclasses import dataclass

from hf_tcm.coding.encoder import BitPair, OutputTriple, State, encode_step

STATES: tuple[State, ...] = ((0, 0), (0, 1), (1, 0), (1, 1))
INPUT_PAIRS: tuple[BitPair, ...] = ((0, 0), (0, 1), (1, 0), (1, 1))


@dataclass(frozen=True, slots=True)
class TrellisBranch:
    """One deterministic transition for an input pair and current state."""

    state: State
    input_pair: BitPair
    output: OutputTriple
    next_state: State


def build_trellis() -> tuple[TrellisBranch, ...]:
    """Return all 16 transitions in stable state/input order."""
    return tuple(
        TrellisBranch(
            state=state,
            input_pair=input_pair,
            output=output,
            next_state=next_state,
        )
        for state in STATES
        for input_pair in INPUT_PAIRS
        for output, next_state in (encode_step(input_pair, state),)
    )
