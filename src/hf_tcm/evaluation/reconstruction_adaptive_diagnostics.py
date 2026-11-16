"""Paired evaluation diagnostics for frozen and adaptive [A](1) estimates.

This module composes existing B4d and B5b APIs. It is evaluation-only: true
gain and reference bits are used to create/score the fixture, never passed to
the estimator or decoder.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from numbers import Integral, Real
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.encoder import INITIAL_STATE
from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.decoding.reconstruction_viterbi import (
    ReconstructionViterbiResult,
    decode_reconstruction_viterbi,
)
from hf_tcm.evaluation.error_metrics import (
    ErrorEvaluation,
    decoded_path_symbol_indices,
    encode_reference_symbol_indices,
    evaluate_run,
)
from hf_tcm.evaluation.matched_m2_b5_experiment import (
    ORACLE_CSI_MATCHED_CONTROL,
    generate_independent_complex_awgn,
)
from hf_tcm.evaluation.matched_m2_observation import effective_discrete_gamma_b
from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION, index_to_label
from hf_tcm.modulation.psk8 import modulate
from hf_tcm.receiver.iq import symbols_to_iq_waveform
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
from hf_tcm.receiver.reconstruction_posterior import build_initial_reconstruction_prior
from hf_tcm.receiver.reconstruction_posterior_estimator_sequence import (
    run_reconstruction_posterior_estimator_sequence,
)
from hf_tcm.reconstruction_config import validate_reconstructed_offline_config

FloatArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]
BitArray = NDArray[np.int8]
SymbolArray = NDArray[np.int64]
ReceiverMode = Literal["monolithic", "segmented"]

ORACLE_FROZEN = "oracle_frozen"
MISMATCHED_FROZEN = "mismatched_frozen"
MISMATCHED_ADAPTIVE = "mismatched_adaptive"
EXPERIMENT_STATUS = (
    "isolated adaptive-estimator diagnostic experiment, NOT validated BER advantage, "
    "NOT paper-exact receiver"
)


def _immutable(values: ArrayLike, *, dtype: np.dtype, shape: tuple[int, ...], name: str) -> NDArray:
    try:
        raw = np.asarray(values)
        if np.iscomplexobj(raw) and dtype.kind != "c":
            raise ValueError
        array = np.asarray(raw, dtype=dtype)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite and have shape {shape}") from exc
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be finite and have shape {shape}")
    owned = np.array(array, dtype=dtype, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=dtype).reshape(shape)


def _integer(value: object, *, name: str, minimum: int | None = None) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")
    result = int(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return result


def _positive_real(value: object, *, name: str, allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite positive real value")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be a finite positive real value")
    return result


def _readonly_bits(value: ArrayLike) -> BitArray:
    raw = np.asarray(value)
    if (
        raw.ndim != 1
        or raw.size == 0
        or raw.size % 2
        or raw.dtype.kind not in "iub"
        or np.any((raw != 0) & (raw != 1))
    ):
        raise ValueError("reference_information_bits must contain 2F binary integers")
    return _immutable(
        raw,
        dtype=np.dtype(np.int8),
        shape=(raw.size,),
        name="reference_information_bits",
    )


def _immutable_received(noise: ArrayLike | None, *, shape: tuple[int, ...]) -> ComplexArray:
    try:
        raw = np.asarray(noise)
        if not np.iscomplexobj(raw):
            raise ValueError
        values = np.asarray(raw, dtype=np.complex128)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"noise must be a complex array with shape {shape}") from exc
    if (
        values.shape != shape
        or not np.all(np.isfinite(values.real))
        or not np.all(np.isfinite(values.imag))
    ):
        raise ValueError(f"noise must be finite and have shape {shape}")
    owned = np.array(values, dtype=np.complex128, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=np.complex128)


def _config_operands(
    configuration: Mapping[str, object], *, origin: int, initial_time: int
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    validated = validate_reconstructed_offline_config(configuration)
    labeling = validated["labeling"]
    timebase = validated["timebase"]
    observation = validated["observation_model"]
    estimator = validated["estimator"]
    if (
        labeling["name"] != ASSUMED_NATURAL_BINARY
        or tuple(labeling["bit_order"]) != OUTPUT_BIT_ORDER
        or tuple(labeling["output_to_b"]) != tuple(range(8))
        or labeling["phase_offset_rad"] != 0.0
    ):
        raise ValueError("configuration must use the accepted explicit ADR-002 mapping")
    if (
        timebase["name"] != APPROXIMATE_RECTANGULAR_8SPS
        or timebase["samples_per_symbol"] != ADR012_SAMPLES_PER_SYMBOL
        or timebase["symbol_origin_sample"] != origin
        or timebase["path_count"] != 1
        or tuple(timebase["path_delays_samples"]) != (0,)
    ):
        raise ValueError("configuration must match L=1, zero-delay, 8-sample ADR-012")
    if (
        observation["kind"] != "adr012_l1_real_mean8"
        or observation["iq_rule"] != "(-Im(received), Re(received))"
        or observation["sample_reduction"] != "arithmetic_mean_exactly_8"
        or observation["waveform_rule"] != ADR012_WAVEFORM_RULE
    ):
        raise ValueError("configuration must use the accepted ADR-012 profile")
    if estimator["initial_time_index"] != initial_time:
        raise ValueError("initial estimator clock must match the explicit run clock")
    return validated, labeling, timebase


def _schedule_alpha(value: Real | Sequence[Real], *, count: int) -> tuple[float, ...]:
    if isinstance(value, Real) and not isinstance(value, (bool, np.bool_)):
        values = (float(value),) * count
    else:
        array = np.asarray(value)
        if array.ndim != 1 or array.shape != (count,) or array.dtype.kind not in "iuf":
            raise ValueError("adaptive alpha_prime must be scalar or an explicit (F,) schedule")
        values = tuple(float(item) for item in array)
    if not all(math.isfinite(item) for item in values):
        raise ValueError("adaptive alpha_prime values must be finite")
    return values


def _schedule_iq(value: ArrayLike, *, name: str, count: int) -> tuple[FloatArray, ...]:
    try:
        raw = np.asarray(value)
        if np.iscomplexobj(raw):
            raise ValueError
        array = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite shape (1,2) or (F,1,2)") from exc
    if array.shape == (1, 2):
        values = tuple(np.array(array, dtype=np.float64, copy=True) for _ in range(count))
    elif array.shape == (count, 1, 2):
        values = tuple(
            np.array(array[index], dtype=np.float64, copy=True) for index in range(count)
        )
    else:
        raise ValueError(f"{name} must have shape (1,2) or ({count},1,2)")
    if any(not np.all(np.isfinite(item)) for item in values):
        raise ValueError(f"{name} values must be finite")
    return values


@dataclass(frozen=True, slots=True)
class AdaptiveEstimatorSymbolDiagnostic:
    """One B4d row copied from the actual recursion pass and its state handoff."""

    absolute_symbol_index: int
    estimator_time_index: int
    first_sample_index: int
    last_sample_index: int
    prediction_cutoff_sample_index: int
    observation_cutoff_sample_index: int
    pre_state: ReconstructionEstimatorState
    observed_iq: FloatArray
    predicted_iq: FloatArray
    candidate_metrics: FloatArray
    posterior: FloatArray
    post_state: ReconstructionEstimatorState
    fluctuating_increment: FloatArray
    full_increment: FloatArray
    full_estimate_error_norm: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observed_iq",
            _immutable(
                self.observed_iq, dtype=np.dtype(np.float64), shape=(2,), name="observed_iq"
            ),
        )
        object.__setattr__(
            self,
            "predicted_iq",
            _immutable(
                self.predicted_iq, dtype=np.dtype(np.float64), shape=(16, 2), name="predicted_iq"
            ),
        )
        object.__setattr__(
            self,
            "candidate_metrics",
            _immutable(
                self.candidate_metrics,
                dtype=np.dtype(np.float64),
                shape=(16,),
                name="candidate_metrics",
            ),
        )
        object.__setattr__(
            self,
            "posterior",
            _immutable(self.posterior, dtype=np.dtype(np.float64), shape=(16,), name="posterior"),
        )
        object.__setattr__(
            self,
            "fluctuating_increment",
            _immutable(
                self.fluctuating_increment,
                dtype=np.dtype(np.float64),
                shape=(1, 2),
                name="fluctuating_increment",
            ),
        )
        object.__setattr__(
            self,
            "full_increment",
            _immutable(
                self.full_increment, dtype=np.dtype(np.float64), shape=(1, 2), name="full_increment"
            ),
        )


@dataclass(frozen=True, slots=True)
class AdaptiveEstimatorModeResult:
    """Result for one explicit estimator policy on a shared received buffer."""

    mode: str
    initial_csi_provenance: str
    initial_state: ReconstructionEstimatorState
    alpha_prime: tuple[float, ...]
    k_tilde: tuple[FloatArray, ...]
    mu0: tuple[FloatArray, ...]
    history: tuple[AdaptiveEstimatorSymbolDiagnostic, ...]
    candidate_metrics: FloatArray
    posterior_history: FloatArray
    final_state: ReconstructionEstimatorState
    final_posterior: FloatArray
    decoded_hypothesis_path: tuple[int, ...]
    decoded_information_bits: BitArray
    decoded_symbol_indices: SymbolArray
    decoder_result: ReconstructionViterbiResult
    evaluation: ErrorEvaluation
    received_sha256: str
    receiver_mode: ReceiverMode

    def __post_init__(self) -> None:
        count = len(self.history)
        object.__setattr__(
            self,
            "candidate_metrics",
            _immutable(
                self.candidate_metrics,
                dtype=np.dtype(np.float64),
                shape=(count, 16),
                name="candidate_metrics",
            ),
        )
        object.__setattr__(
            self,
            "posterior_history",
            _immutable(
                self.posterior_history,
                dtype=np.dtype(np.float64),
                shape=(count, 16),
                name="posterior_history",
            ),
        )
        object.__setattr__(
            self,
            "final_posterior",
            _immutable(
                self.final_posterior,
                dtype=np.dtype(np.float64),
                shape=(16,),
                name="final_posterior",
            ),
        )
        object.__setattr__(
            self,
            "decoded_information_bits",
            _immutable(
                self.decoded_information_bits,
                dtype=np.dtype(np.int8),
                shape=(2 * count,),
                name="decoded_information_bits",
            ),
        )
        object.__setattr__(
            self,
            "decoded_symbol_indices",
            _immutable(
                self.decoded_symbol_indices,
                dtype=np.dtype(np.int64),
                shape=(count,),
                name="decoded_symbol_indices",
            ),
        )
        if len(self.received_sha256) != 64:
            raise ValueError("received_sha256 must be a SHA-256 hex digest")


@dataclass(frozen=True, slots=True)
class AdaptiveEstimatorDiagnosticResult:
    """A/B/C evaluation record; the receiver result itself contains no truth."""

    run_id: str
    status: str
    real_channel_gain: float
    beta: float
    sigma_squared: float | None
    effective_discrete_gamma_b: float | None
    noise_seed: int | None
    noise_stream_id: str | None
    noise_provenance: str
    noise_mode: str
    received_sha256: str
    symbol_origin_sample: int
    first_symbol_index: int
    initial_estimator_time_index: int
    absolute_symbol_indices: tuple[int, ...]
    absolute_sample_indices: tuple[int, ...]
    reference_information_bits: BitArray
    reference_symbol_indices: SymbolArray
    oracle_frozen: AdaptiveEstimatorModeResult
    mismatched_frozen: AdaptiveEstimatorModeResult
    mismatched_adaptive: AdaptiveEstimatorModeResult

    def __post_init__(self) -> None:
        count = len(self.absolute_symbol_indices)
        object.__setattr__(
            self,
            "reference_information_bits",
            _immutable(
                self.reference_information_bits,
                dtype=np.dtype(np.int8),
                shape=(2 * count,),
                name="reference_information_bits",
            ),
        )
        object.__setattr__(
            self,
            "reference_symbol_indices",
            _immutable(
                self.reference_symbol_indices,
                dtype=np.dtype(np.int64),
                shape=(count,),
                name="reference_symbol_indices",
            ),
        )


def _mode_run(
    *,
    mode: str,
    initial_state: ReconstructionEstimatorState,
    alpha: tuple[float, ...],
    gains: tuple[FloatArray, ...],
    regular: tuple[FloatArray, ...],
    received: ComplexArray,
    labels: NDArray[np.int64],
    received_start: int,
    origin: int,
    first_symbol: int,
    first_time: int,
    beta: float,
    labeling: Mapping[str, object],
    timebase: Mapping[str, object],
    receiver_mode: ReceiverMode,
    partition: tuple[int, ...],
    reference_bits: BitArray,
    reference_symbols: SymbolArray,
    received_sha256: str,
    true_gain_for_evaluation: float,
) -> AdaptiveEstimatorModeResult:
    count = len(reference_symbols)
    segments = partition if receiver_mode == "segmented" else (count,)
    current_state = initial_state
    current_posterior: FloatArray | None = None
    previous_symbol: int | None = None
    previous_estimator_time: int | None = None
    history: list[AdaptiveEstimatorSymbolDiagnostic] = []
    metric_rows: list[FloatArray] = []
    posterior_rows: list[FloatArray] = []
    offset = 0
    prior = build_initial_reconstruction_prior(initial_state=INITIAL_STATE)
    for segment_index, segment_size in enumerate(segments):
        segment_first_symbol = first_symbol + offset
        sample_offset = offset * ADR012_SAMPLES_PER_SYMBOL
        sample_stop = sample_offset + segment_size * ADR012_SAMPLES_PER_SYMBOL
        sequence = run_reconstruction_posterior_estimator_sequence(
            received=received[sample_offset:sample_stop],
            absolute_sample_indices=labels[sample_offset:sample_stop],
            received_start_sample=received_start + sample_offset,
            symbol_origin_sample=origin,
            first_symbol_index=segment_first_symbol,
            sequence_origin_symbol_index=first_symbol,
            symbol_count=segment_size,
            symbol_indices=tuple(range(segment_first_symbol, segment_first_symbol + segment_size)),
            initial_state=current_state,
            initial_estimator_time_index=current_state.time_index,
            run_mode="new_independent_sequence" if segment_index == 0 else "continuation",
            initial_prior=prior if segment_index == 0 else None,
            previous_posterior=current_posterior,
            continuation_from_symbol_index=previous_symbol,
            continuation_from_estimator_time_index=previous_estimator_time,
            beta=beta,
            alpha_prime=alpha[offset : offset + segment_size],
            k_tilde=np.stack(gains[offset : offset + segment_size]),
            mu0=np.stack(regular[offset : offset + segment_size]),
            include_history=True,
            profile=ADR012_PROFILE,
            adr_profile=ADR012_PROFILE_ID,
            path_count=1,
            path_delays_samples=(0,),
            samples_per_symbol=ADR012_SAMPLES_PER_SYMBOL,
            iq_rule=ADR012_IQ_RULE,
            waveform_rule=ADR012_WAVEFORM_RULE,
            labeling_profile=str(labeling["name"]),
            bit_order=tuple(labeling["bit_order"]),
            timebase_profile=str(timebase["name"]),
            symbol_to_sample_rule=RECTANGULAR_ZOH_RULE,
            edge_policy="zero_padding",
        )
        if sequence.history is None:
            raise RuntimeError("B4d did not return the required per-symbol history")
        for local_position, entry in enumerate(sequence.history):
            step = entry.b4c_result
            pre_state = (
                current_state
                if local_position == 0
                else sequence.history[local_position - 1].b4c_result.next_state
            )
            post_state = step.next_state
            symbol = entry.symbol_index
            first_sample = origin + ADR012_SAMPLES_PER_SYMBOL * symbol
            last_sample = first_sample + ADR012_SAMPLES_PER_SYMBOL - 1
            mu = regular[offset + local_position]
            if not np.allclose(
                post_state.full_iq, post_state.fluctuating_iq + mu, rtol=0.0, atol=1e-12
            ):
                raise ValueError(
                    "post-step full estimate must equal fluctuating estimate plus this step's mu0"
                )
            candidate = step.candidate_result
            diagnostic = AdaptiveEstimatorSymbolDiagnostic(
                absolute_symbol_index=symbol,
                estimator_time_index=entry.estimator_time_index,
                first_sample_index=first_sample,
                last_sample_index=last_sample,
                prediction_cutoff_sample_index=candidate.prediction_cutoff_sample_index,
                observation_cutoff_sample_index=candidate.metric_available_after_sample_index,
                pre_state=pre_state,
                observed_iq=step.observed_iq,
                predicted_iq=step.predicted_iq,
                candidate_metrics=candidate.metrics,
                posterior=step.posterior,
                post_state=post_state,
                fluctuating_increment=post_state.fluctuating_iq - pre_state.fluctuating_iq,
                full_increment=post_state.full_iq - pre_state.full_iq,
                full_estimate_error_norm=float(
                    np.linalg.norm(post_state.full_iq - np.full((1, 2), true_gain_for_evaluation))
                ),
            )
            history.append(diagnostic)
            metric_rows.append(candidate.metrics)
            posterior_rows.append(step.posterior)
        current_state = sequence.final_state
        current_posterior = sequence.final_posterior
        previous_symbol = sequence.final_symbol_index
        previous_estimator_time = sequence.final_estimator_time_index - 1
        offset += segment_size

    metrics = np.stack(metric_rows)
    posterior_history = np.stack(posterior_rows)
    symbols = tuple(row.absolute_symbol_index for row in history)
    times = tuple(row.estimator_time_index for row in history)
    decoder = decode_reconstruction_viterbi(
        metrics,
        hypotheses=HYPOTHESES,
        initial_state=INITIAL_STATE,
        sequence_mode="new_independent_sequence",
        profile="reconstructed_offline",
        edge_indices=tuple(range(count)),
        symbol_indices=symbols,
        estimator_time_indices=times,
    )
    decoded_symbols = decoded_path_symbol_indices(
        decoder.hypothesis_ids,
        profile=ASSUMED_NATURAL_BINARY,
        bit_order=OUTPUT_BIT_ORDER,
    )
    evaluation = evaluate_run(
        reference_bits,
        decoder.decoded_bits,
        reference_symbols,
        decoded_symbols,
    )
    return AdaptiveEstimatorModeResult(
        mode=mode,
        initial_csi_provenance=(
            ORACLE_CSI_MATCHED_CONTROL
            if mode == ORACLE_FROZEN
            else "explicit mismatched initial estimate"
        ),
        initial_state=initial_state,
        alpha_prime=alpha,
        k_tilde=gains,
        mu0=regular,
        history=tuple(history),
        candidate_metrics=metrics,
        posterior_history=posterior_history,
        final_state=current_state,
        final_posterior=current_posterior,
        decoded_hypothesis_path=decoder.hypothesis_ids,
        decoded_information_bits=decoder.decoded_bits,
        decoded_symbol_indices=decoded_symbols,
        decoder_result=decoder,
        evaluation=evaluation,
        received_sha256=received_sha256,
        receiver_mode=receiver_mode,
    )


def run_adaptive_estimator_diagnostic(
    *,
    run_id: str,
    reference_information_bits: ArrayLike,
    real_channel_gain: Real,
    sigma_squared: Real | None,
    noise: ArrayLike | None,
    noise_seed: int | None,
    noise_stream_id: str | None,
    noise_provenance: str,
    symbol_origin_sample: int,
    first_symbol_index: int,
    initial_estimator_time_index: int,
    configuration: Mapping[str, object],
    mismatched_initial_state: ReconstructionEstimatorState,
    adaptive_alpha_prime: Real | Sequence[Real],
    adaptive_k_tilde: ArrayLike,
    adaptive_mu0: ArrayLike,
    receiver_mode: ReceiverMode,
    segment_partition: Sequence[int] | None,
) -> AdaptiveEstimatorDiagnosticResult:
    """Run oracle-frozen, mismatched-frozen and mismatched-adaptive B5 passes.

    Only one noise array or one explicit PCG64 seed is accepted. The generated
    received buffer is immutable and shared across all three estimator modes.
    The true gain is used only by this evaluation layer for waveform creation
    and post-decode coefficient-error diagnostics.
    """
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id must be nonempty")
    if not isinstance(noise_provenance, str) or not noise_provenance.strip():
        raise ValueError("noise_provenance must be explicitly documented")
    gain = _positive_real(real_channel_gain, name="real_channel_gain")
    variance = _positive_real(sigma_squared, name="sigma_squared", allow_none=True)
    assert gain is not None
    origin = _integer(symbol_origin_sample, name="symbol_origin_sample", minimum=0)
    first_symbol = _integer(first_symbol_index, name="first_symbol_index", minimum=0)
    first_time = _integer(initial_estimator_time_index, name="initial_estimator_time_index")
    if (noise is None) == (noise_seed is None):
        raise ValueError("provide exactly one explicit noise array or noise_seed")
    if receiver_mode not in ("monolithic", "segmented"):
        raise ValueError("receiver_mode must be 'monolithic' or 'segmented'")
    bits = _readonly_bits(reference_information_bits)
    count = bits.size // 2
    if receiver_mode == "monolithic":
        if segment_partition is not None:
            raise ValueError("monolithic mode requires segment_partition=None")
        partition = (count,)
    else:
        if not isinstance(segment_partition, Sequence) or isinstance(
            segment_partition, (str, bytes)
        ):
            raise ValueError("segmented mode requires an explicit partition")
        partition = tuple(
            _integer(item, name="segment size", minimum=1) for item in segment_partition
        )
        if not partition or sum(partition) != count:
            raise ValueError("segment partition must contain positive sizes summing to F")
    if not isinstance(mismatched_initial_state, ReconstructionEstimatorState):
        raise ValueError("mismatched_initial_state must be a ReconstructionEstimatorState")
    if (
        mismatched_initial_state.time_index != first_time
        or mismatched_initial_state.full_iq.shape != (1, 2)
    ):
        raise ValueError("mismatched initial state must be L=1 at the explicit estimator time")
    if np.array_equal(mismatched_initial_state.full_iq, np.asarray([[gain, gain]])):
        raise ValueError("mismatched_initial_state.full_iq must differ from the true oracle pair")
    validated, labeling, timebase = _config_operands(
        configuration, origin=origin, initial_time=first_time
    )
    beta = float(validated["likelihood"]["beta"])
    reference_symbols = encode_reference_symbol_indices(
        bits,
        profile=ASSUMED_NATURAL_BINARY,
        bit_order=OUTPUT_BIT_ORDER,
    )
    labels = [
        index_to_label(int(index), profile=BASELINE_ASSUMPTION) for index in reference_symbols
    ]
    baseband_symbols = modulate(labels, phase_offset=0.0, profile=BASELINE_ASSUMPTION)
    i_wave, q_wave = symbols_to_iq_waveform(
        baseband_symbols, samples_per_symbol=ADR012_SAMPLES_PER_SYMBOL
    )
    clean = gain * (i_wave + 1j * q_wave)
    sample_count = ADR012_SAMPLES_PER_SYMBOL * count
    seed_value: int | None = None
    stream_id: str | None = None
    if noise is None:
        if variance is None:
            raise ValueError("seeded AWGN requires explicit sigma_squared > 0")
        seed_value = _integer(noise_seed, name="noise_seed", minimum=0)
        if not isinstance(noise_stream_id, str) or not noise_stream_id.strip():
            raise ValueError("seeded AWGN requires an explicit nonempty noise_stream_id")
        noise_values = generate_independent_complex_awgn(
            sample_count=sample_count,
            sigma_squared=variance,
            seed=seed_value,
            stream_id=noise_stream_id,
        ).noise
        stream_id = noise_stream_id.strip()
        noise_mode = "seeded_independent_circular_complex_sample_awgn"
    else:
        if noise_seed is not None:
            raise ValueError("explicit noise and noise_seed are mutually exclusive")
        if noise_stream_id is not None and (
            not isinstance(noise_stream_id, str) or not noise_stream_id.strip()
        ):
            raise ValueError("noise_stream_id must be nonempty when supplied")
        noise_values = _immutable_received(noise, shape=(sample_count,))
        stream_id = None if noise_stream_id is None else noise_stream_id.strip()
        noise_mode = (
            "explicit_zero_noise_control"
            if not np.any(noise_values)
            else "explicit_complex_noise_array"
        )
    received = _immutable_received(clean + noise_values, shape=(sample_count,))
    received_start = origin + ADR012_SAMPLES_PER_SYMBOL * first_symbol
    if received_start + sample_count > np.iinfo(np.int64).max:
        raise ValueError("sample labels exceed the supported int64 range")
    absolute_samples = np.arange(received_start, received_start + sample_count, dtype=np.int64)
    absolute_symbols = tuple(range(first_symbol, first_symbol + count))
    reference_symbols = _immutable(
        reference_symbols, dtype=np.dtype(np.int64), shape=(count,), name="reference_symbol_indices"
    )
    digest = hashlib.sha256(received.tobytes()).hexdigest()

    zero = np.zeros((1, 2), dtype=np.float64)
    frozen_alpha = (1.0,) * count
    frozen_gains = tuple(zero.copy() for _ in range(count))
    frozen_mu = tuple(zero.copy() for _ in range(count))
    oracle_state = ReconstructionEstimatorState([[gain, gain]], [[gain, gain]], first_time)
    oracle = _mode_run(
        mode=ORACLE_FROZEN,
        initial_state=oracle_state,
        alpha=frozen_alpha,
        gains=frozen_gains,
        regular=frozen_mu,
        received=received,
        labels=absolute_samples,
        received_start=received_start,
        origin=origin,
        first_symbol=first_symbol,
        first_time=first_time,
        beta=beta,
        labeling=labeling,
        timebase=timebase,
        receiver_mode=receiver_mode,
        partition=partition,
        reference_bits=bits,
        reference_symbols=reference_symbols,
        received_sha256=digest,
        true_gain_for_evaluation=gain,
    )
    mismatched_frozen = _mode_run(
        mode=MISMATCHED_FROZEN,
        initial_state=mismatched_initial_state,
        alpha=frozen_alpha,
        gains=frozen_gains,
        regular=frozen_mu,
        received=received,
        labels=absolute_samples,
        received_start=received_start,
        origin=origin,
        first_symbol=first_symbol,
        first_time=first_time,
        beta=beta,
        labeling=labeling,
        timebase=timebase,
        receiver_mode=receiver_mode,
        partition=partition,
        reference_bits=bits,
        reference_symbols=reference_symbols,
        received_sha256=digest,
        true_gain_for_evaluation=gain,
    )
    alpha_values = _schedule_alpha(adaptive_alpha_prime, count=count)
    gain_values = _schedule_iq(adaptive_k_tilde, name="adaptive_k_tilde", count=count)
    mu_values = _schedule_iq(adaptive_mu0, name="adaptive_mu0", count=count)
    is_frozen_policy = all(value == 1.0 for value in alpha_values) and all(
        not np.any(value) for value in gain_values + mu_values
    )
    if is_frozen_policy:
        raise ValueError("adaptive recursion parameters must differ from the frozen policy")
    adaptive = _mode_run(
        mode=MISMATCHED_ADAPTIVE,
        initial_state=mismatched_initial_state,
        alpha=alpha_values,
        gains=gain_values,
        regular=mu_values,
        received=received,
        labels=absolute_samples,
        received_start=received_start,
        origin=origin,
        first_symbol=first_symbol,
        first_time=first_time,
        beta=beta,
        labeling=labeling,
        timebase=timebase,
        receiver_mode=receiver_mode,
        partition=partition,
        reference_bits=bits,
        reference_symbols=reference_symbols,
        received_sha256=digest,
        true_gain_for_evaluation=gain,
    )

    gamma = None if variance is None else effective_discrete_gamma_b(gain, variance)
    return AdaptiveEstimatorDiagnosticResult(
        run_id=run_id.strip(),
        status=EXPERIMENT_STATUS,
        real_channel_gain=gain,
        beta=beta,
        sigma_squared=variance,
        effective_discrete_gamma_b=gamma,
        noise_seed=seed_value,
        noise_stream_id=stream_id,
        noise_provenance=noise_provenance.strip(),
        noise_mode=noise_mode,
        received_sha256=digest,
        symbol_origin_sample=origin,
        first_symbol_index=first_symbol,
        initial_estimator_time_index=first_time,
        absolute_symbol_indices=absolute_symbols,
        absolute_sample_indices=tuple(int(value) for value in absolute_samples),
        reference_information_bits=bits,
        reference_symbol_indices=reference_symbols,
        oracle_frozen=oracle,
        mismatched_frozen=mismatched_frozen,
        mismatched_adaptive=adaptive,
    )
