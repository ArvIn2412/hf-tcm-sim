"""Bounded-memory finite-depth and full-frame Viterbi for Encoder A."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.encoder import STATE_ORDER, TerminationPolicy, transition_table

DecoderMode = Literal["full_frame", "finite_depth"]
FinalStatePolicy = Literal["auto", "free", "known_terminated"]
TraceOutputMode = Literal["compact", "full"]
_EDGES = transition_table()
_STATE_INDEX = {state: i for i, state in enumerate(STATE_ORDER)}
_EDGE_BY_STATE_INPUT = {(row[1], row[2]): row[0] for row in _EDGES}


@dataclass(frozen=True, slots=True)
class ViterbiConfig:
    initial_state: tuple[int, int]
    traceback_depth: int | None = None
    decoder_mode: DecoderMode = "finite_depth"
    expected_symbol_count: int | None = None
    termination_policy: TerminationPolicy = "none"
    final_state_policy: FinalStatePolicy = "auto"
    tie_break_policy: str = "canonical_first_edge_then_state_order"
    trace_output_mode: TraceOutputMode = "compact"

    def __post_init__(self) -> None:
        if self.initial_state not in _STATE_INDEX:
            raise ValueError("initial_state must be a valid Encoder A state")
        if self.decoder_mode not in {"full_frame", "finite_depth"}:
            raise ValueError("decoder_mode must be full_frame or finite_depth")
        if self.decoder_mode == "finite_depth" and (
            type(self.traceback_depth) is not int or self.traceback_depth < 1
        ):
            raise ValueError("finite_depth mode requires a positive traceback_depth")
        if self.traceback_depth is not None and (
            type(self.traceback_depth) is not int or self.traceback_depth < 1
        ):
            raise ValueError("traceback_depth must be a positive integer or None")
        if self.expected_symbol_count is not None and (
            type(self.expected_symbol_count) is not int or self.expected_symbol_count < 1
        ):
            raise ValueError("expected_symbol_count must be a positive integer or None")
        if self.decoder_mode == "full_frame" and self.expected_symbol_count is None:
            raise ValueError("full_frame mode requires expected_symbol_count")
        if self.termination_policy not in {"none", "zero_tail_2"}:
            raise ValueError("unsupported termination_policy")
        if self.termination_policy == "zero_tail_2" and (
            self.expected_symbol_count is None or self.expected_symbol_count < 3
        ):
            raise ValueError("zero_tail_2 requires at least 3 expected symbols")
        if self.final_state_policy not in {"auto", "free", "known_terminated"}:
            raise ValueError("unsupported final_state_policy")
        if (
            self.final_state_policy == "known_terminated"
            and self.termination_policy != "zero_tail_2"
        ):
            raise ValueError("known_terminated requires termination_policy='zero_tail_2'")
        if self.tie_break_policy != "canonical_first_edge_then_state_order":
            raise ValueError("unsupported tie_break_policy")
        if self.trace_output_mode not in {"compact", "full"}:
            raise ValueError("trace_output_mode must be compact or full")


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    symbol_index: int
    decision_available_at: int
    traceback_depth_used: int
    edge_id: int
    input_pair: tuple[int, int]
    source_state: tuple[int, int]
    target_state: tuple[int, int]
    decoder_mode: str
    decision_policy: str


@dataclass(frozen=True, slots=True)
class ViterbiResult:
    decoded_edge_ids: NDArray[np.int16]
    information_pairs: NDArray[np.int8]
    state_path: NDArray[np.int8]
    final_state: tuple[int, int]
    survivor_final_state: tuple[int, int]
    final_metric: int | float
    decisions: tuple[DecisionRecord, ...]
    decoder_mode: str
    traceback_depth: int | None
    state_metrics: NDArray[np.generic]
    survivor_edge_ids: NDArray[np.int16]
    survivor_buffer_max_rows: int
    frame_end_policy: str

    @property
    def path_metrics(self) -> NDArray[np.generic]:
        """Compatibility name used by the REPRO-04 result adapter."""
        return self.state_metrics


@dataclass(frozen=True, slots=True)
class _SurvivorRow:
    symbol_index: int
    edge_by_target: NDArray[np.int16]


class FiniteDepthViterbiDecoder:
    """Online decoder storing at most ``traceback_depth`` survivor rows."""

    def __init__(self, config: ViterbiConfig) -> None:
        if not isinstance(config, ViterbiConfig):
            raise TypeError("config must be ViterbiConfig")
        if config.decoder_mode != "finite_depth":
            raise ValueError("streaming decoder requires decoder_mode='finite_depth'")
        self.config = config
        self._depth = int(config.traceback_depth)
        self._integer_metrics: bool | None = None
        self._metrics = np.full(4, np.inf, dtype=np.float64)
        self._metrics[_STATE_INDEX[config.initial_state]] = 0.0
        self._survivors: deque[_SurvivorRow] = deque(maxlen=self._depth)
        self._metric_history: list[NDArray[np.generic]] | None = (
            [self._metrics.copy()] if config.trace_output_mode == "full" else None
        )
        self._survivor_history: list[NDArray[np.int16]] | None = (
            [] if config.trace_output_mode == "full" else None
        )
        self._decisions: list[DecisionRecord] = []
        self._count = 0
        self._closed = False
        self._max_rows = 0
        self._final_metric: int | float = 0
        self._final_state = config.initial_state

    @property
    def consumed_rows(self) -> int:
        return self._count

    @property
    def survivor_buffer_rows(self) -> int:
        return len(self._survivors)

    @property
    def survivor_buffer_max_rows(self) -> int:
        return self._max_rows

    def consume_metric_row(self, branch_metrics: object) -> DecisionRecord | None:
        if self._closed:
            raise RuntimeError("decoder has already been flushed")
        if (
            self.config.expected_symbol_count is not None
            and self._count >= self.config.expected_symbol_count
        ):
            raise ValueError("more metric rows supplied than expected_symbol_count")
        row = np.asarray(branch_metrics)
        if row.shape != (16,) or row.dtype.kind not in "iuf":
            raise ValueError("each branch metric row must be a numeric vector of shape (16,)")
        if not np.all(np.isfinite(row)) or np.any(row < 0):
            raise ValueError("branch metrics must be finite and nonnegative")
        is_integer = row.dtype.kind in "iu"
        if self._integer_metrics is None:
            self._integer_metrics = is_integer
            if is_integer:
                self._metrics = np.full(4, np.iinfo(np.int64).max // 4, dtype=np.int64)
                self._metrics[_STATE_INDEX[self.config.initial_state]] = 0
                if self._metric_history is not None:
                    self._metric_history[0] = self._metrics.copy()
        elif self._integer_metrics != is_integer:
            raise ValueError("branch metric dtype must not change within a frame")

        infinity = np.iinfo(np.int64).max // 4 if is_integer else np.inf
        next_metrics = np.full(4, infinity, dtype=np.int64 if is_integer else np.float64)
        edge_by_target = np.full(4, -1, dtype=np.int16)
        zero_tail = (
            self.config.termination_policy == "zero_tail_2"
            and self.config.expected_symbol_count is not None
            and self._count >= self.config.expected_symbol_count - 2
        )
        for edge_id, source, pair, _output, target in _EDGES:
            if zero_tail and pair != (0, 0):
                continue
            source_index, target_index = _STATE_INDEX[source], _STATE_INDEX[target]
            prefix = self._metrics[source_index]
            if prefix >= infinity:
                continue
            candidate = prefix + (int(row[edge_id]) if is_integer else float(row[edge_id]))
            if candidate < next_metrics[target_index]:
                next_metrics[target_index] = candidate
                edge_by_target[target_index] = edge_id
        if np.all(edge_by_target < 0):
            raise ValueError("no valid path satisfies configured trellis constraints")
        self._metrics = next_metrics
        self._survivors.append(
            _SurvivorRow(self._count, np.frombuffer(edge_by_target.tobytes(), dtype=np.int16))
        )
        self._max_rows = max(self._max_rows, len(self._survivors))
        if self._metric_history is not None:
            self._metric_history.append(next_metrics.copy())
            self._survivor_history.append(edge_by_target.copy())
        self._count += 1

        if self._count < self._depth:
            return None
        endpoint = self._select_endpoint(final=False)
        path = self._traceback(endpoint, self._depth)
        first_index, first_edge = path[0]
        record = self._record(first_index, first_edge, self._depth, self._count - 1, "finite_depth")
        self._decisions.append(record)
        return record

    def flush(self) -> tuple[DecisionRecord, ...]:
        if self._closed:
            raise RuntimeError("decoder has already been flushed")
        if self._count < 1:
            raise ValueError("cannot flush an empty frame")
        if (
            self.config.expected_symbol_count is not None
            and self._count != self.config.expected_symbol_count
        ):
            raise ValueError("consumed metric rows do not match expected_symbol_count")
        self._closed = True
        final_endpoint = self._select_endpoint(final=True)
        self._final_state = STATE_ORDER[final_endpoint]
        self._final_metric = self._metrics[final_endpoint].item()
        actual_depth = min(self._count, self._depth)
        final_path = self._traceback(final_endpoint, actual_depth)
        last_emitted = self._decisions[-1].symbol_index if self._decisions else -1
        newly_finalized: list[DecisionRecord] = []
        for symbol_index, edge_id in final_path:
            if symbol_index <= last_emitted:
                continue
            depth_used = self._count - symbol_index
            record = self._record(
                symbol_index,
                edge_id,
                depth_used,
                self._count - 1,
                "frame_flush",
            )
            self._decisions.append(record)
            newly_finalized.append(record)
        if len(self._decisions) != self._count or [d.symbol_index for d in self._decisions] != list(
            range(self._count)
        ):
            raise RuntimeError("finite-depth decoder emitted missing or duplicate decisions")

        pairs = np.asarray([d.input_pair for d in self._decisions], dtype=np.int8)
        # Per-symbol survivor edges are decisions from overlapping survivor paths and may not
        # join at boundaries. Reconstruct the valid Encoder A path from the emitted input pairs.
        states = np.empty((self._count + 1, 2), dtype=np.int8)
        states[0] = self.config.initial_state
        edges = np.empty(self._count, dtype=np.int16)
        state = self.config.initial_state
        for index, pair_array in enumerate(pairs):
            pair = int(pair_array[0]), int(pair_array[1])
            edges[index] = _EDGE_BY_STATE_INPUT[(state, pair)]
            state = (pair[1], state[0])
            states[index + 1] = state
        metric_dtype = np.int64 if self._integer_metrics else np.float64
        metrics = (
            np.asarray(self._metric_history, dtype=metric_dtype)
            if self._metric_history is not None
            else np.empty((0, 4), dtype=metric_dtype)
        )
        survivors = (
            np.asarray(self._survivor_history, dtype=np.int16)
            if self._survivor_history is not None
            else np.empty((0, 4), dtype=np.int16)
        )
        self._final_state = tuple(int(x) for x in states[-1])
        frame_policy = (
            "zero_tail_2_known_final_state"
            if self.config.termination_policy == "zero_tail_2"
            else "free_final_state_best_survivor_flush"
        )
        self._result = ViterbiResult(
            decoded_edge_ids=edges,
            information_pairs=pairs,
            state_path=states,
            final_state=tuple(int(x) for x in states[-1]),
            survivor_final_state=self._final_state,
            final_metric=self._final_metric,
            decisions=tuple(self._decisions),
            decoder_mode="finite_depth",
            traceback_depth=self._depth,
            state_metrics=metrics,
            survivor_edge_ids=survivors,
            survivor_buffer_max_rows=self._max_rows,
            frame_end_policy=frame_policy,
        )
        return tuple(newly_finalized)

    def result(self) -> ViterbiResult:
        if not self._closed or not hasattr(self, "_result"):
            raise RuntimeError("result is available only after flush")
        return self._result

    def _select_endpoint(self, *, final: bool) -> int:
        known_final = self.config.final_state_policy == "known_terminated" or (
            self.config.final_state_policy == "auto"
            and self.config.termination_policy == "zero_tail_2"
        )
        if final and known_final:
            endpoint = _STATE_INDEX[(0, 0)]
            if not np.isfinite(self._metrics[endpoint]):
                raise ValueError("known terminating state is unreachable")
            return endpoint
        return int(np.argmin(self._metrics))

    def _traceback(self, endpoint: int, depth: int) -> list[tuple[int, int]]:
        if depth < 1 or depth > len(self._survivors):
            raise RuntimeError("survivor traceback depth exceeds buffered history")
        rows = list(self._survivors)[-depth:]
        current = endpoint
        reversed_path: list[tuple[int, int]] = []
        for survivor_row in reversed(rows):
            edge_id = int(survivor_row.edge_by_target[current])
            if edge_id < 0:
                raise RuntimeError("Viterbi survivor traceback is incomplete")
            reversed_path.append((survivor_row.symbol_index, edge_id))
            current = _STATE_INDEX[_EDGES[edge_id][1]]
        reversed_path.reverse()
        return reversed_path

    def _record(
        self, symbol_index: int, edge_id: int, depth: int, available_at: int, policy: str
    ) -> DecisionRecord:
        _edge_id, source, pair, _coded, target = _EDGES[edge_id]
        return DecisionRecord(
            symbol_index=symbol_index,
            decision_available_at=available_at,
            traceback_depth_used=depth,
            edge_id=edge_id,
            input_pair=pair,
            source_state=source,
            target_state=target,
            decoder_mode="finite_depth",
            decision_policy=policy,
        )


def run_viterbi(branch_metric_rows: object, config: ViterbiConfig) -> ViterbiResult:
    """Batch wrapper for the same row-by-row engine used by streaming callers."""
    rows = np.asarray(branch_metric_rows)
    if rows.ndim != 2 or rows.shape[1] != 16 or rows.shape[0] < 1:
        raise ValueError("branch_metric_rows must have shape (F,16), F >= 1")
    if config.expected_symbol_count is not None and len(rows) != config.expected_symbol_count:
        raise ValueError("branch row count does not match expected_symbol_count")
    effective = config
    if config.decoder_mode == "full_frame":
        effective = ViterbiConfig(
            initial_state=config.initial_state,
            traceback_depth=len(rows),
            decoder_mode="finite_depth",
            expected_symbol_count=len(rows),
            termination_policy=config.termination_policy,
            final_state_policy=config.final_state_policy,
            tie_break_policy=config.tie_break_policy,
            trace_output_mode=config.trace_output_mode,
        )
    decoder = FiniteDepthViterbiDecoder(effective)
    for row in rows:
        decoder.consume_metric_row(row)
    decoder.flush()
    result = decoder.result()
    if config.decoder_mode == "full_frame":
        return ViterbiResult(
            decoded_edge_ids=result.decoded_edge_ids,
            information_pairs=result.information_pairs,
            state_path=result.state_path,
            final_state=result.final_state,
            survivor_final_state=result.survivor_final_state,
            final_metric=result.final_metric,
            decisions=tuple(
                DecisionRecord(
                    symbol_index=d.symbol_index,
                    decision_available_at=len(rows) - 1,
                    traceback_depth_used=len(rows),
                    edge_id=d.edge_id,
                    input_pair=d.input_pair,
                    source_state=d.source_state,
                    target_state=d.target_state,
                    decoder_mode="full_frame",
                    decision_policy="full_frame_terminal_survivor",
                )
                for d in result.decisions
            ),
            decoder_mode="full_frame",
            traceback_depth=None,
            state_metrics=result.state_metrics,
            survivor_edge_ids=result.survivor_edge_ids,
            survivor_buffer_max_rows=result.survivor_buffer_max_rows,
            frame_end_policy=result.frame_end_policy,
        )
    return result
