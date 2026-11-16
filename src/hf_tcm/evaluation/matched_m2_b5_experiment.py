"""Paired discrete-AWGN M2/B5 controls on one immutable received buffer."""

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
from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.decoding.branch_metrics import soft_branch_cost
from hf_tcm.decoding.viterbi import DecodeResult, decode_viterbi
from hf_tcm.evaluation.error_metrics import (
    ErrorEvaluation,
    decoded_path_symbol_indices,
    encode_reference_symbol_indices,
    evaluate_run,
)
from hf_tcm.evaluation.matched_m2_observation import (
    MatchedM2ObservationResult,
    prepare_matched_m2_observations,
)
from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION, index_to_label
from hf_tcm.modulation.psk8 import constellation, modulate
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
    output_bits_to_phase_index,
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
    "isolated matched discrete-AWGN paired M2/B5 control experiment, "
    "NOT validated performance advantage, NOT physical HF Eb/N0 calibration, "
    "NOT reproduction of paper results"
)
ORACLE_CSI_MATCHED_CONTROL = "oracle-CSI matched control"
M2TiePolicy = Literal["first canonical incoming edge; final tuple-order state"]
ReceiverMode = Literal["monolithic", "segmented"]
ComplexVector = NDArray[np.complex128]
FloatMatrix = NDArray[np.float64]
BitVector = NDArray[np.int8]
SymbolVector = NDArray[np.int64]
ReceiverResult = ReconstructionConditionalDecodeResult | ReconstructionSegmentedDecodeResult


