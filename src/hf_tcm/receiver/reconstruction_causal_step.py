"""Causal one-symbol bridge to the explicit-operand estimator step."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_estimator_step import advance_reconstruction_estimator_state
from hf_tcm.receiver.reconstruction_forward_snapshot import (
    ReconstructionForwardCoefficientSnapshot,
    snapshot_full_iq_for_forward,
)
from hf_tcm.receiver.reconstruction_observation import extract_adr012_observed_iq

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class CausalOnePathSymbolStep:
    """One completed-symbol update and its next-symbol forward snapshot."""

    observed_iq: FloatArray
    previous_time_index: int
    processed_symbol_index: int
    available_after_sample_index: int
    prediction_data_cutoff_sample: int
    posterior_data_cutoff_sample: int
    next_usable_symbol_index: int
    next_state: ReconstructionEstimatorState
    forward_snapshot: ReconstructionForwardCoefficientSnapshot

    def __post_init__(self) -> None:
        observed = np.asarray(self.observed_iq, dtype=np.float64)
        if observed.shape != (2,) or not np.all(np.isfinite(observed)):
            raise ValueError("observed_iq must be finite shape (2,)")
        owned = np.array(observed, dtype=np.float64, copy=True)
        immutable = np.frombuffer(owned.tobytes(), dtype=np.float64)
        object.__setattr__(self, "observed_iq", immutable)
        for name in (
            "previous_time_index",
            "processed_symbol_index",
            "available_after_sample_index",
            "prediction_data_cutoff_sample",
            "posterior_data_cutoff_sample",
            "next_usable_symbol_index",
        ):
            value = getattr(self, name)
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
                raise ValueError(f"{name} must be an integer absolute index")
            object.__setattr__(self, name, int(value))


def advance_real_one_path_symbol(
    state: ReconstructionEstimatorState,
    received: ArrayLike,
    *,
    absolute_sample_indices: ArrayLike,
    received_start_sample: int,
    symbol_origin_sample: int,
    target_symbol_index: int,
    time_index: int,
    profile: str,
    adr_profile: str,
    path_count: int,
    path_delays_samples: tuple[int, ...] | list[int],
    samples_per_symbol: int,
    iq_rule: str,
    alpha_prime: float,
    k_tilde: ArrayLike,
    mu0: ArrayLike,
    predicted_iq: ArrayLike,
    posterior: ArrayLike,
    prediction_data_cutoff_sample: int,
    posterior_data_cutoff_sample: int,
    waveform_rule: str,
) -> CausalOnePathSymbolStep:
    """Extract one completed symbol, update once, and snapshot for later use.

    The caller explicitly pairs ``target_symbol_index`` and ``time_index``;
    this API does not convert between their origins. The state label must
    equal the supplied pre-observation estimator index. After the update the
    estimator clock is ``time_index + 1`` and the result is usable from symbol
    ``target_symbol_index + 1`` onward.
    """
    if not isinstance(state, ReconstructionEstimatorState):
        raise ValueError("state must be a ReconstructionEstimatorState")
    if isinstance(target_symbol_index, (bool, np.bool_)) or not isinstance(
        target_symbol_index, Integral
    ):
        raise ValueError("target_symbol_index must be an integer absolute index")
    symbol = int(target_symbol_index)
    if isinstance(time_index, (bool, np.bool_)) or not isinstance(time_index, Integral):
        raise ValueError("time_index must be an integer absolute estimator index")
    current_time = int(time_index)
    if state.time_index != current_time:
        raise ValueError("time_index must match state.time_index before observation")

    observed = extract_adr012_observed_iq(
        received,
        absolute_sample_indices=absolute_sample_indices,
        received_start_sample=received_start_sample,
        symbol_origin_sample=symbol_origin_sample,
        target_symbol_index=symbol,
        profile=profile,
        adr_profile=adr_profile,
        path_count=path_count,
        path_delays_samples=path_delays_samples,
        samples_per_symbol=samples_per_symbol,
        iq_rule=iq_rule,
        waveform_rule=waveform_rule,
    )
    available_after = int(symbol_origin_sample) + 8 * (symbol + 1) - 1
    for name, value in (
        ("prediction_data_cutoff_sample", prediction_data_cutoff_sample),
        ("posterior_data_cutoff_sample", posterior_data_cutoff_sample),
    ):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
            raise ValueError(f"{name} must be an integer absolute sample index")
        if int(value) > available_after:
            raise ValueError(f"{name} cannot be later than the current symbol cutoff")
    next_state = advance_reconstruction_estimator_state(
        state,
        time_index=current_time,
        next_time_index=current_time + 1,
        alpha_prime=alpha_prime,
        k_tilde=k_tilde,
        mu0=mu0,
        observed_iq=observed,
        predicted_iq=predicted_iq,
        posterior=posterior,
    )
    snapshot = snapshot_full_iq_for_forward(
        next_state,
        estimator_time_index=current_time + 1,
    )
    return CausalOnePathSymbolStep(
        observed_iq=observed,
        previous_time_index=current_time,
        processed_symbol_index=symbol,
        available_after_sample_index=available_after,
        prediction_data_cutoff_sample=int(prediction_data_cutoff_sample),
        posterior_data_cutoff_sample=int(posterior_data_cutoff_sample),
        next_usable_symbol_index=symbol + 1,
        next_state=next_state,
        forward_snapshot=snapshot,
    )
