"""Isolated single-symbol candidate, posterior, and estimator state step."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Integral, Real
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.receiver.iq_prediction import iq_quadratures_from_index
from hf_tcm.receiver.reconstruction_candidate_metrics import (
    ReconstructionCandidateMetricResult,
    generate_reconstruction_candidate_metrics,
)
from hf_tcm.receiver.reconstruction_causal_step import (
    CausalOnePathSymbolStep,
    advance_real_one_path_symbol,
)
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_forward_snapshot import snapshot_full_iq_for_forward
from hf_tcm.receiver.reconstruction_labeling import (
    hypothesis_to_phase_index,
)
from hf_tcm.receiver.reconstruction_observation import (
    ADR012_PROFILE,
    ADR012_PROFILE_ID,
    ADR012_SAMPLES_PER_SYMBOL,
)
from hf_tcm.receiver.reconstruction_posterior import (
    initial_reconstruction_observation_update,
    transition_reconstruction_posterior,
)

FloatArray = NDArray[np.float64]
EdgeMode = Literal["first_edge", "later_edge"]
_HYPOTHESIS_IDS = tuple(hypothesis.hypothesis_id for hypothesis in HYPOTHESES)


def _readonly_float_array(value: ArrayLike, *, shape: tuple[int, ...], name: str) -> FloatArray:
    try:
        raw = np.asarray(value)
        if np.iscomplexobj(raw):
            raise ValueError
        result = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real array with shape {shape}") from exc
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite real array with shape {shape}")
    owned = np.array(result, dtype=np.float64, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=np.float64).reshape(shape)


def _absolute_index(value: object, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer absolute index")
    return int(value)


@dataclass(frozen=True, slots=True)
class ReconstructionPosteriorEstimatorStepResult:
    """One explicit, causal single-path update and immutable diagnostics."""

    candidate_result: ReconstructionCandidateMetricResult
    posterior: FloatArray
    predicted_iq: FloatArray
    causal_step: CausalOnePathSymbolStep
    edge_mode: EdgeMode

    def __post_init__(self) -> None:
        posterior = _readonly_float_array(
            self.posterior, shape=(len(HYPOTHESES),), name="posterior"
        )
        predicted = _readonly_float_array(
            self.predicted_iq,
            shape=(len(HYPOTHESES), 2),
            name="predicted_iq",
        )
        object.__setattr__(self, "posterior", posterior)
        object.__setattr__(self, "predicted_iq", predicted)

    @property
    def next_state(self) -> ReconstructionEstimatorState:
        return self.causal_step.next_state

    @property
    def observed_iq(self) -> FloatArray:
        return self.causal_step.observed_iq

    @property
    def hypothesis_ids(self) -> tuple[int, ...]:
        return self.candidate_result.hypothesis_ids

    @property
    def available_after_sample_index(self) -> int:
        return self.causal_step.available_after_sample_index

    @property
    def prediction_data_cutoff_sample(self) -> int:
        return self.causal_step.prediction_data_cutoff_sample

    @property
    def posterior_data_cutoff_sample(self) -> int:
        return self.causal_step.posterior_data_cutoff_sample

    @property
    def next_usable_symbol_index(self) -> int:
        return self.causal_step.next_usable_symbol_index


def process_reconstruction_posterior_estimator_step(
    *,
    received: ArrayLike,
    absolute_sample_indices: ArrayLike,
    received_start_sample: int,
    symbol_origin_sample: int,
    target_symbol_index: int,
    state: ReconstructionEstimatorState,
    time_index: int,
    edge_mode: EdgeMode,
    initial_prior: ArrayLike | None,
    previous_posterior: ArrayLike | None,
    beta: Real,
    alpha_prime: Real,
    k_tilde: ArrayLike,
    mu0: ArrayLike,
    prediction_data_cutoff_sample: int,
    posterior_data_cutoff_sample: int,
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
) -> ReconstructionPosteriorEstimatorStepResult:
    """Process one complete symbol through B4b, B4a, and the causal [A](1) step.

    The caller explicitly selects ``first_edge`` (initial edge prior, no
    transition) or ``later_edge`` (previous edge posterior, transition then
    current metric). All clocks, cutoffs, profile conventions, posterior
    inputs, and estimator parameters are required operands. No receiver loop,
    observation inference, or hidden defaults are introduced.
    """
    if edge_mode not in ("first_edge", "later_edge"):
        raise ValueError("edge_mode must be 'first_edge' or 'later_edge'")
    if edge_mode == "first_edge":
        if initial_prior is None or previous_posterior is not None:
            raise ValueError("first_edge requires initial_prior and forbids previous_posterior")
    elif previous_posterior is None or initial_prior is not None:
        raise ValueError("later_edge requires previous_posterior and forbids initial_prior")

    symbol = _absolute_index(target_symbol_index, name="target_symbol_index")
    clock = _absolute_index(time_index, name="time_index")
    origin = _absolute_index(symbol_origin_sample, name="symbol_origin_sample")
    prediction_cutoff = _absolute_index(
        prediction_data_cutoff_sample, name="prediction_data_cutoff_sample"
    )
    posterior_cutoff = _absolute_index(
        posterior_data_cutoff_sample, name="posterior_data_cutoff_sample"
    )
    first_sample = origin + ADR012_SAMPLES_PER_SYMBOL * symbol
    expected_prediction_cutoff = first_sample - 1
    expected_posterior_cutoff = first_sample + ADR012_SAMPLES_PER_SYMBOL - 1
    if prediction_cutoff != expected_prediction_cutoff:
        raise ValueError("prediction_data_cutoff_sample must be immediately before target symbol")
    if posterior_cutoff != expected_posterior_cutoff:
        raise ValueError("posterior_data_cutoff_sample must be the final target-symbol sample")

    if not isinstance(state, ReconstructionEstimatorState):
        raise ValueError("state must be a ReconstructionEstimatorState")
    if state.time_index != clock:
        raise ValueError("time_index must explicitly match pre-observation state.time_index")
    if state.full_iq.shape != (1, 2) or state.fluctuating_iq.shape != (1, 2):
        raise ValueError("integrated step requires an L=1 state with shape (1, 2)")
    # Snapshot before any current-symbol observation is extracted. Both B4b
    # and the estimator prediction operand use this exact immutable value.
    pre_snapshot = snapshot_full_iq_for_forward(state, estimator_time_index=clock)

    candidate_result = generate_reconstruction_candidate_metrics(
        received=received,
        absolute_sample_indices=absolute_sample_indices,
        received_start_sample=received_start_sample,
        symbol_origin_sample=origin,
        target_symbol_index=symbol,
        state=state,
        time_index=clock,
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
    if candidate_result.hypothesis_ids != _HYPOTHESIS_IDS:
        raise ValueError("candidate metrics must use canonical HYPOTHESES order")
    if (
        candidate_result.target_symbol_index != symbol
        or candidate_result.estimator_time_index != clock
    ):
        raise ValueError("candidate result time labels do not match the requested symbol step")
    if candidate_result.prediction_cutoff_sample_index != expected_prediction_cutoff:
        raise ValueError("candidate result prediction cutoff does not match the requested symbol")
    if candidate_result.metric_available_after_sample_index != expected_posterior_cutoff:
        raise ValueError("candidate metrics are not labelled at the target observation cutoff")
    expected_sample_indices = tuple(range(first_sample, first_sample + ADR012_SAMPLES_PER_SYMBOL))
    if candidate_result.sample_indices != expected_sample_indices:
        raise ValueError("candidate sample labels do not match the requested target symbol")
    if (
        candidate_result.profile != ADR012_PROFILE
        or candidate_result.profile_id != ADR012_PROFILE_ID
    ):
        raise ValueError("candidate metrics do not carry the accepted ADR-012 profile provenance")

    expected_bits = tuple(hypothesis.output_bits for hypothesis in HYPOTHESES)
    expected_phases = tuple(
        hypothesis_to_phase_index(
            hypothesis,
            profile=labeling_profile,
            bit_order=bit_order,
        )
        for hypothesis in HYPOTHESES
    )
    if (
        candidate_result.output_bits != expected_bits
        or candidate_result.phase_indices != expected_phases
    ):
        raise ValueError("candidate metadata is not aligned with canonical HYPOTHESES order")

    if edge_mode == "first_edge":
        posterior = initial_reconstruction_observation_update(
            prior=initial_prior,
            candidate_metrics=candidate_result.metrics,
            beta=beta,
        )
    else:
        posterior = transition_reconstruction_posterior(
            previous_posterior,
            candidate_result.metrics,
            beta=beta,
        )

    phase_indices = np.asarray(candidate_result.phase_indices, dtype=np.int64)
    coefficients = pre_snapshot.estimated_path_coefficients[0]
    predicted_iq = iq_quadratures_from_index(
        phase_indices,
        np.full(len(HYPOTHESES), coefficients[0], dtype=np.float64),
        np.full(len(HYPOTHESES), coefficients[1], dtype=np.float64),
    )
    if predicted_iq.shape != (len(HYPOTHESES), 2):
        raise RuntimeError("iq_prediction returned an unexpected recursion operand shape")
    repeated_predictions = np.repeat(
        predicted_iq[:, np.newaxis, :], ADR012_SAMPLES_PER_SYMBOL, axis=1
    )
    if not np.allclose(
        candidate_result.sample_predictions_iq,
        repeated_predictions,
        rtol=1e-14,
        atol=1e-14,
    ):
        raise ValueError("B4b sample predictions do not match [A](5) recursion predictions")

    causal_step = advance_real_one_path_symbol(
        state,
        received,
        absolute_sample_indices=absolute_sample_indices,
        received_start_sample=received_start_sample,
        symbol_origin_sample=origin,
        target_symbol_index=symbol,
        time_index=clock,
        profile=profile,
        adr_profile=adr_profile,
        path_count=path_count,
        path_delays_samples=path_delays_samples,
        samples_per_symbol=samples_per_symbol,
        iq_rule=iq_rule,
        alpha_prime=alpha_prime,
        k_tilde=k_tilde,
        mu0=mu0,
        predicted_iq=predicted_iq,
        posterior=posterior,
        prediction_data_cutoff_sample=prediction_cutoff,
        posterior_data_cutoff_sample=posterior_cutoff,
        waveform_rule=waveform_rule,
    )
    return ReconstructionPosteriorEstimatorStepResult(
        candidate_result=candidate_result,
        posterior=posterior,
        predicted_iq=predicted_iq,
        causal_step=causal_step,
        edge_mode=edge_mode,
    )
