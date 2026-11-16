"""Evaluation-only causal traces copied from actual B4d history.

This adapter accepts an already received deterministic sample buffer. It does
not create channel data, inspect reference bits, tune receiver parameters, or
change the B4d/B5b computations.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from numbers import Integral, Real

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.encoder import INITIAL_STATE
from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.decoding.reconstruction_viterbi import (
    ReconstructionViterbiResult,
    decode_reconstruction_viterbi,
)
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_forward import (
    APPROXIMATE_RECTANGULAR_8SPS,
    RECTANGULAR_ZOH_RULE,
)
from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER
from hf_tcm.receiver.reconstruction_observation import (
    ADR012_IQ_RULE,
    ADR012_PROFILE,
    ADR012_PROFILE_ID,
    ADR012_SAMPLES_PER_SYMBOL,
    ADR012_WAVEFORM_RULE,
)
from hf_tcm.receiver.reconstruction_posterior import build_initial_reconstruction_prior
from hf_tcm.receiver.reconstruction_posterior_estimator_sequence import (
    run_reconstruction_posterior_estimator_sequence,
)

FloatArray = NDArray[np.float64]
BitArray = NDArray[np.int8]
ComplexArray = NDArray[np.complex128]
_HYPOTHESIS_IDS = tuple(hypothesis.hypothesis_id for hypothesis in HYPOTHESES)
TRACE_STATUS = (
    "isolated causal estimator trace diagnostics, NOT new performance evidence, "
    "NOT established root cause, NOT paper-exact joint receiver"
)


def _immutable(value: ArrayLike, *, dtype: np.dtype, shape: tuple[int, ...], name: str) -> NDArray:
    try:
        raw = np.asarray(value)
        if np.iscomplexobj(raw) and dtype.kind != "c":
            raise ValueError
        array = np.asarray(raw, dtype=dtype)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite and have shape {shape}") from exc
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be finite and have shape {shape}")
    owned = np.array(array, dtype=dtype, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=dtype).reshape(shape)


def _index(value: object, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")
    return int(value)


def _iq_schedule(value: ArrayLike, *, name: str, count: int) -> tuple[FloatArray, ...]:
    try:
        raw = np.asarray(value)
        if np.iscomplexobj(raw) or raw.dtype.kind not in "iuf":
            raise ValueError
        array = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite shape (1,2) or (F,1,2)") from exc
    if array.shape == (1, 2):
        values = tuple(np.array(array, copy=True) for _ in range(count))
    elif array.shape == (count, 1, 2):
        values = tuple(np.array(array[index], copy=True) for index in range(count))
    else:
        raise ValueError(f"{name} must have shape (1,2) or ({count},1,2)")
    if any(not np.all(np.isfinite(item)) for item in values):
        raise ValueError(f"{name} must contain only finite values")
    return values


def _alpha_schedule(value: Real | Sequence[Real], *, count: int) -> tuple[float, ...]:
    if isinstance(value, Real) and not isinstance(value, (bool, np.bool_)):
        values = (float(value),) * count
    else:
        raw = np.asarray(value)
        if raw.ndim != 1 or raw.shape != (count,) or raw.dtype.kind not in "iuf":
            raise ValueError("adaptive_alpha_prime must be a scalar or an explicit (F,) schedule")
        values = tuple(float(item) for item in raw)
    if not all(math.isfinite(item) for item in values):
        raise ValueError("adaptive_alpha_prime must be finite")
    return values


@dataclass(frozen=True, slots=True)
class ReconstructionCausalSymbolTrace:
    """One row copied from B4d, including explicit clock and update provenance."""

    sequence_id: str
    absolute_symbol_index: int
    estimator_time_index: int
    segment_index: int
    segment_local_position: int
    sample_window: tuple[int, ...]
    prediction_cutoff_sample_index: int
    observation_cutoff_sample_index: int
    pre_state: ReconstructionEstimatorState
    observed_iq: FloatArray
    predicted_iq: FloatArray
    sample_predictions_iq: FloatArray
    candidate_metrics: FloatArray
    hypothesis_ids: tuple[int, ...]
    phase_indices: tuple[int, ...]
    edge_mode: str
    posterior_input: FloatArray
    posterior_input_kind: str
    posterior_transition_provenance: str
    posterior: FloatArray
    posterior_sum: float
    posterior_normalized: bool
    transition_predicted_posterior: None
    alpha_prime: float
    k_tilde: FloatArray
    mu0: FloatArray
    innovation_operand: FloatArray
    innovation_provenance: str
    post_state: ReconstructionEstimatorState
    fluctuating_increment: FloatArray
    full_increment: FloatArray
    decoded_hypothesis_id: int | None = None

    def __post_init__(self) -> None:
        for field, shape in (
            ("observed_iq", (2,)),
            ("predicted_iq", (16, 2)),
            ("sample_predictions_iq", (16, 8, 2)),
            ("candidate_metrics", (16,)),
            ("posterior_input", (16,)),
            ("posterior", (16,)),
            ("k_tilde", (1, 2)),
            ("mu0", (1, 2)),
            ("innovation_operand", (2,)),
            ("fluctuating_increment", (1, 2)),
            ("full_increment", (1, 2)),
        ):
            object.__setattr__(
                self,
                field,
                _immutable(
                    getattr(self, field),
                    dtype=np.dtype(np.float64),
                    shape=shape,
                    name=field,
                ),
            )
        if len(self.sample_window) != ADR012_SAMPLES_PER_SYMBOL:
            raise ValueError("sample_window must contain exactly eight absolute sample labels")
        if self.hypothesis_ids != _HYPOTHESIS_IDS:
            raise ValueError("trace hypothesis IDs must preserve canonical B4d order")
        if self.edge_mode not in ("first_edge", "later_edge"):
            raise ValueError("edge_mode must come from the actual B4c result")


@dataclass(frozen=True, slots=True)
class ReconstructionCausalModeTrace:
    mode: str
    sequence_id: str
    received_sha256: str
    initial_state: ReconstructionEstimatorState
    history: tuple[ReconstructionCausalSymbolTrace, ...]
    frozen_metric_history: FloatArray
    final_state: ReconstructionEstimatorState
    decoded_hypothesis_path: tuple[int, ...]
    decoded_information_bits: BitArray
    best_conditional_path_cost: float
    decoded_path_valid: bool
    decoder_result: ReconstructionViterbiResult
    decode_call_count: int

    def __post_init__(self) -> None:
        count = len(self.history)
        object.__setattr__(
            self,
            "frozen_metric_history",
            _immutable(
                self.frozen_metric_history,
                dtype=np.dtype(np.float64),
                shape=(count, 16),
                name="frozen_metric_history",
            ),
        )
        object.__setattr__(
            self,
            "decoded_information_bits",
            _immutable(
                self.decoded_information_bits,
                dtype=np.dtype(np.int8),
                shape=(2 * count,),
                name="decoded_information_bits",
            ),
        )
        if self.decode_call_count != 1:
            raise ValueError("B5b must decode the frozen metric history exactly once")


@dataclass(frozen=True, slots=True)
class ReconstructionCausalTracePair:
    status: str
    sequence_id: str
    received_sha256: str
    beta: float
    symbol_origin_sample: int
    first_symbol_index: int
    initial_estimator_time_index: int
    frozen: ReconstructionCausalModeTrace
    adaptive: ReconstructionCausalModeTrace


@dataclass(frozen=True, slots=True)
class ReconstructionCausalTraceComparison:
    received_sha256_equal: bool
    initial_state_equal: bool
    pre_state_differing_symbols: tuple[int, ...]
    post_state_differing_symbols: tuple[int, ...]
    posterior_differing_symbols: tuple[int, ...]
    candidate_metric_differing_symbols: tuple[int, ...]
    coefficient_increment_differing_symbols: tuple[int, ...]
    decoded_edge_differing_symbols: tuple[int, ...]
    first_estimator_state_divergence_symbol: int | None
    first_candidate_metric_divergence_symbol: int | None


def _mode_trace(
    *,
    mode: str,
    received: ComplexArray,
    labels: NDArray[np.int64],
    received_start_sample: int,
    symbol_origin_sample: int,
    first_symbol_index: int,
    initial_estimator_time_index: int,
    initial_state: ReconstructionEstimatorState,
    beta: float,
    alpha: tuple[float, ...],
    gains: tuple[FloatArray, ...],
    regular: tuple[FloatArray, ...],
    sequence_id: str,
    partition: tuple[int, ...],
    received_sha256: str,
) -> ReconstructionCausalModeTrace:
    count = len(alpha)
    prior = build_initial_reconstruction_prior(initial_state=INITIAL_STATE)
    current_state = initial_state
    current_posterior: FloatArray | None = None
    previous_symbol: int | None = None
    previous_time: int | None = None
    trace_rows: list[ReconstructionCausalSymbolTrace] = []
    metric_rows: list[FloatArray] = []
    offset = 0
    for segment_index, segment_size in enumerate(partition):
        start = offset * ADR012_SAMPLES_PER_SYMBOL
        stop = start + segment_size * ADR012_SAMPLES_PER_SYMBOL
        first_symbol = first_symbol_index + offset
        sequence = run_reconstruction_posterior_estimator_sequence(
            received=received[start:stop],
            absolute_sample_indices=labels[start:stop],
            received_start_sample=received_start_sample + start,
            symbol_origin_sample=symbol_origin_sample,
            first_symbol_index=first_symbol,
            sequence_origin_symbol_index=first_symbol_index,
            symbol_count=segment_size,
            symbol_indices=tuple(range(first_symbol, first_symbol + segment_size)),
            initial_state=current_state,
            initial_estimator_time_index=current_state.time_index,
            run_mode="new_independent_sequence" if segment_index == 0 else "continuation",
            initial_prior=prior if segment_index == 0 else None,
            previous_posterior=current_posterior,
            continuation_from_symbol_index=previous_symbol,
            continuation_from_estimator_time_index=previous_time,
            beta=beta,
            alpha_prime=alpha[offset : offset + segment_size],
            k_tilde=np.stack(gains[offset : offset + segment_size]),
            mu0=np.stack(regular[offset : offset + segment_size]),
            include_history=True,
            profile=ADR012_PROFILE,
            adr_profile=ADR012_PROFILE_ID,
            path_count=1,
            path_delays_samples=(0,),
            samples_per_symbol=ADR012_SAMPLES_PER_SYMBOL,
            iq_rule=ADR012_IQ_RULE,
            waveform_rule=ADR012_WAVEFORM_RULE,
            labeling_profile=ASSUMED_NATURAL_BINARY,
            bit_order=OUTPUT_BIT_ORDER,
            timebase_profile=APPROXIMATE_RECTANGULAR_8SPS,
            symbol_to_sample_rule=RECTANGULAR_ZOH_RULE,
            edge_policy="zero_padding",
        )
        if sequence.history is None or len(sequence.history) != segment_size:
            raise RuntimeError("B4d did not return complete per-symbol history")
        for local_position, entry in enumerate(sequence.history):
            step = entry.b4c_result
            candidate = step.candidate_result
            symbol = first_symbol + local_position
            expected_window = tuple(
                range(
                    symbol_origin_sample + ADR012_SAMPLES_PER_SYMBOL * symbol,
                    symbol_origin_sample + ADR012_SAMPLES_PER_SYMBOL * (symbol + 1),
                )
            )
            pre_state = (
                current_state
                if local_position == 0
                else sequence.history[local_position - 1].b4c_result.next_state
            )
            if candidate.sample_indices != expected_window:
                raise ValueError("B4d sample labels do not match symbol clock provenance")
            if candidate.hypothesis_ids != _HYPOTHESIS_IDS:
                raise ValueError("B4d history did not preserve canonical hypothesis order")
            posterior_input = prior if step.edge_mode == "first_edge" else current_posterior
            if posterior_input is None:
                raise ValueError("B4d continuation lacks the actual previous posterior operand")
            posterior_input_kind = (
                "adr004_initial_prior" if step.edge_mode == "first_edge" else "previous_posterior"
            )
            transition_provenance = (
                "none_first_edge"
                if step.edge_mode == "first_edge"
                else "adr003_transition_then_current_metric_likelihood"
            )
            innovation = np.sum(
                step.posterior[:, np.newaxis] * (step.observed_iq - step.predicted_iq), axis=0
            )
            post_state = step.next_state
            row = ReconstructionCausalSymbolTrace(
                sequence_id=sequence_id,
                absolute_symbol_index=symbol,
                estimator_time_index=entry.estimator_time_index,
                segment_index=segment_index,
                segment_local_position=local_position,
                sample_window=candidate.sample_indices,
                prediction_cutoff_sample_index=candidate.prediction_cutoff_sample_index,
                observation_cutoff_sample_index=candidate.metric_available_after_sample_index,
                pre_state=pre_state,
                observed_iq=step.observed_iq,
                predicted_iq=step.predicted_iq,
                sample_predictions_iq=candidate.sample_predictions_iq,
                candidate_metrics=candidate.metrics,
                hypothesis_ids=candidate.hypothesis_ids,
                phase_indices=candidate.phase_indices,
                edge_mode=step.edge_mode,
                posterior_input=posterior_input,
                posterior_input_kind=posterior_input_kind,
                posterior_transition_provenance=transition_provenance,
                posterior=step.posterior,
                posterior_sum=math.fsum(float(value) for value in step.posterior),
                posterior_normalized=math.isclose(
                    math.fsum(float(value) for value in step.posterior),
                    1.0,
                    rel_tol=1e-10,
                    abs_tol=1e-10,
                ),
                transition_predicted_posterior=None,
                alpha_prime=alpha[offset + local_position],
                k_tilde=gains[offset + local_position],
                mu0=regular[offset + local_position],
                innovation_operand=innovation,
                innovation_provenance="derived_from_actual_B4c_posterior_observation_prediction",
                post_state=post_state,
                fluctuating_increment=post_state.fluctuating_iq - pre_state.fluctuating_iq,
                full_increment=post_state.full_iq - pre_state.full_iq,
            )
            if not math.isclose(row.posterior_sum, 1.0, rel_tol=1e-10, abs_tol=1e-10):
                raise ValueError("B4d posterior is not normalized")
            trace_rows.append(row)
            metric_rows.append(candidate.metrics)
            current_posterior = step.posterior
            current_state = post_state
        previous_symbol = sequence.final_symbol_index
        previous_time = sequence.final_estimator_time_index - 1
        offset += segment_size

    frozen_metrics = np.stack(metric_rows)
    symbols = tuple(row.absolute_symbol_index for row in trace_rows)
    times = tuple(row.estimator_time_index for row in trace_rows)
    decoded = decode_reconstruction_viterbi(
        frozen_metrics,
        hypotheses=HYPOTHESES,
        initial_state=INITIAL_STATE,
        sequence_mode="new_independent_sequence",
        profile="reconstructed_offline",
        edge_indices=tuple(range(count)),
        symbol_indices=symbols,
        estimator_time_indices=times,
    )
    path_valid = (
        len(validate_hypothesis_edge_path(decoded.hypothesis_ids, initial_state=INITIAL_STATE))
        == count
    )
    completed_rows = tuple(
        replace(row, decoded_hypothesis_id=decoded.hypothesis_ids[index])
        for index, row in enumerate(trace_rows)
    )
    return ReconstructionCausalModeTrace(
        mode=mode,
        sequence_id=sequence_id,
        received_sha256=received_sha256,
        initial_state=initial_state,
        history=completed_rows,
        frozen_metric_history=frozen_metrics,
        final_state=current_state,
        decoded_hypothesis_path=decoded.hypothesis_ids,
        decoded_information_bits=decoded.decoded_bits,
        best_conditional_path_cost=decoded.best_path_metric,
        decoded_path_valid=path_valid,
        decoder_result=decoded,
        decode_call_count=1,
    )


def run_reconstruction_causal_trace_pair(
    *,
    received: ArrayLike,
    absolute_sample_indices: ArrayLike,
    received_start_sample: int,
    symbol_origin_sample: int,
    first_symbol_index: int,
    initial_estimator_time_index: int,
    initial_state: ReconstructionEstimatorState,
    beta: Real,
    sequence_id: str,
    adaptive_alpha_prime: Real | Sequence[Real],
    adaptive_k_tilde: ArrayLike,
    adaptive_mu0: ArrayLike,
    segment_partition: Sequence[int] | None = None,
) -> ReconstructionCausalTracePair:
    """Trace frozen B and adaptive C on the same caller-supplied sample buffer.

    The API has no reference-bit or channel-truth operand. B and C share the
    received samples, initial state, beta, and clock labels; only their update
    schedules differ. No observations are generated here.
    """
    samples = np.asarray(received)
    if not np.iscomplexobj(samples) or samples.ndim != 1 or samples.size == 0:
        raise ValueError("received must be a non-empty complex sample vector")
    samples = _immutable(
        samples,
        dtype=np.dtype(np.complex128),
        shape=(samples.size,),
        name="received",
    )
    labels_raw = np.asarray(absolute_sample_indices)
    if labels_raw.shape != samples.shape or labels_raw.dtype.kind not in "iu":
        raise ValueError("absolute_sample_indices must be integer labels matching received")
    labels = np.asarray(labels_raw, dtype=np.int64)
    start = _index(received_start_sample, name="received_start_sample")
    origin = _index(symbol_origin_sample, name="symbol_origin_sample")
    first_symbol = _index(first_symbol_index, name="first_symbol_index")
    first_time = _index(initial_estimator_time_index, name="initial_estimator_time_index")
    if not isinstance(sequence_id, str) or not sequence_id.strip():
        raise ValueError("sequence_id must be a non-empty string")
    if not isinstance(initial_state, ReconstructionEstimatorState):
        raise ValueError("initial_state must be a ReconstructionEstimatorState")
    if initial_state.time_index != first_time or initial_state.full_iq.shape != (1, 2):
        raise ValueError("initial_state must be L=1 and match initial_estimator_time_index")
    if isinstance(beta, (bool, np.bool_)) or not isinstance(beta, Real):
        raise ValueError("beta must be finite and positive")
    beta_value = float(beta)
    if not math.isfinite(beta_value) or beta_value <= 0.0:
        raise ValueError("beta must be finite and positive")
    if samples.size % ADR012_SAMPLES_PER_SYMBOL:
        raise ValueError("received must contain a complete number of eight-sample symbols")
    count = samples.size // ADR012_SAMPLES_PER_SYMBOL
    expected_labels = np.arange(start, start + samples.size, dtype=np.int64)
    expected_start = origin + ADR012_SAMPLES_PER_SYMBOL * first_symbol
    if start != expected_start or not np.array_equal(labels, expected_labels):
        raise ValueError(
            "received labels must be contiguous and start at the requested symbol window"
        )
    if np.array_equal(initial_state.fluctuating_iq, initial_state.full_iq) is False:
        raise ValueError(
            "paired frozen/adaptive trace requires matching initial full/fluctuating state"
        )
    partition = (
        (count,)
        if segment_partition is None
        else tuple(_index(value, name="segment size") for value in segment_partition)
    )
    if not partition or any(value < 1 for value in partition) or sum(partition) != count:
        raise ValueError("segment_partition must contain positive sizes summing to F")
    alpha = _alpha_schedule(adaptive_alpha_prime, count=count)
    adaptive_gains = _iq_schedule(adaptive_k_tilde, name="adaptive_k_tilde", count=count)
    adaptive_regular = _iq_schedule(adaptive_mu0, name="adaptive_mu0", count=count)
    frozen_alpha = (1.0,) * count
    zeros = tuple(np.zeros((1, 2), dtype=np.float64) for _ in range(count))
    digest = hashlib.sha256(samples.tobytes()).hexdigest()
    shared = dict(
        received=samples,
        labels=labels,
        received_start_sample=start,
        symbol_origin_sample=origin,
        first_symbol_index=first_symbol,
        initial_estimator_time_index=first_time,
        initial_state=initial_state,
        beta=beta_value,
        sequence_id=sequence_id,
        partition=partition,
        received_sha256=digest,
    )
    frozen = _mode_trace(
        mode="mismatched_frozen",
        alpha=frozen_alpha,
        gains=zeros,
        regular=zeros,
        **shared,
    )
    adaptive = _mode_trace(
        mode="mismatched_adaptive",
        alpha=alpha,
        gains=adaptive_gains,
        regular=adaptive_regular,
        **shared,
    )
    return ReconstructionCausalTracePair(
        status=TRACE_STATUS,
        sequence_id=sequence_id,
        received_sha256=digest,
        beta=beta_value,
        symbol_origin_sample=origin,
        first_symbol_index=first_symbol,
        initial_estimator_time_index=first_time,
        frozen=frozen,
        adaptive=adaptive,
    )


def compare_reconstruction_causal_traces(
    traces: ReconstructionCausalTracePair, *, rtol: float, atol: float
) -> ReconstructionCausalTraceComparison:
    """Describe B/C divergence with explicit floating-point tolerances."""
    if (
        isinstance(rtol, bool)
        or isinstance(atol, bool)
        or not math.isfinite(float(rtol))
        or not math.isfinite(float(atol))
        or rtol < 0
        or atol < 0
    ):
        raise ValueError("rtol and atol must be finite non-negative tolerances")
    frozen, adaptive = traces.frozen, traces.adaptive
    if len(frozen.history) != len(adaptive.history):
        raise ValueError("paired traces must have equal symbol counts")

    def first_divergence(indices: tuple[int, ...]) -> int | None:
        return indices[0] if indices else None

    pre_differences: list[int] = []
    posterior_differences: list[int] = []
    metric_differences: list[int] = []
    increment_differences: list[int] = []
    decoded_differences: list[int] = []
    state_divergences: list[int] = []
    for left, right in zip(frozen.history, adaptive.history, strict=True):
        symbol = left.absolute_symbol_index
        state_diff = not (
            np.allclose(
                left.pre_state.fluctuating_iq, right.pre_state.fluctuating_iq, rtol=rtol, atol=atol
            )
            and np.allclose(left.pre_state.full_iq, right.pre_state.full_iq, rtol=rtol, atol=atol)
        )
        if state_diff:
            pre_differences.append(symbol)
        post_state_diff = not (
            np.allclose(
                left.post_state.fluctuating_iq,
                right.post_state.fluctuating_iq,
                rtol=rtol,
                atol=atol,
            )
            and np.allclose(
                left.post_state.full_iq,
                right.post_state.full_iq,
                rtol=rtol,
                atol=atol,
            )
        )
        if post_state_diff:
            state_divergences.append(symbol)
        if not np.allclose(left.posterior, right.posterior, rtol=rtol, atol=atol):
            posterior_differences.append(symbol)
        if not np.allclose(left.candidate_metrics, right.candidate_metrics, rtol=rtol, atol=atol):
            metric_differences.append(symbol)
        if not np.allclose(
            left.fluctuating_increment, right.fluctuating_increment, rtol=rtol, atol=atol
        ):
            increment_differences.append(symbol)
        if left.decoded_hypothesis_id != right.decoded_hypothesis_id:
            decoded_differences.append(symbol)
    return ReconstructionCausalTraceComparison(
        received_sha256_equal=frozen.received_sha256 == adaptive.received_sha256,
        initial_state_equal=(
            np.allclose(
                frozen.initial_state.fluctuating_iq,
                adaptive.initial_state.fluctuating_iq,
                rtol=rtol,
                atol=atol,
            )
            and np.allclose(
                frozen.initial_state.full_iq,
                adaptive.initial_state.full_iq,
                rtol=rtol,
                atol=atol,
            )
        ),
        pre_state_differing_symbols=tuple(pre_differences),
        post_state_differing_symbols=tuple(state_divergences),
        posterior_differing_symbols=tuple(posterior_differences),
        candidate_metric_differing_symbols=tuple(metric_differences),
        coefficient_increment_differing_symbols=tuple(increment_differences),
        decoded_edge_differing_symbols=tuple(decoded_differences),
        first_estimator_state_divergence_symbol=first_divergence(tuple(state_divergences)),
        first_candidate_metric_divergence_symbol=first_divergence(tuple(metric_differences)),
    )


def summarize_reconstruction_causal_trace_pair(
    traces: ReconstructionCausalTracePair, *, rtol: float, atol: float
) -> dict[str, object]:
    """Return a compact, JSON-compatible descriptive summary without raw histories."""
    comparison = compare_reconstruction_causal_traces(traces, rtol=rtol, atol=atol)
    rows: list[dict[str, object]] = []
    for frozen, adaptive in zip(traces.frozen.history, traces.adaptive.history, strict=True):
        rows.append(
            {
                "absolute_symbol_index": frozen.absolute_symbol_index,
                "estimator_time_index": frozen.estimator_time_index,
                "sample_window": frozen.sample_window,
                "frozen_full_iq": tuple(float(value) for value in frozen.post_state.full_iq[0]),
                "adaptive_full_iq": tuple(float(value) for value in adaptive.post_state.full_iq[0]),
                "frozen_fluctuating_iq": tuple(
                    float(value) for value in frozen.post_state.fluctuating_iq[0]
                ),
                "adaptive_fluctuating_iq": tuple(
                    float(value) for value in adaptive.post_state.fluctuating_iq[0]
                ),
                "frozen_update_norm": float(np.linalg.norm(frozen.fluctuating_increment)),
                "adaptive_update_norm": float(np.linalg.norm(adaptive.fluctuating_increment)),
                "frozen_posterior_sum": frozen.posterior_sum,
                "adaptive_posterior_sum": adaptive.posterior_sum,
                "frozen_metric_row_equal": bool(
                    np.allclose(
                        frozen.candidate_metrics,
                        adaptive.candidate_metrics,
                        rtol=rtol,
                        atol=atol,
                    )
                ),
                "decoded_edge_frozen": frozen.decoded_hypothesis_id,
                "decoded_edge_adaptive": adaptive.decoded_hypothesis_id,
            }
        )
    return {
        "status": traces.status,
        "sequence_id": traces.sequence_id,
        "received_sha256": traces.received_sha256,
        "first_estimator_state_divergence_symbol": (
            comparison.first_estimator_state_divergence_symbol
        ),
        "first_candidate_metric_divergence_symbol": (
            comparison.first_candidate_metric_divergence_symbol
        ),
        "per_symbol": tuple(rows),
        "frozen_final": {
            "full_iq": tuple(float(value) for value in traces.frozen.final_state.full_iq[0]),
            "fluctuating_iq": tuple(
                float(value) for value in traces.frozen.final_state.fluctuating_iq[0]
            ),
            "decoded_hypothesis_path": traces.frozen.decoded_hypothesis_path,
            "decoded_information_bits": tuple(
                int(value) for value in traces.frozen.decoded_information_bits
            ),
            "best_conditional_path_cost": traces.frozen.best_conditional_path_cost,
            "decoded_path_valid": traces.frozen.decoded_path_valid,
        },
        "adaptive_final": {
            "full_iq": tuple(float(value) for value in traces.adaptive.final_state.full_iq[0]),
            "fluctuating_iq": tuple(
                float(value) for value in traces.adaptive.final_state.fluctuating_iq[0]
            ),
            "decoded_hypothesis_path": traces.adaptive.decoded_hypothesis_path,
            "decoded_information_bits": tuple(
                int(value) for value in traces.adaptive.decoded_information_bits
            ),
            "best_conditional_path_cost": traces.adaptive.best_conditional_path_cost,
            "decoded_path_valid": traces.adaptive.decoded_path_valid,
        },
    }
