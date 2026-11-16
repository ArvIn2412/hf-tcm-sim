"""One explicit received-to-bits smoke run for the narrow reconstructed profile.

This evaluation-side composition is not a Monte Carlo driver, SNR experiment,
matched baseline, validated performance claim, or paper reproduction.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from numbers import Integral, Real
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.encoder import INITIAL_STATE
from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.evaluation.error_metrics import (
    ErrorAggregate,
    ErrorCounts,
    ErrorEvaluation,
    ErrorRates,
    aggregate_error_counts,
    calculate_ber_ser,
    decoded_path_symbol_indices,
    encode_reference_symbol_indices,
    evaluate_run,
)
from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION, index_to_label
from hf_tcm.modulation.psk8 import modulate
from hf_tcm.receiver.iq import symbols_to_iq_waveform
from hf_tcm.receiver.reconstruction_conditional_decode import (
    ReconstructionConditionalDecodeResult,
    decode_reconstruction_conditional_sequence,
)
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_forward import (
    APPROXIMATE_RECTANGULAR_8SPS,
    RECTANGULAR_ZOH_RULE,
)
from hf_tcm.receiver.reconstruction_labeling import (
    ASSUMED_NATURAL_BINARY,
    OUTPUT_BIT_ORDER,
)
from hf_tcm.receiver.reconstruction_observation import (
    ADR012_IQ_RULE,
    ADR012_PROFILE,
    ADR012_PROFILE_ID,
    ADR012_SAMPLES_PER_SYMBOL,
    ADR012_WAVEFORM_RULE,
)
from hf_tcm.receiver.reconstruction_segmented_decode import (
    ReconstructionSegmentedDecodeResult,
    ReconstructionSequenceSegment,
    decode_reconstruction_segmented_sequence,
)
from hf_tcm.reconstruction_config import validate_reconstructed_offline_config

EXPERIMENT_NAME = (
    "isolated reproducible single-path BER/SER smoke experiment, "
    "NOT validated performance comparison, NOT reproduction of paper results"
)
ORACLE_INITIALIZATION_LABEL = "oracle-initialized control experiment"
ReceiverMode = Literal["monolithic", "segmented"]
ReceiverResult = ReconstructionConditionalDecodeResult | ReconstructionSegmentedDecodeResult
IntArray = NDArray[np.int8]
FloatArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]


def _integer(value: object, *, name: str, minimum: int | None = None) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")
    result = int(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return result


def _real(value: object, *, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite real number")
    return result


def _readonly(values: ArrayLike, *, dtype: np.dtype, shape: tuple[int, ...], name: str) -> NDArray:
    try:
        raw = np.asarray(values)
        if np.iscomplexobj(raw) and dtype.kind != "c":
            raise ValueError
        result = np.asarray(raw, dtype=dtype)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must have finite values and shape {shape}") from exc
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must have finite values and shape {shape}")
    owned = np.array(result, dtype=dtype, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=dtype).reshape(shape)


def _configuration_profile(
    configuration: object, *, symbol_origin_sample: int, initial_time_index: int
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    try:
        validated = validate_reconstructed_offline_config(configuration)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"configuration is not a valid reconstructed_offline profile: {exc}"
        ) from exc
    labeling = validated["labeling"]
    timebase = validated["timebase"]
    observation = validated["observation_model"]
    estimator = validated["estimator"]
    if labeling["name"] != ASSUMED_NATURAL_BINARY:
        raise ValueError("configuration must use the accepted ADR-002 assumed_natural_binary map")
    if tuple(labeling["bit_order"]) != OUTPUT_BIT_ORDER or tuple(labeling["output_to_b"]) != tuple(
        range(8)
    ):
        raise ValueError("configuration labeling must match the accepted ADR-002 mapping")
    if labeling["phase_offset_rad"] != 0.0:
        raise ValueError("configuration phase_offset_rad must be 0 for the M4 real-channel profile")
    if (
        timebase["name"] != APPROXIMATE_RECTANGULAR_8SPS
        or timebase["samples_per_symbol"] != ADR012_SAMPLES_PER_SYMBOL
        or timebase["path_count"] != 1
        or tuple(timebase["path_delays_samples"]) != (0,)
        or timebase["symbol_origin_sample"] != symbol_origin_sample
    ):
        raise ValueError(
            "configuration symbol_origin_sample/timebase must match L=1, zero-delay, 8-sample ADR-012"
        )
    if (
        observation["kind"] != "adr012_l1_real_mean8"
        or observation["iq_rule"] != "(-Im(received), Re(received))"
        or observation["sample_reduction"] != "arithmetic_mean_exactly_8"
        or observation["waveform_rule"] != "rectangular_zoh"
    ):
        raise ValueError("configuration must select the exact accepted ADR-012 observation profile")
    if estimator["initial_time_index"] != initial_time_index:
        raise ValueError("initial_estimator_time_index must match configuration.estimator")
    return validated, labeling, timebase, estimator


@dataclass(frozen=True, slots=True)
class ReconstructionSmokeExperimentResult:
    """Evaluation record for one explicit independent coded-sequence run."""

    run_id: str
    symbol_count: int
    receiver_mode: ReceiverMode
    experiment_name: str
    received_source: str
    real_channel_gain: float
    perturbation_provenance: str
    initial_csi_provenance: str
    reference_data_provenance: str
    configuration_json: str
    beta: float
    alpha_prime: float
    k_tilde: FloatArray
    mu0: FloatArray
    initial_estimator_state: ReconstructionEstimatorState
    symbol_origin_sample: int
    first_symbol_index: int
    initial_estimator_time_index: int
    clean_received: ComplexArray
    perturbation: ComplexArray
    received: ComplexArray
    reference_information_bits: IntArray
    decoded_information_bits: IntArray
    reference_symbol_indices: NDArray[np.int64]
    decoded_symbol_indices: NDArray[np.int64]
    candidate_metrics: FloatArray
    decoded_hypothesis_path: tuple[int, ...]
    decoded_path_valid: bool
    final_estimator_state: ReconstructionEstimatorState
    final_posterior: FloatArray
    receiver_result: ReceiverResult
    evaluation: ErrorEvaluation
    absolute_sample_indices: tuple[int, ...]
    absolute_symbol_indices: tuple[int, ...]
    estimator_time_indices: tuple[int, ...]
    prediction_cutoff_sample_indices: tuple[int, ...]
    observation_cutoff_sample_indices: tuple[int, ...]

    @property
    def bit_errors(self) -> int:
        return self.evaluation.counts.bit_errors

    @property
    def total_bits(self) -> int:
        return self.evaluation.counts.total_bits

    @property
    def ber(self) -> float:
        return self.evaluation.ber

    @property
    def symbol_errors(self) -> int:
        return self.evaluation.counts.symbol_errors

    @property
    def total_symbols(self) -> int:
        return self.evaluation.counts.total_symbols

    @property
    def coded_symbol_ser(self) -> float:
        return self.evaluation.ser

    @property
    def ser(self) -> float:
        return self.evaluation.ser


@dataclass(frozen=True, slots=True)
class ReconstructionSmokeAggregate:
    """Pooled smoke-run counts and retained run records, without CI claims."""

    run_records: tuple[ReconstructionSmokeExperimentResult, ...]
    error_aggregate: ErrorAggregate
    rates: ErrorRates
    statistical_claim_status: str = "smoke_only_not_monte_carlo"

    @property
    def run_ids(self) -> tuple[str, ...]:
        return tuple(record.run_id for record in self.run_records)

    @property
    def error_counts(self) -> ErrorCounts:
        return self.error_aggregate.counts

    @property
    def ber(self) -> float:
        return self.rates.ber

    @property
    def ser(self) -> float:
        return self.rates.ser


def run_reconstruction_smoke_experiment(
    *,
    run_id: str,
    symbol_count: int,
    reference_information_bits: ArrayLike,
    real_channel_gain: Real,
    perturbation: ArrayLike,
    perturbation_provenance: str,
    symbol_origin_sample: int,
    first_symbol_index: int,
    initial_estimator_time_index: int,
    configuration: Mapping[str, object],
    receiver_mode: ReceiverMode,
    segment_partition: Sequence[int] | None,
    initial_csi_provenance: str,
) -> ReconstructionSmokeExperimentResult:
    """Generate one explicit real-channel input, decode, then evaluate it.

    `reference_information_bits` is used only before receiver invocation to
    form a separate transmit-side waveform and after decoding for measurement;
    it is never included in the keyword arguments passed to B5c or B5d.
    All estimator and likelihood operands are sourced from the validated,
    explicit inactive reconstruction configuration.
    """
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id must be a nonempty explicit identifier")
    count = _integer(symbol_count, name="symbol_count", minimum=1)
    gain = _real(real_channel_gain, name="real_channel_gain")
    origin = _integer(symbol_origin_sample, name="symbol_origin_sample")
    first_symbol = _integer(first_symbol_index, name="first_symbol_index", minimum=0)
    first_time = _integer(initial_estimator_time_index, name="initial_estimator_time_index")
    if not isinstance(perturbation_provenance, str) or not perturbation_provenance.strip():
        raise ValueError("perturbation_provenance must be explicitly documented")
    if not isinstance(initial_csi_provenance, str) or not initial_csi_provenance.strip():
        raise ValueError("initial_csi_provenance must be explicitly documented")
    if receiver_mode not in ("monolithic", "segmented"):
        raise ValueError("receiver_mode must be 'monolithic' or 'segmented'")
    if receiver_mode == "monolithic" and segment_partition is not None:
        raise ValueError("segment_partition must be None in monolithic mode")
    if receiver_mode == "segmented":
        if not isinstance(segment_partition, Sequence) or isinstance(
            segment_partition, (str, bytes)
        ):
            raise ValueError("segmented mode requires an explicit segment partition")
        partition = tuple(
            _integer(part, name="segment partition entry", minimum=1) for part in segment_partition
        )
        if not partition or sum(partition) != count:
            raise ValueError(
                "segment partition must contain positive sizes summing to symbol_count"
            )
    else:
        partition = ()

    validated, labeling, timebase, estimator = _configuration_profile(
        configuration,
        symbol_origin_sample=origin,
        initial_time_index=first_time,
    )
    try:
        reference_bits = np.asarray(reference_information_bits)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("reference_information_bits must be a one-dimensional bit array") from exc
    if (
        reference_bits.ndim != 1
        or reference_bits.shape != (2 * count,)
        or reference_bits.dtype.kind not in "iub"
        or np.any((reference_bits != 0) & (reference_bits != 1))
    ):
        raise ValueError("reference_information_bits must have exactly 2F bits")
    reference_bit_copy = _readonly(
        reference_bits,
        dtype=np.dtype(np.int8),
        shape=(2 * count,),
        name="reference_information_bits",
    )
    reference_symbol_indices = encode_reference_symbol_indices(
        reference_bit_copy,
        profile=ASSUMED_NATURAL_BINARY,
        bit_order=OUTPUT_BIT_ORDER,
    )
    mapped_labels = [
        index_to_label(int(index), profile=BASELINE_ASSUMPTION)
        for index in reference_symbol_indices
    ]
    symbol_values = modulate(
        mapped_labels,
        phase_offset=float(labeling["phase_offset_rad"]),
        profile=BASELINE_ASSUMPTION,
    )
    in_phase, quadrature = symbols_to_iq_waveform(
        symbol_values,
        samples_per_symbol=ADR012_SAMPLES_PER_SYMBOL,
    )
    clean = np.asarray(gain * (in_phase + 1j * quadrature), dtype=np.complex128)
    received_perturbation = np.asarray(perturbation)
    if (
        received_perturbation.shape != (count * ADR012_SAMPLES_PER_SYMBOL,)
        or not np.iscomplexobj(received_perturbation)
        or not np.all(np.isfinite(received_perturbation.real))
        or not np.all(np.isfinite(received_perturbation.imag))
    ):
        raise ValueError("perturbation must be a finite complex array with shape (8F,)")
    received_start = origin + ADR012_SAMPLES_PER_SYMBOL * first_symbol
    labels = np.arange(received_start, received_start + count * 8, dtype=np.int64)
    received = clean + np.asarray(received_perturbation, dtype=np.complex128)

    initial_estimates = estimator["initial_estimates"]
    initial_state = ReconstructionEstimatorState(
        initial_estimates["fluctuating_iq"],
        initial_estimates["full_iq"],
        first_time,
    )
    if initial_csi_provenance.strip() == ORACLE_INITIALIZATION_LABEL and (
        not np.array_equal(initial_state.fluctuating_iq, [[gain, gain]])
        or not np.array_equal(initial_state.full_iq, [[gain, gain]])
    ):
        raise ValueError(
            "oracle-initialized control estimate must explicitly equal the real channel gain"
        )
    if tuple(validated["initial"]["state"]) != INITIAL_STATE:
        raise ValueError("independent coded sequences must use ADR-004 encoder state (0, 0)")
    beta = _real(validated["likelihood"]["beta"], name="beta")
    alpha_prime = _real(estimator["alpha_prime"], name="alpha_prime")
    k_tilde = _readonly(
        estimator["k_tilde"], dtype=np.dtype(np.float64), shape=(1, 2), name="k_tilde"
    )
    mu0 = _readonly(estimator["mu0"], dtype=np.dtype(np.float64), shape=(1, 2), name="mu0")
    symbols = tuple(range(first_symbol, first_symbol + count))
    common_operands = {
        "received": received,
        "absolute_sample_indices": labels,
        "received_start_sample": received_start,
        "symbol_origin_sample": origin,
        "sequence_origin_symbol_index": first_symbol,
        "initial_estimator_state": initial_state,
        "initial_estimator_time_index": first_time,
        "initial_encoder_state": tuple(validated["initial"]["state"]),
        "beta": beta,
        "alpha_prime": alpha_prime,
        "k_tilde": k_tilde,
        "mu0": mu0,
        "profile": ADR012_PROFILE,
        "adr_profile": ADR012_PROFILE_ID,
        "path_count": 1,
        "path_delays_samples": (0,),
        "samples_per_symbol": ADR012_SAMPLES_PER_SYMBOL,
        "iq_rule": ADR012_IQ_RULE,
        "waveform_rule": ADR012_WAVEFORM_RULE,
        "labeling_profile": labeling["name"],
        "bit_order": tuple(labeling["bit_order"]),
        "timebase_profile": timebase["name"],
        "symbol_to_sample_rule": RECTANGULAR_ZOH_RULE,
        "edge_policy": "zero_padding",
    }
    if receiver_mode == "monolithic":
        receiver_result: ReceiverResult = decode_reconstruction_conditional_sequence(
            **common_operands,
            first_symbol_index=first_symbol,
            symbol_count=count,
            symbol_indices=symbols,
            sequence_mode="new_independent_sequence",
        )
    else:
        segments: list[ReconstructionSequenceSegment] = []
        symbol_offset = 0
        sample_offset = 0
        for segment_size in partition:
            segments.append(
                ReconstructionSequenceSegment(
                    first_symbol_index=first_symbol + symbol_offset,
                    received_start_offset=sample_offset,
                    symbol_count=segment_size,
                )
            )
            symbol_offset += segment_size
            sample_offset += segment_size * ADR012_SAMPLES_PER_SYMBOL
        receiver_result = decode_reconstruction_segmented_sequence(
            **common_operands,
            segments=tuple(segments),
        )

    core = (
        receiver_result.decode_result
        if isinstance(receiver_result, ReconstructionSegmentedDecodeResult)
        else receiver_result
    )
    decoded_path = tuple(core.decoded_hypothesis_path)
    validate_hypothesis_edge_path(decoded_path, initial_state=INITIAL_STATE)
    decoded_symbol_indices = decoded_path_symbol_indices(
        decoded_path,
        profile=ASSUMED_NATURAL_BINARY,
        bit_order=OUTPUT_BIT_ORDER,
    )
    evaluation = evaluate_run(
        reference_bit_copy,
        core.decoded_information_bits,
        reference_symbol_indices,
        decoded_symbol_indices,
    )
    readonly_clean = _readonly(
        clean,
        dtype=np.dtype(np.complex128),
        shape=(count * 8,),
        name="clean_received",
    )
    readonly_perturbation = _readonly(
        received_perturbation,
        dtype=np.dtype(np.complex128),
        shape=(count * 8,),
        name="perturbation",
    )
    readonly_received = _readonly(
        received,
        dtype=np.dtype(np.complex128),
        shape=(count * 8,),
        name="received",
    )
    readonly_metrics = _readonly(
        core.candidate_metrics,
        dtype=np.dtype(np.float64),
        shape=(count, 16),
        name="candidate_metrics",
    )
    readonly_posterior = _readonly(
        core.final_posterior,
        dtype=np.dtype(np.float64),
        shape=(16,),
        name="final_posterior",
    )
    decoded_bits = _readonly(
        core.decoded_information_bits,
        dtype=np.dtype(np.int8),
        shape=(2 * count,),
        name="decoded_information_bits",
    )
    readonly_reference_symbols = _readonly(
        reference_symbol_indices,
        dtype=np.dtype(np.int64),
        shape=(count,),
        name="reference_symbol_indices",
    )
    readonly_decoded_symbols = _readonly(
        decoded_symbol_indices,
        dtype=np.dtype(np.int64),
        shape=(count,),
        name="decoded_symbol_indices",
    )
    configuration_json = json.dumps(validated, sort_keys=True, separators=(",", ":"))
    return ReconstructionSmokeExperimentResult(
        run_id=run_id.strip(),
        symbol_count=count,
        receiver_mode=receiver_mode,
        experiment_name=EXPERIMENT_NAME,
        received_source=(
            "M1 encode + ADR-002 8PSK + explicit real gain + M3 rectangular ZOH + explicit perturbation"
        ),
        real_channel_gain=gain,
        perturbation_provenance=perturbation_provenance.strip(),
        initial_csi_provenance=initial_csi_provenance.strip(),
        reference_data_provenance="explicit reference bits; evaluation side only; no RNG",
        configuration_json=configuration_json,
        beta=beta,
        alpha_prime=alpha_prime,
        k_tilde=k_tilde,
        mu0=mu0,
        initial_estimator_state=initial_state,
        symbol_origin_sample=origin,
        first_symbol_index=first_symbol,
        initial_estimator_time_index=first_time,
        clean_received=readonly_clean,
        perturbation=readonly_perturbation,
        received=readonly_received,
        reference_information_bits=reference_bit_copy,
        decoded_information_bits=decoded_bits,
        reference_symbol_indices=readonly_reference_symbols,
        decoded_symbol_indices=readonly_decoded_symbols,
        candidate_metrics=readonly_metrics,
        decoded_hypothesis_path=decoded_path,
        decoded_path_valid=True,
        final_estimator_state=core.final_estimator_state,
        final_posterior=readonly_posterior,
        receiver_result=receiver_result,
        evaluation=evaluation,
        absolute_sample_indices=tuple(int(value) for value in labels),
        absolute_symbol_indices=core.symbol_indices,
        estimator_time_indices=core.estimator_time_indices,
        prediction_cutoff_sample_indices=core.prediction_cutoff_sample_indices,
        observation_cutoff_sample_indices=core.observation_cutoff_sample_indices,
    )


def aggregate_reconstruction_smoke_runs(
    runs: Sequence[ReconstructionSmokeExperimentResult],
) -> ReconstructionSmokeAggregate:
    """Pool a small explicit run set while retaining all individual run records."""
    records = tuple(runs)
    if not records or any(
        not isinstance(run, ReconstructionSmokeExperimentResult) for run in records
    ):
        raise ValueError("runs must contain one or more smoke experiment records")
    run_ids = tuple(run.run_id for run in records)
    if len(set(run_ids)) != len(run_ids):
        raise ValueError("run_id values must be unique within an aggregate")
    pooled = aggregate_error_counts(tuple(run.evaluation for run in records))
    return ReconstructionSmokeAggregate(
        run_records=records,
        error_aggregate=pooled,
        rates=calculate_ber_ser(pooled),
    )