def _integer(value: object, *, name: str, minimum: int | None = None) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")
    result = int(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return result


def _real(value: object, *, name: str, positive: bool = False) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        qualifier = "finite positive" if positive else "finite"
        raise ValueError(f"{name} must be a {qualifier} real number")
    return result


def _immutable(values: ArrayLike, *, dtype: np.dtype, shape: tuple[int, ...], name: str) -> NDArray:
    try:
        raw = np.asarray(values)
        if np.iscomplexobj(raw) and dtype.kind != "c":
            raise ValueError
        array = np.asarray(raw, dtype=dtype)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must have finite values and shape {shape}") from exc
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must have finite values and shape {shape}")
    owned = np.array(array, dtype=dtype, order="C", copy=True)
    return np.frombuffer(owned.tobytes(), dtype=dtype).reshape(shape)


@dataclass(frozen=True, slots=True)
class IndependentComplexAwgnRealization:
    """One explicit evaluation-side draw of iid circular complex sample noise."""

    noise: ComplexVector
    sample_count: int
    sigma_squared: float
    seed: int
    noise_stream_id: str
    bit_generator: str = "PCG64"

    def __post_init__(self) -> None:
        values = _immutable(
            self.noise,
            dtype=np.dtype(np.complex128),
            shape=(self.sample_count,),
            name="noise",
        )
        if self.sample_count < 1:
            raise ValueError("sample_count must be positive")
        if not math.isfinite(self.sigma_squared) or self.sigma_squared <= 0.0:
            raise ValueError("sigma_squared must be finite and > 0")
        object.__setattr__(self, "noise", values)

    @property
    def component_variance(self) -> float:
        """Per-real-component variance implied by the explicit complex variance."""
        return self.sigma_squared / 2.0


def generate_independent_complex_awgn(
    *, sample_count: int, sigma_squared: Real, seed: int, stream_id: str
) -> IndependentComplexAwgnRealization:
    """Generate explicit iid `CN(0, sigma_squared)` samples from PCG64.

    This is an evaluation-only generator for ADR-015. It does not alter or call
    the symbol-rate M2 AWGN helper or the M3 AR(1) noise process.
    """
    count = _integer(sample_count, name="sample_count", minimum=1)
    variance = _real(sigma_squared, name="sigma_squared", positive=True)
    seed_value = _integer(seed, name="seed", minimum=0)
    if not isinstance(stream_id, str) or not stream_id.strip():
        raise ValueError("stream_id must be a nonempty explicit identifier")
    rng = np.random.Generator(np.random.PCG64(seed_value))
    scale = math.sqrt(variance / 2.0)
    noise = scale * (rng.standard_normal(count) + 1j * rng.standard_normal(count))
    return IndependentComplexAwgnRealization(
        noise=np.asarray(noise, dtype=np.complex128),
        sample_count=count,
        sigma_squared=variance,
        seed=seed_value,
        noise_stream_id=stream_id.strip(),
    )


@dataclass(frozen=True, slots=True)
class MatchedM2B5ExperimentResult:
    """Paired evaluation results; reference data and raw received are not retained."""

    run_id: str
    experiment_name: str
    symbol_count: int
    real_channel_gain: float
    sigma_squared: float | None
    effective_discrete_gamma_b: float | None
    effective_discrete_gamma_b_db: float | None
    noise_seed: int | None
    noise_stream_id: str | None
    noise_provenance: str
    noise_mode: str
    receiver_mode: ReceiverMode
    initial_csi_provenance: str
    symbol_origin_sample: int
    first_symbol_index: int
    initial_estimator_time_index: int
    absolute_sample_indices: tuple[int, ...]
    absolute_symbol_indices: tuple[int, ...]
    estimator_time_indices: tuple[int, ...]
    prediction_cutoff_sample_indices: tuple[int, ...]
    observation_cutoff_sample_indices: tuple[int, ...]
    segment_partition: tuple[int, ...]
    received_shape: tuple[int, ...]
    received_sha256: str
    m2_observation: MatchedM2ObservationResult
    m2_decode_result: DecodeResult
    m2_decoded_information_bits: BitVector
    m2_decoded_hypothesis_path: tuple[int, ...]
    m2_decoded_symbol_indices: SymbolVector
    b5_result: ReceiverResult
    b5_decoded_information_bits: BitVector
    b5_decoded_hypothesis_path: tuple[int, ...]
    b5_decoded_symbol_indices: SymbolVector
    candidate_metrics: FloatMatrix
    m2_evaluation: ErrorEvaluation
    b5_evaluation: ErrorEvaluation
    m2_branch_metrics: FloatMatrix
    metric_equivalence_offsets: NDArray[np.float64]
    metric_equivalence_scale: float
    metric_equivalence_max_abs_error: float
    candidate_minimizers_match: tuple[bool, ...]
    claim_status: str = EXPERIMENT_NAME
    m2_tie_policy: M2TiePolicy = "first canonical incoming edge; final tuple-order state"
    b5_tie_policy: str = "ADR-013 minimum hypothesis_id on survivor ties; minimum canonical M1 state index on final ties"

    def __post_init__(self) -> None:
        count = self.symbol_count
        object.__setattr__(
            self,
            "m2_decoded_information_bits",
            _immutable(
                self.m2_decoded_information_bits,
                dtype=np.dtype(np.int8),
                shape=(2 * count,),
                name="m2_decoded_information_bits",
            ),
        )
        object.__setattr__(
            self,
            "b5_decoded_information_bits",
            _immutable(
                self.b5_decoded_information_bits,
                dtype=np.dtype(np.int8),
                shape=(2 * count,),
                name="b5_decoded_information_bits",
            ),
        )
        object.__setattr__(
            self,
            "m2_decoded_symbol_indices",
            _immutable(
                self.m2_decoded_symbol_indices,
                dtype=np.dtype(np.int64),
                shape=(count,),
                name="m2_decoded_symbol_indices",
            ),
        )
        object.__setattr__(
            self,
            "b5_decoded_symbol_indices",
            _immutable(
                self.b5_decoded_symbol_indices,
                dtype=np.dtype(np.int64),
                shape=(count,),
                name="b5_decoded_symbol_indices",
            ),
        )
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
            "m2_branch_metrics",
            _immutable(
                self.m2_branch_metrics,
                dtype=np.dtype(np.float64),
                shape=(count, 16),
                name="m2_branch_metrics",
            ),
        )
        object.__setattr__(
            self,
            "metric_equivalence_offsets",
            _immutable(
                self.metric_equivalence_offsets,
                dtype=np.dtype(np.float64),
                shape=(count,),
                name="metric_equivalence_offsets",
            ),
        )
        if len(self.absolute_symbol_indices) != count or len(self.estimator_time_indices) != count:
            raise ValueError("symbol and estimator labels must contain exactly F entries")
        if len(self.candidate_minimizers_match) != count:
            raise ValueError("candidate_minimizers_match must contain exactly F entries")
        if self.received_shape != (8 * count,) or len(self.received_sha256) != 64:
            raise ValueError("received provenance must describe exactly 8F samples")


