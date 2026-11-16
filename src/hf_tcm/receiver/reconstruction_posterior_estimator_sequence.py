"""Explicitly scheduled causal single-path reconstruction symbol sequences."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Integral, Real
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_observation import ADR012_SAMPLES_PER_SYMBOL
from hf_tcm.receiver.reconstruction_posterior import build_initial_reconstruction_prior
from hf_tcm.receiver.reconstruction_posterior_estimator_step import (
    ReconstructionPosteriorEstimatorStepResult,
    process_reconstruction_posterior_estimator_step,
)

FloatArray = NDArray[np.float64]
SequenceMode = Literal["new_independent_sequence", "continuation"]


def _integer(value: object, *, name: str, nonnegative: bool = False) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer absolute index")
    result = int(value)
    if nonnegative and result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


def _readonly_posterior(value: ArrayLike) -> FloatArray:
    try:
        raw = np.asarray(value)
        if np.iscomplexobj(raw):
            raise ValueError
        posterior = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("final_posterior must be a finite real vector of shape (16,)") from exc
    if posterior.shape != (len(HYPOTHESES),) or not np.all(np.isfinite(posterior)):
        raise ValueError("final_posterior must be a finite real vector of shape (16,)")
    if np.any(posterior < 0.0) or not math.isclose(
        math.fsum(float(value) for value in posterior), 1.0, rel_tol=1e-10, abs_tol=1e-10
    ):
        raise ValueError("final_posterior must be a normalized probability vector")
    owned = np.array(posterior, dtype=np.float64, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=np.float64)


def _alpha_schedule(value: Real | Sequence[Real], *, count: int) -> tuple[float, ...]:
    if isinstance(value, Real) and not isinstance(value, (bool, np.bool_)):
        values = (float(value),) * count
    else:
        try:
            raw = np.asarray(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("alpha_prime schedule must provide one value per symbol") from exc
        if raw.ndim != 1 or raw.shape != (count,) or raw.dtype.kind not in "iuf":
            raise ValueError("alpha_prime schedule must provide one value per symbol")
        values = tuple(float(item) for item in raw)
    if not all(math.isfinite(item) for item in values):
        raise ValueError("alpha_prime values must be finite")
    return values


def _iq_parameter_schedule(value: ArrayLike, *, name: str, count: int) -> tuple[FloatArray, ...]:
    try:
        raw = np.asarray(value)
        if np.iscomplexobj(raw) or raw.dtype.kind not in "iuf":
            raise ValueError
        array = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            f"{name} must be a finite real (1, 2) value or (N, 1, 2) schedule"
        ) from exc
    if array.shape == (1, 2):
        arrays = tuple(np.array(array, dtype=np.float64, copy=True) for _ in range(count))
    elif array.shape == (count, 1, 2):
        arrays = tuple(
            np.array(array[index], dtype=np.float64, copy=True) for index in range(count)
        )
    else:
        raise ValueError(f"{name} must have shape (1, 2) or ({count}, 1, 2)")
    if any(not np.all(np.isfinite(item)) for item in arrays):
        raise ValueError(f"{name} values must be finite")
    return arrays


@dataclass(frozen=True, slots=True)
class ReconstructionSequenceSymbolResult:
    """Immutable diagnostics and explicit clock labels for one processed symbol."""

    symbol_index: int
    estimator_time_index: int
    first_sample_index: int
    last_sample_index: int
    b4c_result: ReconstructionPosteriorEstimatorStepResult


@dataclass(frozen=True, slots=True)
class ReconstructionPosteriorEstimatorSequenceResult:
    """Final state/posterior and optional per-symbol immutable history."""

    final_state: ReconstructionEstimatorState
    final_posterior: FloatArray
    run_mode: SequenceMode
    sequence_origin_symbol_index: int
    first_symbol_index: int
    final_symbol_index: int
    next_symbol_index: int
    initial_estimator_time_index: int
    final_estimator_time_index: int
    symbol_origin_sample: int
    received_start_sample: int
    symbol_count: int
    history: tuple[ReconstructionSequenceSymbolResult, ...] | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "final_posterior", _readonly_posterior(self.final_posterior))


def run_reconstruction_posterior_estimator_sequence(
    *,
    received: ArrayLike,
    absolute_sample_indices: ArrayLike,
    received_start_sample: int,
    symbol_origin_sample: int,
    first_symbol_index: int,
    sequence_origin_symbol_index: int,
    symbol_count: int,
    symbol_indices: Sequence[int],
    initial_state: ReconstructionEstimatorState,
    initial_estimator_time_index: int,
    run_mode: SequenceMode,
    initial_prior: ArrayLike | None,
    previous_posterior: ArrayLike | None,
    continuation_from_symbol_index: int | None,
    continuation_from_estimator_time_index: int | None,
    beta: Real,
    alpha_prime: Real | Sequence[Real],
    k_tilde: ArrayLike,
    mu0: ArrayLike,
    include_history: bool,
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
) -> ReconstructionPosteriorEstimatorSequenceResult:
    """Run one continuous buffer through the existing B4c step per symbol.

    ``new_independent_sequence`` applies the ADR-004 initial edge prior once,
    without transition. ``continuation`` requires the posterior and clocks of
    the immediately preceding completed symbol and starts with one transition.
    Neither mode resets at frame/reporting boundaries; this API handles one
    contiguous received buffer for exactly the requested complete symbols.
    """
    if run_mode not in ("new_independent_sequence", "continuation"):
        raise ValueError("run_mode must be 'new_independent_sequence' or 'continuation'")
    if not isinstance(initial_state, ReconstructionEstimatorState):
        raise ValueError("initial_state must be a ReconstructionEstimatorState")
    if not isinstance(include_history, bool):
        raise ValueError("include_history must be a bool")

    first_symbol = _integer(first_symbol_index, name="first_symbol_index", nonnegative=True)
    sequence_origin = _integer(
        sequence_origin_symbol_index,
        name="sequence_origin_symbol_index",
        nonnegative=True,
    )
    count = _integer(symbol_count, name="symbol_count", nonnegative=True)
    if count < 1:
        raise ValueError("symbol_count must be positive")
    origin = _integer(symbol_origin_sample, name="symbol_origin_sample")
    first_time = _integer(initial_estimator_time_index, name="initial_estimator_time_index")
    received_start = _integer(received_start_sample, name="received_start_sample")
    if initial_state.time_index != first_time:
        raise ValueError("initial state time_index must equal initial_estimator_time_index")

    try:
        raw_symbol_indices = np.asarray(symbol_indices)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("symbol_indices must explicitly list one integer per symbol") from exc
    if (
        raw_symbol_indices.ndim != 1
        or raw_symbol_indices.shape != (count,)
        or raw_symbol_indices.dtype.kind not in "iu"
    ):
        raise ValueError("symbol_indices must explicitly list one integer per symbol")
    indices = tuple(int(item) for item in raw_symbol_indices)
    expected_indices = tuple(range(first_symbol, first_symbol + count))
    if indices != expected_indices:
        raise ValueError("symbol_indices must be contiguous with no duplicates or skipped symbols")

    expected_received_start = origin + ADR012_SAMPLES_PER_SYMBOL * first_symbol
    if received_start != expected_received_start:
        raise ValueError("received_start_sample must start at sample O+8*first_symbol_index")
    expected_sample_count = count * ADR012_SAMPLES_PER_SYMBOL
    try:
        samples = np.asarray(received)
        labels_raw = np.asarray(absolute_sample_indices)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("received and absolute_sample_indices must be arrays") from exc
    if samples.ndim != 1 or not np.iscomplexobj(samples):
        raise ValueError("received must be a one-dimensional complex aggregate buffer")
    if samples.shape != (expected_sample_count,):
        raise ValueError("received must contain exactly 8 samples per requested symbol")
    if not np.all(np.isfinite(samples.real)) or not np.all(np.isfinite(samples.imag)):
        raise ValueError("received samples must be finite")
    if (
        labels_raw.shape != samples.shape
        or labels_raw.ndim != 1
        or labels_raw.dtype.kind not in "iu"
    ):
        raise ValueError("absolute_sample_indices must label every received sample with integers")
    expected_labels = np.arange(
        received_start, received_start + expected_sample_count, dtype=np.int64
    )
    if not np.array_equal(labels_raw, expected_labels):
        raise ValueError("absolute_sample_indices must be contiguous from received_start_sample")

    if run_mode == "new_independent_sequence":
        if (
            initial_prior is None
            or previous_posterior is not None
            or continuation_from_symbol_index is not None
            or continuation_from_estimator_time_index is not None
        ):
            raise ValueError(
                "new_independent_sequence requires initial_prior and forbids continuation operands"
            )
        if first_symbol != sequence_origin:
            raise ValueError("new independent sequence must begin at sequence_origin_symbol_index")
        expected_prior = build_initial_reconstruction_prior(initial_state=(0, 0))
        try:
            prior_raw = np.asarray(initial_prior)
            if np.iscomplexobj(prior_raw):
                raise ValueError
            supplied_prior = np.asarray(prior_raw, dtype=np.float64)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("initial_prior must be the ADR-004 edge prior") from exc
        if supplied_prior.shape != (len(HYPOTHESES),) or not np.allclose(
            supplied_prior, expected_prior, rtol=0.0, atol=1e-12
        ):
            raise ValueError("initial_prior must be the ADR-004 prior for current_state=(0, 0)")
    else:
        if initial_prior is not None or previous_posterior is None:
            raise ValueError("continuation requires previous_posterior and forbids initial_prior")
        if continuation_from_symbol_index is None or continuation_from_estimator_time_index is None:
            raise ValueError("continuation requires preceding symbol and estimator time labels")
        previous_symbol = _integer(
            continuation_from_symbol_index,
            name="continuation_from_symbol_index",
            nonnegative=True,
        )
        previous_time = _integer(
            continuation_from_estimator_time_index,
            name="continuation_from_estimator_time_index",
        )
        if first_symbol != previous_symbol + 1:
            raise ValueError("continuation first symbol must immediately follow preceding symbol")
        if previous_symbol < sequence_origin:
            raise ValueError("continuation predecessor cannot precede sequence origin")
        if first_time != previous_time + 1:
            raise ValueError(
                "continuation state time_index must equal preceding estimator time + 1"
            )

    alphas = _alpha_schedule(alpha_prime, count=count)
    gains = _iq_parameter_schedule(k_tilde, name="k_tilde", count=count)
    regular_values = _iq_parameter_schedule(mu0, name="mu0", count=count)
    if not isinstance(beta, Real) or isinstance(beta, (bool, np.bool_)):
        raise ValueError("beta must be a finite real number > 0")
    try:
        beta_value = float(beta)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("beta must be a finite real number > 0") from exc
    if not math.isfinite(beta_value) or beta_value <= 0.0:
        raise ValueError("beta must be a finite real number > 0")

    state = initial_state
    current_posterior: ArrayLike | None = previous_posterior
    history: list[ReconstructionSequenceSymbolResult] | None = [] if include_history else None
    canonical_ids = tuple(hypothesis.hypothesis_id for hypothesis in HYPOTHESES)
    for offset, symbol in enumerate(indices):
        estimator_time = first_time + offset
        if state.time_index != estimator_time:
            raise ValueError("estimator clock is not continuous across sequence steps")
        first_sample = origin + ADR012_SAMPLES_PER_SYMBOL * symbol
        final_sample = first_sample + ADR012_SAMPLES_PER_SYMBOL - 1
        prefix_end = (offset + 1) * ADR012_SAMPLES_PER_SYMBOL
        step_result = process_reconstruction_posterior_estimator_step(
            received=samples[:prefix_end],
            absolute_sample_indices=labels_raw[:prefix_end],
            received_start_sample=received_start,
            symbol_origin_sample=origin,
            target_symbol_index=symbol,
            state=state,
            time_index=estimator_time,
            edge_mode=(
                "first_edge"
                if run_mode == "new_independent_sequence" and offset == 0
                else "later_edge"
            ),
            initial_prior=initial_prior
            if run_mode == "new_independent_sequence" and offset == 0
            else None,
            previous_posterior=(
                None
                if run_mode == "new_independent_sequence" and offset == 0
                else current_posterior
            ),
            beta=beta,
            alpha_prime=alphas[offset],
            k_tilde=gains[offset],
            mu0=regular_values[offset],
            prediction_data_cutoff_sample=first_sample - 1,
            posterior_data_cutoff_sample=final_sample,
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
        if step_result.hypothesis_ids != canonical_ids:
            raise ValueError("B4c result changed canonical HYPOTHESES order within the sequence")
        if step_result.next_state.time_index != estimator_time + 1:
            raise ValueError("B4c step did not advance estimator clock by exactly one")
        if step_result.next_usable_symbol_index != symbol + 1:
            raise ValueError("B4c successor state is not labelled for the next symbol")
        if history is not None:
            history.append(
                ReconstructionSequenceSymbolResult(
                    symbol_index=symbol,
                    estimator_time_index=estimator_time,
                    first_sample_index=first_sample,
                    last_sample_index=final_sample,
                    b4c_result=step_result,
                )
            )
        state = step_result.next_state
        current_posterior = step_result.posterior

    if current_posterior is None:
        raise RuntimeError("non-empty sequence did not produce a posterior")
    final_symbol = indices[-1]
    return ReconstructionPosteriorEstimatorSequenceResult(
        final_state=state,
        final_posterior=np.asarray(current_posterior),
        run_mode=run_mode,
        sequence_origin_symbol_index=sequence_origin,
        first_symbol_index=first_symbol,
        final_symbol_index=final_symbol,
        next_symbol_index=final_symbol + 1,
        initial_estimator_time_index=first_time,
        final_estimator_time_index=state.time_index,
        symbol_origin_sample=origin,
        received_start_sample=received_start,
        symbol_count=count,
        history=None if history is None else tuple(history),
    )
