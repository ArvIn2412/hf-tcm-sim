"""Shared pilot frontend and isolated Euclidean/Hamming TCM metric controls.

This module is an experimental adapter. It does not replace the established
Joint, B0, or B1 receiver implementations.
"""

from __future__ import annotations

import hashlib
import math
from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.encoder import STATE_ORDER, transition_table
from hf_tcm.repro.finite_viterbi import DecisionRecord, ViterbiResult

_EDGES = transition_table()
_STATE_INDEX = {state: index for index, state in enumerate(STATE_ORDER)}
_EDGE_BY_STATE_INPUT = {(row[1], row[2]): row[0] for row in _EDGES}
_EDGE_OUTPUTS = np.asarray([row[3] for row in _EDGES], dtype=np.int8)
_EDGE_PHASES = np.asarray(
    [4 * row[3][0] + 2 * row[3][1] + row[3][2] for row in _EDGES], dtype=np.int8
)


def _immutable(values: object, dtype: np.dtype[Any]) -> NDArray[Any]:
    owned = np.array(values, dtype=dtype, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=dtype).reshape(owned.shape)


def _positive_finite(value: object, name: str, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError(
            f"{name} must be finite and {'non-negative' if allow_zero else 'positive'}"
        )
    result = float(value)
    if not math.isfinite(result) or (result < 0 if allow_zero else result <= 0):
        raise ValueError(
            f"{name} must be finite and {'non-negative' if allow_zero else 'positive'}"
        )
    return result


def _phase_symbols(amplitude: float, phase_offset_rad: float = 0.0) -> NDArray[np.complex128]:
    amplitude = _positive_finite(amplitude, "amplitude")
    if not math.isfinite(float(phase_offset_rad)):
        raise ValueError("phase_offset_rad must be finite")
    phases = float(phase_offset_rad) + np.arange(8, dtype=np.float64) * (math.pi / 4.0)
    return np.asarray(amplitude * np.exp(1j * phases), dtype=np.complex128)


@dataclass(frozen=True, slots=True)
class PilotSchedule:
    """Public known-input schedule; unknown payload positions never contain bits."""

    frame_symbols: int
    pilot_mask: NDArray[np.bool_]
    payload_mask: NDArray[np.bool_]
    pilot_input_pairs: NDArray[np.int8]
    phase_known_mask: NDArray[np.bool_]
    known_phase_indices: NDArray[np.int8]
    initial_state: tuple[int, int]
    preamble_symbols: int
    pilot_period: int
    pilot_burst_symbols: int
    sha256: str


def build_pilot_schedule(
    *,
    frame_symbols: int,
    preamble_symbols: int = 4,
    pilot_period: int = 32,
    pilot_burst_symbols: int = 4,
    initial_state: tuple[int, int] = (0, 0),
) -> PilotSchedule:
    """Build deterministic pilot pairs and independently knowable coded phases.

    Interior pilot bursts need two known input pairs to remove dependence on
    the preceding payload encoder state. Those first two output phases are
    deliberately unavailable to the channel estimator.
    """
    if type(frame_symbols) is not int or frame_symbols < 4:
        raise ValueError("frame_symbols must be an integer >= 4")
    if type(preamble_symbols) is not int or preamble_symbols < 1:
        raise ValueError("preamble_symbols must be a positive integer")
    if type(pilot_period) is not int or pilot_period < 1:
        raise ValueError("pilot_period must be a positive integer")
    if type(pilot_burst_symbols) is not int or pilot_burst_symbols < 3:
        raise ValueError("pilot_burst_symbols must be at least 3 to flush encoder state")
    if (
        not isinstance(initial_state, tuple)
        or len(initial_state) != 2
        or any(type(bit) is not int or bit not in (0, 1) for bit in initial_state)
    ):
        raise ValueError("initial_state must be a pair of binary integers")
    if preamble_symbols >= frame_symbols:
        raise ValueError("preamble must leave at least one payload symbol")

    pilot_mask = np.zeros(frame_symbols, dtype=bool)
    pilot_mask[:preamble_symbols] = True
    for start in range(pilot_period, frame_symbols, pilot_period):
        pilot_mask[start : min(frame_symbols, start + pilot_burst_symbols)] = True
    if np.all(pilot_mask):
        raise ValueError("pilot schedule must leave at least one payload symbol")

    pairs = np.full((frame_symbols, 2), -1, dtype=np.int8)
    pattern = ((0, 0), (0, 1), (1, 1), (1, 0))
    run_position = 0
    in_run = False
    for index, is_pilot in enumerate(pilot_mask):
        if not is_pilot:
            in_run = False
            continue
        if not in_run:
            run_position = 0
            in_run = True
        pairs[index] = pattern[run_position % len(pattern)]
        run_position += 1

    known_phase_mask = np.zeros(frame_symbols, dtype=bool)
    phase_indices = np.full(frame_symbols, -1, dtype=np.int8)
    state: tuple[int | None, int | None] = initial_state
    for index in range(frame_symbols):
        if pilot_mask[index]:
            u0, u1 = (int(value) for value in pairs[index])
            previous_1, previous_2 = state
            if previous_1 is not None and previous_2 is not None:
                coded = (u0, u1 ^ previous_2, previous_1)
                phase_indices[index] = 4 * coded[0] + 2 * coded[1] + coded[2]
                known_phase_mask[index] = True
            state = (u1, previous_1)
        else:
            # The next encoder state is (unknown second input bit, previous_1).
            state = (None, state[0])

    payload_mask = ~pilot_mask
    digest = hashlib.sha256()
    for array in (pilot_mask, payload_mask, pairs, known_phase_mask, phase_indices):
        digest.update(np.ascontiguousarray(array).tobytes())
    digest.update(
        repr(
            (frame_symbols, initial_state, preamble_symbols, pilot_period, pilot_burst_symbols)
        ).encode()
    )
    return PilotSchedule(
        frame_symbols=frame_symbols,
        pilot_mask=_immutable(pilot_mask, np.dtype(np.bool_)),
        payload_mask=_immutable(payload_mask, np.dtype(np.bool_)),
        pilot_input_pairs=_immutable(pairs, np.dtype(np.int8)),
        phase_known_mask=_immutable(known_phase_mask, np.dtype(np.bool_)),
        known_phase_indices=_immutable(phase_indices, np.dtype(np.int8)),
        initial_state=initial_state,
        preamble_symbols=preamble_symbols,
        pilot_period=pilot_period,
        pilot_burst_symbols=pilot_burst_symbols,
        sha256=digest.hexdigest(),
    )


@dataclass(frozen=True, slots=True)
class MetricFrontendResult:
    symbols: NDArray[np.complex128]
    output_noise_variance: NDArray[np.float64]
    valid_symbol_mask: NDArray[np.bool_]
    estimated_composite_gain: NDArray[np.complex128]
    gain_valid_mask: NDArray[np.bool_]
    gain_update_mask: NDArray[np.bool_]
    gain_age_symbols: NDArray[np.int32]
    selected_sample_indices: NDArray[np.int64]
    clean_sample_count_per_symbol: int
    maximum_delay_samples: int
    mode: str
    observation_sha256: str
    frontend_output_sha256: str
    residual_isi_bound: str


def _validate_observation(observation: ReceiverObservation, symbol_count: int) -> None:
    if not isinstance(observation, ReceiverObservation):
        raise TypeError("observation must be ReceiverObservation; evaluator truth is not accepted")
    if type(symbol_count) is not int or symbol_count < 1:
        raise ValueError("symbol_count must be a positive integer")
    if observation.samples_per_symbol != 8:
        raise ValueError("metric isolation supports the eight-sample ZOH profile only")
    if len(observation.received_samples) < symbol_count * 8:
        raise ValueError("observation does not contain all requested symbol samples")


def _frontend_result(
    *,
    symbols: np.ndarray,
    variance: np.ndarray,
    valid: np.ndarray,
    gains: np.ndarray,
    gain_valid: np.ndarray,
    gain_updates: np.ndarray,
    gain_age: np.ndarray,
    sample_indices: np.ndarray,
    clean_count: int,
    maximum_delay: int,
    mode: str,
    observation: ReceiverObservation,
) -> MetricFrontendResult:
    digest = hashlib.sha256()
    for array in (
        symbols,
        variance,
        valid,
        gains,
        gain_valid,
        gain_updates,
        gain_age,
        sample_indices,
    ):
        digest.update(np.ascontiguousarray(array).tobytes())
    digest.update(mode.encode("ascii"))
    digest.update(observation.sha256.encode("ascii"))
    return MetricFrontendResult(
        symbols=_immutable(symbols, np.dtype(np.complex128)),
        output_noise_variance=_immutable(variance, np.dtype(np.float64)),
        valid_symbol_mask=_immutable(valid, np.dtype(np.bool_)),
        estimated_composite_gain=_immutable(gains, np.dtype(np.complex128)),
        gain_valid_mask=_immutable(gain_valid, np.dtype(np.bool_)),
        gain_update_mask=_immutable(gain_updates, np.dtype(np.bool_)),
        gain_age_symbols=_immutable(gain_age, np.dtype(np.int32)),
        selected_sample_indices=_immutable(sample_indices, np.dtype(np.int64)),
        clean_sample_count_per_symbol=clean_count,
        maximum_delay_samples=maximum_delay,
        mode=mode,
        observation_sha256=observation.sha256,
        frontend_output_sha256=digest.hexdigest(),
        residual_isi_bound=(
            "zero_for_integer_delay_zoh_tail" if maximum_delay else "zero_for_single_path_zoh"
        ),
    )


def run_awgn_direct_frontend(
    observation: ReceiverObservation, *, symbol_count: int
) -> MetricFrontendResult:
    """No-equalizer AWGN control: average the eight direct samples per symbol."""
    _validate_observation(observation, symbol_count)
    values = np.asarray(observation.received_samples[: symbol_count * 8]).reshape(symbol_count, 8)
    symbols = values.mean(axis=1)
    sample_indices = np.arange(symbol_count * 8, dtype=np.int64).reshape(symbol_count, 8)
    variance_value = (
        observation.noise_complex_variance / 8
        if observation.noise_complex_variance is not None
        else math.nan
    )
    variance = np.full(symbol_count, variance_value, dtype=np.float64)
    valid = np.ones(symbol_count, dtype=bool)
    gains = np.ones(symbol_count, dtype=np.complex128)
    gain_valid = np.ones(symbol_count, dtype=bool)
    updates = np.zeros(symbol_count, dtype=bool)
    ages = np.zeros(symbol_count, dtype=np.int32)
    return _frontend_result(
        symbols=symbols,
        variance=variance,
        valid=valid,
        gains=gains,
        gain_valid=gain_valid,
        gain_updates=updates,
        gain_age=ages,
        sample_indices=sample_indices,
        clean_count=8,
        maximum_delay=0,
        mode="awgn_direct_control",
        observation=observation,
    )


def run_pilot_frontend(
    observation: ReceiverObservation,
    schedule: PilotSchedule,
    *,
    amplitude: float,
    path_delays_samples: tuple[int, ...],
    assumed_noise_variance: float = 0.0,
    phase_offset_rad: float = 0.0,
    minimum_gain_power: float = 1e-12,
) -> MetricFrontendResult:
    """Causal pilot estimate and common clean-tail combiner for integer-delay ZOH.

    Only public pilot phases and received samples enter this function. Actual
    tap coefficients, transmitted payload, and EvaluationTruth are not accepted.
    """
    _validate_observation(observation, schedule.frame_symbols)
    if not isinstance(schedule, PilotSchedule):
        raise TypeError("schedule must be PilotSchedule")
    if not path_delays_samples or any(
        type(delay) is not int or delay < 0 for delay in path_delays_samples
    ):
        raise ValueError("path_delays_samples must be non-negative integer delays")
    maximum_delay = max(path_delays_samples)
    if maximum_delay >= 8:
        raise ValueError("pilot equalizer requires maximum delay below eight samples")
    amplitude = _positive_finite(amplitude, "amplitude")
    noise_variance = _positive_finite(
        assumed_noise_variance, "assumed_noise_variance", allow_zero=True
    )
    minimum_gain_power = _positive_finite(minimum_gain_power, "minimum_gain_power")
    if not math.isfinite(float(phase_offset_rad)):
        raise ValueError("phase_offset_rad must be finite")

    frame = schedule.frame_symbols
    clean_count = 8 - maximum_delay
    symbols = np.zeros(frame, dtype=np.complex128)
    variances = np.full(frame, np.nan, dtype=np.float64)
    valid = np.zeros(frame, dtype=bool)
    gains = np.zeros(frame, dtype=np.complex128)
    gain_valid = np.zeros(frame, dtype=bool)
    gain_updates = np.zeros(frame, dtype=bool)
    gain_age = np.full(frame, -1, dtype=np.int32)
    sample_indices = np.empty((frame, clean_count), dtype=np.int64)
    received = np.asarray(observation.received_samples, dtype=np.complex128)
    constellation = _phase_symbols(amplitude, phase_offset_rad)
    current_gain = 0j
    has_gain = False
    last_update = -1

    for symbol_index in range(frame):
        start = symbol_index * 8 + maximum_delay
        indices = np.arange(start, start + clean_count, dtype=np.int64)
        if int(indices[-1]) >= len(received):
            raise ValueError("observation is missing the clean portion of a symbol")
        sample_indices[symbol_index] = indices
        tail = received[indices]
        if has_gain:
            denominator = clean_count * abs(current_gain) ** 2
            if denominator >= minimum_gain_power:
                symbols[symbol_index] = (
                    np.vdot(np.full(clean_count, current_gain, dtype=np.complex128), tail)
                    / denominator
                )
                variances[symbol_index] = noise_variance / denominator
                valid[symbol_index] = True
                gains[symbol_index] = current_gain
                gain_valid[symbol_index] = True
                gain_age[symbol_index] = symbol_index - last_update

        if schedule.phase_known_mask[symbol_index]:
            pilot_symbol = constellation[int(schedule.known_phase_indices[symbol_index])]
            estimate = np.vdot(np.full(clean_count, pilot_symbol, dtype=np.complex128), tail) / (
                clean_count * abs(pilot_symbol) ** 2
            )
            if abs(estimate) ** 2 >= minimum_gain_power:
                current_gain = complex(estimate)
                has_gain = True
                last_update = symbol_index
                gain_updates[symbol_index] = True

    if np.any(schedule.payload_mask & ~valid):
        missing = np.flatnonzero(schedule.payload_mask & ~valid)
        raise ValueError(
            "pilot frontend has no valid causal gain estimate for payload symbols "
            f"{missing[:8].tolist()}"
        )
    return _frontend_result(
        symbols=symbols,
        variance=variances,
        valid=valid,
        gains=gains,
        gain_valid=gain_valid,
        gain_updates=gain_updates,
        gain_age=gain_age,
        sample_indices=sample_indices,
        clean_count=clean_count,
        maximum_delay=maximum_delay,
        mode="causal_pilot_composite_gain_clean_tail",
        observation=observation,
    )


def run_oracle_csi_frontend(
    observation: ReceiverObservation,
    schedule: PilotSchedule,
    *,
    amplitude: float,
    path_delays_samples: tuple[int, ...],
    path_coefficients_by_sample: object,
    assumed_noise_variance: float = 0.0,
    minimum_gain_power: float = 1e-12,
) -> MetricFrontendResult:
    """Oracle-only diagnostic combiner using evaluator-provided tap traces.

    This API is intentionally separate from the practical pilot frontend. Its
    outputs must be tagged ``diagnostic_oracle_csi`` and excluded from practical
    BER and energy-gain summaries.
    """
    _validate_observation(observation, schedule.frame_symbols)
    if not path_delays_samples or any(
        type(delay) is not int or delay < 0 for delay in path_delays_samples
    ):
        raise ValueError("path_delays_samples must be non-negative integer delays")
    maximum_delay = max(path_delays_samples)
    if maximum_delay >= 8:
        raise ValueError("oracle clean-tail combiner requires maximum delay below eight samples")
    amplitude = _positive_finite(amplitude, "amplitude")
    noise_variance = _positive_finite(
        assumed_noise_variance, "assumed_noise_variance", allow_zero=True
    )
    coefficients = np.asarray(path_coefficients_by_sample, dtype=np.complex128)
    required = schedule.frame_symbols * 8 + maximum_delay
    if (
        coefficients.ndim != 2
        or coefficients.shape[0] != len(path_delays_samples)
        or coefficients.shape[1] < required
        or not np.all(np.isfinite(coefficients))
    ):
        raise ValueError("oracle coefficients must have shape (paths, received_samples)")
    clean_count = 8 - maximum_delay
    frame = schedule.frame_symbols
    received = np.asarray(observation.received_samples, dtype=np.complex128)
    symbols = np.zeros(frame, dtype=np.complex128)
    variance = np.full(frame, np.nan, dtype=np.float64)
    valid = np.ones(frame, dtype=bool)
    gains = np.zeros(frame, dtype=np.complex128)
    gain_valid = np.ones(frame, dtype=bool)
    updates = np.zeros(frame, dtype=bool)
    ages = np.zeros(frame, dtype=np.int32)
    sample_indices = np.empty((frame, clean_count), dtype=np.int64)
    for index in range(frame):
        start = index * 8 + maximum_delay
        sample_idx = np.arange(start, start + clean_count, dtype=np.int64)
        sample_indices[index] = sample_idx
        composite = np.sum(coefficients[:, sample_idx], axis=0)
        power = float(np.vdot(composite, composite).real)
        gains[index] = complex(np.mean(composite))
        if power < minimum_gain_power:
            valid[index] = False
            gain_valid[index] = False
            symbols[index] = 0j
            continue
        symbols[index] = np.vdot(composite, received[sample_idx]) / power
        variance[index] = noise_variance / power
    return _frontend_result(
        symbols=symbols,
        variance=variance,
        valid=valid,
        gains=gains,
        gain_valid=gain_valid,
        gain_updates=updates,
        gain_age=ages,
        sample_indices=sample_indices,
        clean_count=clean_count,
        maximum_delay=maximum_delay,
        mode="diagnostic_oracle_csi",
        observation=observation,
    )


def euclidean_branch_metric_rows(
    symbols: object, *, amplitude: float, phase_offset_rad: float = 0.0
) -> NDArray[np.float64]:
    """Squared complex Euclidean costs in the canonical 16-edge order."""
    observed = np.asarray(symbols, dtype=np.complex128)
    if observed.ndim != 1 or len(observed) < 1 or not np.all(np.isfinite(observed)):
        raise ValueError("symbols must be a nonempty finite complex vector")
    constellation = _phase_symbols(amplitude, phase_offset_rad)
    predictions = constellation[_EDGE_PHASES]
    return np.asarray(np.square(np.abs(observed[:, None] - predictions[None, :])), dtype=np.float64)


def hard_phase_decisions(
    symbols: object, *, amplitude: float, phase_offset_rad: float = 0.0
) -> NDArray[np.int8]:
    """Candidate-independent nearest-phase decisions; ties choose lowest index."""
    observed = np.asarray(symbols, dtype=np.complex128)
    if observed.ndim != 1 or len(observed) < 1 or not np.all(np.isfinite(observed)):
        raise ValueError("symbols must be a nonempty finite complex vector")
    constellation = _phase_symbols(amplitude, phase_offset_rad)
    distances = np.square(np.abs(observed[:, None] - constellation[None, :]))
    minima = np.min(distances, axis=1, keepdims=True)
    tolerance = 16.0 * np.finfo(np.float64).eps * max(1.0, float(amplitude) ** 2)
    tied = np.abs(distances - minima) <= tolerance
    return np.argmax(tied, axis=1).astype(np.int8)


def hamming_branch_metric_rows(
    symbols: object, *, amplitude: float, phase_offset_rad: float = 0.0
) -> NDArray[np.int8]:
    """Hard-slice each observation once, then compare it with every edge label."""
    phases = hard_phase_decisions(symbols, amplitude=amplitude, phase_offset_rad=phase_offset_rad)
    hard_triples = np.column_stack(((phases >> 2) & 1, (phases >> 1) & 1, phases & 1)).astype(
        np.int8
    )
    return np.count_nonzero(hard_triples[:, None, :] != _EDGE_OUTPUTS[None, :, :], axis=2).astype(
        np.int8
    )


def pilot_constrained_metric_rows(
    metric_rows: object, schedule: PilotSchedule
) -> tuple[NDArray[np.float64], NDArray[np.int8]]:
    """Zero pilot evidence uniformly and return exact known-input constraints."""
    metrics = np.asarray(metric_rows, dtype=np.float64)
    if metrics.shape != (schedule.frame_symbols, 16) or not np.all(np.isfinite(metrics)):
        raise ValueError("metric_rows must be a finite (frame_symbols,16) matrix")
    constraints = np.full((schedule.frame_symbols, 2), -1, dtype=np.int8)
    constraints[schedule.pilot_mask] = schedule.pilot_input_pairs[schedule.pilot_mask]
    result = metrics.copy()
    for index in np.flatnonzero(schedule.pilot_mask):
        pair = tuple(int(value) for value in schedule.pilot_input_pairs[index])
        for edge_id, _state, edge_pair, _output, _next in _EDGES:
            if edge_pair == pair:
                result[index, edge_id] = 0.0
    return result, constraints


def run_metric_viterbi(
    branch_metric_rows: object,
    *,
    allowed_input_pairs: object | None = None,
    traceback_depth: int = 20,
    initial_state: tuple[int, int] = (0, 0),
) -> ViterbiResult:
    """Finite-depth Viterbi with exact optional input constraints.

    With no constraints this is required to reproduce the maintained finite
    Viterbi implementation byte-for-byte for decoded paths and survivor rows.
    Pilot constraints are edge masks, not large finite metric penalties.
    """
    rows = np.asarray(branch_metric_rows)
    if rows.ndim != 2 or rows.shape[1] != 16 or rows.shape[0] < 1:
        raise ValueError("branch_metric_rows must have shape (F,16), F >= 1")
    if rows.dtype.kind not in "iuf" or not np.all(np.isfinite(rows)) or np.any(rows < 0):
        raise ValueError("branch metrics must be finite nonnegative numeric values")
    if type(traceback_depth) is not int or traceback_depth < 1:
        raise ValueError("traceback_depth must be a positive integer")
    if initial_state not in _STATE_INDEX:
        raise ValueError("initial_state must be a valid Encoder A state")
    count = len(rows)
    if allowed_input_pairs is None:
        constraints = np.full((count, 2), -1, dtype=np.int8)
    else:
        constraints = np.asarray(allowed_input_pairs)
        if constraints.shape != (count, 2) or constraints.dtype.kind not in "iu":
            raise ValueError("allowed_input_pairs must have integer shape (F,2)")
        if np.any(constraints > 1) or np.any(constraints < -1):
            raise ValueError("input constraints must be (-1,-1) or binary pairs")
        if np.any((constraints[:, 0] == -1) != (constraints[:, 1] == -1)):
            raise ValueError("an unconstrained pair must use (-1,-1)")
        constraints = np.asarray(constraints, dtype=np.int8)

    float_metrics = rows.dtype.kind == "f"
    metric_dtype = np.float64 if float_metrics else np.int64
    infinity = np.inf if float_metrics else np.iinfo(np.int64).max // 4
    metrics = np.full(4, infinity, dtype=metric_dtype)
    metrics[_STATE_INDEX[initial_state]] = 0
    metric_history = [metrics.copy()]
    survivor_history: list[NDArray[np.int16]] = []
    survivors: deque[NDArray[np.int16]] = deque(maxlen=traceback_depth)
    decisions: list[DecisionRecord] = []

    def traceback(endpoint: int, depth: int) -> list[tuple[int, int]]:
        history = list(survivors)[-depth:]
        node = endpoint
        reverse_path: list[tuple[int, int]] = []
        for symbol_index, edge_by_target in reversed(history):
            edge_id = int(edge_by_target[node])
            if edge_id < 0:
                raise RuntimeError("constrained survivor traceback is incomplete")
            reverse_path.append((symbol_index, edge_id))
            node = _STATE_INDEX[_EDGES[edge_id][1]]
        reverse_path.reverse()
        return reverse_path

    for row_index, row in enumerate(rows):
        next_metrics = np.full(4, infinity, dtype=metric_dtype)
        edge_by_target = np.full(4, -1, dtype=np.int16)
        constraint = tuple(int(value) for value in constraints[row_index])
        for edge_id, source, pair, _output, target in _EDGES:
            if constraint != (-1, -1) and pair != constraint:
                continue
            source_index, target_index = _STATE_INDEX[source], _STATE_INDEX[target]
            prefix = metrics[source_index]
            if prefix >= infinity:
                continue
            candidate = prefix + (float(row[edge_id]) if float_metrics else int(row[edge_id]))
            if candidate < next_metrics[target_index]:
                next_metrics[target_index] = candidate
                edge_by_target[target_index] = edge_id
        if np.all(edge_by_target < 0):
            raise ValueError("no valid path satisfies configured pilot constraints")
        metrics = next_metrics
        survivor_row = np.frombuffer(edge_by_target.tobytes(), dtype=np.int16)
        survivors.append((row_index, survivor_row))
        survivor_history.append(edge_by_target.copy())
        metric_history.append(metrics.copy())
        seen = row_index + 1
        if seen >= traceback_depth:
            endpoint = int(np.argmin(metrics))
            first_index, first_edge = traceback(endpoint, traceback_depth)[0]
            _edge, source, pair, _coded, target = _EDGES[first_edge]
            decisions.append(
                DecisionRecord(
                    symbol_index=first_index,
                    decision_available_at=seen - 1,
                    traceback_depth_used=traceback_depth,
                    edge_id=first_edge,
                    input_pair=pair,
                    source_state=source,
                    target_state=target,
                    decoder_mode="finite_depth",
                    decision_policy="finite_depth",
                )
            )

    final_state_index = int(np.argmin(metrics))
    final_depth = min(count, traceback_depth)
    final_path = traceback(final_state_index, final_depth)
    last_emitted = decisions[-1].symbol_index if decisions else -1
    for symbol_index, edge_id in final_path:
        if symbol_index <= last_emitted:
            continue
        _edge, source, pair, _coded, target = _EDGES[edge_id]
        decisions.append(
            DecisionRecord(
                symbol_index=symbol_index,
                decision_available_at=count - 1,
                traceback_depth_used=count - symbol_index,
                edge_id=edge_id,
                input_pair=pair,
                source_state=source,
                target_state=target,
                decoder_mode="finite_depth",
                decision_policy="frame_flush",
            )
        )
    decisions.sort(key=lambda item: item.symbol_index)
    if len(decisions) != count or [item.symbol_index for item in decisions] != list(range(count)):
        raise RuntimeError("constrained Viterbi emitted missing or duplicate decisions")

    pairs = np.asarray([item.input_pair for item in decisions], dtype=np.int8)
    state_path = np.empty((count + 1, 2), dtype=np.int8)
    state_path[0] = initial_state
    edge_ids = np.empty(count, dtype=np.int16)
    state = initial_state
    for index, pair_values in enumerate(pairs):
        pair = int(pair_values[0]), int(pair_values[1])
        edge_id = _EDGE_BY_STATE_INPUT[(state, pair)]
        edge_ids[index] = edge_id
        state = (pair[1], state[0])
        state_path[index + 1] = state
    return ViterbiResult(
        decoded_edge_ids=edge_ids,
        information_pairs=pairs,
        state_path=state_path,
        final_state=state,
        survivor_final_state=STATE_ORDER[final_state_index],
        final_metric=metrics[final_state_index].item(),
        decisions=tuple(decisions),
        decoder_mode="finite_depth",
        traceback_depth=traceback_depth,
        state_metrics=np.asarray(metric_history, dtype=metric_dtype),
        survivor_edge_ids=np.asarray(survivor_history, dtype=np.int16),
        survivor_buffer_max_rows=min(count, traceback_depth),
        frame_end_policy="free_final_state_best_survivor_flush",
    )
