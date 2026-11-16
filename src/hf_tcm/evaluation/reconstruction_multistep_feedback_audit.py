"""Deterministic eight-symbol feedback audit; no decoding or performance estimate."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.evaluation.reconstruction_factorial_ablation import FACTORIAL_ARMS, FactorialArmPolicy
from hf_tcm.receiver.reconstruction_alignment import ZERO_PADDING
from hf_tcm.receiver.reconstruction_candidate_metrics import (
    generate_reconstruction_candidate_metrics,
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
    ADR012_WAVEFORM_RULE,
    extract_adr012_observed_iq,
)
from hf_tcm.receiver.reconstruction_posterior import (
    build_initial_reconstruction_prior,
    build_reconstruction_transition_matrix,
    initial_reconstruction_observation_update,
    transition_reconstruction_posterior,
)
from hf_tcm.receiver.reconstruction_posterior_estimator_sequence import (
    run_reconstruction_posterior_estimator_sequence,
)

FloatArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]
_ARM_IDS = tuple(FACTORIAL_ARMS)
FEEDBACK_ARMS = FACTORIAL_ARMS
_F = 8
_H = 16
_BETA = 0.7
_INITIAL = (0.42, 0.91)
_MU0 = (0.0, 0.0)
_TOL = 1e-11


def deterministic_feedback_fixture() -> ComplexArray:
    """Return the declared 64-sample input; it consumes no RNG."""
    return np.asarray(
        [
            complex((n - 31) / 40.0 + ((n % 7) - 3) / 100.0, (((3 * n) % 11) - 5) / 30.0)
            for n in range(64)
        ],
        dtype=np.complex128,
    )


def _ro(value: ArrayLike, shape: tuple[int, ...], name: str) -> FloatArray:
    raw = np.asarray(value)
    if np.iscomplexobj(raw) or raw.dtype.kind not in "iuf":
        raise ValueError(f"{name} must be finite real data with shape {shape}")
    result = np.asarray(raw, dtype=np.float64)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite real data with shape {shape}")
    return np.frombuffer(
        np.array(result, order="C", copy=True).tobytes(), dtype=np.float64
    ).reshape(shape)


def _received(value: ArrayLike) -> ComplexArray:
    raw = np.asarray(value)
    if raw.shape != (64,) or not np.iscomplexobj(raw):
        raise ValueError("received must be a finite complex vector of shape (64,)")
    samples = np.asarray(raw, dtype=np.complex128)
    if not np.all(np.isfinite(samples.real)) or not np.all(np.isfinite(samples.imag)):
        raise ValueError("received must contain finite complex samples")
    return np.frombuffer(np.array(samples, order="C", copy=True).tobytes(), dtype=np.complex128)


def _innovation(posterior: FloatArray, observed: FloatArray, predicted: FloatArray) -> FloatArray:
    return np.asarray(
        [
            math.fsum(
                float(posterior[h]) * (float(observed[j]) - float(predicted[h, j]))
                for h in range(_H)
            )
            for j in range(2)
        ],
        dtype=np.float64,
    )


def _scalar_update(
    state: FloatArray, policy: FactorialArmPolicy, epsilon: FloatArray
) -> tuple[FloatArray, FloatArray]:
    next_state = np.asarray(
        [
            policy.alpha_prime * float(state[j]) + float(policy.k_tilde[j]) * float(epsilon[j])
            for j in range(2)
        ],
        dtype=np.float64,
    )
    return next_state, next_state + np.asarray(_MU0, dtype=np.float64)


@dataclass(frozen=True, slots=True)
class FeedbackSymbolRow:
    symbol_position: int
    symbol_index: int
    estimator_time_index: int
    sample_window: tuple[int, ...]
    prediction_cutoff_sample: int
    observation_cutoff_sample: int
    edge_mode: str
    hypothesis_ids: tuple[int, ...]
    pre_fluctuating: FloatArray
    pre_full: FloatArray
    predictions: FloatArray
    metrics: FloatArray
    posterior_prior: FloatArray
    posterior_prior_provenance: str
    posterior: FloatArray
    posterior_sum: float
    own_posterior_innovation: FloatArray
    supplied_innovation: FloatArray
    supplied_innovation_origin: str
    innovation_difference: FloatArray
    alpha_prime: float
    k_tilde: FloatArray
    coefficient_delta: FloatArray
    post_fluctuating: FloatArray
    post_full: FloatArray
    q_provenance: str
    raw_q_exported: bool
    finite: bool

    def __post_init__(self) -> None:
        shapes = {
            "pre_fluctuating": (2,),
            "pre_full": (2,),
            "predictions": (16, 2),
            "metrics": (16,),
            "posterior_prior": (16,),
            "posterior": (16,),
            "own_posterior_innovation": (2,),
            "supplied_innovation": (2,),
            "innovation_difference": (2,),
            "k_tilde": (2,),
            "coefficient_delta": (2,),
            "post_fluctuating": (2,),
            "post_full": (2,),
        }
        for key, shape in shapes.items():
            object.__setattr__(self, key, _ro(getattr(self, key), shape, key))


@dataclass(frozen=True, slots=True)
class FeedbackArmTrajectory:
    arm_id: str
    policy: FactorialArmPolicy
    rows: tuple[FeedbackSymbolRow, ...]
    frozen_metric_matrix: FloatArray

    def __post_init__(self) -> None:
        if len(self.rows) != 8:
            raise ValueError("each arm must contain exactly eight symbol rows")
        object.__setattr__(
            self,
            "frozen_metric_matrix",
            _ro(self.frozen_metric_matrix, (8, 16), "frozen_metric_matrix"),
        )


@dataclass(frozen=True, slots=True)
class FactorialInteractionRow:
    symbol_index: int
    pre_state: FloatArray
    post_state: FloatArray
    metrics: FloatArray
    posterior: FloatArray

    def __post_init__(self) -> None:
        for key, shape in (
            ("pre_state", (2,)),
            ("post_state", (2,)),
            ("metrics", (16,)),
            ("posterior", (16,)),
        ):
            object.__setattr__(self, key, _ro(getattr(self, key), shape, key))


@dataclass(frozen=True, slots=True)
class RegimeAudit:
    regime: str
    arms: Mapping[str, FeedbackArmTrajectory]
    interactions: tuple[FactorialInteractionRow, ...]

    def __post_init__(self) -> None:
        if tuple(self.arms) != _ARM_IDS or len(self.interactions) != 8:
            raise ValueError("regime must have canonical B/A/K/C arms and eight rows")
        object.__setattr__(self, "arms", MappingProxyType(dict(self.arms)))


@dataclass(frozen=True, slots=True)
class FeedbackContrastRow:
    symbol_index: int
    state_pre_by_arm: Mapping[str, FloatArray]
    state_post_by_arm: Mapping[str, FloatArray]
    metric_by_arm: Mapping[str, FloatArray]
    posterior_by_arm: Mapping[str, FloatArray]


@dataclass(frozen=True, slots=True)
class ReconstructionMultistepFeedbackResult:
    fixture_sha256: str
    beta: float
    received_sample_count: int
    symbol_origin_sample: int
    first_symbol_index: int
    estimator_time_origin: int
    reference_innovations: FloatArray
    reference_innovation_origin: str
    closed_loop: RegimeAudit
    common_operand: RegimeAudit
    feedback_contrasts: tuple[FeedbackContrastRow, ...]
    decoder_invoked: bool
    random_generation_invoked: bool
    invariant_status: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reference_innovations",
            _ro(self.reference_innovations, (8, 2), "reference_innovations"),
        )


def _prior(
    position: int, previous: FloatArray | None, first: FloatArray, transition: FloatArray
) -> tuple[FloatArray, str, str]:
    if position == 0:
        return (
            first,
            "ADR-004 initial edge prior",
            "initial_prior_directly_supplied; no transition q",
        )
    assert previous is not None
    q = np.asarray(
        [
            math.fsum(float(previous[i]) * float(transition[i, j]) for i in range(16))
            for j in range(16)
        ],
        dtype=np.float64,
    )
    return (
        q,
        "derived previous posterior @ ADR-003 transition",
        "derived_from_previous_posterior_and_ADR003_transition",
    )


def _interaction(arms: Mapping[str, FeedbackArmTrajectory]) -> tuple[FactorialInteractionRow, ...]:
    rows = []
    for f in range(8):
        b, a, k, c = (arms[key].rows[f] for key in _ARM_IDS)
        rows.append(
            FactorialInteractionRow(
                b.symbol_index,
                c.pre_fluctuating - a.pre_fluctuating - k.pre_fluctuating + b.pre_fluctuating,
                c.post_fluctuating - a.post_fluctuating - k.post_fluctuating + b.post_fluctuating,
                c.metrics - a.metrics - k.metrics + b.metrics,
                c.posterior - a.posterior - k.posterior + b.posterior,
            )
        )
    return tuple(rows)


def _sequence_kwargs(
    received: ComplexArray,
    labels: NDArray[np.int64],
    start: int,
    origin: int,
    first_symbol: int,
    tick: int,
    initial_state: ReconstructionEstimatorState,
    first_prior: FloatArray,
    policy: FactorialArmPolicy,
) -> dict[str, object]:
    return {
        "received": received,
        "absolute_sample_indices": labels,
        "received_start_sample": start,
        "symbol_origin_sample": origin,
        "first_symbol_index": first_symbol,
        "sequence_origin_symbol_index": first_symbol,
        "symbol_count": 8,
        "symbol_indices": tuple(range(first_symbol, first_symbol + 8)),
        "initial_state": initial_state,
        "initial_estimator_time_index": tick,
        "run_mode": "new_independent_sequence",
        "initial_prior": first_prior,
        "previous_posterior": None,
        "continuation_from_symbol_index": None,
        "continuation_from_estimator_time_index": None,
        "beta": _BETA,
        "alpha_prime": policy.alpha_prime,
        "k_tilde": np.asarray(policy.k_tilde, dtype=np.float64).reshape(1, 2),
        "mu0": np.zeros((1, 2), dtype=np.float64),
        "include_history": True,
        "profile": ADR012_PROFILE,
        "adr_profile": ADR012_PROFILE_ID,
        "path_count": 1,
        "path_delays_samples": (0,),
        "samples_per_symbol": 8,
        "iq_rule": ADR012_IQ_RULE,
        "waveform_rule": ADR012_WAVEFORM_RULE,
        "labeling_profile": ASSUMED_NATURAL_BINARY,
        "bit_order": OUTPUT_BIT_ORDER,
        "timebase_profile": APPROXIMATE_RECTANGULAR_8SPS,
        "symbol_to_sample_rule": RECTANGULAR_ZOH_RULE,
        "edge_policy": ZERO_PADDING,
    }


def run_reconstruction_multistep_feedback_audit(
    *,
    received: ArrayLike,
    symbol_origin_sample: int = 0,
    first_symbol_index: int = 0,
    estimator_time_origin: int = 0,
) -> ReconstructionMultistepFeedbackResult:
    """Run actual closed loops, then common frozen-B innovation counterfactuals."""
    samples = _received(received)
    for value, name in (
        (symbol_origin_sample, "symbol_origin_sample"),
        (first_symbol_index, "first_symbol_index"),
        (estimator_time_origin, "estimator_time_origin"),
    ):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
            raise ValueError(f"{name} must be an integer")
    if symbol_origin_sample < 0 or first_symbol_index < 0:
        raise ValueError("sample and symbol origins must be non-negative")
    origin, first_symbol, tick0 = (
        int(symbol_origin_sample),
        int(first_symbol_index),
        int(estimator_time_origin),
    )
    start = origin + 8 * first_symbol
    labels = np.arange(start, start + 64, dtype=np.int64)
    initial = np.asarray(_INITIAL, dtype=np.float64)
    state0 = ReconstructionEstimatorState(initial.reshape(1, 2), initial.reshape(1, 2), tick0)
    first_prior = build_initial_reconstruction_prior(initial_state=(0, 0))
    transition = build_reconstruction_transition_matrix()
    hypothesis_ids = tuple(h.hypothesis_id for h in HYPOTHESES)

    # Actual closed-loop uses B4d, including each arm's own posterior/innovation.
    sequence_results = {
        arm: run_reconstruction_posterior_estimator_sequence(
            **_sequence_kwargs(
                samples, labels, start, origin, first_symbol, tick0, state0, first_prior, policy
            )
        )
        for arm, policy in FACTORIAL_ARMS.items()
    }
    closed_rows: dict[str, tuple[FeedbackSymbolRow, ...]] = {}
    for arm, policy in FACTORIAL_ARMS.items():
        history = sequence_results[arm].history
        if history is None or len(history) != 8:
            raise RuntimeError("B4d did not return eight rows")
        rows: list[FeedbackSymbolRow] = []
        pre_fluct, pre_full = initial.copy(), initial.copy()
        prev_posterior = None
        for pos, item in enumerate(history):
            step = item.b4c_result
            if step.hypothesis_ids != hypothesis_ids or step.edge_mode != (
                "first_edge" if pos == 0 else "later_edge"
            ):
                raise RuntimeError("B4d edge ordering/lifecycle mismatch")
            pprior, pprov, qprov = _prior(pos, prev_posterior, first_prior, transition)
            predicted = np.asarray(step.predicted_iq, dtype=np.float64)
            observed = np.asarray(step.observed_iq, dtype=np.float64)
            epsilon = _innovation(step.posterior, observed, predicted)
            post = step.next_state
            post_fluct, post_full = post.fluctuating_iq[0], post.full_iq[0]
            rows.append(
                FeedbackSymbolRow(
                    pos,
                    item.symbol_index,
                    item.estimator_time_index,
                    tuple(range(item.first_sample_index, item.last_sample_index + 1)),
                    step.prediction_data_cutoff_sample,
                    step.posterior_data_cutoff_sample,
                    step.edge_mode,
                    step.hypothesis_ids,
                    pre_fluct,
                    pre_full,
                    predicted,
                    step.candidate_result.metrics,
                    pprior,
                    pprov,
                    step.posterior,
                    math.fsum(float(x) for x in step.posterior),
                    epsilon,
                    epsilon,
                    "own_current_posterior_weighted_innovation",
                    np.zeros(2),
                    policy.alpha_prime,
                    np.asarray(policy.k_tilde),
                    post_fluct - pre_fluct,
                    post_fluct,
                    post_full,
                    qprov,
                    False,
                    all(
                        np.all(np.isfinite(value))
                        for value in (
                            pre_fluct,
                            pre_full,
                            predicted,
                            step.candidate_result.metrics,
                            step.posterior,
                            epsilon,
                            post_fluct,
                            post_full,
                        )
                    ),
                )
            )
            pre_fluct, pre_full = post_fluct.copy(), post_full.copy()
            prev_posterior = np.asarray(step.posterior)
        closed_rows[arm] = tuple(rows)

    # Freeze the complete reference vector before any counterfactual replay.
    reference = np.asarray(
        [row.own_posterior_innovation for row in closed_rows["B"]], dtype=np.float64
    )
    reference = np.frombuffer(
        np.array(reference, order="C", copy=True).tobytes(), dtype=np.float64
    ).reshape(8, 2)

    # Evaluation-only replay: own posterior is diagnostic; update uses epsilon_B[f].
    common_rows: dict[str, tuple[FeedbackSymbolRow, ...]] = {}
    for arm, policy in FACTORIAL_ARMS.items():
        pre_fluct, pre_full = initial.copy(), initial.copy()
        prev_posterior = None
        rows = []
        for pos in range(8):
            symbol, tick = first_symbol + pos, tick0 + pos
            state = ReconstructionEstimatorState(
                pre_fluct.reshape(1, 2), pre_full.reshape(1, 2), tick
            )
            candidate = generate_reconstruction_candidate_metrics(
                received=samples,
                absolute_sample_indices=labels,
                received_start_sample=start,
                symbol_origin_sample=origin,
                target_symbol_index=symbol,
                state=state,
                time_index=tick,
                profile=ADR012_PROFILE,
                adr_profile=ADR012_PROFILE_ID,
                path_count=1,
                path_delays_samples=(0,),
                samples_per_symbol=8,
                iq_rule=ADR012_IQ_RULE,
                waveform_rule=ADR012_WAVEFORM_RULE,
                labeling_profile=ASSUMED_NATURAL_BINARY,
                bit_order=OUTPUT_BIT_ORDER,
                timebase_profile=APPROXIMATE_RECTANGULAR_8SPS,
                symbol_to_sample_rule=RECTANGULAR_ZOH_RULE,
                edge_policy=ZERO_PADDING,
            )
            if candidate.hypothesis_ids != hypothesis_ids:
                raise RuntimeError("candidate API changed canonical edge order")
            observed = np.asarray(
                extract_adr012_observed_iq(
                    samples,
                    absolute_sample_indices=labels,
                    received_start_sample=start,
                    symbol_origin_sample=origin,
                    target_symbol_index=symbol,
                    profile=ADR012_PROFILE,
                    adr_profile=ADR012_PROFILE_ID,
                    path_count=1,
                    path_delays_samples=(0,),
                    samples_per_symbol=8,
                    iq_rule=ADR012_IQ_RULE,
                    waveform_rule=ADR012_WAVEFORM_RULE,
                ),
                dtype=np.float64,
            )
            predicted = np.asarray(candidate.sample_predictions_iq[:, 0, :], dtype=np.float64)
            posterior = (
                initial_reconstruction_observation_update(
                    prior=first_prior, candidate_metrics=candidate.metrics, beta=_BETA
                )
                if pos == 0
                else transition_reconstruction_posterior(
                    prev_posterior, candidate.metrics, beta=_BETA
                )
            )
            pprior, pprov, qprov = _prior(pos, prev_posterior, first_prior, transition)
            own_epsilon, supplied = _innovation(posterior, observed, predicted), reference[pos]
            next_fluct, next_full = _scalar_update(pre_fluct, policy, supplied)
            rows.append(
                FeedbackSymbolRow(
                    pos,
                    symbol,
                    tick,
                    tuple(range(origin + 8 * symbol, origin + 8 * (symbol + 1))),
                    origin + 8 * symbol - 1,
                    origin + 8 * (symbol + 1) - 1,
                    "first_edge" if pos == 0 else "later_edge",
                    hypothesis_ids,
                    pre_fluct,
                    pre_full,
                    predicted,
                    candidate.metrics,
                    pprior,
                    pprov,
                    posterior,
                    math.fsum(float(x) for x in posterior),
                    own_epsilon,
                    supplied,
                    "frozen_B_actual_closed_loop_innovation",
                    own_epsilon - supplied,
                    policy.alpha_prime,
                    np.asarray(policy.k_tilde),
                    next_fluct - pre_fluct,
                    next_fluct,
                    next_full,
                    qprov,
                    False,
                    all(
                        np.all(np.isfinite(value))
                        for value in (
                            pre_fluct,
                            pre_full,
                            predicted,
                            candidate.metrics,
                            posterior,
                            own_epsilon,
                            supplied,
                            next_fluct,
                            next_full,
                        )
                    ),
                )
            )
            pre_fluct, pre_full, prev_posterior = next_fluct, next_full, posterior
        common_rows[arm] = tuple(rows)

    def regime(name: str, source: dict[str, tuple[FeedbackSymbolRow, ...]]) -> RegimeAudit:
        arms = {
            arm: FeedbackArmTrajectory(
                arm,
                FACTORIAL_ARMS[arm],
                source[arm],
                np.stack([row.metrics for row in source[arm]]),
            )
            for arm in _ARM_IDS
        }
        return RegimeAudit(name, arms, _interaction(arms))

    closed, common = regime("CLOSED_LOOP", closed_rows), regime("COMMON_OPERAND", common_rows)
    feedback = []
    for pos in range(8):
        feedback.append(
            FeedbackContrastRow(
                closed.arms["B"].rows[pos].symbol_index,
                MappingProxyType(
                    {
                        arm: _ro(
                            closed.arms[arm].rows[pos].pre_fluctuating
                            - common.arms[arm].rows[pos].pre_fluctuating,
                            (2,),
                            "D_state_pre",
                        )
                        for arm in _ARM_IDS
                    }
                ),
                MappingProxyType(
                    {
                        arm: _ro(
                            closed.arms[arm].rows[pos].post_fluctuating
                            - common.arms[arm].rows[pos].post_fluctuating,
                            (2,),
                            "D_state_post",
                        )
                        for arm in _ARM_IDS
                    }
                ),
                MappingProxyType(
                    {
                        arm: _ro(
                            closed.arms[arm].rows[pos].metrics - common.arms[arm].rows[pos].metrics,
                            (16,),
                            "D_metric",
                        )
                        for arm in _ARM_IDS
                    }
                ),
                MappingProxyType(
                    {
                        arm: _ro(
                            closed.arms[arm].rows[pos].posterior
                            - common.arms[arm].rows[pos].posterior,
                            (16,),
                            "D_posterior",
                        )
                        for arm in _ARM_IDS
                    }
                ),
            )
        )

    # Shared first step and B/A controls are explicit invariant gates.
    for audit in (closed, common):
        base = audit.arms["B"].rows[0]
        for arm in ("A", "K", "C"):
            row = audit.arms[arm].rows[0]
            if not (
                np.array_equal(row.metrics, base.metrics)
                and np.array_equal(row.posterior, base.posterior)
                and np.array_equal(row.own_posterior_innovation, base.own_posterior_innovation)
            ):
                raise RuntimeError("INVARIANT FAILURE: first-step arm operands differ")
        b, a, k, c = (audit.arms[arm].rows[0].post_fluctuating for arm in _ARM_IDS)
        if not np.allclose(c - a - k + b, 0.0, rtol=0.0, atol=1e-12):
            raise RuntimeError("INVARIANT FAILURE: first-step state factorial identity failed")
    for arm in ("B", "A"):
        for left, right in zip(closed.arms[arm].rows, common.arms[arm].rows, strict=True):
            if not (
                np.allclose(left.post_fluctuating, right.post_fluctuating, rtol=0, atol=_TOL)
                and np.allclose(left.metrics, right.metrics, rtol=0, atol=_TOL)
                and np.allclose(left.posterior, right.posterior, rtol=0, atol=_TOL)
            ):
                raise RuntimeError(f"INVARIANT FAILURE: {arm} closed/common control diverged")

    return ReconstructionMultistepFeedbackResult(
        hashlib.sha256(samples.tobytes()).hexdigest(),
        _BETA,
        64,
        origin,
        first_symbol,
        tick0,
        reference,
        "actual B closed-loop own posterior-weighted innovation; frozen before replay",
        closed,
        common,
        tuple(feedback),
        False,
        False,
        "first_step_and_B_A_control_invariants_passed",
    )


def feedback_audit_to_json(result: ReconstructionMultistepFeedbackResult) -> str:
    """Serialize all 64 symbol rows and contrasts in stable canonical order."""

    def row_payload(row: FeedbackSymbolRow) -> dict[str, object]:
        return {
            "symbol_position": row.symbol_position,
            "symbol_index": row.symbol_index,
            "estimator_time_index": row.estimator_time_index,
            "sample_window": list(row.sample_window),
            "prediction_cutoff_sample": row.prediction_cutoff_sample,
            "observation_cutoff_sample": row.observation_cutoff_sample,
            "edge_mode": row.edge_mode,
            "hypothesis_ids": list(row.hypothesis_ids),
            "pre_fluctuating": row.pre_fluctuating.tolist(),
            "pre_full": row.pre_full.tolist(),
            "predictions": row.predictions.tolist(),
            "metrics": row.metrics.tolist(),
            "posterior_prior": row.posterior_prior.tolist(),
            "posterior_prior_provenance": row.posterior_prior_provenance,
            "posterior": row.posterior.tolist(),
            "posterior_sum": row.posterior_sum,
            "own_posterior_innovation": row.own_posterior_innovation.tolist(),
            "supplied_innovation": row.supplied_innovation.tolist(),
            "supplied_innovation_origin": row.supplied_innovation_origin,
            "innovation_difference": row.innovation_difference.tolist(),
            "alpha_prime": row.alpha_prime,
            "k_tilde": row.k_tilde.tolist(),
            "coefficient_delta": row.coefficient_delta.tolist(),
            "post_fluctuating": row.post_fluctuating.tolist(),
            "post_full": row.post_full.tolist(),
            "q_provenance": row.q_provenance,
            "raw_q_exported": row.raw_q_exported,
            "finite": row.finite,
        }

    def regime_payload(regime: RegimeAudit) -> dict[str, object]:
        return {
            "regime": regime.regime,
            "arms": {
                arm_id: {
                    "alpha_prime": trajectory.policy.alpha_prime,
                    "k_tilde": list(trajectory.policy.k_tilde),
                    "frozen_metric_matrix": trajectory.frozen_metric_matrix.tolist(),
                    "rows": [row_payload(row) for row in trajectory.rows],
                }
                for arm_id, trajectory in regime.arms.items()
            },
            "factorial_interactions": [
                {
                    "symbol_index": row.symbol_index,
                    "pre_state": row.pre_state.tolist(),
                    "post_state": row.post_state.tolist(),
                    "metrics": row.metrics.tolist(),
                    "posterior": row.posterior.tolist(),
                }
                for row in regime.interactions
            ],
        }

    payload = {
        "schema_version": "m6g.feedback-trace.v1",
        "classification": (
            "deterministic multistep feedback audit; not performance evidence; "
            "not historical M5j root-cause proof; not paper-exact"
        ),
        "fixture_sha256": result.fixture_sha256,
        "received_sample_count": result.received_sample_count,
        "beta": result.beta,
        "symbol_origin_sample": result.symbol_origin_sample,
        "first_symbol_index": result.first_symbol_index,
        "estimator_time_origin": result.estimator_time_origin,
        "reference_innovation_origin": result.reference_innovation_origin,
        "reference_innovations": result.reference_innovations.tolist(),
        "closed_loop": regime_payload(result.closed_loop),
        "common_operand": regime_payload(result.common_operand),
        "feedback_contrasts": [
            {
                "symbol_index": row.symbol_index,
                "state_pre_by_arm": {
                    key: value.tolist() for key, value in row.state_pre_by_arm.items()
                },
                "state_post_by_arm": {
                    key: value.tolist() for key, value in row.state_post_by_arm.items()
                },
                "metric_by_arm": {key: value.tolist() for key, value in row.metric_by_arm.items()},
                "posterior_by_arm": {
                    key: value.tolist() for key, value in row.posterior_by_arm.items()
                },
            }
            for row in result.feedback_contrasts
        ],
        "decoder_invoked": result.decoder_invoked,
        "random_generation_invoked": result.random_generation_invoked,
        "invariant_status": result.invariant_status,
    }
    return json.dumps(payload, allow_nan=False, sort_keys=False, separators=(",", ":")) + "\n"


def write_feedback_audit_json(
    result: ReconstructionMultistepFeedbackResult, path: str | Path
) -> Path:
    """Atomically write the deterministic trace to a caller-selected new namespace."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(feedback_audit_to_json(result), encoding="utf-8", newline="\n")
    temporary.replace(target)
    return target
