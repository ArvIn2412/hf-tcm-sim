"""Deterministic four-arm, two-symbol update ablation for reconstruction.

This isolated evaluation adapter drives the existing B4d sequence API with
one caller-supplied complex buffer. It runs no RNG, encoder, channel, decoder,
or performance evaluation. The A/K arm names denote ablation components, not
additional receiver modes.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass
from numbers import Integral
from types import MappingProxyType

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.receiver.reconstruction_alignment import ZERO_PADDING
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
from hf_tcm.receiver.reconstruction_posterior import (
    build_initial_reconstruction_prior,
    build_reconstruction_transition_matrix,
    initial_reconstruction_observation_update,
)
from hf_tcm.receiver.reconstruction_posterior_estimator_sequence import (
    ReconstructionPosteriorEstimatorSequenceResult,
    run_reconstruction_posterior_estimator_sequence,
)

FloatArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]
_HYPOTHESIS_COUNT = 16
_SYMBOL_COUNT = 2
_BETA = 0.7
_TOLERANCE = 1e-12


@dataclass(frozen=True, slots=True)
class FactorialArmPolicy:
    """Frozen historical update coefficients for one experimental arm."""

    alpha_prime: float
    k_tilde: tuple[float, float]


FACTORIAL_ARMS: Mapping[str, FactorialArmPolicy] = MappingProxyType(
    {
        "B": FactorialArmPolicy(alpha_prime=1.0, k_tilde=(0.0, 0.0)),
        "A": FactorialArmPolicy(alpha_prime=0.85, k_tilde=(0.0, 0.0)),
        "K": FactorialArmPolicy(alpha_prime=1.0, k_tilde=(0.35, -0.2)),
        "C": FactorialArmPolicy(alpha_prime=0.85, k_tilde=(0.35, -0.2)),
    }
)


def _received_buffer(value: ArrayLike) -> ComplexArray:
    try:
        raw = np.asarray(value)
        if raw.shape != (_SYMBOL_COUNT * ADR012_SAMPLES_PER_SYMBOL,) or not np.iscomplexobj(raw):
            raise ValueError
        result = np.asarray(raw, dtype=np.complex128)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("received must be a finite complex vector of shape (16,)") from exc
    if not np.all(np.isfinite(result.real)) or not np.all(np.isfinite(result.imag)):
        raise ValueError("received must contain only finite complex samples")
    owned = np.array(result, dtype=np.complex128, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=np.complex128)


def _index(value: object, *, name: str, nonnegative: bool = False) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")
    result = int(value)
    if nonnegative and result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


def _readonly(value: ArrayLike, *, shape: tuple[int, ...], name: str) -> FloatArray:
    try:
        raw = np.asarray(value)
        if np.iscomplexobj(raw) or raw.dtype.kind not in "iuf":
            raise ValueError
        array = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite with shape {shape}") from exc
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be finite with shape {shape}")
    owned = np.array(array, dtype=np.float64, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=np.float64).reshape(shape)


@dataclass(frozen=True, slots=True)
class FactorialVectorContrasts:
    """Component, combined, and factorial interaction contrasts."""

    alpha: FloatArray
    correction: FloatArray
    combined: FloatArray
    interaction: FloatArray

    def __post_init__(self) -> None:
        for name in ("alpha", "correction", "combined", "interaction"):
            object.__setattr__(self, name, _readonly(getattr(self, name), shape=(16,), name=name))


@dataclass(frozen=True, slots=True)
class FactorialPosteriorContrasts:
    """Contrasts kept separate for actual-transition and common-prior updates."""

    actual: FactorialVectorContrasts
    fixed_common_prior: FactorialVectorContrasts


@dataclass(frozen=True, slots=True)
class FactorialArmResult:
    """Two actual B4d steps plus one explicitly separate common-prior view."""

    arm_id: str
    policy: FactorialArmPolicy
    sequence_result: ReconstructionPosteriorEstimatorSequenceResult
    hypothesis_ids: tuple[int, ...]
    first_metrics: FloatArray
    first_posterior: FloatArray
    first_post_state: ReconstructionEstimatorState
    first_innovation_iq: FloatArray
    second_pre_state: ReconstructionEstimatorState
    second_predictions_iq: FloatArray
    second_metrics: FloatArray
    second_actual_posterior: FloatArray
    second_fixed_common_prior_posterior: FloatArray
    second_symbol_index: int
    second_sample_window: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "first_metrics", _readonly(self.first_metrics, shape=(16,), name="first_metrics")
        )
        object.__setattr__(
            self,
            "first_posterior",
            _readonly(self.first_posterior, shape=(16,), name="first_posterior"),
        )
        object.__setattr__(
            self,
            "first_innovation_iq",
            _readonly(self.first_innovation_iq, shape=(2,), name="first_innovation_iq"),
        )
        object.__setattr__(
            self,
            "second_predictions_iq",
            _readonly(self.second_predictions_iq, shape=(16, 2), name="second_predictions_iq"),
        )
        object.__setattr__(
            self,
            "second_metrics",
            _readonly(self.second_metrics, shape=(16,), name="second_metrics"),
        )
        object.__setattr__(
            self,
            "second_actual_posterior",
            _readonly(self.second_actual_posterior, shape=(16,), name="second_actual_posterior"),
        )
        object.__setattr__(
            self,
            "second_fixed_common_prior_posterior",
            _readonly(
                self.second_fixed_common_prior_posterior,
                shape=(16,),
                name="second_fixed_common_prior_posterior",
            ),
        )


@dataclass(frozen=True, slots=True)
class ReconstructionFactorialAblationResult:
    """Immutable, paired four-arm deterministic two-symbol comparison."""

    received_sha256: str
    beta: float
    initial_state: ReconstructionEstimatorState
    initial_prior: FloatArray
    symbol_origin_sample: int
    initial_estimator_time_index: int
    arms: Mapping[str, FactorialArmResult]
    delta_alpha_iq: FloatArray
    delta_k_iq: FloatArray
    delta_combined_iq: FloatArray
    state_interaction_iq: FloatArray
    metric_contrasts: FactorialVectorContrasts
    posterior_contrasts: FactorialPosteriorContrasts
    transition_prior_api_status: str
    derived_transition_prior: FloatArray
    derived_transition_prior_provenance: str
    invariant_status: str

    def __post_init__(self) -> None:
        frozen_arms = MappingProxyType(dict(self.arms))
        if tuple(frozen_arms) != tuple(FACTORIAL_ARMS):
            raise ValueError("arms must be stored in canonical factorial order B, A, K, C")
        object.__setattr__(self, "arms", frozen_arms)
        object.__setattr__(
            self, "initial_prior", _readonly(self.initial_prior, shape=(16,), name="initial_prior")
        )
        for name in ("delta_alpha_iq", "delta_k_iq", "delta_combined_iq", "state_interaction_iq"):
            object.__setattr__(self, name, _readonly(getattr(self, name), shape=(2,), name=name))
        object.__setattr__(
            self,
            "derived_transition_prior",
            _readonly(self.derived_transition_prior, shape=(16,), name="derived_transition_prior"),
        )


def _weighted_innovation(step: object) -> FloatArray:
    observed = step.observed_iq
    predicted = step.predicted_iq
    posterior = step.posterior
    return np.asarray(
        [
            math.fsum(
                float(posterior[hypothesis])
                * (float(observed[axis]) - float(predicted[hypothesis, axis]))
                for hypothesis in range(_HYPOTHESIS_COUNT)
            )
            for axis in range(2)
        ],
        dtype=np.float64,
    )


def _vector_contrasts(
    b: FloatArray, a: FloatArray, k: FloatArray, c: FloatArray
) -> FactorialVectorContrasts:
    return FactorialVectorContrasts(
        alpha=a - b,
        correction=k - b,
        combined=c - b,
        interaction=c - a - k + b,
    )


def run_reconstruction_factorial_ablation(
    *,
    received: ArrayLike,
    symbol_origin_sample: int = 0,
    initial_estimator_time_index: int = 0,
) -> ReconstructionFactorialAblationResult:
    """Run exactly two symbols through B4d for the frozen B/A/K/C policies.

    All arms share the same caller-supplied received samples, initial
    full/fluctuating coefficient `(0.42, 0.91)`, zero `mu0`, beta 0.7,
    ADR-004 prior, clocks, project labeling and metric. No bits, channel truth,
    random stream, decoder or metric-driven policy choice is involved.
    """
    samples = _received_buffer(received)
    origin = _index(symbol_origin_sample, name="symbol_origin_sample", nonnegative=True)
    first_tick = _index(initial_estimator_time_index, name="initial_estimator_time_index")
    sample_start = origin
    sample_labels = np.arange(sample_start, sample_start + samples.size, dtype=np.int64)
    initial_coefficients = np.asarray([[0.42, 0.91]], dtype=np.float64)
    zero_mu0 = np.zeros((1, 2), dtype=np.float64)
    state = ReconstructionEstimatorState(
        fluctuating_iq=initial_coefficients,
        full_iq=initial_coefficients,
        time_index=first_tick,
    )
    prior = build_initial_reconstruction_prior(initial_state=(0, 0))

    raw_results: dict[str, ReconstructionPosteriorEstimatorSequenceResult] = {}
    for arm_id, policy in FACTORIAL_ARMS.items():
        raw_results[arm_id] = run_reconstruction_posterior_estimator_sequence(
            received=samples,
            absolute_sample_indices=sample_labels,
            received_start_sample=sample_start,
            symbol_origin_sample=origin,
            first_symbol_index=0,
            sequence_origin_symbol_index=0,
            symbol_count=_SYMBOL_COUNT,
            symbol_indices=(0, 1),
            initial_state=state,
            initial_estimator_time_index=first_tick,
            run_mode="new_independent_sequence",
            initial_prior=prior,
            previous_posterior=None,
            continuation_from_symbol_index=None,
            continuation_from_estimator_time_index=None,
            beta=_BETA,
            alpha_prime=policy.alpha_prime,
            k_tilde=np.asarray(policy.k_tilde, dtype=np.float64).reshape(1, 2),
            mu0=zero_mu0,
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
            edge_policy=ZERO_PADDING,
        )

    canonical_ids = tuple(hypothesis.hypothesis_id for hypothesis in HYPOTHESES)
    arms: dict[str, FactorialArmResult] = {}
    for arm_id, policy in FACTORIAL_ARMS.items():
        sequence = raw_results[arm_id]
        if sequence.history is None or len(sequence.history) != _SYMBOL_COUNT:
            raise RuntimeError("B4d did not provide both requested symbol histories")
        first = sequence.history[0].b4c_result
        second = sequence.history[1].b4c_result
        if first.hypothesis_ids != canonical_ids or second.hypothesis_ids != canonical_ids:
            raise RuntimeError("B4d changed canonical 16-edge ordering")
        if first.edge_mode != "first_edge" or second.edge_mode != "later_edge":
            raise RuntimeError("B4d first-edge/continuation lifecycle is inconsistent")
        first_post_state = first.causal_step.next_state
        second_pre_state = first_post_state
        common_prior_posterior = initial_reconstruction_observation_update(
            prior=np.full(_HYPOTHESIS_COUNT, 1.0 / _HYPOTHESIS_COUNT, dtype=np.float64),
            candidate_metrics=second.candidate_result.metrics,
            beta=_BETA,
        )
        arms[arm_id] = FactorialArmResult(
            arm_id=arm_id,
            policy=policy,
            sequence_result=sequence,
            hypothesis_ids=canonical_ids,
            first_metrics=first.candidate_result.metrics,
            first_posterior=first.posterior,
            first_post_state=first_post_state,
            first_innovation_iq=_weighted_innovation(first),
            second_pre_state=second_pre_state,
            second_predictions_iq=second.predicted_iq,
            second_metrics=second.candidate_result.metrics,
            second_actual_posterior=second.posterior,
            second_fixed_common_prior_posterior=common_prior_posterior,
            second_symbol_index=sequence.history[1].symbol_index,
            second_sample_window=tuple(
                range(
                    sequence.history[1].first_sample_index,
                    sequence.history[1].last_sample_index + 1,
                )
            ),
        )

    reference_arm = arms["B"]
    for arm_id in ("A", "K", "C"):
        if not np.array_equal(arms[arm_id].first_metrics, reference_arm.first_metrics):
            raise RuntimeError(
                "INVARIANT FAILURE: first-symbol metrics are not identical across arms"
            )
        if not np.array_equal(arms[arm_id].first_posterior, reference_arm.first_posterior):
            raise RuntimeError(
                "INVARIANT FAILURE: first-symbol posterior is not identical across arms"
            )
        if not np.array_equal(arms[arm_id].first_innovation_iq, reference_arm.first_innovation_iq):
            raise RuntimeError(
                "INVARIANT FAILURE: first-symbol innovation is not identical across arms"
            )

    first_pre = np.asarray([0.42, 0.91], dtype=np.float64)
    epsilon = reference_arm.first_innovation_iq
    delta_alpha = (FACTORIAL_ARMS["A"].alpha_prime - FACTORIAL_ARMS["B"].alpha_prime) * first_pre
    delta_k = np.asarray(FACTORIAL_ARMS["K"].k_tilde) * epsilon
    delta_combined = delta_alpha + delta_k
    states = {name: arms[name].first_post_state.fluctuating_iq[0] for name in FACTORIAL_ARMS}
    actual_state_interaction = states["C"] - states["A"] - states["K"] + states["B"]
    checks = (
        (states["A"] - states["B"], delta_alpha),
        (states["K"] - states["B"], delta_k),
        (states["C"] - states["B"], delta_combined),
        (actual_state_interaction, np.zeros(2, dtype=np.float64)),
    )
    if any(
        not np.allclose(actual, expected, rtol=0.0, atol=_TOLERANCE) for actual, expected in checks
    ):
        raise RuntimeError("INVARIANT FAILURE: first-update factorial state decomposition failed")

    first_posteriors = [arms[name].first_posterior for name in FACTORIAL_ARMS]
    transition = build_reconstruction_transition_matrix()
    derived_q_rows = [posterior @ transition for posterior in first_posteriors]
    if any(
        not np.allclose(row, derived_q_rows[0], rtol=0.0, atol=_TOLERANCE)
        for row in derived_q_rows[1:]
    ):
        raise RuntimeError("INVARIANT FAILURE: derived transition prior differs across arms")
    derived_q = np.asarray(derived_q_rows[0], dtype=np.float64)

    second_metric_rows = {name: arms[name].second_metrics for name in FACTORIAL_ARMS}
    actual_posterior_rows = {name: arms[name].second_actual_posterior for name in FACTORIAL_ARMS}
    fixed_posterior_rows = {
        name: arms[name].second_fixed_common_prior_posterior for name in FACTORIAL_ARMS
    }
    return ReconstructionFactorialAblationResult(
        received_sha256=hashlib.sha256(samples.tobytes()).hexdigest(),
        beta=_BETA,
        initial_state=state,
        initial_prior=prior,
        symbol_origin_sample=origin,
        initial_estimator_time_index=first_tick,
        arms=arms,
        delta_alpha_iq=delta_alpha,
        delta_k_iq=delta_k,
        delta_combined_iq=delta_combined,
        state_interaction_iq=actual_state_interaction,
        metric_contrasts=_vector_contrasts(
            second_metric_rows["B"],
            second_metric_rows["A"],
            second_metric_rows["K"],
            second_metric_rows["C"],
        ),
        posterior_contrasts=FactorialPosteriorContrasts(
            actual=_vector_contrasts(
                actual_posterior_rows["B"],
                actual_posterior_rows["A"],
                actual_posterior_rows["K"],
                actual_posterior_rows["C"],
            ),
            fixed_common_prior=_vector_contrasts(
                fixed_posterior_rows["B"],
                fixed_posterior_rows["A"],
                fixed_posterior_rows["K"],
                fixed_posterior_rows["C"],
            ),
        ),
        transition_prior_api_status="not exported; independently derived for audit",
        derived_transition_prior=derived_q,
        derived_transition_prior_provenance=(
            "previous first-symbol posterior @ ADR-003 transition matrix; derived audit value, not raw B4c q"
        ),
        invariant_status="first_symbol_shared_invariants_passed",
    )
