"""Structural validation for an explicitly supplied M1 hypothesis path.

This module checks a completed edge sequence only. It does not search,
score, decode, choose a final state, or implement Viterbi/traceback.
"""

from __future__ import annotations

from collections.abc import Sequence
from numbers import Integral

from hf_tcm.coding.encoder import State
from hf_tcm.coding.hypotheses import HYPOTHESES, Hypothesis


def validate_hypothesis_edge_path(
    hypothesis_ids: Sequence[int],
    *,
    initial_state: State,
) -> tuple[Hypothesis, ...]:
    """Validate explicit edge IDs against an initial memory state and adjacency.

    No final-state policy is imposed. Returned hypotheses preserve the input
    edge order and expose each edge's input/output bits and successor state.
    """
    if (
        not isinstance(initial_state, Sequence)
        or isinstance(initial_state, (str, bytes))
        or len(initial_state) != 2
        or any(type(bit) is not int or bit not in (0, 1) for bit in initial_state)
    ):
        raise ValueError("initial_state must be one of the four M1 memory states")
    if (
        not isinstance(hypothesis_ids, Sequence)
        or isinstance(hypothesis_ids, (str, bytes))
        or not hypothesis_ids
        or any(
            isinstance(hypothesis_id, bool) or not isinstance(hypothesis_id, Integral)
            for hypothesis_id in hypothesis_ids
        )
    ):
        raise ValueError("hypothesis_ids must be a non-empty sequence of integer edge IDs")
    canonical_ids = tuple(hypothesis.hypothesis_id for hypothesis in HYPOTHESES)
    if canonical_ids != tuple(range(len(HYPOTHESES))):
        raise RuntimeError("HYPOTHESES must retain stable row-order IDs")
    if any(not 0 <= int(hypothesis_id) < len(HYPOTHESES) for hypothesis_id in hypothesis_ids):
        raise ValueError("hypothesis_ids contain an ID outside the canonical hypothesis order")

    path = tuple(HYPOTHESES[int(hypothesis_id)] for hypothesis_id in hypothesis_ids)
    if path[0].current_state != tuple(initial_state):
        raise ValueError("first edge current_state must match initial_state")
    for previous, following in zip(path, path[1:]):
        if previous.next_state != following.current_state:
            raise ValueError("edge path contains a structurally invalid adjacent transition")
    return path
