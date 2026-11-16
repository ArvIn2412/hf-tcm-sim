"""Bounded-memory Viterbi over an arbitrary finite expanded trellis graph."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.augmented_trellis import AugmentedTransition, AugmentedTrellis
from hf_tcm.repro.encoder import transition_table

DecoderMode = Literal["full_frame", "finite_depth"]
_BASE_EDGES = transition_table()
_EDGE_FROM_INPUT = {(state, pair): edge_id for edge_id, state, pair, _coded, _target in _BASE_EDGES}


@dataclass(frozen=True, slots=True)
class ExpandedViterbiConfig:
    decoder_mode: DecoderMode
    traceback_depth: int | None
    expected_symbol_count: int
    forced_tail_input_pairs: tuple[tuple[int, int], ...] = ()
    terminal_node_ids: tuple[int, ...] = ()
    tie_break_policy: str = "canonical_first_edge_then_state_order"
    trace_output_mode: Literal["compact", "full"] = "compact"

    def __post_init__(self) -> None:
        if self.decoder_mode not in {"full_frame", "finite_depth"}:
            raise ValueError("decoder_mode must be full_frame or finite_depth")
        if type(self.expected_symbol_count) is not int or self.expected_symbol_count < 1:
            raise ValueError("expected_symbol_count must be positive")
        if self.decoder_mode == "finite_depth":
            if type(self.traceback_depth) is not int or self.traceback_depth < 1:
                raise ValueError("finite_depth requires a positive traceback_depth")
        elif self.traceback_depth is not None:
            raise ValueError("full_frame requires traceback_depth=None")
        if len(self.forced_tail_input_pairs) > self.expected_symbol_count:
            raise ValueError("forced tail cannot be longer than frame")
        if any(
            not isinstance(pair, tuple)
            or len(pair) != 2
            or any(type(bit) is not int or bit not in (0, 1) for bit in pair)
            for pair in self.forced_tail_input_pairs
        ):
            raise ValueError("forced_tail_input_pairs must be binary pairs")
        if any(type(node_id) is not int or node_id < 0 for node_id in self.terminal_node_ids):
            raise ValueError("terminal_node_ids must be nonnegative integer IDs")
        if len(set(self.terminal_node_ids)) != len(self.terminal_node_ids):
            raise ValueError("terminal_node_ids must be unique")
        if self.tie_break_policy != "canonical_first_edge_then_state_order":
            raise ValueError("unsupported tie_break_policy")
        if self.trace_output_mode not in {"compact", "full"}:
            raise ValueError("trace_output_mode must be compact or full")


@dataclass(frozen=True, slots=True)
class ExpandedDecisionRecord:
    symbol_index: int
    decision_available_at: int
    traceback_depth_used: int
    expanded_edge_id: int
    base_edge_id: int
    input_pair: tuple[int, int]
    encoder_source_state: tuple[int, int]
    encoder_target_state: tuple[int, int]
    source_node_id: int
    target_node_id: int
    source_phase_history: tuple[int, ...]
    target_phase_history: tuple[int, ...]
    decision_policy: str


@dataclass(frozen=True, slots=True)
class ExpandedViterbiResult:
    information_pairs: NDArray[np.int8]
    decoded_information_bits: NDArray[np.int8]
    decoded_edge_ids: NDArray[np.int16]
    decoded_state_path: NDArray[np.int8]
    decision_base_edge_ids: NDArray[np.int16]
    decisions: tuple[ExpandedDecisionRecord, ...]
    terminal_survivor_node_id: int
    survivor_final_metric: float
    state_metrics: NDArray[np.float64]
    survivor_expanded_edge_ids: NDArray[np.int32]
    survivor_buffer_max_rows: int
    decoder_mode: str
    traceback_depth: int | None
    frame_end_policy: str


@dataclass(frozen=True, slots=True)
class _SurvivorRow:
    symbol_index: int
    edge_by_target: NDArray[np.int32]


class ExpandedViterbiDecoder:
    """Streaming Viterbi retaining at most eta target-predecessor rows."""

    def __init__(self, trellis: AugmentedTrellis, config: ExpandedViterbiConfig) -> None:
        if not isinstance(trellis, AugmentedTrellis) or not isinstance(
            config, ExpandedViterbiConfig
        ):
            raise TypeError("trellis/config types are invalid")
        if config.decoder_mode != "finite_depth":
            raise ValueError("streaming decoder requires finite_depth mode")
        if any(node_id >= trellis.state_count for node_id in config.terminal_node_ids):
            raise ValueError("terminal node ID is outside trellis")
        self.trellis = trellis
        self.config = config
        self.depth = int(config.traceback_depth)
        self._metrics = np.full(trellis.state_count, np.inf, dtype=np.float64)
        self._metrics[trellis.initial_node_id] = 0.0
        self._rows: deque[_SurvivorRow] = deque(maxlen=self.depth)
        self._metric_history: list[NDArray[np.float64]] | None = (
            [self._metrics.copy()] if config.trace_output_mode == "full" else None
        )
        self._survivor_history: list[NDArray[np.int32]] | None = (
            [] if config.trace_output_mode == "full" else None
        )
        self._decisions: list[ExpandedDecisionRecord] = []
        self._count = 0
        self._max_rows = 0
        self._closed = False
        self._terminal_node = trellis.initial_node_id
        self._terminal_metric = 0.0

    @property
    def survivor_buffer_rows(self) -> int:
        return len(self._rows)

    @property
    def survivor_buffer_max_rows(self) -> int:
        return self._max_rows

    def consume_metric_row(self, branch_metrics: object) -> ExpandedDecisionRecord | None:
        if self._closed:
            raise RuntimeError("decoder has been flushed")
        if self._count >= self.config.expected_symbol_count:
            raise ValueError("more rows than expected_symbol_count")
        costs = np.asarray(branch_metrics, dtype=np.float64)
        if costs.shape != (self.trellis.edge_count,) or np.any(np.isnan(costs)):
            raise ValueError("branch metrics must have shape (expanded_edge_count,)")
        if np.any(costs < 0) or np.any(np.isneginf(costs)):
            raise ValueError("branch metrics must be nonnegative or positive infinity")
        infinity = np.inf
        next_metrics = np.full(self.trellis.state_count, infinity, dtype=np.float64)
        predecessor = np.full(self.trellis.state_count, -1, dtype=np.int32)
        forced_pair = None
        remaining_tail = len(self.config.forced_tail_input_pairs)
        tail_start = self.config.expected_symbol_count - remaining_tail
        if self._count >= tail_start and remaining_tail:
            forced_pair = self.config.forced_tail_input_pairs[self._count - tail_start]
        for edge in self.trellis.edges:
            if forced_pair is not None and edge.input_pair != forced_pair:
                continue
            prefix = self._metrics[edge.source_node_id]
            branch = costs[edge.expanded_edge_id]
            candidate = prefix + branch
            if candidate < next_metrics[edge.target_node_id]:
                next_metrics[edge.target_node_id] = candidate
                predecessor[edge.target_node_id] = edge.expanded_edge_id
        if not np.any(predecessor >= 0):
            raise ValueError("no finite trellis path satisfies configured constraints")
        self._metrics = next_metrics
        self._rows.append(_SurvivorRow(self._count, predecessor))
        self._max_rows = max(self._max_rows, len(self._rows))
        if self._metric_history is not None:
            self._metric_history.append(next_metrics.copy())
            self._survivor_history.append(predecessor.copy())
        self._count += 1
        if self._count < self.depth:
            return None
        endpoint = int(np.argmin(self._metrics))
        first_index, edge_id = self._traceback(endpoint, self.depth)[0]
        decision = self._make_decision(
            first_index, edge_id, self.depth, self._count - 1, "finite_depth"
        )
        self._decisions.append(decision)
        return decision

    def flush(self) -> tuple[ExpandedDecisionRecord, ...]:
        if self._closed:
            raise RuntimeError("decoder has already been flushed")
        if self._count < 1:
            raise ValueError("cannot flush an empty frame")
        if self._count != self.config.expected_symbol_count:
            raise ValueError("metric row count does not match expected_symbol_count")
        self._closed = True
        endpoints = self.config.terminal_node_ids or tuple(range(self.trellis.state_count))
        endpoint = min(endpoints, key=lambda node: (self._metrics[node], node))
        if not np.isfinite(self._metrics[endpoint]):
            raise ValueError("no reachable terminal node satisfies the configured policy")
        self._terminal_node = endpoint
        self._terminal_metric = float(self._metrics[endpoint])
        depth = min(self._count, self.depth)
        final_path = self._traceback(endpoint, depth)
        previous_index = self._decisions[-1].symbol_index if self._decisions else -1
        new: list[ExpandedDecisionRecord] = []
        for index, edge_id in final_path:
            if index <= previous_index:
                continue
            decision = self._make_decision(
                index, edge_id, self._count - index, self._count - 1, "frame_flush"
            )
            self._decisions.append(decision)
            new.append(decision)
        if [decision.symbol_index for decision in self._decisions] != list(range(self._count)):
            raise RuntimeError("decoder emitted duplicate or missing symbol decisions")
        return tuple(new)

    def result(self) -> ExpandedViterbiResult:
        if not self._closed:
            raise RuntimeError("flush must complete before result")
        pairs = np.asarray([record.input_pair for record in self._decisions], dtype=np.int8)
        local_edges = np.asarray(
            [record.base_edge_id for record in self._decisions], dtype=np.int16
        )
        states = np.empty((self._count + 1, 2), dtype=np.int8)
        edges = np.empty(self._count, dtype=np.int16)
        states[0] = self.trellis.initial_state
        state = self.trellis.initial_state
        for index, pair_row in enumerate(pairs):
            pair = int(pair_row[0]), int(pair_row[1])
            edge_id = _EDGE_FROM_INPUT[(state, pair)]
            edges[index] = edge_id
            state = _BASE_EDGES[edge_id][4]
            states[index + 1] = state
        state_metrics = (
            np.asarray(self._metric_history, dtype=np.float64)
            if self._metric_history is not None
            else np.empty((0, self.trellis.state_count), dtype=np.float64)
        )
        survivors = (
            np.asarray(self._survivor_history, dtype=np.int32)
            if self._survivor_history is not None
            else np.empty((0, self.trellis.state_count), dtype=np.int32)
        )
        return ExpandedViterbiResult(
            information_pairs=pairs,
            decoded_information_bits=pairs.reshape(-1).copy(),
            decoded_edge_ids=edges,
            decoded_state_path=states,
            decision_base_edge_ids=local_edges,
            decisions=tuple(self._decisions),
            terminal_survivor_node_id=self._terminal_node,
            survivor_final_metric=self._terminal_metric,
            state_metrics=state_metrics,
            survivor_expanded_edge_ids=survivors,
            survivor_buffer_max_rows=self._max_rows,
            decoder_mode="finite_depth",
            traceback_depth=self.depth,
            frame_end_policy=(
                "public_terminated_state_flush"
                if self.config.terminal_node_ids
                else "free_best_survivor_flush"
            ),
        )

    def _traceback(self, endpoint: int, depth: int) -> list[tuple[int, int]]:
        if depth < 1 or depth > len(self._rows):
            raise RuntimeError("traceback depth exceeds retained expanded survivor history")
        current = endpoint
        path: list[tuple[int, int]] = []
        for row in reversed(list(self._rows)[-depth:]):
            edge_id = int(row.edge_by_target[current])
            if edge_id < 0:
                raise RuntimeError("expanded survivor traceback is incomplete")
            path.append((row.symbol_index, edge_id))
            current = self.trellis.edges[edge_id].source_node_id
        path.reverse()
        return path

    def _make_decision(
        self, symbol_index: int, edge_id: int, depth: int, available_at: int, policy: str
    ) -> ExpandedDecisionRecord:
        edge: AugmentedTransition = self.trellis.edges[edge_id]
        source = self.trellis.nodes[edge.source_node_id]
        target = self.trellis.nodes[edge.target_node_id]
        return ExpandedDecisionRecord(
            symbol_index=symbol_index,
            decision_available_at=available_at,
            traceback_depth_used=depth,
            expanded_edge_id=edge_id,
            base_edge_id=edge.base_edge_id,
            input_pair=edge.input_pair,
            encoder_source_state=edge.source_state,
            encoder_target_state=edge.target_state,
            source_node_id=source.node_id,
            target_node_id=target.node_id,
            source_phase_history=source.phase_history,
            target_phase_history=target.phase_history,
            decision_policy=policy,
        )


def run_expanded_viterbi(
    branch_metric_rows: object,
    trellis: AugmentedTrellis,
    config: ExpandedViterbiConfig,
) -> ExpandedViterbiResult:
    """Batch convenience wrapper around the bounded-memory row consumer."""
    rows = np.asarray(branch_metric_rows, dtype=np.float64)
    if rows.shape != (config.expected_symbol_count, trellis.edge_count):
        raise ValueError("branch_metric_rows must have shape (expected_symbol_count, edge_count)")
    effective = config
    if config.decoder_mode == "full_frame":
        effective = ExpandedViterbiConfig(
            decoder_mode="finite_depth",
            traceback_depth=len(rows),
            expected_symbol_count=len(rows),
            forced_tail_input_pairs=config.forced_tail_input_pairs,
            terminal_node_ids=config.terminal_node_ids,
            tie_break_policy=config.tie_break_policy,
            trace_output_mode=config.trace_output_mode,
        )
    decoder = ExpandedViterbiDecoder(trellis, effective)
    for row in rows:
        decoder.consume_metric_row(row)
    decoder.flush()
    result = decoder.result()
    if config.decoder_mode == "finite_depth":
        return result
    decisions = tuple(
        ExpandedDecisionRecord(
            symbol_index=record.symbol_index,
            decision_available_at=len(rows) - 1,
            traceback_depth_used=len(rows),
            expanded_edge_id=record.expanded_edge_id,
            base_edge_id=record.base_edge_id,
            input_pair=record.input_pair,
            encoder_source_state=record.encoder_source_state,
            encoder_target_state=record.encoder_target_state,
            source_node_id=record.source_node_id,
            target_node_id=record.target_node_id,
            source_phase_history=record.source_phase_history,
            target_phase_history=record.target_phase_history,
            decision_policy="full_frame_terminal_survivor",
        )
        for record in result.decisions
    )
    return ExpandedViterbiResult(
        information_pairs=result.information_pairs,
        decoded_information_bits=result.decoded_information_bits,
        decoded_edge_ids=result.decoded_edge_ids,
        decoded_state_path=result.decoded_state_path,
        decision_base_edge_ids=result.decision_base_edge_ids,
        decisions=decisions,
        terminal_survivor_node_id=result.terminal_survivor_node_id,
        survivor_final_metric=result.survivor_final_metric,
        state_metrics=result.state_metrics,
        survivor_expanded_edge_ids=result.survivor_expanded_edge_ids,
        survivor_buffer_max_rows=result.survivor_buffer_max_rows,
        decoder_mode="full_frame",
        traceback_depth=None,
        frame_end_policy=result.frame_end_policy,
    )
