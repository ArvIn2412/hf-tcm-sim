"""Run explicit-operand reconstruction estimator steps in absolute time order."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from numpy.typing import ArrayLike

from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_estimator_step import (
    advance_reconstruction_estimator_state,
)


@dataclass(frozen=True, slots=True)
class ReconstructionEstimatorStepOperands:
    """All explicit operands and clock labels for one single-beam step."""

    time_index: int
    next_time_index: int
    alpha_prime: float
    k_tilde: ArrayLike
    mu0: ArrayLike
    observed_iq: ArrayLike
    predicted_iq: ArrayLike
    posterior: ArrayLike


@dataclass(frozen=True, slots=True)
class ReconstructionEstimatorSequenceResult:
    """Final state and optional immutable snapshots, including initial state."""

    final_state: ReconstructionEstimatorState
    history: tuple[ReconstructionEstimatorState, ...] | None


def run_reconstruction_estimator_sequence(
    initial_state: ReconstructionEstimatorState,
    steps: Sequence[ReconstructionEstimatorStepOperands],
    *,
    include_history: bool = False,
) -> ReconstructionEstimatorSequenceResult:
    """Run explicit ``L=1`` operands sequentially through the existing step API.

    Each step must begin at the current state's absolute ``time_index`` and
    advance exactly one index. If requested, history contains the initial
    snapshot followed by every successor snapshot.
    """
    if not isinstance(initial_state, ReconstructionEstimatorState):
        raise ValueError("initial_state must be a ReconstructionEstimatorState")
    if not isinstance(steps, Sequence):
        raise ValueError("steps must be a sequence of explicit step operands")
    if not isinstance(include_history, bool):
        raise ValueError("include_history must be a bool")

    state = initial_state
    history: list[ReconstructionEstimatorState] | None = (
        [initial_state] if include_history else None
    )
    for step in steps:
        if not isinstance(step, ReconstructionEstimatorStepOperands):
            raise ValueError("each step must be ReconstructionEstimatorStepOperands")
        state = advance_reconstruction_estimator_state(
            state,
            time_index=step.time_index,
            next_time_index=step.next_time_index,
            alpha_prime=step.alpha_prime,
            k_tilde=step.k_tilde,
            mu0=step.mu0,
            observed_iq=step.observed_iq,
            predicted_iq=step.predicted_iq,
            posterior=step.posterior,
        )
        if history is not None:
            history.append(state)

    return ReconstructionEstimatorSequenceResult(
        final_state=state,
        history=None if history is None else tuple(history),
    )
