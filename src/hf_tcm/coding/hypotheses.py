"""Deterministic structural branch hypotheses derived from the M1 trellis.

The hypothesis IDs here are project-local row indices. Their correspondence
to the article's discrete parameter ``theta`` is not established.
"""

from dataclasses import dataclass

from hf_tcm.coding.encoder import BitPair, OutputTriple, State
from hf_tcm.coding.trellis import build_trellis


@dataclass(frozen=True, slots=True)
class Hypothesis:
    """One state/input branch, with its deterministic encoder result."""

    current_state: State
    input_bits: BitPair
    output_bits: OutputTriple
    next_state: State
    hypothesis_id: int


def build_hypotheses() -> tuple[Hypothesis, ...]:
    """Return the 16 encoder branches in stable trellis order.

    The ID is the zero-based row number from ``build_trellis``. It is a
    deterministic project convention, not a claimed indexing of article
    parameter ``theta``.
    """
    return tuple(
        Hypothesis(
            current_state=branch.state,
            input_bits=branch.input_pair,
            output_bits=branch.output,
            next_state=branch.next_state,
            hypothesis_id=hypothesis_id,
        )
        for hypothesis_id, branch in enumerate(build_trellis())
    )


HYPOTHESES: tuple[Hypothesis, ...] = build_hypotheses()


def is_allowed_transition(
    current_state: State,
    input_bits: BitPair,
    next_state: State,
) -> bool:
    """Check whether a state/input/next-state branch exists in the trellis.

    This is a structural 0/1 membership check. It returns no transition
    probability and does not define a posterior model.
    """
    return any(
        hypothesis.current_state == current_state
        and hypothesis.input_bits == input_bits
        and hypothesis.next_state == next_state
        for hypothesis in HYPOTHESES
    )
