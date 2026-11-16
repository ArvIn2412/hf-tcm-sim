"""Numerically stable finite-state posterior recursion infrastructure.

This generic Bayes update does not establish the article's likelihood model,
its ``theta`` indexing, equation (7) for 8PSK TCM, or estimator equation [A](1).
All probability models are supplied explicitly by the caller.
"""

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.hypotheses import HYPOTHESES

HYPOTHESIS_COUNT = len(HYPOTHESES)
_PROBABILITY_TOLERANCE = 1e-10


def build_allowed_transition_matrix() -> NDArray[np.uint8]:
    """Build the 0/1 adjacency mask for consecutive M4.1 hypotheses.

    Row ``i`` may transition to column ``j`` exactly when hypothesis ``i``'s
    next encoder state equals hypothesis ``j``'s current encoder state. The
    matrix is structural only; its ones are not probabilities.
    """
    allowed = np.zeros((HYPOTHESIS_COUNT, HYPOTHESIS_COUNT), dtype=np.uint8)
    for row, current in enumerate(HYPOTHESES):
        for column, following in enumerate(HYPOTHESES):
            allowed[row, column] = current.next_state == following.current_state
    return allowed


ALLOWED_HYPOTHESIS_TRANSITIONS = build_allowed_transition_matrix()
ALLOWED_HYPOTHESIS_TRANSITIONS.setflags(write=False)


def _as_float_array(values: ArrayLike, *, name: str) -> NDArray[np.float64]:
    try:
        result = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must contain numeric values") from exc
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _probability_vector(
    values: ArrayLike,
    *,
    name: str,
    require_normalized: bool,
) -> NDArray[np.float64]:
    result = _as_float_array(values, name=name)
    if result.shape != (HYPOTHESIS_COUNT,):
        raise ValueError(f"{name} must have shape ({HYPOTHESIS_COUNT},)")
    if np.any(result < 0.0):
        raise ValueError(f"{name} must be non-negative")
    if np.any(result > 1.0 + _PROBABILITY_TOLERANCE):
        raise ValueError(f"{name} probabilities must not exceed 1")

    total = math.fsum(float(value) for value in result)
    if total <= 0.0:
        raise ValueError(f"{name} must sum to 1")
    if require_normalized and not math.isclose(
        total,
        1.0,
        rel_tol=_PROBABILITY_TOLERANCE,
        abs_tol=_PROBABILITY_TOLERANCE,
    ):
        raise ValueError(f"{name} must sum to 1")
    return result / total


def _transition_matrix(values: ArrayLike) -> NDArray[np.float64]:
    result = _as_float_array(values, name="transition_matrix")
    expected_shape = (HYPOTHESIS_COUNT, HYPOTHESIS_COUNT)
    if result.shape != expected_shape:
        raise ValueError(f"transition_matrix must have shape {expected_shape}")
    if np.any(result < 0.0):
        raise ValueError("transition_matrix must be non-negative")
    if np.any(result > 1.0 + _PROBABILITY_TOLERANCE):
        raise ValueError("transition_matrix probabilities must not exceed 1")
    if np.any(result[ALLOWED_HYPOTHESIS_TRANSITIONS == 0] > 0.0):
        raise ValueError("transition_matrix assigns positive mass to a forbidden transition")

    row_sums = np.array(
        [math.fsum(float(value) for value in row) for row in result],
        dtype=np.float64,
    )
    if not np.allclose(
        row_sums,
        1.0,
        rtol=_PROBABILITY_TOLERANCE,
        atol=_PROBABILITY_TOLERANCE,
    ):
        raise ValueError("transition_matrix must be row-stochastic (each row must sum to 1)")
    return result / row_sums[:, np.newaxis]


def _likelihood_vector(values: ArrayLike) -> NDArray[np.float64]:
    result = _as_float_array(values, name="likelihoods")
    if result.shape != (HYPOTHESIS_COUNT,):
        raise ValueError(f"likelihoods must have shape ({HYPOTHESIS_COUNT},)")
    if np.any(result < 0.0):
        raise ValueError("likelihoods must be non-negative")
    return result


def _logsumexp(values: NDArray[np.float64], *, axis: int) -> NDArray[np.float64]:
    """Compute log(sum(exp(values))) without overflowing or underflowing."""
    return np.logaddexp.reduce(values, axis=axis)


def posterior_update(
    initial_distribution: ArrayLike,
    transition_matrix: ArrayLike,
    likelihoods: ArrayLike,
) -> NDArray[np.float64]:
    """Return one normalized posterior update over the 16 M4.1 hypotheses.

    Inputs are explicit: a normalized initial distribution, a row-stochastic
    transition-probability matrix supported only on structurally allowed
    M4.1 edges, and a non-negative likelihood vector. No model is inferred or
    supplied by default. A zero total evidence likelihood raises ``ValueError``.
    """
    prior = _probability_vector(
        initial_distribution,
        name="initial_distribution",
        require_normalized=True,
    )
    transitions = _transition_matrix(transition_matrix)
    likelihood = _likelihood_vector(likelihoods)

    with np.errstate(divide="ignore"):
        log_prior = np.log(prior)
        log_transitions = np.log(transitions)
        log_likelihood = np.log(likelihood)

    log_predictive = _logsumexp(log_prior[:, np.newaxis] + log_transitions, axis=0)
    log_unnormalized = log_predictive + log_likelihood
    log_evidence = float(_logsumexp(log_unnormalized, axis=0))
    if not math.isfinite(log_evidence):
        raise ValueError("likelihoods produce zero evidence for the supplied prior and transitions")

    posterior = np.exp(log_unnormalized - log_evidence)
    posterior /= math.fsum(float(value) for value in posterior)
    return posterior
