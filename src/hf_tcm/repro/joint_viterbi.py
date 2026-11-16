"""Full-frame four-state Viterbi over real-valued REPRO-05 branch costs."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.encoder import STATE_ORDER, transition_table

_EDGES = transition_table()
_STATE_INDEX = {state: i for i, state in enumerate(STATE_ORDER)}


@dataclass(frozen=True, slots=True)
class JointViterbiResult:
    state_metrics: NDArray[np.float64]
    survivor_edge_ids: NDArray[np.int16]
    decoded_edge_ids: NDArray[np.int16]
    state_path: NDArray[np.int8]
    information_pairs: NDArray[np.int8]
    final_state: tuple[int, int]
    final_metric: float


def decode_joint_viterbi(
    branch_metrics: object,
    *,
    initial_state: tuple[int, int],
    termination_policy: str = "none",
) -> JointViterbiResult:
    costs = np.asarray(branch_metrics, dtype=np.float64)
    if costs.ndim != 2 or costs.shape[1] != 16 or costs.shape[0] < 1:
        raise ValueError("branch_metrics must have shape (F,16), F >= 1")
    if not np.all(np.isfinite(costs)) or np.any(costs < 0):
        raise ValueError("branch metrics must be finite and nonnegative")
    if initial_state not in _STATE_INDEX:
        raise ValueError("initial_state must be a valid Encoder A state")
    if termination_policy not in {"none", "zero_tail_2"}:
        raise ValueError("unsupported termination_policy")
    count = len(costs)
    if termination_policy == "zero_tail_2" and count < 3:
        raise ValueError("zero_tail_2 requires at least one payload and two tail symbols")
    infinity = np.finfo(np.float64).max / 16
    metrics = np.full((count + 1, 4), infinity, dtype=np.float64)
    survivors = np.full((count, 4), -1, dtype=np.int16)
    metrics[0, _STATE_INDEX[initial_state]] = 0.0
    for k in range(count):
        zero_tail = termination_policy == "zero_tail_2" and k >= count - 2
        for edge_id, source, pair, _coded, target in _EDGES:
            if zero_tail and pair != (0, 0):
                continue
            src, dst = _STATE_INDEX[source], _STATE_INDEX[target]
            prefix = metrics[k, src]
            if prefix >= infinity:
                continue
            candidate = prefix + costs[k, edge_id]
            if candidate < metrics[k + 1, dst]:
                metrics[k + 1, dst] = candidate
                survivors[k, dst] = edge_id
    final_index = (
        _STATE_INDEX[(0, 0)] if termination_policy == "zero_tail_2" else int(np.argmin(metrics[-1]))
    )
    if not np.isfinite(metrics[-1, final_index]) or metrics[-1, final_index] >= infinity:
        raise ValueError("no valid path satisfies configured trellis constraints")
    edges = np.empty(count, dtype=np.int16)
    state_indices = np.empty(count + 1, dtype=np.int8)
    state_indices[-1] = final_index
    current = final_index
    for k in range(count - 1, -1, -1):
        edge = int(survivors[k, current])
        if edge < 0:
            raise RuntimeError("Viterbi survivor traceback is incomplete")
        edges[k] = edge
        current = _STATE_INDEX[_EDGES[edge][1]]
        state_indices[k] = current
    if current != _STATE_INDEX[initial_state]:
        raise RuntimeError("Viterbi traceback did not return to initial state")
    states = np.asarray([STATE_ORDER[int(i)] for i in state_indices], dtype=np.int8)
    pairs = np.asarray([_EDGES[int(edge)][2] for edge in edges], dtype=np.int8)
    return JointViterbiResult(
        state_metrics=metrics,
        survivor_edge_ids=survivors,
        decoded_edge_ids=edges,
        state_path=states,
        information_pairs=pairs,
        final_state=STATE_ORDER[final_index],
        final_metric=float(metrics[-1, final_index]),
    )
