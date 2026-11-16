"""Four-state full-frame Viterbi decoder with integer Hamming costs."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.encoder import STATE_ORDER, transition_table

_EDGE_TABLE = transition_table()
_STATE_INDEX = {state: index for index, state in enumerate(STATE_ORDER)}
_INF = np.iinfo(np.int64).max // 4


@dataclass(frozen=True, slots=True)
class ViterbiResult:
    path_metrics: NDArray[np.int64]
    survivor_edge_ids: NDArray[np.int16]
    decoded_edge_ids: NDArray[np.int16]
    state_path: NDArray[np.int8]
    information_pairs: NDArray[np.int8]
    final_state: tuple[int, int]
    final_metric: int


def decode_hamming_viterbi(
    branch_metrics: object,
    *,
    initial_state: tuple[int, int],
    termination_policy: str = "none",
) -> ViterbiResult:
    costs = np.asarray(branch_metrics)
    if (
        costs.ndim != 2
        or costs.shape[1] != 16
        or costs.shape[0] < 1
        or costs.dtype.kind not in "iu"
    ):
        raise ValueError("branch_metrics must be a nonempty integer array of shape (F,16)")
    if np.any(costs < 0) or np.any(costs > 3):
        raise ValueError("Hamming branch costs must be integers from 0 through 3")
    if initial_state not in _STATE_INDEX:
        raise ValueError("initial_state must be a valid Encoder A state")
    if termination_policy not in {"none", "zero_tail_2"}:
        raise ValueError("termination_policy must be none or zero_tail_2")
    count = len(costs)
    if termination_policy == "zero_tail_2" and count < 3:
        raise ValueError("zero_tail_2 requires at least one payload and two tail symbols")
    state_metrics = np.full((count + 1, 4), _INF, dtype=np.int64)
    survivors = np.full((count, 4), -1, dtype=np.int16)
    state_metrics[0, _STATE_INDEX[initial_state]] = 0
    for time in range(count):
        force_zero = termination_policy == "zero_tail_2" and time >= count - 2
        for edge_id, source, pair, _output, target in _EDGE_TABLE:
            if force_zero and pair != (0, 0):
                continue
            src, dst = _STATE_INDEX[source], _STATE_INDEX[target]
            previous = state_metrics[time, src]
            if previous >= _INF:
                continue
            candidate = previous + int(costs[time, edge_id])
            # Strict comparison preserves first canonical edge on equal costs.
            if candidate < state_metrics[time + 1, dst]:
                state_metrics[time + 1, dst] = candidate
                survivors[time, dst] = edge_id
    if termination_policy == "zero_tail_2":
        final_index = _STATE_INDEX[(0, 0)]
    else:
        final_index = int(np.argmin(state_metrics[-1]))
    if state_metrics[-1, final_index] >= _INF:
        raise ValueError("no valid trellis path satisfies the decoder constraints")
    decoded_edges = np.empty(count, dtype=np.int16)
    state_indices = np.empty(count + 1, dtype=np.int8)
    state_indices[-1] = final_index
    current = final_index
    for time in range(count - 1, -1, -1):
        edge_id = int(survivors[time, current])
        if edge_id < 0:
            raise RuntimeError("survivor traceback is incomplete")
        decoded_edges[time] = edge_id
        current = _STATE_INDEX[_EDGE_TABLE[edge_id][1]]
        state_indices[time] = current
    if current != _STATE_INDEX[initial_state]:
        raise RuntimeError("traceback did not return to the configured initial state")
    pairs = np.asarray([_EDGE_TABLE[int(edge_id)][2] for edge_id in decoded_edges], dtype=np.int8)
    states = np.asarray([STATE_ORDER[int(index)] for index in state_indices], dtype=np.int8)
    return ViterbiResult(
        path_metrics=state_metrics,
        survivor_edge_ids=survivors,
        decoded_edge_ids=decoded_edges,
        state_path=states,
        information_pairs=pairs,
        final_state=STATE_ORDER[final_index],
        final_metric=int(state_metrics[-1, final_index]),
    )
