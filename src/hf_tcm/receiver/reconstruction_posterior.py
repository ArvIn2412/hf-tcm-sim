"""Project reconstruction transition, likelihood, and posterior adapters.

These functions operate on the local ordered 16-edge hypothesis space. They
do not implement the paper's posterior model or construct candidate metrics.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from numbers import Integral, Real

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.posterior import (
    ALLOWED_HYPOTHESIS_TRANSITIONS,
    HYPOTHESIS_COUNT,
    posterior_update,
)

FloatArray = NDArray[np.float64]
_INITIAL_STATE = (0, 0)
_PROBABILITY_TOLERANCE = 1e-10


def _finite_real_vector(values: ArrayLike, *, name: str) -> FloatArray:
    try:
        raw = np.asarray(values)
        if np.iscomplexobj(raw) or raw.dtype.kind not in "iuf":
            raise ValueError
        result = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real vector") from exc
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _canonical_hypothesis_order() -> None:
    if len(HYPOTHESES) != HYPOTHESIS_COUNT:
        raise RuntimeError("canonical hypothesis count does not match posterior API")
    if tuple(hypothesis.hypothesis_id for hypothesis in HYPOTHESES) != tuple(
        range(HYPOTHESIS_COUNT)
    ):
        raise RuntimeError("HYPOTHESES must retain stable hypothesis_id row order")


def _validated_hypothesis_order(hypothesis_order: Sequence[int] | None) -> NDArray[np.int64]:
    if hypothesis_order is None:
        _canonical_hypothesis_order()
        return np.arange(HYPOTHESIS_COUNT, dtype=np.int64)
    if (
        not isinstance(hypothesis_order, Sequence)
        or isinstance(hypothesis_order, (str, bytes))
        or len(hypothesis_order) != HYPOTHESIS_COUNT
        or any(
            isinstance(item, (bool, np.bool_)) or not isinstance(item, Integral)
            for item in hypothesis_order
        )
    ):
        raise ValueError("hypothesis_order must be a permutation of hypothesis IDs 0..15")
    order = np.asarray(hypothesis_order, dtype=np.int64)
    if not np.array_equal(np.sort(order), np.arange(HYPOTHESIS_COUNT)):
        raise ValueError("hypothesis_order must be a permutation of hypothesis IDs 0..15")
    return order


def _structural_mask_from_hypotheses() -> NDArray[np.bool_]:
    _canonical_hypothesis_order()
    return np.array(
        [
            [previous.next_state == following.current_state for following in HYPOTHESES]
            for previous in HYPOTHESES
        ],
        dtype=bool,
    )


def build_reconstruction_transition_matrix(
    *, hypothesis_order: Sequence[int] | None = None
) -> FloatArray:
    """Build ADR-003 row-stochastic probabilities in canonical edge order.

    Matrix row ``h`` is the previous edge and column ``k`` the next edge.
    Each structurally allowed destination receives ``1/d(h)`` where ``d``
    is counted from the current structural mask; forbidden transitions are 0.
    The returned array is immutable and is distinct from the 0/1 mask.
    """
    order = _validated_hypothesis_order(hypothesis_order)
    structural_canonical = _structural_mask_from_hypotheses()
    mask = np.asarray(ALLOWED_HYPOTHESIS_TRANSITIONS, dtype=bool)
    if mask.shape != (HYPOTHESIS_COUNT, HYPOTHESIS_COUNT) or not np.array_equal(
        mask, structural_canonical
    ):
        raise RuntimeError("posterior structural mask/order disagrees with HYPOTHESES")

    structural = structural_canonical[np.ix_(order, order)]
    degrees = structural.sum(axis=1)
    if np.any(degrees == 0):
        raise RuntimeError("every hypothesis must have at least one allowed successor")
    probabilities = structural.astype(np.float64) / degrees[:, np.newaxis]
    if np.any(probabilities[~structural] != 0.0):
        raise RuntimeError("transition probabilities escaped structural support")
    if not np.allclose(probabilities.sum(axis=1), 1.0, rtol=0.0, atol=1e-15):
        raise RuntimeError("reconstruction transition matrix is not row-stochastic")

    owned = np.array(probabilities, dtype=np.float64, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=np.float64).reshape(owned.shape)


def build_initial_reconstruction_prior(
    *,
    initial_state: Sequence[int],
    hypothesis_order: Sequence[int] | None = None,
) -> FloatArray:
    """Return ADR-004's edge prior, uniform by ``current_state`` only.

    The accepted reconstruction profile fixes the encoder initial state to
    ``(0, 0)``. Hypothesis IDs and next states are not used to choose support.
    """
    if (
        not isinstance(initial_state, Sequence)
        or isinstance(initial_state, (str, bytes))
        or len(initial_state) != 2
        or any(
            isinstance(bit, (bool, np.bool_)) or not isinstance(bit, Integral) or bit not in (0, 1)
            for bit in initial_state
        )
    ):
        raise ValueError("initial_state must be a pair of integer bits")
    if tuple(initial_state) != _INITIAL_STATE:
        raise ValueError("ADR-004 requires initial_state=(0, 0)")

    order = _validated_hypothesis_order(hypothesis_order)
    support = np.array(
        [hypothesis.current_state == _INITIAL_STATE for hypothesis in HYPOTHESES],
        dtype=bool,
    )
    support_count = int(support.sum())
    if support_count != 4:
        raise RuntimeError("ADR-004 expects exactly four edges with current_state=(0, 0)")
    prior = np.zeros(HYPOTHESIS_COUNT, dtype=np.float64)
    prior[support] = 1.0 / support_count
    prior = prior[order]
    return np.frombuffer(prior.tobytes(), dtype=np.float64)


def _finite_positive_beta(beta: Real) -> float:
    if isinstance(beta, (bool, np.bool_)) or not isinstance(beta, Real):
        raise ValueError("beta must be a finite real number > 0")
    try:
        value = float(beta)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("beta must be a finite real number > 0") from exc
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("beta must be a finite real number > 0")
    return value


def _validated_distribution(values: ArrayLike, *, name: str) -> FloatArray:
    distribution = _finite_real_vector(values, name=name)
    if distribution.shape != (HYPOTHESIS_COUNT,):
        raise ValueError(f"{name} must have shape ({HYPOTHESIS_COUNT},)")
    if np.any(distribution < 0.0) or np.any(distribution > 1.0 + _PROBABILITY_TOLERANCE):
        raise ValueError(f"{name} must contain probabilities in [0, 1]")
    total = math.fsum(float(value) for value in distribution)
    if not math.isclose(
        total,
        1.0,
        rel_tol=_PROBABILITY_TOLERANCE,
        abs_tol=_PROBABILITY_TOLERANCE,
    ):
        raise ValueError(f"{name} must sum to 1")
    return distribution / total


def _shifted_likelihood(
    metrics: FloatArray,
    beta: float,
    *,
    active_support: NDArray[np.bool_],
) -> FloatArray:
    if active_support.shape != (HYPOTHESIS_COUNT,) or not np.any(active_support):
        raise ValueError("active likelihood support must contain at least one hypothesis")
    minimum = float(np.min(metrics[active_support]))
    differences = metrics - minimum
    likelihood = np.zeros(HYPOTHESIS_COUNT, dtype=np.float64)
    with np.errstate(over="ignore", under="ignore", invalid="raise"):
        scaled = beta * differences[active_support]
        likelihood[active_support] = np.exp(-scaled)
    if not np.all(np.isfinite(likelihood)) or np.any(likelihood < 0.0):
        raise ValueError("likelihood scaling is outside the supported numeric range")
    if not np.any(likelihood[active_support] > 0.0):
        raise ValueError("likelihood scaling produced zero evidence on active support")
    return likelihood


def reconstruction_likelihood(candidate_metrics: ArrayLike, *, beta: Real) -> FloatArray:
    """Return stable likelihood weights proportional to ``exp(-beta*F_rx)``.

    A common log shift subtracts the best log-likelihood before exponentiation.
    This only multiplies the entire likelihood vector by one positive scalar,
    so normalized posterior probabilities are unchanged. Finite products that
    exceed floating-point range become zero relative weights; the best metric
    remains exactly one. Non-finite inputs and invalid beta are rejected.
    """
    metrics = _finite_real_vector(candidate_metrics, name="candidate_metrics")
    if metrics.shape != (HYPOTHESIS_COUNT,):
        raise ValueError(f"candidate_metrics must have shape ({HYPOTHESIS_COUNT},)")
    if np.any(metrics < 0.0):
        raise ValueError("candidate_metrics must be non-negative")
    scale = _finite_positive_beta(beta)
    active = np.ones(HYPOTHESIS_COUNT, dtype=bool)
    return _shifted_likelihood(metrics, scale, active_support=active)


def initial_reconstruction_observation_update(
    *,
    prior: ArrayLike,
    candidate_metrics: ArrayLike,
    beta: Real,
) -> FloatArray:
    """Apply the first observation to the initial edge prior without transition.

    The initial prior already describes the first edge from encoder state
    ``(0,0)``. The first edge's own metric updates that distribution directly;
    applying the transition matrix here would skip the first edge.
    """
    distribution = _validated_distribution(prior, name="prior")
    metrics = _finite_real_vector(candidate_metrics, name="candidate_metrics")
    if metrics.shape != (HYPOTHESIS_COUNT,):
        raise ValueError(f"candidate_metrics must have shape ({HYPOTHESIS_COUNT},)")
    if np.any(metrics < 0.0):
        raise ValueError("candidate_metrics must be non-negative")
    scale = _finite_positive_beta(beta)
    active = distribution > 0.0
    likelihood = _shifted_likelihood(metrics, scale, active_support=active)
    weighted = distribution * likelihood
    evidence = math.fsum(float(value) for value in weighted)
    if not math.isfinite(evidence) or evidence <= 0.0:
        raise ValueError("first observation produced zero or non-finite evidence")
    posterior = weighted / evidence
    posterior /= math.fsum(float(value) for value in posterior)
    return posterior


def transition_reconstruction_posterior(
    previous_posterior: ArrayLike,
    candidate_metrics: ArrayLike,
    *,
    beta: Real,
    hypothesis_order: Sequence[int] | None = None,
) -> FloatArray:
    """Transition from edge time ``t`` then apply the metric emission at ``t+1``.

    This adapter supplies ADR-003 transition probabilities and ADR-005 shifted
    likelihoods to the existing generic ``coding.posterior.posterior_update``.
    Its output is the posterior over the next edge, not the current edge.
    If ``hypothesis_order`` is supplied, prior, metrics, and output use that
    sequence of canonical hypothesis IDs; the adapter remaps internally.
    """
    order = _validated_hypothesis_order(hypothesis_order)
    prior_in_order = _validated_distribution(previous_posterior, name="previous_posterior")
    metrics = _finite_real_vector(candidate_metrics, name="candidate_metrics")
    if metrics.shape != (HYPOTHESIS_COUNT,):
        raise ValueError(f"candidate_metrics must have shape ({HYPOTHESIS_COUNT},)")
    if np.any(metrics < 0.0):
        raise ValueError("candidate_metrics must be non-negative")
    scale = _finite_positive_beta(beta)
    prior = np.zeros(HYPOTHESIS_COUNT, dtype=np.float64)
    metrics_canonical = np.empty(HYPOTHESIS_COUNT, dtype=np.float64)
    prior[order] = prior_in_order
    metrics_canonical[order] = metrics

    transitions = build_reconstruction_transition_matrix()
    active_next = np.any(transitions[prior > 0.0] > 0.0, axis=0)
    likelihood = _shifted_likelihood(metrics_canonical, scale, active_support=active_next)
    posterior_canonical = posterior_update(
        initial_distribution=prior,
        transition_matrix=transitions,
        likelihoods=likelihood,
    )
    return posterior_canonical[order]