def _validated_reference_bits(values: ArrayLike, *, count: int) -> BitVector:
    try:
        raw = np.asarray(values)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("reference_information_bits must contain exactly 2F bits") from exc
    if (
        raw.ndim != 1
        or raw.shape != (2 * count,)
        or raw.dtype.kind not in "iub"
        or np.any((raw != 0) & (raw != 1))
    ):
        raise ValueError("reference_information_bits must contain exactly 2F bits")
    return _immutable(
        raw, dtype=np.dtype(np.int8), shape=(2 * count,), name="reference_information_bits"
    )


def _validate_frozen_configuration(
    configuration: object,
    *,
    gain: float,
    origin: int,
    initial_time: int,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    try:
        validated = validate_reconstructed_offline_config(configuration)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"configuration is invalid for reconstructed_offline: {exc}") from exc
    labeling = validated["labeling"]
    timebase = validated["timebase"]
    observation = validated["observation_model"]
    estimator = validated["estimator"]
    initial = estimator["initial_estimates"]
    if (
        labeling["name"] != ASSUMED_NATURAL_BINARY
        or tuple(labeling["bit_order"]) != OUTPUT_BIT_ORDER
        or tuple(labeling["output_to_b"]) != tuple(range(8))
        or labeling["phase_offset_rad"] != 0.0
    ):
        raise ValueError("configuration must use zero-offset ADR-002 natural-binary labeling")
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
        raise ValueError("configuration must use the exact accepted ADR-012 observation profile")
    if estimator["initial_time_index"] != initial_time:
        raise ValueError("initial estimator time must match the validated configuration")
    if estimator["alpha_prime"] != 1.0:
        raise ValueError("matched B5 control requires the explicit frozen-estimator alpha_prime=1")
    if not np.array_equal(np.asarray(estimator["k_tilde"], dtype=np.float64), np.zeros((1, 2))):
        raise ValueError("matched B5 control requires explicit K_tilde=[[0,0]]")
    if not np.array_equal(np.asarray(estimator["mu0"], dtype=np.float64), np.zeros((1, 2))):
        raise ValueError("matched B5 control requires explicit mu0=[[0,0]]")
    expected_estimate = np.asarray([[gain, gain]], dtype=np.float64)
    for field in ("fluctuating_iq", "full_iq"):
        if not np.array_equal(np.asarray(initial[field], dtype=np.float64), expected_estimate):
            raise ValueError(f"matched B5 control requires oracle-initialized {field}=(a,a)")
    return validated, labeling, timebase


def _m2_path_hypotheses(result: DecodeResult) -> tuple[int, ...]:
    if len(result.state_path) != len(result.input_pairs) + 1:
        raise ValueError("M2 decoder state path does not align with decoded input pairs")
    ids: list[int] = []
    for pair, current_state, next_state in zip(
        result.input_pairs, result.state_path[:-1], result.state_path[1:], strict=True
    ):
        matches = tuple(
            hypothesis
            for hypothesis in HYPOTHESES
            if hypothesis.current_state == current_state and hypothesis.input_bits == pair
        )
        if len(matches) != 1 or matches[0].next_state != next_state:
            raise ValueError("M2 traceback does not match the canonical M1 trellis")
        ids.append(matches[0].hypothesis_id)
    path = validate_hypothesis_edge_path(ids, initial_state=INITIAL_STATE)
    return tuple(edge.hypothesis_id for edge in path)


