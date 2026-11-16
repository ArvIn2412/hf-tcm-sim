"""Independent REPRO-01 Encoder A implementation and transition trace."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.source_bits import immutable_int8

State = tuple[int, int]
TerminationPolicy = Literal["none", "zero_tail_2"]
STATE_ORDER: tuple[State, ...] = ((0, 0), (1, 0), (0, 1), (1, 1))
INPUT_ORDER: tuple[tuple[int, int], ...] = ((0, 0), (0, 1), (1, 0), (1, 1))
EDGE_ORDER_ID = "state_order_00_10_01_11_input_binary_00_01_10_11_v1"


def _state(value: Iterable[int]) -> State:
    try:
        pair = tuple(value)
    except TypeError as exc:
        raise ValueError("initial_state must contain exactly two binary integers") from exc
    if len(pair) != 2 or any(type(bit) is not int or bit not in (0, 1) for bit in pair):
        raise ValueError("initial_state must contain exactly two binary integers")
    return pair[0], pair[1]


def _input_pairs(values: object) -> NDArray[np.int8]:
    try:
        array = np.asarray(values)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("input_pairs must be a finite integer array with shape (F,2)") from exc
    if array.dtype.kind not in "iu" or array.ndim != 2 or array.shape[1:] != (2,):
        raise ValueError("input_pairs must be an integer array with shape (F,2)")
    if array.shape[0] < 1:
        raise ValueError("input_pairs must be nonempty")
    if np.any(array < 0) or np.any(array > 1):
        raise ValueError("input_pairs may contain only 0 and 1")
    return np.asarray(array, dtype=np.int8, order="C")


def _transition(state: State, pair: tuple[int, int]) -> tuple[tuple[int, int, int], State]:
    previous_1, previous_2 = state
    u0, u1 = pair
    coded = (u0, u1 ^ previous_2, previous_1)
    return coded, (u1, previous_1)


def _edge_id(state: State, pair: tuple[int, int]) -> int:
    return STATE_ORDER.index(state) * 4 + INPUT_ORDER.index(pair)


def transition_table() -> tuple[
    tuple[int, State, tuple[int, int], tuple[int, int, int], State], ...
]:
    """Return the complete immutable edge table in the versioned REPRO order."""
    rows = []
    for state in STATE_ORDER:
        for pair in INPUT_ORDER:
            output, next_state = _transition(state, pair)
            rows.append((_edge_id(state, pair), state, pair, output, next_state))
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class EncoderResult:
    payload_input_pairs: NDArray[np.int8]
    input_pairs: NDArray[np.int8]
    coded_triples: NDArray[np.int8]
    pre_states: NDArray[np.int8]
    post_states: NDArray[np.int8]
    state_history: NDArray[np.int8]
    edge_ids: NDArray[np.int16]
    initial_state: State
    final_state: State
    termination_policy: str
    termination_metadata: dict[str, Any]


def encode(
    input_pairs: object,
    *,
    initial_state: Iterable[int] = (0, 0),
    termination_policy: TerminationPolicy = "none",
) -> EncoderResult:
    """Encode input pairs; the only tail policy appends two explicit zero pairs."""
    payload = _input_pairs(input_pairs)
    start = _state(initial_state)
    if termination_policy not in ("none", "zero_tail_2"):
        raise ValueError("termination_policy must be 'none' or 'zero_tail_2'")
    tail_count = 2 if termination_policy == "zero_tail_2" else 0
    if tail_count:
        complete_pairs = np.concatenate((payload, np.zeros((tail_count, 2), dtype=np.int8)))
    else:
        complete_pairs = payload.copy()

    count = len(complete_pairs)
    outputs = np.empty((count, 3), dtype=np.int8)
    pre_states = np.empty((count, 2), dtype=np.int8)
    post_states = np.empty((count, 2), dtype=np.int8)
    edge_ids = np.empty(count, dtype=np.int16)
    state = start
    for index, pair_array in enumerate(complete_pairs):
        pair = int(pair_array[0]), int(pair_array[1])
        pre_states[index] = state
        outputs[index], state = _transition(state, pair)
        post_states[index] = state
        edge_ids[index] = _edge_id(tuple(pre_states[index].tolist()), pair)
    history = np.concatenate((np.asarray([start], dtype=np.int8), post_states), axis=0)
    termination_metadata = MappingProxyType(
        {
            "policy": termination_policy,
            "tail_steps": tail_count,
            "tail_input_pairs": [[0, 0]] * tail_count,
            "payload_steps": int(len(payload)),
            "encoded_steps": count,
            "state_forced_to_zero": bool(tail_count and state == (0, 0)),
        }
    )
    return EncoderResult(
        payload_input_pairs=immutable_int8(payload),
        input_pairs=immutable_int8(complete_pairs),
        coded_triples=immutable_int8(outputs),
        pre_states=immutable_int8(pre_states),
        post_states=immutable_int8(post_states),
        state_history=immutable_int8(history),
        edge_ids=np.frombuffer(edge_ids.tobytes(), dtype=np.int16),
        initial_state=start,
        final_state=state,
        termination_policy=termination_policy,
        termination_metadata=termination_metadata,
    )
