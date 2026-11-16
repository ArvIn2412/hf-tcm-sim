"""Isolated causal candidate metrics for the narrow one-path profile."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Integral

import numpy as np
from numpy.typing import NDArray

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.receiver.reconstruction_aggregate import compute_project_reconstruction_metric
from hf_tcm.receiver.reconstruction_alignment import ZERO_PADDING
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_forward import (
    APPROXIMATE_RECTANGULAR_8SPS,
    RECTANGULAR_ZOH_RULE,
    predict_reconstructed_aggregate_iq,
)
from hf_tcm.receiver.reconstruction_forward_snapshot import snapshot_full_iq_for_forward
from hf_tcm.receiver.reconstruction_labeling import (
    ASSUMED_NATURAL_BINARY,
    OUTPUT_BIT_ORDER,
    hypothesis_to_phase_index,
)
from hf_tcm.receiver.reconstruction_observation import (
    ADR012_IQ_RULE,
    ADR012_PROFILE,
    ADR012_PROFILE_ID,
    ADR012_SAMPLES_PER_SYMBOL,
    ADR012_WAVEFORM_RULE,
    extract_adr012_observed_iq_samples,
)

FloatArray = NDArray[np.float64]
_HYPOTHESIS_COUNT = 16


def _validated_order(hypothesis_order: Sequence[int] | None) -> tuple[int, ...]:
    canonical = tuple(hypothesis.hypothesis_id for hypothesis in HYPOTHESES)
    if canonical != tuple(range(_HYPOTHESIS_COUNT)):
        raise RuntimeError("HYPOTHESES must retain stable hypothesis_id row order")
    if hypothesis_order is None:
        return canonical
    if (
        not isinstance(hypothesis_order, Sequence)
        or isinstance(hypothesis_order, (str, bytes))
        or len(hypothesis_order) != _HYPOTHESIS_COUNT
        or any(
            isinstance(item, (bool, np.bool_)) or not isinstance(item, Integral)
            for item in hypothesis_order
        )
    ):
        raise ValueError("hypothesis_order must be a permutation of hypothesis IDs 0..15")
    order = tuple(int(item) for item in hypothesis_order)
    if tuple(sorted(order)) != canonical:
        raise ValueError("hypothesis_order must be a permutation of hypothesis IDs 0..15")
    return order


def _absolute_index(value: object, *, name: str, nonnegative: bool = False) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer absolute index")
    result = int(value)
    if nonnegative and result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


@dataclass(frozen=True, slots=True)
class ReconstructionCandidateMetricResult:
    """Immutable metrics and aligned hypothesis/time provenance."""

    metrics: FloatArray
    sample_predictions_iq: FloatArray
    hypothesis_ids: tuple[int, ...]
    output_bits: tuple[tuple[int, int, int], ...]
    phase_indices: tuple[int, ...]
    target_symbol_index: int
    estimator_time_index: int
    sample_indices: tuple[int, ...]
    prediction_cutoff_sample_index: int
    metric_available_after_sample_index: int
    profile: str
    profile_id: str

    def __post_init__(self) -> None:
        array = np.asarray(self.metrics, dtype=np.float64)
        if array.shape != (_HYPOTHESIS_COUNT,) or not np.all(np.isfinite(array)):
            raise ValueError("metrics must be a finite vector with shape (16,)")
        if np.any(array < 0.0):
            raise ValueError("metrics must be non-negative")
        owned = np.array(array, dtype=np.float64, order="C", copy=True)
        immutable = np.frombuffer(owned.tobytes(), dtype=np.float64)
        object.__setattr__(self, "metrics", immutable)
        predictions = np.asarray(self.sample_predictions_iq, dtype=np.float64)
        if predictions.shape != (_HYPOTHESIS_COUNT, ADR012_SAMPLES_PER_SYMBOL, 2) or not np.all(
            np.isfinite(predictions)
        ):
            raise ValueError("sample_predictions_iq must be finite shape (16, 8, 2)")
        prediction_copy = np.array(predictions, dtype=np.float64, order="C", copy=True)
        immutable_predictions = np.frombuffer(prediction_copy.tobytes(), dtype=np.float64).reshape(
            prediction_copy.shape
        )
        object.__setattr__(self, "sample_predictions_iq", immutable_predictions)


def generate_reconstruction_candidate_metrics(
    *,
    received: object,
    absolute_sample_indices: object,
    received_start_sample: int,
    symbol_origin_sample: int,
    target_symbol_index: int,
    state: ReconstructionEstimatorState,
    time_index: int,
    profile: str,
    adr_profile: str,
    path_count: int,
    path_delays_samples: tuple[int, ...] | list[int],
    samples_per_symbol: int,
    iq_rule: str,
    waveform_rule: str,
    labeling_profile: str,
    bit_order: Sequence[str],
    timebase_profile: str,
    symbol_to_sample_rule: str,
    edge_policy: str,
    hypothesis_order: Sequence[int] | None = None,
) -> ReconstructionCandidateMetricResult:
    """Generate one ``F_rx`` value for each local TCM edge hypothesis.

    Predictions use the pre-observation state's ``full_iq``. Candidate phase
    indices are derived from each hypothesis's M1 ``output_bits`` through the
    explicit assumed-numeric labeling adapter. Metrics compare all eight
    per-sample ADR-012 I/Q pairs and never use the averaged recursion operand.
    """
    symbol = _absolute_index(target_symbol_index, name="target_symbol_index", nonnegative=True)
    clock = _absolute_index(time_index, name="time_index", nonnegative=True)
    origin = _absolute_index(symbol_origin_sample, name="symbol_origin_sample")
    _absolute_index(received_start_sample, name="received_start_sample")
    if not isinstance(state, ReconstructionEstimatorState):
        raise ValueError("state must be a ReconstructionEstimatorState")
    if state.time_index != clock:
        raise ValueError("time_index must explicitly match pre-observation state.time_index")
    if state.full_iq.shape != (1, 2) or state.fluctuating_iq.shape != (1, 2):
        raise ValueError("candidate metrics require an L=1 estimator state of shape (1, 2)")
    if profile != ADR012_PROFILE:
        raise ValueError("profile must be 'reconstructed_offline' for ADR-012")
    if adr_profile != ADR012_PROFILE_ID:
        raise ValueError("adr_profile must be the exact accepted ADR-012 L=1 profile")
    if path_count != 1:
        raise ValueError("candidate metrics require L=1")
    if tuple(path_delays_samples) != (0,):
        raise ValueError("candidate metrics require exactly one zero-delay path")
    if samples_per_symbol != ADR012_SAMPLES_PER_SYMBOL:
        raise ValueError("candidate metrics require exactly 8 samples per symbol")
    if iq_rule != ADR012_IQ_RULE:
        raise ValueError("iq_rule must select the exact ADR-012 I/Q mapping and mean")
    if waveform_rule != ADR012_WAVEFORM_RULE:
        raise ValueError("candidate metrics require rectangular ZOH")
    if labeling_profile != ASSUMED_NATURAL_BINARY:
        raise ValueError(f"labeling_profile must be {ASSUMED_NATURAL_BINARY!r}")
    if tuple(bit_order) != OUTPUT_BIT_ORDER:
        raise ValueError(f"bit_order must be {OUTPUT_BIT_ORDER!r}")
    if timebase_profile != APPROXIMATE_RECTANGULAR_8SPS:
        raise ValueError(f"timebase_profile must be {APPROXIMATE_RECTANGULAR_8SPS!r}")
    if symbol_to_sample_rule != RECTANGULAR_ZOH_RULE:
        raise ValueError(f"symbol_to_sample_rule must be {RECTANGULAR_ZOH_RULE!r}")
    if edge_policy != ZERO_PADDING:
        raise ValueError("edge_policy must be 'zero_padding'")

    first_sample = origin + ADR012_SAMPLES_PER_SYMBOL * symbol
    sample_indices = tuple(range(first_sample, first_sample + ADR012_SAMPLES_PER_SYMBOL))
    # Snapshot and all candidate predictions are constructed before inspecting
    # current-symbol observations. The prior state is the prediction cutoff.
    snapshot = snapshot_full_iq_for_forward(state, estimator_time_index=clock)
    order = _validated_order(hypothesis_order)
    predictions: list[FloatArray] = []
    output_bits: list[tuple[int, int, int]] = []
    phase_indices: list[int] = []
    for hypothesis_id in order:
        hypothesis = HYPOTHESES[hypothesis_id]
        bits = hypothesis.output_bits
        phase_index = hypothesis_to_phase_index(
            hypothesis,
            profile=labeling_profile,
            bit_order=bit_order,
        )
        prediction = predict_reconstructed_aggregate_iq(
            candidate_output_bits=(bits,),
            estimated_path_coefficients=snapshot.estimated_path_coefficients,
            path_delays_samples=(0,),
            # The one-symbol forward frame is anchored directly at this
            # candidate's absolute start; no earlier or future candidate bits
            # are synthesized to reach target_symbol_index.
            symbol_origin_sample=first_sample,
            frame_start_sample=first_sample,
            frame_sample_count=ADR012_SAMPLES_PER_SYMBOL,
            labeling_profile=labeling_profile,
            bit_order=bit_order,
            timebase_profile=timebase_profile,
            symbol_to_sample_rule=symbol_to_sample_rule,
            edge_policy=edge_policy,
        )
        if prediction.shape != (ADR012_SAMPLES_PER_SYMBOL, 2):
            raise RuntimeError("forward model returned an unexpected single-symbol shape")
        predictions.append(prediction)
        output_bits.append(tuple(int(bit) for bit in bits))
        phase_indices.append(phase_index)

    observed_samples = extract_adr012_observed_iq_samples(
        received,
        absolute_sample_indices=absolute_sample_indices,
        received_start_sample=received_start_sample,
        symbol_origin_sample=origin,
        target_symbol_index=symbol,
        profile=profile,
        adr_profile=adr_profile,
        path_count=path_count,
        path_delays_samples=path_delays_samples,
        samples_per_symbol=samples_per_symbol,
        iq_rule=iq_rule,
        waveform_rule=waveform_rule,
    )
    metrics = [
        compute_project_reconstruction_metric(observed_samples, prediction)
        for prediction in predictions
    ]

    return ReconstructionCandidateMetricResult(
        metrics=np.asarray(metrics, dtype=np.float64),
        sample_predictions_iq=np.stack(predictions, axis=0),
        hypothesis_ids=order,
        output_bits=tuple(output_bits),
        phase_indices=tuple(phase_indices),
        target_symbol_index=symbol,
        estimator_time_index=clock,
        sample_indices=sample_indices,
        prediction_cutoff_sample_index=first_sample - 1,
        metric_available_after_sample_index=sample_indices[-1],
        profile=ADR012_PROFILE,
        profile_id=ADR012_PROFILE_ID,
    )