def _m2_metrics_and_equivalence(
    *,
    received: ComplexVector,
    observations: ComplexVector,
    gain: float,
    candidate_metrics: FloatMatrix,
) -> tuple[FloatMatrix, NDArray[np.float64], float, tuple[bool, ...]]:
    phase_points = constellation()
    phase_indices = tuple(
        output_bits_to_phase_index(
            hypothesis.output_bits,
            profile=ASSUMED_NATURAL_BINARY,
            bit_order=OUTPUT_BIT_ORDER,
        )
        for hypothesis in HYPOTHESES
    )
    branch_rows: list[list[float]] = []
    offsets: list[float] = []
    equivalent_b5_rows: list[list[float]] = []
    minimizers: list[bool] = []
    max_error = 0.0
    for symbol_offset, observation in enumerate(observations):
        window_start = 8 * symbol_offset
        window = received[window_start : window_start + 8]
        if window.shape != (8,):
            raise ValueError("received buffer is missing an 8-sample symbol block")
        mean = complex(np.mean(window, dtype=np.complex128))
        centered_energy = float(np.sum(np.abs(window - mean) ** 2))
        branch = [
            float(soft_branch_cost(observation, phase_points[index])) for index in phase_indices
        ]
        equivalent = [centered_energy + 8.0 * gain * gain * value for value in branch]
        branch_rows.append(branch)
        offsets.append(centered_energy)
        equivalent_b5_rows.append(equivalent)
        max_error = max(
            max_error,
            float(np.max(np.abs(candidate_metrics[symbol_offset] - np.asarray(equivalent)))),
        )
        minimizers.append(
            int(np.argmin(candidate_metrics[symbol_offset])) == int(np.argmin(equivalent))
        )
    branch_matrix = np.asarray(branch_rows, dtype=np.float64)
    offset_array = np.asarray(offsets, dtype=np.float64)
    expected_matrix = np.asarray(equivalent_b5_rows, dtype=np.float64)
    if not np.all(np.isfinite(branch_matrix)) or not np.all(np.isfinite(expected_matrix)):
        raise ValueError("matched metric equivalence diagnostics overflowed")
    return branch_matrix, offset_array, max_error, tuple(minimizers)


