"""Isolated end-to-end single-path reconstruction and conditional decoding."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Real
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.encoder import INITIAL_STATE, State
from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.decoding.reconstruction_viterbi import (
    ReconstructionViterbiResult,
    decode_reconstruction_viterbi,
)
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_observation import ADR012_PROFILE_ID
from hf_tcm.receiver.reconstruction_posterior import build_initial_reconstruction_prior
from hf_tcm.receiver.reconstruction_posterior_estimator_sequence import (
    ReconstructionPosteriorEstimatorSequenceResult,
    run_reconstruction_posterior_estimator_sequence,
)

FloatArray = NDArray[np.float64]
BitArray = NDArray[np.int8]
SequenceMode = Literal["new_independent_sequence", "continuation"]
_HYPOTHESIS_IDS = tuple(hypothesis.hypothesis_id for hypothesis in HYPOTHESES)


def _readonly_float_matrix(value: ArrayLike, *, shape: tuple[int, int]) -> FloatArray:
    try:
        raw = np.asarray(value)
        if np.iscomplexobj(raw) or raw.dtype.kind not in "iuf":
            raise ValueError
        matrix = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            f"candidate_metrics must be a finite real matrix with shape {shape}"
        ) from exc
    if matrix.shape != shape or not np.all(np.isfinite(matrix)) or np.any(matrix < 0.0):
        raise ValueError(f"candidate_metrics must be finite, non-negative, and have shape {shape}")
    owned = np.array(matrix, dtype=np.float64, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=np.float64).reshape(shape)


def _readonly_posterior(value: ArrayLike) -> FloatArray:
    try:
        raw = np.asarray(value)
        if np.iscomplexobj(raw) or raw.dtype.kind not in "iuf":
            raise ValueError
        posterior = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("final_posterior must be a finite real normalized vector (16,)") from exc
    if posterior.shape != (16,) or not np.all(np.isfinite(posterior)) or np.any(posterior < 0.0):
        raise ValueError("final_posterior must be a finite real normalized vector (16,)")
    if not math.isclose(
        math.fsum(float(value) for value in posterior), 1.0, rel_tol=1e-10, abs_tol=1e-10
    ):
        raise ValueError("final_posterior must be normalized")
    owned = np.array(posterior, dtype=np.float64, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=np.float64)


@dataclass(frozen=True, slots=True)
class ReconstructionMetricRowProvenance:
    """B4c provenance copied from the exact metric result used at one step."""

    absolute_symbol_index: int
    estimator_time_index: int
    sample_indices: tuple[int, ...]
    prediction_cutoff_sample_index: int
    observation_cutoff_sample_index: int
    hypothesis_ids: tuple[int, ...]
    profile: str
    profile_id: str


@dataclass(frozen=True, slots=True)
class ReconstructionConditionalDecodeResult:
    """Immutable received-to-decoded-bits result for one independent sequence.

    ``candidate_metrics`` is the exact `(F,16)` copy of the per-symbol B4c
    metric rows used by B4a. The wrapped Viterbi result contains immutable
    input-pair `(F,2)` and information-bit `(2F,)` arrays.
    """

    decoder_result: ReconstructionViterbiResult
    final_estimator_state: ReconstructionEstimatorState
    final_posterior: FloatArray
    candidate_metrics: FloatArray
    metric_provenance: tuple[ReconstructionMetricRowProvenance, ...]
    profile: Literal["reconstructed_offline"]

    def __post_init__(self) -> None:
        count = len(self.metric_provenance)
        object.__setattr__(
            self,
            "candidate_metrics",
            _readonly_float_matrix(self.candidate_metrics, shape=(count, len(HYPOTHESES))),
        )
        object.__setattr__(self, "final_posterior", _readonly_posterior(self.final_posterior))
        if self.profile != "reconstructed_offline":
            raise ValueError("profile must be 'reconstructed_offline'")

    @property
    def decoded_information_bits(self) -> BitArray:
        return self.decoder_result.decoded_bits

    @property
    def decoded_input_pairs(self) -> NDArray[np.int8]:
        return self.decoder_result.input_pairs

    @property
    def decoded_hypothesis_path(self) -> tuple[int, ...]:
        return self.decoder_result.hypothesis_ids

    @property
    def best_conditional_path_cost(self) -> float:
        return self.decoder_result.best_path_metric

    @property
    def final_encoder_state(self) -> State:
        return self.decoder_result.final_state

    @property
    def hypothesis_order(self) -> tuple[int, ...]:
        return self.decoder_result.hypothesis_order

    @property
    def symbol_indices(self) -> tuple[int, ...]:
        return tuple(row.absolute_symbol_index for row in self.metric_provenance)

    @property
    def estimator_time_indices(self) -> tuple[int, ...]:
        return tuple(row.estimator_time_index for row in self.metric_provenance)

    @property
    def final_estimator_time_index(self) -> int:
        return self.final_estimator_state.time_index

    @property
    def final_completed_symbol_index(self) -> int:
        return self.metric_provenance[-1].absolute_symbol_index

    @property
    def prediction_cutoff_sample_indices(self) -> tuple[int, ...]:
        return tuple(row.prediction_cutoff_sample_index for row in self.metric_provenance)

    @property
    def observation_cutoff_sample_indices(self) -> tuple[int, ...]:
        return tuple(row.observation_cutoff_sample_index for row in self.metric_provenance)


def _validated_initial_encoder_state(value: State) -> State:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) != 2
        or any(type(bit) is not int or bit not in (0, 1) for bit in value)
        or tuple(value) != INITIAL_STATE
    ):
        raise ValueError("initial_encoder_state must be the ADR-004 independent state (0, 0)")
    return INITIAL_STATE


def _metric_rows_from_history(
    sequence: ReconstructionPosteriorEstimatorSequenceResult,
    *,
    symbol_origin_sample: int,
    expected_symbols: tuple[int, ...],
    initial_estimator_time_index: int,
) -> tuple[FloatArray, tuple[ReconstructionMetricRowProvenance, ...]]:
    history = sequence.history
    if history is None or len(history) != len(expected_symbols):
        raise ValueError("B4d must return immutable per-symbol history for every processed symbol")
    if sequence.run_mode != "new_independent_sequence":
        raise ValueError("conditional decoding requires a complete new independent B4d sequence")
    if sequence.symbol_count != len(expected_symbols):
        raise ValueError("B4d symbol_count does not match the requested metric-row count")

    rows: list[FloatArray] = []
    provenance: list[ReconstructionMetricRowProvenance] = []
    for offset, (entry, symbol) in enumerate(zip(history, expected_symbols, strict=True)):
        step = entry.b4c_result
        candidate = step.candidate_result
        estimator_time = initial_estimator_time_index + offset
        first_sample = symbol_origin_sample + 8 * symbol
        last_sample = first_sample + 7
        expected_sample_indices = tuple(range(first_sample, last_sample + 1))
        if entry.symbol_index != symbol or candidate.target_symbol_index != symbol:
            raise ValueError("B4d metric row symbol label does not match its requested row")
        if (
            entry.estimator_time_index != estimator_time
            or candidate.estimator_time_index != estimator_time
        ):
            raise ValueError("B4d metric row estimator-time label does not match its requested row")
        if candidate.hypothesis_ids != _HYPOTHESIS_IDS or step.hypothesis_ids != _HYPOTHESIS_IDS:
            raise ValueError("B4d metric row must use canonical HYPOTHESES order")
        if candidate.sample_indices != expected_sample_indices:
            raise ValueError("B4d metric row sample labels do not match the absolute symbol window")
        if candidate.prediction_cutoff_sample_index != first_sample - 1:
            raise ValueError("B4d metric row prediction cutoff is inconsistent")
        if candidate.metric_available_after_sample_index != last_sample:
            raise ValueError("B4d metric row observation cutoff is inconsistent")
        if (
            candidate.profile != "reconstructed_offline"
            or candidate.profile_id != ADR012_PROFILE_ID
        ):
            raise ValueError("B4d metric row lacks the accepted reconstructed ADR-012 provenance")
        metrics = np.asarray(candidate.metrics, dtype=np.float64)
        if (
            metrics.shape != (len(HYPOTHESES),)
            or not np.all(np.isfinite(metrics))
            or np.any(metrics < 0.0)
        ):
            raise ValueError("B4d candidate metric row must be finite nonnegative shape (16,)")
        rows.append(metrics)
        provenance.append(
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
    matrix = np.stack(rows, axis=0)
    return _readonly_float_matrix(matrix, shape=(len(expected_symbols), len(HYPOTHESES))), tuple(
        provenance
    )


def decode_reconstruction_conditional_sequence(
    *,
    received: ArrayLike,
    absolute_sample_indices: ArrayLike,
    received_start_sample: int,
    symbol_origin_sample: int,
    first_symbol_index: int,
    sequence_origin_symbol_index: int,
    symbol_count: int,
    symbol_indices: Sequence[int],
    initial_estimator_state: ReconstructionEstimatorState,
    initial_estimator_time_index: int,
    initial_encoder_state: State,
    sequence_mode: SequenceMode,
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
) -> ReconstructionConditionalDecodeResult:
    """Run B4d once, freeze the metrics it used, then run B5b once.

    This entry point accepts only a complete independent sequence starting at
    its trellis origin. Split-run continuation can be performed through B4d,
    but this adapter does not stitch continuation fragments or reset a decoder
    at frame boundaries.
    """
    if sequence_mode != "new_independent_sequence":
        raise ValueError("conditional decoding requires sequence_mode='new_independent_sequence'")
    encoder_state = _validated_initial_encoder_state(initial_encoder_state)
    try:
        count = int(symbol_count)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("symbol_count must be a positive integer") from exc
    if isinstance(symbol_count, bool) or count != symbol_count or count < 1:
        raise ValueError("symbol_count must be a positive integer")
    try:
        symbols = tuple(int(value) for value in symbol_indices)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("symbol_indices must explicitly label every symbol") from exc
    if len(symbols) != count or any(
        isinstance(value, (bool, np.bool_)) or int(value) != value for value in symbol_indices
    ):
        raise ValueError("symbol_indices must contain exactly symbol_count integer labels")
    if symbols != tuple(range(first_symbol_index, first_symbol_index + count)):
        raise ValueError(
            "symbol_indices must be contiguous and ordered for one independent sequence"
        )
    if first_symbol_index != sequence_origin_symbol_index:
        raise ValueError("first_symbol_index must equal the sequence origin symbol index")

    sequence = run_reconstruction_posterior_estimator_sequence(
        received=received,
        absolute_sample_indices=absolute_sample_indices,
        received_start_sample=received_start_sample,
        symbol_origin_sample=symbol_origin_sample,
        first_symbol_index=first_symbol_index,
        sequence_origin_symbol_index=sequence_origin_symbol_index,
        symbol_count=count,
        symbol_indices=symbols,
        initial_state=initial_estimator_state,
        initial_estimator_time_index=initial_estimator_time_index,
        run_mode="new_independent_sequence",
        initial_prior=build_initial_reconstruction_prior(initial_state=encoder_state),
        previous_posterior=None,
        continuation_from_symbol_index=None,
        continuation_from_estimator_time_index=None,
        beta=beta,
        alpha_prime=alpha_prime,
        k_tilde=k_tilde,
        mu0=mu0,
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
    frozen_metrics, provenance = _metric_rows_from_history(
        sequence,
        symbol_origin_sample=symbol_origin_sample,
        expected_symbols=symbols,
        initial_estimator_time_index=initial_estimator_time_index,
    )
    if sequence.final_state.time_index != sequence.final_estimator_time_index:
        raise ValueError("B4d final state timestamp and final estimator-time label disagree")
    estimator_labels = tuple(row.estimator_time_index for row in provenance)
    decoder_result = decode_reconstruction_viterbi(
        frozen_metrics,
        hypotheses=HYPOTHESES,
        initial_state=encoder_state,
        sequence_mode="new_independent_sequence",
        profile="reconstructed_offline",
        edge_indices=tuple(range(count)),
        symbol_indices=symbols,
        estimator_time_indices=estimator_labels,
    )
    return ReconstructionConditionalDecodeResult(
        decoder_result=decoder_result,
        final_estimator_state=sequence.final_state,
        final_posterior=sequence.final_posterior,
        candidate_metrics=frozen_metrics,
        metric_provenance=provenance,
        profile="reconstructed_offline",
    )
