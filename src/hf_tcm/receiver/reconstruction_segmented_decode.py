"""Segment one received sequence for B4d, then decode once with B5b."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Integral, Real
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.encoder import INITIAL_STATE, State
from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.decoding.reconstruction_viterbi import decode_reconstruction_viterbi
from hf_tcm.receiver.reconstruction_conditional_decode import (
    ReconstructionConditionalDecodeResult,
    ReconstructionMetricRowProvenance,
)
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_observation import (
    ADR012_PROFILE_ID,
    ADR012_SAMPLES_PER_SYMBOL,
)
from hf_tcm.receiver.reconstruction_posterior import build_initial_reconstruction_prior
from hf_tcm.receiver.reconstruction_posterior_estimator_sequence import (
    ReconstructionPosteriorEstimatorSequenceResult,
    run_reconstruction_posterior_estimator_sequence,
)

FloatArray = NDArray[np.float64]
BitArray = NDArray[np.int8]
EdgeMode = Literal["first_edge", "later_edge"]
_HYPOTHESIS_IDS = tuple(hypothesis.hypothesis_id for hypothesis in HYPOTHESES)


def _integer(value: object, *, name: str, minimum: int | None = None) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")
    result = int(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return result


def _readonly_array(value: ArrayLike, *, shape: tuple[int, ...], name: str) -> FloatArray:
    try:
        raw = np.asarray(value)
        if np.iscomplexobj(raw) or raw.dtype.kind not in "iuf":
            raise ValueError
        result = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite real values with shape {shape}") from exc
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite real values with shape {shape}")
    owned = np.array(result, dtype=np.float64, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=np.float64).reshape(shape)


def _alpha_values(value: Real | Sequence[Real], *, count: int) -> tuple[float, ...] | float:
    if isinstance(value, Real) and not isinstance(value, (bool, np.bool_)):
        scalar = float(value)
        if not math.isfinite(scalar):
            raise ValueError("alpha_prime must be finite")
        return scalar
    try:
        raw = np.asarray(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("alpha_prime must be a scalar or a complete per-symbol schedule") from exc
    if raw.shape != (count,) or raw.dtype.kind not in "iuf":
        raise ValueError(f"alpha_prime schedule must have shape ({count},)")
    values = tuple(float(item) for item in raw)
    if not all(math.isfinite(item) for item in values):
        raise ValueError("alpha_prime schedule must contain only finite values")
    return values


def _iq_values(value: ArrayLike, *, name: str, count: int) -> FloatArray | tuple[FloatArray, ...]:
    try:
        raw = np.asarray(value)
        if np.iscomplexobj(raw) or raw.dtype.kind not in "iuf":
            raise ValueError
        values = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must have shape (1, 2) or ({count}, 1, 2)") from exc
    if values.shape == (1, 2):
        if not np.all(np.isfinite(values)):
            raise ValueError(f"{name} values must be finite")
        return np.array(values, dtype=np.float64, copy=True)
    if values.shape != (count, 1, 2) or not np.all(np.isfinite(values)):
        raise ValueError(f"{name} must have shape (1, 2) or ({count}, 1, 2) with finite values")
    return tuple(np.array(values[index], dtype=np.float64, copy=True) for index in range(count))


@dataclass(frozen=True, slots=True)
class ReconstructionSequenceSegment:
    """One nonempty segment; offset is measured in samples in the received buffer."""

    first_symbol_index: int
    received_start_offset: int
    symbol_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "first_symbol_index",
            _integer(self.first_symbol_index, name="first_symbol_index", minimum=0),
        )
        object.__setattr__(
            self,
            "received_start_offset",
            _integer(self.received_start_offset, name="received_start_offset", minimum=0),
        )
        object.__setattr__(
            self,
            "symbol_count",
            _integer(self.symbol_count, name="symbol_count", minimum=1),
        )


@dataclass(frozen=True, slots=True)
class ReconstructionSegmentBoundary:
    """Absolute clocks and half-open buffer/sequence bounds for one segment."""

    segment_index: int
    first_symbol_index: int
    last_symbol_index: int
    received_start_offset: int
    received_stop_offset: int
    first_sample_index: int
    last_sample_index: int
    sequence_start_position: int
    sequence_stop_position: int
    first_estimator_time_index: int
    final_estimator_time_index: int


@dataclass(frozen=True, slots=True)
class ReconstructionSegmentSymbolLabel:
    """Independent time and position labels for one B4d-processed symbol."""

    absolute_symbol_index: int
    estimator_time_index: int
    segment_index: int
    segment_local_position: int
    sequence_position: int
    first_sample_index: int
    last_sample_index: int
    prediction_cutoff_sample_index: int
    observation_cutoff_sample_index: int
    hypothesis_ids: tuple[int, ...]
    edge_mode: EdgeMode


@dataclass(frozen=True, slots=True)
class ReconstructionSegmentedDecodeResult:
    """Immutable result for a segmented B4d pass and one final B5b decode."""

    decode_result: ReconstructionConditionalDecodeResult
    posterior_history: FloatArray
    segment_boundaries: tuple[ReconstructionSegmentBoundary, ...]
    symbol_schedule: tuple[ReconstructionSegmentSymbolLabel, ...]

    def __post_init__(self) -> None:
        count = len(self.symbol_schedule)
        posterior_history = _readonly_array(
            self.posterior_history,
            shape=(count, len(HYPOTHESES)),
            name="posterior_history",
        )
        if np.any(posterior_history < 0.0) or not np.allclose(
            np.sum(posterior_history, axis=1), 1.0, rtol=0.0, atol=1e-10
        ):
            raise ValueError("posterior_history must contain normalized probability rows")
        object.__setattr__(
            self,
            "posterior_history",
            posterior_history,
        )
        if len(self.segment_boundaries) == 0 or count == 0:
            raise ValueError("segmented result must contain symbols and segment boundaries")
        if not np.array_equal(self.posterior_history[-1], self.decode_result.final_posterior):
            raise ValueError("posterior_history final row must equal final_posterior")

    @property
    def candidate_metrics(self) -> FloatArray:
        return self.decode_result.candidate_metrics

    @property
    def decoded_input_pairs(self) -> NDArray[np.int8]:
        return self.decode_result.decoded_input_pairs

    @property
    def decoded_information_bits(self) -> BitArray:
        return self.decode_result.decoded_information_bits

    @property
    def decoded_hypothesis_path(self) -> tuple[int, ...]:
        return self.decode_result.decoded_hypothesis_path

    @property
    def best_conditional_path_cost(self) -> float:
        return self.decode_result.best_conditional_path_cost

    @property
    def final_encoder_state(self) -> State:
        return self.decode_result.final_encoder_state

    @property
    def final_estimator_state(self) -> ReconstructionEstimatorState:
        return self.decode_result.final_estimator_state

    @property
    def final_posterior(self) -> FloatArray:
        return self.decode_result.final_posterior

    @property
    def metric_provenance(self) -> tuple[ReconstructionMetricRowProvenance, ...]:
        return self.decode_result.metric_provenance

    @property
    def hypothesis_order(self) -> tuple[int, ...]:
        return self.decode_result.hypothesis_order

    @property
    def symbol_indices(self) -> tuple[int, ...]:
        return self.decode_result.symbol_indices

    @property
    def estimator_time_indices(self) -> tuple[int, ...]:
        return self.decode_result.estimator_time_indices

    @property
    def prediction_cutoff_sample_indices(self) -> tuple[int, ...]:
        return self.decode_result.prediction_cutoff_sample_indices

    @property
    def observation_cutoff_sample_indices(self) -> tuple[int, ...]:
        return self.decode_result.observation_cutoff_sample_indices


def _scheduled_alpha(
    schedule: tuple[float, ...] | float, *, start: int, stop: int
) -> tuple[float, ...] | float:
    return schedule if isinstance(schedule, float) else schedule[start:stop]


def _scheduled_iq(
    schedule: FloatArray | tuple[FloatArray, ...], *, start: int, stop: int
) -> FloatArray:
    if isinstance(schedule, tuple):
        return np.stack(schedule[start:stop], axis=0)
    return schedule


def _extract_segment_history(
    sequence: ReconstructionPosteriorEstimatorSequenceResult,
    *,
    segment: ReconstructionSequenceSegment,
    segment_index: int,
    sequence_start_position: int,
    symbol_origin_sample: int,
    sequence_origin_symbol_index: int,
    first_estimator_time_index: int,
    first_run: bool,
) -> tuple[
    list[FloatArray],
    list[FloatArray],
    list[ReconstructionMetricRowProvenance],
    list[ReconstructionSegmentSymbolLabel],
]:
    history = sequence.history
    if history is None or len(history) != segment.symbol_count:
        raise ValueError("B4d must return one immutable history entry per segment symbol")
    expected_mode = "new_independent_sequence" if first_run else "continuation"
    if sequence.run_mode != expected_mode or sequence.symbol_count != segment.symbol_count:
        raise ValueError("B4d segment mode or symbol count does not match the segment contract")
    if sequence.sequence_origin_symbol_index != sequence_origin_symbol_index:
        raise ValueError("B4d changed the independent sequence origin")
    if sequence.first_symbol_index != segment.first_symbol_index:
        raise ValueError("B4d segment first symbol index changed")

    metric_rows: list[FloatArray] = []
    posterior_rows: list[FloatArray] = []
    metric_provenance: list[ReconstructionMetricRowProvenance] = []
    schedule: list[ReconstructionSegmentSymbolLabel] = []
    for local_position, entry in enumerate(history):
        symbol = segment.first_symbol_index + local_position
        estimator_time = first_estimator_time_index + local_position
        first_sample = symbol_origin_sample + ADR012_SAMPLES_PER_SYMBOL * symbol
        last_sample = first_sample + ADR012_SAMPLES_PER_SYMBOL - 1
        candidate = entry.b4c_result.candidate_result
        edge_mode: EdgeMode = "first_edge" if first_run and local_position == 0 else "later_edge"
        if entry.symbol_index != symbol or candidate.target_symbol_index != symbol:
            raise ValueError("B4d history symbol labels are not contiguous within the segment")
        if (
            entry.estimator_time_index != estimator_time
            or candidate.estimator_time_index != estimator_time
        ):
            raise ValueError("B4d history estimator clock is not continuous within the segment")
        if entry.first_sample_index != first_sample or entry.last_sample_index != last_sample:
            raise ValueError("B4d history sample bounds do not match the absolute symbol window")
        if entry.b4c_result.edge_mode != edge_mode:
            raise ValueError("B4d repeated or skipped first-edge initialization")
        if candidate.hypothesis_ids != _HYPOTHESIS_IDS:
            raise ValueError("B4d metric columns do not use canonical HYPOTHESES order")
        expected_samples = tuple(range(first_sample, last_sample + 1))
        if candidate.sample_indices != expected_samples:
            raise ValueError("B4d candidate samples do not match the segment's absolute window")
        if candidate.prediction_cutoff_sample_index != first_sample - 1:
            raise ValueError("B4d prediction cutoff does not match the segment symbol")
        if candidate.metric_available_after_sample_index != last_sample:
            raise ValueError("B4d observation cutoff does not match the segment symbol")
        if (
            candidate.profile != "reconstructed_offline"
            or candidate.profile_id != ADR012_PROFILE_ID
        ):
            raise ValueError("B4d metric row lacks the accepted ADR-012 profile provenance")
        metrics = np.asarray(candidate.metrics, dtype=np.float64)
        posterior = np.asarray(entry.b4c_result.posterior, dtype=np.float64)
        if (
            metrics.shape != (len(HYPOTHESES),)
            or not np.all(np.isfinite(metrics))
            or np.any(metrics < 0.0)
        ):
            raise ValueError("B4d candidate metrics must be finite nonnegative shape (16,)")
        if posterior.shape != (len(HYPOTHESES),) or not np.all(np.isfinite(posterior)):
            raise ValueError("B4d posterior must be finite shape (16,)")
        metric_rows.append(metrics)
        posterior_rows.append(posterior)
        metric_provenance.append(
            ReconstructionMetricRowProvenance(
                absolute_symbol_index=symbol,
                estimator_time_index=estimator_time,
                sample_indices=candidate.sample_indices,
                prediction_cutoff_sample_index=candidate.prediction_cutoff_sample_index,
                observation_cutoff_sample_index=candidate.metric_available_after_sample_index,
                hypothesis_ids=candidate.hypothesis_ids,
                profile=candidate.profile,
                profile_id=candidate.profile_id,
            )
        )
        schedule.append(
            ReconstructionSegmentSymbolLabel(
                absolute_symbol_index=symbol,
                estimator_time_index=estimator_time,
                segment_index=segment_index,
                segment_local_position=local_position,
                sequence_position=sequence_start_position + local_position,
                first_sample_index=first_sample,
                last_sample_index=last_sample,
                prediction_cutoff_sample_index=first_sample - 1,
                observation_cutoff_sample_index=last_sample,
                hypothesis_ids=candidate.hypothesis_ids,
                edge_mode=edge_mode,
            )
        )
    return metric_rows, posterior_rows, metric_provenance, schedule


def decode_reconstruction_segmented_sequence(
    *,
    received: ArrayLike,
    absolute_sample_indices: ArrayLike,
    received_start_sample: int,
    symbol_origin_sample: int,
    sequence_origin_symbol_index: int,
    initial_estimator_state: ReconstructionEstimatorState,
    initial_estimator_time_index: int,
    initial_encoder_state: State,
    segments: Sequence[ReconstructionSequenceSegment],
    beta: Real,
    alpha_prime: Real | Sequence[Real],
    k_tilde: ArrayLike,
    mu0: ArrayLike,
    profile: str,
    adr_profile: str,
    path_count: int,
    path_delays_samples: Sequence[int],
    samples_per_symbol: int,
    iq_rule: str,
    waveform_rule: str,
    labeling_profile: str,
    bit_order: Sequence[str],
    timebase_profile: str,
    symbol_to_sample_rule: str,
    edge_policy: str,
) -> ReconstructionSegmentedDecodeResult:
    """Process contiguous buffer segments with B4d continuation, then decode once.

    Segment offsets are sample offsets into one received buffer. Segments must
    partition it exactly and label one uninterrupted absolute symbol sequence.
    Only the first segment starts an independent sequence; all later segments
    continue its estimator/posterior clocks. B5b is invoked once after the
    final segment has returned.
    """
    if not isinstance(initial_estimator_state, ReconstructionEstimatorState):
        raise ValueError("initial_estimator_state must be a ReconstructionEstimatorState")
    first_time = _integer(initial_estimator_time_index, name="initial_estimator_time_index")
    if first_time != initial_estimator_state.time_index:
        raise ValueError("initial_estimator_time_index must match the initial state timestamp")
    sequence_origin = _integer(
        sequence_origin_symbol_index, name="sequence_origin_symbol_index", minimum=0
    )
    origin = _integer(symbol_origin_sample, name="symbol_origin_sample")
    received_start = _integer(received_start_sample, name="received_start_sample")
    if (
        not isinstance(initial_encoder_state, Sequence)
        or isinstance(initial_encoder_state, (str, bytes))
        or len(initial_encoder_state) != 2
        or any(type(bit) is not int or bit not in (0, 1) for bit in initial_encoder_state)
        or tuple(initial_encoder_state) != INITIAL_STATE
    ):
        raise ValueError("initial_encoder_state must be ADR-004 state (0, 0)")
    if not isinstance(segments, Sequence) or isinstance(segments, (str, bytes)) or not segments:
        raise ValueError("segments must be a nonempty ordered sequence")
    if any(not isinstance(segment, ReconstructionSequenceSegment) for segment in segments):
        raise ValueError("every segment must be a ReconstructionSequenceSegment")

    total_symbols = sum(segment.symbol_count for segment in segments)
    first_symbol = segments[0].first_symbol_index
    if first_symbol != sequence_origin:
        raise ValueError("first segment must begin at sequence_origin_symbol_index")
    if received_start != origin + ADR012_SAMPLES_PER_SYMBOL * first_symbol:
        raise ValueError("received_start_sample must equal O + 8*first absolute symbol index")

    expected_symbol = first_symbol
    expected_offset = 0
    for segment in segments:
        if segment.first_symbol_index != expected_symbol:
            raise ValueError("segment symbol labels contain a duplicate or gap")
        if segment.received_start_offset != expected_offset:
            raise ValueError("segments overlap or leave a received-buffer gap")
        expected_symbol += segment.symbol_count
        expected_offset += segment.symbol_count * ADR012_SAMPLES_PER_SYMBOL

    try:
        samples = np.asarray(received)
        labels = np.asarray(absolute_sample_indices)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("received and absolute_sample_indices must be arrays") from exc
    if samples.ndim != 1 or not np.iscomplexobj(samples):
        raise ValueError("received must be a one-dimensional complex buffer")
    if samples.shape != (expected_offset,):
        raise ValueError("received must contain exactly 8 samples for every segmented symbol")
    if not np.all(np.isfinite(samples.real)) or not np.all(np.isfinite(samples.imag)):
        raise ValueError("received samples must be finite")
    if labels.shape != samples.shape or labels.dtype.kind not in "iu":
        raise ValueError("absolute_sample_indices must provide one integer label per sample")
    expected_labels = np.arange(received_start, received_start + expected_offset, dtype=np.int64)
    if not np.array_equal(labels, expected_labels):
        raise ValueError("absolute_sample_indices must be contiguous and ordered")

    alphas = _alpha_values(alpha_prime, count=total_symbols)
    gains = _iq_values(k_tilde, name="k_tilde", count=total_symbols)
    regular_values = _iq_values(mu0, name="mu0", count=total_symbols)
    if not isinstance(beta, Real) or isinstance(beta, (bool, np.bool_)):
        raise ValueError("beta must be a finite real value > 0")
    try:
        beta_value = float(beta)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("beta must be a finite real value > 0") from exc
    if not math.isfinite(beta_value) or beta_value <= 0.0:
        raise ValueError("beta must be a finite real value > 0")

    prior = build_initial_reconstruction_prior(initial_state=INITIAL_STATE)
    current_state = initial_estimator_state
    current_posterior: FloatArray | None = None
    previous_sequence: ReconstructionPosteriorEstimatorSequenceResult | None = None
    metric_rows: list[FloatArray] = []
    posterior_rows: list[FloatArray] = []
    metric_provenance: list[ReconstructionMetricRowProvenance] = []
    symbol_schedule: list[ReconstructionSegmentSymbolLabel] = []
    boundaries: list[ReconstructionSegmentBoundary] = []
    sequence_position = 0

    for segment_index, segment in enumerate(segments):
        sample_count = segment.symbol_count * ADR012_SAMPLES_PER_SYMBOL
        buffer_start = segment.received_start_offset
        buffer_stop = buffer_start + sample_count
        segment_symbols = tuple(
            range(segment.first_symbol_index, segment.first_symbol_index + segment.symbol_count)
        )
        run_mode = "new_independent_sequence" if segment_index == 0 else "continuation"
        sequence = run_reconstruction_posterior_estimator_sequence(
            received=samples[buffer_start:buffer_stop],
            absolute_sample_indices=labels[buffer_start:buffer_stop],
            received_start_sample=received_start + buffer_start,
            symbol_origin_sample=origin,
            first_symbol_index=segment.first_symbol_index,
            sequence_origin_symbol_index=sequence_origin,
            symbol_count=segment.symbol_count,
            symbol_indices=segment_symbols,
            initial_state=current_state,
            initial_estimator_time_index=current_state.time_index,
            run_mode=run_mode,
            initial_prior=prior if segment_index == 0 else None,
            previous_posterior=current_posterior,
            continuation_from_symbol_index=(
                None if previous_sequence is None else previous_sequence.final_symbol_index
            ),
            continuation_from_estimator_time_index=(
                None
                if previous_sequence is None
                else previous_sequence.final_estimator_time_index - 1
            ),
            beta=beta_value,
            alpha_prime=_scheduled_alpha(
                alphas, start=sequence_position, stop=sequence_position + segment.symbol_count
            ),
            k_tilde=_scheduled_iq(
                gains, start=sequence_position, stop=sequence_position + segment.symbol_count
            ),
            mu0=_scheduled_iq(
                regular_values,
                start=sequence_position,
                stop=sequence_position + segment.symbol_count,
            ),
            include_history=True,
            profile=profile,
            adr_profile=adr_profile,
            path_count=path_count,
            path_delays_samples=path_delays_samples,
            samples_per_symbol=samples_per_symbol,
            iq_rule=iq_rule,
            waveform_rule=waveform_rule,
            labeling_profile=labeling_profile,
            bit_order=bit_order,
            timebase_profile=timebase_profile,
            symbol_to_sample_rule=symbol_to_sample_rule,
            edge_policy=edge_policy,
        )
        if sequence.final_state.time_index != sequence.final_estimator_time_index:
            raise ValueError("B4d final state and estimator clock disagree")
        if sequence.final_estimator_time_index != current_state.time_index + segment.symbol_count:
            raise ValueError("B4d segment did not advance estimator time once per symbol")
        rows, posteriors, provenance, labels_for_symbols = _extract_segment_history(
            sequence,
            segment=segment,
            segment_index=segment_index,
            sequence_start_position=sequence_position,
            symbol_origin_sample=origin,
            sequence_origin_symbol_index=sequence_origin,
            first_estimator_time_index=current_state.time_index,
            first_run=segment_index == 0,
        )
        metric_rows.extend(rows)
        posterior_rows.extend(posteriors)
        metric_provenance.extend(provenance)
        symbol_schedule.extend(labels_for_symbols)
        boundaries.append(
            ReconstructionSegmentBoundary(
                segment_index=segment_index,
                first_symbol_index=segment.first_symbol_index,
                last_symbol_index=segment_symbols[-1],
                received_start_offset=buffer_start,
                received_stop_offset=buffer_stop,
                first_sample_index=received_start + buffer_start,
                last_sample_index=received_start + buffer_stop - 1,
                sequence_start_position=sequence_position,
                sequence_stop_position=sequence_position + segment.symbol_count,
                first_estimator_time_index=sequence.initial_estimator_time_index,
                final_estimator_time_index=sequence.final_estimator_time_index,
            )
        )
        current_state = sequence.final_state
        current_posterior = sequence.final_posterior
        previous_sequence = sequence
        sequence_position += segment.symbol_count

    if current_posterior is None or previous_sequence is None:
        raise RuntimeError("nonempty segmentation did not produce an estimator result")
    frozen_metrics = np.stack(metric_rows, axis=0)
    posterior_history = np.stack(posterior_rows, axis=0)
    ordered_symbols = tuple(item.absolute_symbol_index for item in symbol_schedule)
    ordered_times = tuple(item.estimator_time_index for item in symbol_schedule)
    decoder = decode_reconstruction_viterbi(
        frozen_metrics,
        hypotheses=HYPOTHESES,
        initial_state=INITIAL_STATE,
        sequence_mode="new_independent_sequence",
        profile="reconstructed_offline",
        edge_indices=tuple(range(total_symbols)),
        symbol_indices=ordered_symbols,
        estimator_time_indices=ordered_times,
    )
    combined = ReconstructionConditionalDecodeResult(
        decoder_result=decoder,
        final_estimator_state=current_state,
        final_posterior=current_posterior,
        candidate_metrics=frozen_metrics,
        metric_provenance=tuple(metric_provenance),
        profile="reconstructed_offline",
    )
    return ReconstructionSegmentedDecodeResult(
        decode_result=combined,
        posterior_history=posterior_history,
        segment_boundaries=tuple(boundaries),
        symbol_schedule=tuple(symbol_schedule),
    )
