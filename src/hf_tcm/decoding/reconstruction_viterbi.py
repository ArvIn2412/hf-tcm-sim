"""Conditional full-trellis Viterbi over frozen reconstruction branch costs.

This is an isolated project decoder. It does not calculate candidate metrics,
update an estimator/posterior, or claim a paper-exact joint receiver.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.encoder import INITIAL_STATE, State
from hf_tcm.coding.hypotheses import HYPOTHESES, Hypothesis
from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.coding.trellis import STATES

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
SequenceMode = Literal["new_independent_sequence", "continuation"]
HYPOTHESIS_COUNT = 16
STATE_COUNT = 4


def _immutable_array(values: NDArray, *, dtype: np.dtype) -> NDArray:
    owned = np.array(values, dtype=dtype, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=dtype).reshape(owned.shape)


def _validated_costs(candidate_metrics: ArrayLike) -> FloatArray:
    try:
        raw = np.asarray(candidate_metrics)
        if raw.dtype.kind not in "iuf":
            raise ValueError("candidate_metrics must contain real numeric branch costs")
        metrics = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("candidate_metrics must be a finite real matrix") from exc
    if metrics.ndim != 2 or metrics.shape[1:] != (HYPOTHESIS_COUNT,) or metrics.shape[0] < 1:
        raise ValueError("candidate_metrics must have shape (F, 16) with F >= 1")
    if not np.all(np.isfinite(metrics)):
        raise ValueError("candidate_metrics must contain only finite branch costs")
    if np.any(metrics < 0.0):
        raise ValueError("candidate_metrics must contain non-negative branch costs")
    return np.array(metrics, dtype=np.float64, order="C", copy=True)


def _validated_hypotheses(hypotheses: Sequence[Hypothesis]) -> tuple[Hypothesis, ...]:
    try:
        order = tuple(hypotheses)
    except TypeError as exc:
        raise ValueError("hypotheses must use the immutable canonical HYPOTHESES ordering") from exc
    if order != HYPOTHESES or tuple(h.hypothesis_id for h in order) != tuple(range(16)):
        raise ValueError("hypotheses must use the canonical HYPOTHESES ordering")
    return order


def _validated_labels(values: object, *, name: str, length: int) -> tuple[int, ...]:
    try:
        labels_array = np.asarray(values)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a one-dimensional sequence of integer labels") from exc
    if (
        labels_array.ndim != 1
        or labels_array.shape != (length,)
        or labels_array.dtype.kind not in "iu"
    ):
        raise ValueError(f"{name} must contain exactly F={length} integer labels (length mismatch)")
    labels = tuple(int(value) for value in labels_array)
    if any(label < 0 for label in labels):
        raise ValueError(f"{name} must contain non-negative labels")
    if any(right != left + 1 for left, right in zip(labels, labels[1:])):
        raise ValueError(f"{name} must be consecutive and increasing")
    return labels


def _validated_initial_state(initial_state: State) -> State:
    if (
        not isinstance(initial_state, Sequence)
        or isinstance(initial_state, (str, bytes))
        or len(initial_state) != 2
        or any(type(bit) is not int or bit not in (0, 1) for bit in initial_state)
    ):
        raise ValueError("initial_state must be the accepted independent state (0, 0)")
    if tuple(initial_state) != INITIAL_STATE:
        raise ValueError("initial_state must be the accepted independent state (0, 0)")
    return INITIAL_STATE


@dataclass(frozen=True, slots=True)
class ReconstructionViterbiResult:
    """Immutable traceback and diagnostics for one independent sequence.

    ``input_pairs`` has shape ``(F, 2)`` and ``decoded_bits`` shape ``(2F,)``.
    ``survivor_metrics`` and ``predecessor_hypothesis_ids`` have shape
    ``(F, 4)``; state columns follow M1 ``STATES`` and unreachable predecessor
    entries are ``-1``. Edge, absolute-symbol, and estimator-time labels are
    returned separately and are never inferred from each other.
    """

    best_path_metric: float
    initial_state: State
    final_state: State
    hypothesis_ids: tuple[int, ...]
    hypothesis_order: tuple[int, ...]
    sequence_mode: Literal["new_independent_sequence"]
    profile: Literal["reconstructed_offline"]
    input_pairs: NDArray[np.int8]
    decoded_bits: NDArray[np.int8]
    edge_indices: tuple[int, ...]
    symbol_indices: tuple[int, ...]
    estimator_time_indices: tuple[int, ...]
    state_path: tuple[State, ...]
    survivor_metrics: FloatArray
    predecessor_hypothesis_ids: IntArray


def decode_reconstruction_viterbi(
    candidate_metrics: ArrayLike,
    *,
    hypotheses: Sequence[Hypothesis],
    initial_state: State,
    sequence_mode: SequenceMode,
    profile: str,
    edge_indices: object,
    symbol_indices: object,
    estimator_time_indices: object,
) -> ReconstructionViterbiResult:
    """Minimize frozen B4b costs over all structurally valid M1 edge paths.

    The matrix columns must be in canonical ``HYPOTHESES`` order. The
    independent sequence always starts at ``(0,0)``; continuation from an
    arbitrary memory state is intentionally rejected. Every label sequence
    is an explicit, consecutive caller-supplied axis. Absolute symbol labels
    and estimator time labels need not have the same origin or value.

    Survivor ties use exact floating-point equality and the lowest canonical
    hypothesis ID. Final-state ties use the first state in M1 ``STATES``.
    The final state is otherwise free; no tail bits or forced termination are
    added. This minimizes only the additive objective formed from this frozen
    conditional cost matrix.
    """
    costs = _validated_costs(candidate_metrics)
    count = costs.shape[0]
    if sequence_mode != "new_independent_sequence":
        raise ValueError(
            "continuation is unsupported; decode one explicit new_independent_sequence at a time"
        )
    if profile != "reconstructed_offline":
        raise ValueError("profile must be 'reconstructed_offline'")
    canonical_hypotheses = _validated_hypotheses(hypotheses)
    start = _validated_initial_state(initial_state)
    edge_labels = _validated_labels(edge_indices, name="edge_indices", length=count)
    symbols = _validated_labels(symbol_indices, name="symbol_indices", length=count)
    estimator_times = _validated_labels(
        estimator_time_indices, name="estimator_time_indices", length=count
    )

    state_positions = {state: index for index, state in enumerate(STATES)}
    previous = np.full(STATE_COUNT, math.inf, dtype=np.float64)
    previous[state_positions[start]] = 0.0
    survivor_metrics = np.full((count, STATE_COUNT), math.inf, dtype=np.float64)
    predecessor_ids = np.full((count, STATE_COUNT), -1, dtype=np.int64)

    for time_index in range(count):
        current = np.full(STATE_COUNT, math.inf, dtype=np.float64)
        for hypothesis in canonical_hypotheses:
            source_index = state_positions[hypothesis.current_state]
            previous_cost = float(previous[source_index])
            if math.isinf(previous_cost):
                continue
            branch_cost = float(costs[time_index, hypothesis.hypothesis_id])
            candidate = previous_cost + branch_cost
            if not math.isfinite(candidate):
                raise ValueError("cumulative path cost overflowed floating-point range")
            destination_index = state_positions[hypothesis.next_state]
            incumbent = float(current[destination_index])
            incumbent_id = int(predecessor_ids[time_index, destination_index])
            if candidate < incumbent or (
                candidate == incumbent
                and (incumbent_id < 0 or hypothesis.hypothesis_id < incumbent_id)
            ):
                current[destination_index] = candidate
                predecessor_ids[time_index, destination_index] = hypothesis.hypothesis_id
        survivor_metrics[time_index] = current
        previous = current

    final_state_index = min(
        (index for index, value in enumerate(previous) if math.isfinite(float(value))),
        key=lambda index: (float(previous[index]), index),
    )
    best_metric = float(previous[final_state_index])

    selected_ids = [-1] * count
    state_index = final_state_index
    for time_index in range(count - 1, -1, -1):
        hypothesis_id = int(predecessor_ids[time_index, state_index])
        if hypothesis_id < 0:
            raise RuntimeError("traceback reached a state without a survivor edge")
        hypothesis = canonical_hypotheses[hypothesis_id]
        if state_positions[hypothesis.next_state] != state_index:
            raise RuntimeError("survivor edge does not enter the traceback state")
        selected_ids[time_index] = hypothesis_id
        state_index = state_positions[hypothesis.current_state]
    if state_index != state_positions[start]:
        raise RuntimeError("traceback did not return to the accepted initial state")

    selected_path = validate_hypothesis_edge_path(selected_ids, initial_state=start)
    final_state = selected_path[-1].next_state
    if state_positions[final_state] != final_state_index:
        raise RuntimeError("traceback final state disagrees with the selected survivor")

    input_pairs = np.asarray([edge.input_bits for edge in selected_path], dtype=np.int8)
    decoded_bits = input_pairs.reshape(-1)
    recomputed_metric = 0.0
    for time_index, hypothesis_id in enumerate(selected_ids):
        recomputed_metric += float(costs[time_index, hypothesis_id])
        if not math.isfinite(recomputed_metric):
            raise ValueError("traceback cumulative path cost overflowed floating-point range")
    if recomputed_metric != best_metric:
        raise RuntimeError("traceback cost does not equal the selected final survivor metric")

    states: tuple[State, ...] = (start, *(edge.next_state for edge in selected_path))
    return ReconstructionViterbiResult(
        best_path_metric=best_metric,
        initial_state=start,
        final_state=final_state,
        hypothesis_ids=tuple(selected_ids),
        hypothesis_order=tuple(h.hypothesis_id for h in canonical_hypotheses),
        sequence_mode="new_independent_sequence",
        profile="reconstructed_offline",
        input_pairs=_immutable_array(input_pairs, dtype=np.dtype(np.int8)),
        decoded_bits=_immutable_array(decoded_bits, dtype=np.dtype(np.int8)),
        edge_indices=edge_labels,
        symbol_indices=symbols,
        estimator_time_indices=estimator_times,
        state_path=states,
        survivor_metrics=_immutable_array(survivor_metrics, dtype=np.dtype(np.float64)),
        predecessor_hypothesis_ids=_immutable_array(predecessor_ids, dtype=np.dtype(np.int64)),
    )
