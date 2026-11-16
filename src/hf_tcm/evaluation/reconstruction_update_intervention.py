"""One-step estimator-state intervention for reconstructed candidate metrics.

This evaluation-only adapter holds the next ADR-012 I/Q window, canonical
project hypotheses, beta, and metric definition fixed while comparing the
next-symbol predictions and metrics from the pre-update and post-update
coefficient states. It is neither a receiver mode nor a paper-exact model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Integral, Real

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.receiver.iq_prediction import iq_quadratures_from_index
from hf_tcm.receiver.paper_recursion import update_quadrature_estimates
from hf_tcm.receiver.reconstruction_aggregate import compute_project_reconstruction_metric
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_labeling import (
    ASSUMED_NATURAL_BINARY,
    OUTPUT_BIT_ORDER,
    hypothesis_to_phase_index,
)
from hf_tcm.receiver.reconstruction_observation import ADR012_SAMPLES_PER_SYMBOL
from hf_tcm.receiver.reconstruction_posterior import initial_reconstruction_observation_update

FloatArray = NDArray[np.float64]
_HYPOTHESIS_COUNT = 16
_ABSOLUTE_TOLERANCE = 1e-10


def _finite_vector(value: ArrayLike, *, shape: tuple[int, ...], name: str) -> FloatArray:
    try:
        raw = np.asarray(value)
        if np.iscomplexobj(raw) or raw.dtype.kind not in "iuf":
            raise ValueError
        result = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real array with shape {shape}") from exc
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite real array with shape {shape}")
    return np.array(result, dtype=np.float64, order="C", copy=True)


def _readonly(value: ArrayLike, *, shape: tuple[int, ...], name: str) -> FloatArray:
    owned = _finite_vector(value, shape=shape, name=name)
    return np.frombuffer(owned.tobytes(), dtype=np.float64).reshape(shape)


def _index(value: object, *, name: str, nonnegative: bool = False) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")
    result = int(value)
    if nonnegative and result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


def _positive_finite(value: Real, *, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number > 0")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be a finite real number > 0")
    return result


def _finite_real(value: Real, *, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite real number")
    return result


def _canonical_phase_indices(hypothesis_ids: tuple[int, ...]) -> tuple[int, ...]:
    expected_ids = tuple(hypothesis.hypothesis_id for hypothesis in HYPOTHESES)
    if expected_ids != tuple(range(_HYPOTHESIS_COUNT)):
        raise RuntimeError("project HYPOTHESES must retain canonical IDs 0..15")
    if hypothesis_ids != expected_ids:
        raise ValueError("hypothesis_ids must use canonical project order 0..15")
    return tuple(
        hypothesis_to_phase_index(
            hypothesis,
            profile=ASSUMED_NATURAL_BINARY,
            bit_order=OUTPUT_BIT_ORDER,
        )
        for hypothesis in HYPOTHESES
    )


def _predictions(coefficients: FloatArray, phase_indices: tuple[int, ...]) -> FloatArray:
    return iq_quadratures_from_index(
        np.asarray(phase_indices, dtype=np.int64),
        np.full(_HYPOTHESIS_COUNT, coefficients[0], dtype=np.float64),
        np.full(_HYPOTHESIS_COUNT, coefficients[1], dtype=np.float64),
    )


def _metrics(received_iq: FloatArray, predictions_iq: FloatArray) -> FloatArray:
    rows = [
        compute_project_reconstruction_metric(
            received_iq,
            np.repeat(prediction[np.newaxis, :], ADR012_SAMPLES_PER_SYMBOL, axis=0),
        )
        for prediction in predictions_iq
    ]
    return np.asarray(rows, dtype=np.float64)


@dataclass(frozen=True, slots=True)
class ReconstructionUpdateIntervention:
    """Immutable result of one actual [A](1) update and next-row comparison."""

    symbol_index: int
    estimator_time_index: int
    symbol_origin_sample: int
    prediction_cutoff_sample: int
    observation_cutoff_sample: int
    next_metric_sample_window: tuple[int, ...]
    hypothesis_ids: tuple[int, ...]
    phase_indices: tuple[int, ...]
    beta: float
    posterior_update_mode: str
    innovation_provenance: str
    before_state: ReconstructionEstimatorState
    after_state: ReconstructionEstimatorState
    derived_weighted_innovation_iq: FloatArray
    coefficient_increment_iq: FloatArray
    before_predictions_iq: FloatArray
    after_predictions_iq: FloatArray
    delta_predictions_iq: FloatArray
    before_metrics: FloatArray
    after_metrics: FloatArray
    delta_metrics: FloatArray
    fixed_prior: FloatArray
    posterior_before: FloatArray
    posterior_after: FloatArray

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "derived_weighted_innovation_iq",
            _readonly(self.derived_weighted_innovation_iq, shape=(2,), name="innovation"),
        )
        object.__setattr__(
            self,
            "coefficient_increment_iq",
            _readonly(self.coefficient_increment_iq, shape=(2,), name="coefficient_increment"),
        )
        for name in ("before_predictions_iq", "after_predictions_iq", "delta_predictions_iq"):
            object.__setattr__(self, name, _readonly(getattr(self, name), shape=(16, 2), name=name))
        for name in (
            "before_metrics",
            "after_metrics",
            "delta_metrics",
            "fixed_prior",
            "posterior_before",
            "posterior_after",
        ):
            object.__setattr__(self, name, _readonly(getattr(self, name), shape=(16,), name=name))


def run_reconstruction_update_intervention(
    *,
    pre_fluctuating_iq: ArrayLike,
    mu0: ArrayLike,
    alpha_prime: Real,
    k_tilde: ArrayLike,
    current_observed_iq: ArrayLike,
    current_predicted_iq: ArrayLike,
    current_posterior: ArrayLike,
    next_received_iq_samples: ArrayLike,
    fixed_prior: ArrayLike,
    beta: Real,
    symbol_index: int = 0,
    estimator_time_index: int = 0,
    symbol_origin_sample: int = 0,
    hypothesis_ids: tuple[int, ...] = tuple(range(_HYPOTHESIS_COUNT)),
) -> ReconstructionUpdateIntervention:
    """Apply one explicit update, then compare next-symbol local metrics.

    The current update uses only the supplied current-symbol operands. The
    next received observation, 16 project hypotheses, ADR-002 labeling,
    squared-residual metric, and beta are identical before and after. The
    fixed-prior posterior comparison applies the existing first-edge
    observation update independently to the two metric rows; it is not a
    closed-loop sequence or a decoder invocation.
    """
    symbol = _index(symbol_index, name="symbol_index", nonnegative=True)
    tick = _index(estimator_time_index, name="estimator_time_index", nonnegative=True)
    origin = _index(symbol_origin_sample, name="symbol_origin_sample")
    if not isinstance(hypothesis_ids, tuple):
        raise ValueError("hypothesis_ids must be the explicit canonical tuple")
    ids = tuple(_index(item, name="hypothesis ID", nonnegative=True) for item in hypothesis_ids)
    phases = _canonical_phase_indices(ids)

    previous = _finite_vector(pre_fluctuating_iq, shape=(2,), name="pre_fluctuating_iq")
    regular = _finite_vector(mu0, shape=(2,), name="mu0")
    gain = _finite_vector(k_tilde, shape=(2,), name="k_tilde")
    observation = _finite_vector(current_observed_iq, shape=(2,), name="current_observed_iq")
    predictions = _finite_vector(current_predicted_iq, shape=(16, 2), name="current_predicted_iq")
    weights = _finite_vector(current_posterior, shape=(16,), name="current_posterior")
    next_received = _finite_vector(
        next_received_iq_samples,
        shape=(ADR012_SAMPLES_PER_SYMBOL, 2),
        name="next_received_iq_samples",
    )
    prior = _finite_vector(fixed_prior, shape=(16,), name="fixed_prior")
    alpha = _finite_real(alpha_prime, name="alpha_prime")
    beta_value = _positive_finite(beta, name="beta")
    if np.any(weights < 0.0) or not math.isclose(
        math.fsum(float(value) for value in weights), 1.0, rel_tol=0.0, abs_tol=1e-10
    ):
        raise ValueError("current_posterior must be a normalized nonnegative vector")
    if np.any(prior < 0.0) or not math.isclose(
        math.fsum(float(value) for value in prior), 1.0, rel_tol=0.0, abs_tol=1e-10
    ):
        raise ValueError("fixed_prior must be a normalized nonnegative vector")

    full_before = previous + regular
    before_state = ReconstructionEstimatorState(
        fluctuating_iq=previous[np.newaxis, :],
        full_iq=full_before[np.newaxis, :],
        time_index=tick,
    )

    # Independent, read-only scalar evaluation of the derived innovation.
    innovation = np.asarray(
        [
            math.fsum(
                float(weights[index]) * (float(observation[axis]) - float(predictions[index, axis]))
                for index in range(_HYPOTHESIS_COUNT)
            )
            for axis in range(2)
        ],
        dtype=np.float64,
    )
    next_fluctuating, next_full = update_quadrature_estimates(
        previous_fluctuating=previous,
        alpha_prime=alpha,
        k_tilde=gain,
        posterior=weights,
        observed_iq=observation,
        predicted_iq=predictions,
        mu0=regular,
    )
    after_state = ReconstructionEstimatorState(
        fluctuating_iq=next_fluctuating[np.newaxis, :],
        full_iq=next_full[np.newaxis, :],
        time_index=tick + 1,
    )

    before_prediction = _predictions(full_before, phases)
    after_prediction = _predictions(next_full, phases)
    before_metrics = _metrics(next_received, before_prediction)
    after_metrics = _metrics(next_received, after_prediction)
    posterior_before = initial_reconstruction_observation_update(
        prior=prior, candidate_metrics=before_metrics, beta=beta_value
    )
    posterior_after = initial_reconstruction_observation_update(
        prior=prior, candidate_metrics=after_metrics, beta=beta_value
    )
    first_next_sample = origin + ADR012_SAMPLES_PER_SYMBOL * (symbol + 1)

    return ReconstructionUpdateIntervention(
        symbol_index=symbol,
        estimator_time_index=tick,
        symbol_origin_sample=origin,
        prediction_cutoff_sample=origin + ADR012_SAMPLES_PER_SYMBOL * symbol - 1,
        observation_cutoff_sample=origin + ADR012_SAMPLES_PER_SYMBOL * (symbol + 1) - 1,
        next_metric_sample_window=tuple(
            range(first_next_sample, first_next_sample + ADR012_SAMPLES_PER_SYMBOL)
        ),
        hypothesis_ids=ids,
        phase_indices=phases,
        beta=beta_value,
        posterior_update_mode="fixed_prior_first_edge_update_no_transition",
        innovation_provenance="derived_scalar_sum_from_current_posterior_observation_predictions",
        before_state=before_state,
        after_state=after_state,
        derived_weighted_innovation_iq=innovation,
        coefficient_increment_iq=next_fluctuating - previous,
        before_predictions_iq=before_prediction,
        after_predictions_iq=after_prediction,
        delta_predictions_iq=after_prediction - before_prediction,
        before_metrics=before_metrics,
        after_metrics=after_metrics,
        delta_metrics=after_metrics - before_metrics,
        fixed_prior=prior,
        posterior_before=posterior_before,
        posterior_after=posterior_after,
    )