def run_matched_m2_b5_experiment(
    *,
    run_id: str,
    symbol_count: int,
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
    receiver_mode: ReceiverMode,
    segment_partition: Sequence[int] | None,
    initial_csi_provenance: str,
) -> MatchedM2B5ExperimentResult:
    """Run M2 and B5 on the same explicit or once-generated received samples."""
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id must be a nonempty explicit identifier")
    count = _integer(symbol_count, name="symbol_count", minimum=1)
    gain = _real(real_channel_gain, name="real_channel_gain", positive=True)
    variance = (
        None if sigma_squared is None else _real(sigma_squared, name="sigma_squared", positive=True)
    )
    origin = _integer(symbol_origin_sample, name="symbol_origin_sample", minimum=0)
    first_symbol = _integer(first_symbol_index, name="first_symbol_index", minimum=0)
    first_time = _integer(initial_estimator_time_index, name="initial_estimator_time_index")
    if not isinstance(noise_provenance, str) or not noise_provenance.strip():
        raise ValueError("noise_provenance must be explicitly documented")
    if initial_csi_provenance != ORACLE_CSI_MATCHED_CONTROL:
        raise ValueError("this M5d profile requires the explicit oracle-CSI matched-control label")
    if receiver_mode not in ("monolithic", "segmented"):
        raise ValueError("receiver_mode must be 'monolithic' or 'segmented'")
    if receiver_mode == "monolithic" and segment_partition is not None:
        raise ValueError("segment_partition must be None in monolithic mode")
    if receiver_mode == "segmented":
        if not isinstance(segment_partition, Sequence) or isinstance(
            segment_partition, (str, bytes)
        ):
            raise ValueError("segmented mode requires an explicit partition")
        partition = tuple(
            _integer(value, name="segment partition entry", minimum=1)
            for value in segment_partition
        )
        if not partition or sum(partition) != count:
            raise ValueError("segment partition must contain positive sizes summing to F")
    else:
        partition = ()
    if (noise is None) == (noise_seed is None):
        raise ValueError("provide exactly one of explicit noise or noise_seed")
    validated, labeling, timebase = _validate_frozen_configuration(
        configuration,
        gain=gain,
        origin=origin,
        initial_time=first_time,
    )
    reference_bits = _validated_reference_bits(reference_information_bits, count=count)
    reference_symbol_indices = encode_reference_symbol_indices(
        reference_bits,
        profile=ASSUMED_NATURAL_BINARY,
        bit_order=OUTPUT_BIT_ORDER,
    )
    labels = [
        index_to_label(int(index), profile=BASELINE_ASSUMPTION)
        for index in reference_symbol_indices
    ]
    symbols = modulate(labels, phase_offset=0.0, profile=BASELINE_ASSUMPTION)
    waveform_i, waveform_q = symbols_to_iq_waveform(
        symbols, samples_per_symbol=ADR012_SAMPLES_PER_SYMBOL
    )
    clean = gain * (waveform_i + 1j * waveform_q)
    seed_value: int | None
    stream_value: str | None
    if noise is None:
        if variance is None:
            raise ValueError("seeded AWGN generation requires explicit sigma_squared > 0")
        seed_value = _integer(noise_seed, name="noise_seed", minimum=0)
        if not isinstance(noise_stream_id, str) or not noise_stream_id.strip():
            raise ValueError("seeded AWGN requires a nonempty noise_stream_id")
        realization = generate_independent_complex_awgn(
            sample_count=8 * count,
            sigma_squared=variance,
            seed=seed_value,
            stream_id=noise_stream_id,
        )
        noise_values = realization.noise
        stream_value = realization.noise_stream_id
        noise_mode = "seeded_independent_circular_complex_sample_awgn"
    else:
        seed_value = None
        if noise_seed is not None:
            raise ValueError("explicit noise arrays and noise_seed are mutually exclusive")
        if noise_stream_id is not None and (
            not isinstance(noise_stream_id, str) or not noise_stream_id.strip()
        ):
            raise ValueError("noise_stream_id must be nonempty when supplied")
        stream_value = None if noise_stream_id is None else noise_stream_id.strip()
        try:
            raw_noise = np.asarray(noise)
            if not np.iscomplexobj(raw_noise):
                raise ValueError
            noise_values = np.asarray(raw_noise, dtype=np.complex128)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                "explicit noise must be a finite complex array with shape (8F,)"
            ) from exc
        if (
            noise_values.shape != (8 * count,)
            or not np.all(np.isfinite(noise_values.real))
            or not np.all(np.isfinite(noise_values.imag))
        ):
            raise ValueError("explicit noise must be a finite complex array with shape (8F,)")
        noise_mode = (
            "explicit_complex_noise_array"
            if np.any(noise_values)
            else "explicit_zero_noise_control"
        )

    received_values = np.asarray(clean + noise_values, dtype=np.complex128)
    if not np.all(np.isfinite(received_values.real)) or not np.all(
        np.isfinite(received_values.imag)
    ):
        raise ValueError("received samples are outside the supported numeric range")
    received_start = origin + ADR012_SAMPLES_PER_SYMBOL * first_symbol
    if received_start + 8 * count > np.iinfo(np.int64).max:
        raise ValueError("absolute sample labels exceed the supported int64 range")
    absolute_samples = np.arange(received_start, received_start + 8 * count, dtype=np.int64)
    immutable_received = _immutable(
        received_values,
        dtype=np.dtype(np.complex128),
        shape=(8 * count,),
        name="received",
    )
    # Evaluation-side M2 reduction and B5 decode share this exact buffer value.
    m2_observation = prepare_matched_m2_observations(
        immutable_received,
        absolute_sample_indices=absolute_samples,
        received_start_sample=received_start,
        symbol_origin_sample=origin,
        symbol_indices=tuple(range(first_symbol, first_symbol + count)),
        real_channel_gain=gain,
        sigma_squared=variance,
        profile=ADR012_PROFILE,
        path_count=1,
        path_delays_samples=(0,),
        samples_per_symbol=ADR012_SAMPLES_PER_SYMBOL,
    )

    estimator = validated["estimator"]
    estimates = estimator["initial_estimates"]
    initial_state = ReconstructionEstimatorState(
        estimates["fluctuating_iq"], estimates["full_iq"], first_time
    )
    initial_encoder_state = tuple(validated["initial"]["state"])
    symbols_absolute = tuple(range(first_symbol, first_symbol + count))
    common_operands = {
        "received": immutable_received,
        "absolute_sample_indices": absolute_samples,
        "received_start_sample": received_start,
        "symbol_origin_sample": origin,
        "sequence_origin_symbol_index": first_symbol,
        "initial_estimator_state": initial_state,
        "initial_estimator_time_index": first_time,
        "initial_encoder_state": initial_encoder_state,
        "beta": float(validated["likelihood"]["beta"]),
        "alpha_prime": float(estimator["alpha_prime"]),
        "k_tilde": estimator["k_tilde"],
        "mu0": estimator["mu0"],
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
        b5_result: ReceiverResult = decode_reconstruction_conditional_sequence(
            **common_operands,
            first_symbol_index=first_symbol,
            symbol_count=count,
            symbol_indices=symbols_absolute,
            sequence_mode="new_independent_sequence",
        )
    else:
        segments: list[ReconstructionSequenceSegment] = []
        symbol_offset = 0
        sample_offset = 0
        for size in partition:
            segments.append(
                ReconstructionSequenceSegment(
                    first_symbol_index=first_symbol + symbol_offset,
                    received_start_offset=sample_offset,
                    symbol_count=size,
                )
            )
            symbol_offset += size
            sample_offset += size * ADR012_SAMPLES_PER_SYMBOL
        b5_result = decode_reconstruction_segmented_sequence(
            **common_operands,
            segments=tuple(segments),
        )
    core = (
        b5_result.decode_result
        if isinstance(b5_result, ReconstructionSegmentedDecodeResult)
        else b5_result
    )
    m2_result = decode_viterbi(
        m2_observation.observations,
        mode="soft",
        initial_state=INITIAL_STATE,
        final_state=None,
        phase_offset=0.0,
        profile=BASELINE_ASSUMPTION,
    )
    m2_path = _m2_path_hypotheses(m2_result)
    validate_hypothesis_edge_path(m2_path, initial_state=INITIAL_STATE)
    m2_bits = _immutable(
        np.asarray(m2_result.decoded_bits, dtype=np.int8),
        dtype=np.dtype(np.int8),
        shape=(2 * count,),
        name="m2_decoded_information_bits",
    )
    b5_bits = _immutable(
        core.decoded_information_bits,
        dtype=np.dtype(np.int8),
        shape=(2 * count,),
        name="b5_decoded_information_bits",
    )
    m2_symbols = decoded_path_symbol_indices(
        m2_path, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    b5_symbols = decoded_path_symbol_indices(
        core.decoded_hypothesis_path, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    m2_evaluation = evaluate_run(reference_bits, m2_bits, reference_symbol_indices, m2_symbols)
    b5_evaluation = evaluate_run(reference_bits, b5_bits, reference_symbol_indices, b5_symbols)
    branch_metrics, offsets, equivalence_error, minimizers_match = _m2_metrics_and_equivalence(
        received=immutable_received,
        observations=m2_observation.observations,
        gain=gain,
        candidate_metrics=core.candidate_metrics,
    )
    estimator_labels = tuple(row.estimator_time_index for row in core.metric_provenance)
    digest = hashlib.sha256(immutable_received.tobytes()).hexdigest()
    gamma = m2_observation.effective_discrete_gamma_b
    gamma_db = m2_observation.effective_discrete_gamma_b_db
    return MatchedM2B5ExperimentResult(
        run_id=run_id.strip(),
        experiment_name=EXPERIMENT_NAME,
        symbol_count=count,
        real_channel_gain=gain,
        sigma_squared=variance,
        effective_discrete_gamma_b=gamma,
        effective_discrete_gamma_b_db=gamma_db,
        noise_seed=seed_value,
        noise_stream_id=stream_value,
        noise_provenance=noise_provenance.strip(),
        noise_mode=noise_mode,
        receiver_mode=receiver_mode,
        initial_csi_provenance=initial_csi_provenance,
        symbol_origin_sample=origin,
        first_symbol_index=first_symbol,
        initial_estimator_time_index=first_time,
        absolute_sample_indices=tuple(int(value) for value in absolute_samples),
        absolute_symbol_indices=core.decoder_result.symbol_indices,
        estimator_time_indices=estimator_labels,
        prediction_cutoff_sample_indices=tuple(
            row.prediction_cutoff_sample_index for row in core.metric_provenance
        ),
        observation_cutoff_sample_indices=tuple(
            row.observation_cutoff_sample_index for row in core.metric_provenance
        ),
        segment_partition=partition,
        received_shape=tuple(immutable_received.shape),
        received_sha256=digest,
        m2_observation=m2_observation,
        m2_decode_result=m2_result,
        m2_decoded_information_bits=m2_bits,
        m2_decoded_hypothesis_path=m2_path,
        m2_decoded_symbol_indices=m2_symbols,
        b5_result=b5_result,
        b5_decoded_information_bits=b5_bits,
        b5_decoded_hypothesis_path=core.decoded_hypothesis_path,
        b5_decoded_symbol_indices=b5_symbols,
        candidate_metrics=core.candidate_metrics,
        m2_evaluation=m2_evaluation,
        b5_evaluation=b5_evaluation,
        m2_branch_metrics=branch_metrics,
        metric_equivalence_offsets=offsets,
        metric_equivalence_scale=8.0 * gain * gain,
        metric_equivalence_max_abs_error=equivalence_error,
        candidate_minimizers_match=minimizers_match,
    )
