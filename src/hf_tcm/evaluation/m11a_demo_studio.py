"""Deterministic, evaluation-only trace collection for the M11 demo studio.

This module does not create RNGs. Receiver computations are invoked only by
``build_demo_trace`` after an explicit caller action; all reference bits,
transmitter values and deterministic noise remain on the evaluation side.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hf_tcm.coding.encoder import INITIAL_STATE, encode_step
from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.trellis import STATES
from hf_tcm.decoding.reconstruction_viterbi import decode_reconstruction_viterbi
from hf_tcm.evaluation.error_metrics import (
    count_bit_errors,
    count_symbol_errors,
    decoded_path_symbol_indices,
    encode_reference_symbol_indices,
)
from hf_tcm.evaluation.m9b_fixed_policy_evaluation_runner import (
    _receiver_configuration,
    resolve_m9_clock_origins,
)
from hf_tcm.modulation.psk8 import constellation
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_forward import (
    RECTANGULAR_ZOH_RULE,
)
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
)
from hf_tcm.receiver.reconstruction_posterior import (
    build_initial_reconstruction_prior,
    reconstruction_likelihood,
)
from hf_tcm.receiver.reconstruction_posterior_estimator_sequence import (
    run_reconstruction_posterior_estimator_sequence,
)

ROOT = Path(__file__).resolve().parents[3]
CLASSIFICATION = "DETERMINISTIC DEMONSTRATION — NOT SCIENTIFIC EVIDENCE"
DEMO_BIT_PATTERNS: dict[str, tuple[int, ...]] = {
    "alternating": (0, 1, 0, 1, 1, 0, 1, 0),
    "grouped": (0, 0, 0, 0, 1, 1, 1, 1),
    "edge_walk": (0, 0, 0, 1, 1, 0, 1, 1),
    "all_zero": (0, 0, 0, 0, 0, 0, 0, 0),
}
DEFAULT_BITS = DEMO_BIT_PATTERNS["alternating"]
NOISE_FIXTURES: dict[str, str] = {
    "zero": "w[n]=0 for every sample",
    "low_amplitude_a": "Re(w[n])=0.004*((n mod 5)-2); Im(w[n])=0.003*((3n mod 7)-3)",
    "alternating_b": "Re(w[n])=0.006*(-1)^n; Im(w[n])=0.002*((n mod 3)-1)",
}
POLICY_IDS = ("historical_frozen_B", "anch_a085_k025")
DEFAULT_NOISE_FIXTURE = "low_amplitude_a"
GROUPS = (
    "Encoder/TCM",
    "State transition mapping",
    "8PSK modulation",
    "Waveform and sampling",
    "Channel and AWGN",
    "Receiver IQ conventions",
    "Candidate prediction",
    "Candidate metric",
    "Posterior normalization",
    "Estimator recursion",
    "Viterbi decoding",
    "Evaluation/statistics",
    "Dataset provenance",
    "Scientific limitations",
)


_M9_CONFIGURATION = json.loads(
    (ROOT / "configs/m9b_evaluation_approved_run.json").read_text(encoding="utf-8")
)


def _configured_policy(candidate_id: str) -> dict[str, Any]:
    return next(row for row in _M9_CONFIGURATION["policies"] if row["candidate_id"] == candidate_id)


def _default_anchored_policy() -> dict[str, Any]:
    return _configured_policy("anch_a085_k025")


def _default_frozen_policy() -> dict[str, Any]:
    return _configured_policy("historical_frozen_B")


_DEFAULT_FROZEN_POLICY = _default_frozen_policy()
_DEFAULT_ANCHORED_POLICY = _default_anchored_policy()


@dataclass(frozen=True, slots=True)
class DemoRequest:
    """Pending deterministic demo inputs; constructing it never runs a receiver."""

    bits: tuple[int, ...] = DEFAULT_BITS
    receiver_mode: str = "compare"
    alpha_prime: float = float(_DEFAULT_ANCHORED_POLICY["alpha_prime"])
    k_tilde: tuple[float, float] = tuple(_DEFAULT_ANCHORED_POLICY["k_tilde"])
    beta: float = float(_DEFAULT_ANCHORED_POLICY["beta"])
    noise_fixture: str = DEFAULT_NOISE_FIXTURE


# Fixed, receiver-independent input preset for the thesis defense.  The
# existing short default remains the fast regression smoke fixture.
DEFENSE_DEMO_REQUEST = DemoRequest(
    bits=tuple(DEMO_BIT_PATTERNS["edge_walk"][index % 8] for index in range(64)),
    receiver_mode="compare",
    alpha_prime=float(_DEFAULT_ANCHORED_POLICY["alpha_prime"]),
    k_tilde=tuple(float(value) for value in _DEFAULT_ANCHORED_POLICY["k_tilde"]),
    beta=float(_DEFAULT_ANCHORED_POLICY["beta"]),
    noise_fixture=DEFAULT_NOISE_FIXTURE,
)


def _json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return _json_value(value.tolist())
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return "Infinity" if value > 0 else "-Infinity" if value < 0 else "NaN"
    if isinstance(value, complex):
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _validate_request(request: DemoRequest) -> tuple[int, ...]:
    if not isinstance(request, DemoRequest):
        raise ValueError("request must be a DemoRequest")
    bits = tuple(request.bits)
    if not 2 <= len(bits) <= 64 or len(bits) % 2:
        raise ValueError("demo bits must contain 2..64 bits in complete 2-bit groups")
    if any(type(bit) is not int or bit not in (0, 1) for bit in bits):
        raise ValueError("demo bits must contain only integer 0/1 values")
    if request.receiver_mode not in {"frozen", "anchored", "compare"}:
        raise ValueError("receiver_mode must be frozen, anchored, or compare")
    values = (request.alpha_prime, *request.k_tilde, request.beta)
    if any(isinstance(value, bool) or not math.isfinite(float(value)) for value in values):
        raise ValueError("demo numeric parameters must be finite real values")
    if request.beta <= 0.0:
        raise ValueError("beta must be > 0 according to the existing posterior API")
    if len(request.k_tilde) != 2:
        raise ValueError("k_tilde must contain exactly I and Q coefficients")
    if request.noise_fixture not in NOISE_FIXTURES:
        raise ValueError("unknown deterministic noise fixture")
    return bits


def _deterministic_noise(count: int, fixture: str) -> NDArray[np.complex128]:
    n = np.arange(count, dtype=np.int64)
    if fixture == "zero":
        values = np.zeros(count, dtype=np.complex128)
    elif fixture == "low_amplitude_a":
        values = 0.004 * ((n % 5) - 2) + 1j * 0.003 * (((3 * n) % 7) - 3)
    else:
        values = 0.006 * np.where(n % 2 == 0, 1, -1) + 1j * 0.002 * ((n % 3) - 1)
    return np.asarray(values, dtype=np.complex128)


def pipeline_stage_catalog() -> list[dict[str, Any]]:
    labels = (
        ("Information bits", "u[0:2F]", "bit", "simulation/evaluation input"),
        ("Grouping into 2-bit inputs", "u_f=(u_{2f},u_{2f+1})", "bit pair", "M1 encoder contract"),
        ("Encoder state before transition", "q_f", "two memory bits", "M1 state path"),
        ("TCM transition selection", "(q_f,u_f)→q_{f+1}", "edge ID", "canonical M1 trellis"),
        ("Three encoded output bits", "c_f=(c_2,c_1,c_0)", "bits", "M1 encoder output"),
        ("ADR-002 edge-to-phase mapping", "b_f=map(c_f)", "phase index", "reconstructed mapping"),
        (
            "8PSK symbol generation",
            "x_f=e^{j2πb_f/8}",
            "complex symbol",
            "normalized constellation",
        ),
        ("Rectangular ZOH waveform", "x[n]=x_{⌊n/8⌋}", "complex sample", "8 samples/symbol"),
        ("Channel gain application", "a·x[n]", "complex sample", "deterministic demo channel"),
        ("AWGN contribution", "w[n]", "complex sample", "selected deterministic fixture"),
        (
            "Received complex samples",
            "y[n]=a·x[n]+w[n]",
            "complex sample",
            "evaluation-side buffer",
        ),
        (
            "ADR-012 observed-IQ transform",
            "Y_f=mean((-Im y, Re y))",
            "I/Q",
            "observed eight-sample window",
        ),
        ("Initial estimator state", "(s_0,full_0)", "I/Q", "selected receiver configuration"),
        ("Full estimator state", "full_f=s_f+μ_0", "I/Q", "actual pre-update state"),
        ("Sixteen edge predictions", "U[f,h]", "I/Q per edge", "actual B4b prediction"),
        ("Sixteen candidate metrics", "F_rx[f,h]", "squared residual", "actual B4b metric"),
        (
            "Pseudo-likelihood calculation",
            "L[f,h]∝exp(-βF_rx)",
            "relative weight",
            "ADR-005 reconstruction",
        ),
        ("Sixteen posterior weights", "p[f,h]", "probability", "actual B4c posterior"),
        (
            "Posterior-weighted innovation",
            "ε_f=Σ_h p(U_obs-U_h)",
            "I/Q",
            "derived from B4c operands",
        ),
        (
            "Recursive coefficient update",
            "s_{f+1}=α′s_f+K̃⊙ε_f",
            "I/Q increment",
            "actual B4c update",
        ),
        ("Next-symbol prediction", "U[f+1,h]", "I/Q per edge", "next pre-update state"),
        ("Frozen metric sequence", "F_rx[0:F,0:16]", "F×16 matrix", "input to conditional decoder"),
        (
            "Viterbi dynamic programming",
            "J_f(q′)=min_q(J_{f-1}(q)+F_f(h))",
            "survivor cost",
            "derived from frozen metrics",
        ),
        ("Survivor path / traceback", "ĥ[0:F]", "edge path", "actual conditional Viterbi"),
        ("Decoded information bits", "û[0:2F]", "bits", "actual conditional Viterbi"),
        ("Reference comparison", "û versus u", "paired positions", "evaluation-only"),
        ("Bit errors / symbol errors", "N_bit,N_sym", "integer count", "raw count API"),
        (
            "BER / SER / paired statistics",
            "BER=N_bit/N_bits; SER=N_sym/F",
            "rate / CI",
            "paired study data only",
        ),
    )
    return [
        {
            "stage_id": f"{index:02d}",
            "name": name,
            "formula": formula,
            "unit": unit,
            "provenance": source,
            "raw_derived_provenance": _STAGE_VALUE_PROVENANCE[index - 1],
            "previous_stage_id": f"{index - 1:02d}" if index > 1 else None,
            "next_stage_id": f"{index + 1:02d}" if index < 28 else None,
        }
        for index, (name, formula, unit, source) in enumerate(labels, start=1)
    ]


_STAGE_DATA_SOURCES = (
    ("trace.input.information_bits", "fixed fixture input", "explicit bits"),
    ("trace.input.input_pairs", "encoder input pairs", "2-bit grouping"),
    ("trace.transmitter.states", "M1 encoder state path", "four canonical states"),
    ("trace.transmitter.edge_ids", "canonical HYPOTHESES ids", "selected edge id"),
    ("trace.transmitter.encoded_output_bits", "encode_step output", "three output bits"),
    ("trace.transmitter.phase_indices", "ADR-002 mapping", "reconstructed mapping"),
    ("trace.transmitter.transmitted_symbols", "8PSK constellation", "normalized symbol"),
    ("trace.transmitter.transmitted_samples", "rectangular ZOH", "8 samples/symbol"),
    ("trace.transmitter.channel_contribution_samples", "fixed gain x Tx", "demo channel"),
    ("trace.transmitter.noise_samples", "fixed noise fixture", "no RNG"),
    ("trace.transmitter.received_samples", "channel + fixed noise", "shared B/anchored buffer"),
    ("arm.symbols[].observed_iq_samples", "actual B4d observation window", "ADR-012"),
    (
        "arm.parameters + sequence_origin",
        "approved policy config and runtime clock",
        "exact policy init",
    ),
    ("arm.symbols[].pre_state", "actual B4d history", "pre-update estimator state"),
    ("arm.symbols[].predicted_iq", "actual B4d candidate result", "16 canonical edges"),
    ("arm.symbols[].candidate_metrics", "actual B4d candidate result", "ADR-005 metric"),
    ("arm.symbols[].pseudo_likelihood", "actual metrics + configured beta", "ADR-005 assumption"),
    ("arm.symbols[].posterior", "actual B4c posterior", "normalized 16 weights"),
    (
        "arm.symbols[].innovation",
        "derived from actual posterior/prediction operands",
        "project reconstruction",
    ),
    ("arm.symbols[].post_state", "actual B4d next state", "alpha/K recursion"),
    (
        "next arm.symbols[].predicted_iq",
        "next row actual B4d history",
        "unavailable on final symbol",
    ),
    ("arm.frozen_metric_sequence", "actual B4d metric rows", "conditional decoder input"),
    ("arm.viterbi.survivor_metrics", "actual conditional Viterbi", "4 state survivor costs"),
    ("arm.viterbi.decoded_edge_path + state_path", "actual conditional Viterbi", "traceback"),
    ("arm.viterbi.decoded_bits", "actual conditional Viterbi", "decoded information bits"),
    (
        "arm.reference_comparison",
        "evaluation-side reference comparison",
        "explicit reference fixture",
    ),
    (
        "arm.reference_comparison raw counts",
        "existing count_bit_errors/count_symbol_errors",
        "integer errors",
    ),
    (
        "arm.reference_comparison BER/SER",
        "raw errors / fixture denominators",
        "single fixture only",
    ),
)

_STAGE_VALUE_PROVENANCE = (
    "raw explicit evaluation input",
    "derived 2-bit grouping",
    "derived M1 encoder state path",
    "derived canonical encoder transition",
    "derived M1 output bits",
    "derived ADR-002 project mapping",
    "derived 8PSK constellation lookup",
    "derived rectangular ZOH samples",
    "derived fixed-gain channel output",
    "raw explicit deterministic noise fixture",
    "derived received sample buffer",
    "raw B4d trace field / ADR-012 observation",
    "raw approved config plus resolved runtime clock state",
    "raw actual B4d pre-update state",
    "raw actual B4d candidate predictions",
    "raw actual B4d candidate metrics",
    "derived ADR-005 pseudo-likelihood from metrics and beta",
    "raw actual B4c posterior",
    "derived from actual posterior, observation, and predictions",
    "raw B4d post-state plus derived update components",
    "raw next-row B4d predictions; unavailable at final symbol",
    "raw actual B4d metric sequence",
    "raw actual conditional Viterbi survivor metrics",
    "raw actual conditional Viterbi edge/state path",
    "raw actual conditional Viterbi decoded bits",
    "derived evaluation-side reference comparison",
    "derived integer counts from existing count functions",
    "derived single-fixture BER/SER; paired inference unavailable",
)


def _stage_runtime_values(
    trace: Mapping[str, Any], stage_number: int, symbol_offset: int, arm_offset: int
) -> tuple[Any, Any, str | None]:
    """Return the same source-backed input/output values represented in UI stage details."""
    arm = trace["arms"][arm_offset]
    row = arm["symbols"][symbol_offset]
    transmitter = trace["transmitter"]
    offset = row["symbol_index"]
    sample_start = offset * ADR012_SAMPLES_PER_SYMBOL
    sample_end = sample_start + ADR012_SAMPLES_PER_SYMBOL
    edge = row["selected_encoder_edge_id"]
    values: tuple[Any, Any] = (
        ("explicit fixture", trace["input"]["information_bits"]),
        (trace["input"]["information_bits"], row["input_bit_pair"]),
        (row["input_bit_pair"], row["encoder_state_before"]),
        (
            {"state": row["encoder_state_before"], "input": row["input_bit_pair"]},
            {"edge_id": edge, "next_state": row["encoder_state_after"]},
        ),
        (edge, row["encoded_output_bits"]),
        (row["encoded_output_bits"], row["phase_index"]),
        (row["phase_index"], transmitter["transmitted_symbols"][offset]),
        (
            transmitter["transmitted_symbols"][offset],
            transmitter["transmitted_samples"][sample_start:sample_end],
        ),
        (
            {
                "samples": transmitter["transmitted_samples"][sample_start:sample_end],
                "gain": row["channel_gain"],
            },
            row["channel_contribution"],
        ),
        (
            {
                "fixture": trace["input"]["noise_fixture"],
                "formula": trace["input"]["noise_formula"],
            },
            row["noise_samples"],
        ),
        (
            {"channel": row["channel_contribution"], "noise": row["noise_samples"]},
            row["received_samples"],
        ),
        (row["received_samples"], row["observed_iq_samples"]),
        (
            {
                "policy": arm["candidate_id"],
                "initial_fluctuating": arm["parameters"]["initial_fluctuating_iq"],
                "mu0": arm["parameters"]["mu0"],
            },
            {"pre_state": row["pre_state"], "initial_full": arm["parameters"]["initial_full_iq"]},
        ),
        (row["pre_state"], row["pre_state"]["full_iq"]),
        (row["pre_state"], row["predicted_iq"]),
        (
            {"observed_iq": row["observed_iq"], "predicted_iq": row["predicted_iq"]},
            row["candidate_metrics"],
        ),
        (
            {"metrics": row["candidate_metrics"], "beta": arm["parameters"]["beta"]},
            row["pseudo_likelihood"],
        ),
        (
            {"prior": row["posterior_input"], "likelihood": row["pseudo_likelihood"]},
            row["posterior"],
        ),
        (
            {
                "posterior": row["posterior"],
                "observed_iq": row["observed_iq"],
                "predicted_iq": row["predicted_iq"],
            },
            row["innovation"],
        ),
        (
            {
                "pre_state": row["pre_state"],
                "alpha_prime": arm["parameters"]["alpha_prime"],
                "k_tilde": arm["parameters"]["k_tilde"],
                "innovation": row["innovation"],
            },
            {
                "alpha_decay": row["alpha_contribution"],
                "correction": row["correction_contribution"],
                "post_state": row["post_state"],
            },
        ),
        (
            row["post_state"],
            arm["symbols"][symbol_offset + 1]["predicted_iq"]
            if symbol_offset + 1 < len(arm["symbols"])
            else None,
        ),
        ("causal per-symbol metric rows", arm["frozen_metric_sequence"]),
        (arm["frozen_metric_sequence"], arm["viterbi"]["survivor_metrics"]),
        (
            {
                "survivor_metrics": arm["viterbi"]["survivor_metrics"],
                "predecessors": arm["viterbi"]["predecessor_hypothesis_ids"],
            },
            {
                "edge_path": arm["viterbi"]["decoded_edge_path"],
                "state_path": arm["viterbi"]["state_path"],
            },
        ),
        (arm["viterbi"]["decoded_edge_path"], arm["viterbi"]["decoded_bits"]),
        (
            {
                "reference_bits": trace["input"]["information_bits"],
                "decoded_bits": arm["viterbi"]["decoded_bits"],
            },
            arm["reference_comparison"],
        ),
        (
            arm["reference_comparison"],
            {
                "bit_errors": arm["reference_comparison"]["bit_errors"],
                "symbol_errors": arm["reference_comparison"]["symbol_errors"],
            },
        ),
        (
            {
                "errors": arm["reference_comparison"]["bit_errors"],
                "total_bits": arm["reference_comparison"]["total_bits"],
                "symbol_errors": arm["reference_comparison"]["symbol_errors"],
                "total_symbols": arm["reference_comparison"]["total_symbols"],
            },
            {"BER": arm["reference_comparison"]["ber"], "SER": arm["reference_comparison"]["ser"]},
        ),
    )
    input_value, output_value = values[stage_number - 1]
    explanation = (
        "Paired confidence inference is unavailable: a single deterministic fixture is not an archived independent study."
        if stage_number == 28
        else None
    )
    return input_value, output_value, explanation


def build_stage_coverage_audit(trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Audit each UI stage against actual deterministic trace values."""
    if len(trace.get("stages", [])) != 28 or not trace.get("arms"):
        raise ValueError("stage audit requires a complete 28-stage demo trace")
    symbol_offset = min(len(trace["arms"][0]["symbols"]) // 2, len(trace["arms"][0]["symbols"]) - 1)
    tests = "test_automated_stage_audit_checks_real_render_data_for_all_28_stages"
    result = []
    for index, stage in enumerate(trace["stages"], start=1):
        input_value, output_value, unavailable = _stage_runtime_values(
            trace, index, symbol_offset, 0
        )
        partial = index == 28
        result.append(
            {
                "stage_id": stage["stage_id"],
                "stage_name": stage["name"],
                "actual_renderer": "renderPipeline → stageValue → #stage-detail",
                "data_source": _STAGE_DATA_SOURCES[index - 1][0],
                "raw_derived_provenance": _STAGE_VALUE_PROVENANCE[index - 1],
                "parameter_source": _STAGE_DATA_SOURCES[index - 1][1],
                "formula_source": stage["formula"] + " / " + stage["provenance"],
                "runtime_coverage": "PARTIAL_BY_DESIGN" if partial else "IMPLEMENTED_WITH_VALUES",
                "test_coverage": tests,
                "rendered_inputs_present": input_value is not None,
                "rendered_outputs_present": output_value is not None or partial,
                "symbol_index": trace["arms"][0]["symbols"][symbol_offset]["symbol_index"],
                "estimator_tick": trace["arms"][0]["symbols"][symbol_offset]["estimator_tick"],
                "sample_indices": trace["arms"][0]["symbols"][symbol_offset]["sample_indices"],
                "unavailable_explanation": unavailable,
            }
        )
    return result


def _policy_rows(request: DemoRequest) -> list[dict[str, Any]]:
    frozen = dict(_DEFAULT_FROZEN_POLICY)
    frozen["beta"] = request.beta
    anchored = dict(_DEFAULT_ANCHORED_POLICY)
    anchored.update(
        candidate_id="anch_a085_k025"
        if request.alpha_prime == _DEFAULT_ANCHORED_POLICY["alpha_prime"]
        and list(request.k_tilde) == _DEFAULT_ANCHORED_POLICY["k_tilde"]
        else "anch_demo",
        alpha_prime=request.alpha_prime,
        k_tilde=list(request.k_tilde),
        beta=request.beta,
    )
    if request.receiver_mode == "frozen":
        return [frozen]
    if request.receiver_mode == "anchored":
        return [anchored]
    return [frozen, anchored]


def _call_estimator(
    received: NDArray[np.complex128], policy: Mapping[str, Any]
) -> tuple[Any, Any, tuple[int, ...], tuple[int, ...]]:
    receiver = _receiver_configuration()
    clocks = resolve_m9_clock_origins(receiver)
    count = received.size // ADR012_SAMPLES_PER_SYMBOL
    start = (
        clocks.absolute_sample_origin + ADR012_SAMPLES_PER_SYMBOL * clocks.absolute_symbol_origin
    )
    labels = np.arange(start, start + received.size, dtype=np.int64)
    initial_state = ReconstructionEstimatorState(
        [policy["initial_fluctuating_iq"]],
        [policy["initial_full_iq"]],
        clocks.estimator_time_index_origin,
    )
    result = run_reconstruction_posterior_estimator_sequence(
        received=received,
        absolute_sample_indices=labels,
        received_start_sample=start,
        symbol_origin_sample=clocks.absolute_sample_origin,
        first_symbol_index=clocks.absolute_symbol_origin,
        sequence_origin_symbol_index=clocks.absolute_symbol_origin,
        symbol_count=count,
        symbol_indices=tuple(
            range(clocks.absolute_symbol_origin, clocks.absolute_symbol_origin + count)
        ),
        initial_state=initial_state,
        initial_estimator_time_index=clocks.estimator_time_index_origin,
        run_mode="new_independent_sequence",
        initial_prior=build_initial_reconstruction_prior(initial_state=INITIAL_STATE),
        previous_posterior=None,
        continuation_from_symbol_index=None,
        continuation_from_estimator_time_index=None,
        beta=float(policy["beta"]),
        alpha_prime=float(policy["alpha_prime"]),
        k_tilde=np.asarray([policy["k_tilde"]], dtype=np.float64),
        mu0=np.asarray([policy["mu0"]], dtype=np.float64),
        include_history=True,
        profile=ADR012_PROFILE,
        adr_profile=ADR012_PROFILE_ID,
        path_count=1,
        path_delays_samples=(0,),
        samples_per_symbol=ADR012_SAMPLES_PER_SYMBOL,
        iq_rule=ADR012_IQ_RULE,
        waveform_rule=ADR012_WAVEFORM_RULE,
        labeling_profile=str(receiver["labeling"]["name"]),
        bit_order=tuple(receiver["labeling"]["bit_order"]),
        timebase_profile=str(receiver["timebase"]["name"]),
        symbol_to_sample_rule=RECTANGULAR_ZOH_RULE,
        edge_policy="zero_padding",
    )
    if result.history is None or len(result.history) != count:
        raise RuntimeError("B4d did not expose complete per-symbol trace history")
    symbols = tuple(range(clocks.absolute_symbol_origin, clocks.absolute_symbol_origin + count))
    times = tuple(clocks.estimator_time_index_origin + offset for offset in range(count))
    decoder = decode_reconstruction_viterbi(
        np.stack([entry.b4c_result.candidate_result.metrics for entry in result.history]),
        hypotheses=HYPOTHESES,
        initial_state=INITIAL_STATE,
        sequence_mode="new_independent_sequence",
        profile=ADR012_PROFILE,
        edge_indices=tuple(range(count)),
        symbol_indices=symbols,
        estimator_time_indices=times,
    )
    return result, decoder, symbols, times


def _state_payload(state: ReconstructionEstimatorState) -> dict[str, Any]:
    return {
        "fluctuating_iq": state.fluctuating_iq[0].tolist(),
        "full_iq": state.full_iq[0].tolist(),
        "time_index": state.time_index,
    }


def build_demo_trace(request: DemoRequest = DemoRequest()) -> dict[str, Any]:
    """Run one explicitly requested, deterministic demo through B4d and B5b."""
    bits = _validate_request(request)
    pairs = tuple((bits[index], bits[index + 1]) for index in range(0, len(bits), 2))
    states = [INITIAL_STATE]
    outputs: list[tuple[int, int, int]] = []
    edge_ids: list[int] = []
    state = INITIAL_STATE
    for pair in pairs:
        output, next_state = encode_step(pair, state)
        edge = next(
            hypothesis
            for hypothesis in HYPOTHESES
            if hypothesis.current_state == state and hypothesis.input_bits == pair
        )
        outputs.append(output)
        edge_ids.append(edge.hypothesis_id)
        states.append(next_state)
        state = next_state
    phases = tuple(
        hypothesis_to_phase_index(
            HYPOTHESES[edge_id], profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
        )
        for edge_id in edge_ids
    )
    tx_symbols = constellation()[np.asarray(phases, dtype=np.int64)]
    transmitted = np.repeat(tx_symbols, ADR012_SAMPLES_PER_SYMBOL)
    noise = _deterministic_noise(transmitted.size, request.noise_fixture)
    channel_gain = float(_M9_CONFIGURATION["profile"]["real_channel_gain"])
    channel_output = np.asarray(channel_gain * transmitted, dtype=np.complex128)
    received = np.asarray(channel_output + noise, dtype=np.complex128)
    received.setflags(write=False)
    tx_samples_payload = [
        {"real": float(value.real), "imag": float(value.imag)} for value in transmitted
    ]
    noise_payload = [{"real": float(value.real), "imag": float(value.imag)} for value in noise]
    received_payload = [
        {"real": float(value.real), "imag": float(value.imag)} for value in received
    ]
    arm_payloads: list[dict[str, Any]] = []
    reference_symbol_indices = encode_reference_symbol_indices(
        bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    for policy in _policy_rows(request):
        sequence, decoder, symbol_indices, time_indices = _call_estimator(received, policy)
        history = sequence.history
        assert history is not None
        rows: list[dict[str, Any]] = []
        metric_matrix = np.stack([entry.b4c_result.candidate_result.metrics for entry in history])
        initial_prior = build_initial_reconstruction_prior(initial_state=INITIAL_STATE)
        for offset, entry in enumerate(history):
            step = entry.b4c_result
            candidate = step.candidate_result
            pre = (
                ReconstructionEstimatorState(
                    [policy["initial_fluctuating_iq"]],
                    [policy["initial_full_iq"]],
                    time_indices[0],
                )
                if offset == 0
                else history[offset - 1].b4c_result.next_state
            )
            post = step.next_state
            posterior_input = (
                initial_prior if offset == 0 else history[offset - 1].b4c_result.posterior
            )
            innovation = np.sum(
                step.posterior[:, np.newaxis] * (step.observed_iq - step.predicted_iq), axis=0
            )
            alpha_delta = (float(policy["alpha_prime"]) - 1.0) * pre.fluctuating_iq[0]
            correction_delta = np.asarray(policy["k_tilde"]) * innovation
            likelihood = reconstruction_likelihood(candidate.metrics, beta=float(policy["beta"]))
            sample_start = candidate.sample_indices[0]
            rows.append(
                {
                    "symbol_index": entry.symbol_index,
                    "estimator_tick": entry.estimator_time_index,
                    "sample_indices": list(candidate.sample_indices),
                    "prediction_cutoff_sample": candidate.prediction_cutoff_sample_index,
                    "observation_cutoff_sample": candidate.metric_available_after_sample_index,
                    "input_bit_pair": list(pairs[offset]),
                    "encoder_state_before": list(states[offset]),
                    "selected_encoder_edge_id": edge_ids[offset],
                    "encoder_state_after": list(states[offset + 1]),
                    "encoded_output_bits": list(outputs[offset]),
                    "phase_index": phases[offset],
                    "transmitted_symbol": {
                        "real": float(tx_symbols[offset].real),
                        "imag": float(tx_symbols[offset].imag),
                    },
                    "transmitted_samples": tx_samples_payload[offset * 8 : offset * 8 + 8],
                    "channel_gain": channel_gain,
                    "channel_contribution": [
                        {"real": float(value.real), "imag": float(value.imag)}
                        for value in channel_output[offset * 8 : offset * 8 + 8]
                    ],
                    "noise_samples": noise_payload[offset * 8 : offset * 8 + 8],
                    "received_samples": received_payload[offset * 8 : offset * 8 + 8],
                    "observed_iq_samples": [
                        {"i": float(-received[n].imag), "q": float(received[n].real)}
                        for n in range(sample_start, sample_start + 8)
                    ],
                    "pre_state": _state_payload(pre),
                    "observed_iq": step.observed_iq.tolist(),
                    "predicted_iq": candidate.sample_predictions_iq[:, 0, :].tolist(),
                    "sample_predictions_iq": candidate.sample_predictions_iq.tolist(),
                    "hypothesis_ids": list(candidate.hypothesis_ids),
                    "edge_definitions": [
                        {
                            "edge_id": hypothesis.hypothesis_id,
                            "source_state": list(hypothesis.current_state),
                            "input_bits": list(hypothesis.input_bits),
                            "output_bits": list(hypothesis.output_bits),
                            "target_state": list(hypothesis.next_state),
                            "phase_index": int(candidate.phase_indices[hypothesis.hypothesis_id]),
                        }
                        for hypothesis in HYPOTHESES
                    ],
                    "candidate_metrics": candidate.metrics.tolist(),
                    "pseudo_likelihood": likelihood.tolist(),
                    "posterior_input": posterior_input.tolist(),
                    "posterior_input_kind": "ADR-004 prior"
                    if offset == 0
                    else "previous own posterior",
                    "posterior": step.posterior.tolist(),
                    "posterior_sum": math.fsum(float(value) for value in step.posterior),
                    "posterior_normalized": math.isclose(
                        math.fsum(float(value) for value in step.posterior), 1.0, abs_tol=1e-10
                    ),
                    "innovation": innovation.tolist(),
                    "alpha_contribution": alpha_delta.tolist(),
                    "correction_contribution": correction_delta.tolist(),
                    "coefficient_increment": (
                        post.fluctuating_iq[0] - pre.fluctuating_iq[0]
                    ).tolist(),
                    "post_state": _state_payload(post),
                    "next_symbol_pre_state": _state_payload(post),
                    "finite": bool(
                        np.all(np.isfinite(candidate.metrics))
                        and np.all(np.isfinite(step.posterior))
                        and np.all(np.isfinite(post.full_iq))
                    ),
                }
            )
        decoded_symbols = decoded_path_symbol_indices(
            decoder.hypothesis_ids, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
        )
        decoded_bits = decoder.decoded_bits.tolist()
        bit_errors = count_bit_errors(bits, decoded_bits)
        symbol_errors = count_symbol_errors(reference_symbol_indices, decoded_symbols)
        for symbol_index, row in enumerate(rows):
            decoded_pair = decoder.input_pairs[symbol_index].tolist()
            reference_pair = list(pairs[symbol_index])
            row["reference_comparison"] = {
                "decoded_input_pair": decoded_pair,
                "reference_input_pair": reference_pair,
                "bit_error_flags": [
                    int(left != right)
                    for left, right in zip(decoded_pair, reference_pair, strict=True)
                ],
                "decoded_phase_index": int(decoded_symbols[symbol_index]),
                "reference_phase_index": int(reference_symbol_indices[symbol_index]),
                "symbol_error": bool(
                    decoded_symbols[symbol_index] != reference_symbol_indices[symbol_index]
                ),
            }
        arm_payloads.append(
            {
                "candidate_id": policy["candidate_id"],
                "parameters": _json_value(policy),
                "sequence_origin": {
                    "sample": int(rows[0]["sample_indices"][0]),
                    "symbol": int(symbol_indices[0]),
                    "estimator_tick": int(time_indices[0]),
                },
                "symbols": rows,
                "frozen_metric_sequence": metric_matrix.tolist(),
                "viterbi": {
                    "decoded_bits": decoded_bits,
                    "decoded_input_pairs": decoder.input_pairs.tolist(),
                    "decoded_edge_path": list(decoder.hypothesis_ids),
                    "state_path": [list(value) for value in decoder.state_path],
                    "survivor_metrics": decoder.survivor_metrics.tolist(),
                    "survivor_metrics_shape": list(decoder.survivor_metrics.shape),
                    "predecessor_hypothesis_ids": decoder.predecessor_hypothesis_ids.tolist(),
                    "best_conditional_path_cost": decoder.best_path_metric,
                    "decoder_calls": 1,
                    "semantics": "conditional full Viterbi over frozen causal metrics; not forward-backward HMM inference",
                },
                "reference_comparison": {
                    "reference_data_provenance": "explicit demo input; evaluation side only",
                    "bit_errors": bit_errors,
                    "total_bits": len(bits),
                    "symbol_errors": symbol_errors,
                    "total_symbols": len(pairs),
                    "ber": bit_errors / len(bits),
                    "ser": symbol_errors / len(pairs),
                },
                "final_state": _state_payload(sequence.final_state),
                "final_posterior": sequence.final_posterior.tolist(),
                "finite_coefficient_trajectory": all(row["finite"] for row in rows),
            }
        )
    return {
        "schema_version": "m11a.demo-trace.v1",
        "classification": CLASSIFICATION,
        "scientific_status": {
            "profile": "reconstructed_offline",
            "paper_exact": False,
            "receiver_enabled": False,
            "source_mapping_status": "SOURCE_UNRESOLVED",
            "metric_status": "ADR-005 pseudo-likelihood; SCI-METRIC-02 remains open",
            "innovation_status": "project reconstruction operand; author innovation semantics unresolved",
        },
        "input": {
            "information_bits": list(bits),
            "input_pairs": [list(pair) for pair in pairs],
            "symbol_count": len(pairs),
            "sample_count": int(received.size),
            "noise_fixture": request.noise_fixture,
            "noise_formula": NOISE_FIXTURES[request.noise_fixture],
            "channel_gain": channel_gain,
            "received_sha256": __import__("hashlib")
            .sha256(np.asarray(received, dtype="<c16").tobytes())
            .hexdigest(),
            "clock_origins": resolve_m9_clock_origins(_receiver_configuration()).as_dict(),
            "rng_used": False,
            "channel_truth_passed_to_receiver": False,
            "reference_bits_passed_to_receiver": False,
        },
        "stage_status": "AVAILABLE_RAW_AND_DERIVED_WITH_STAGE28_PARTIAL",
        "symbols": list(range(len(pairs))),
        "stages": pipeline_stage_catalog(),
        "transmitter": {
            "states": [list(value) for value in states],
            "edge_ids": edge_ids,
            "encoded_output_bits": [list(value) for value in outputs],
            "phase_indices": list(phases),
            "transmitted_symbols": [
                {"real": float(value.real), "imag": float(value.imag)} for value in tx_symbols
            ],
            "transmitted_samples": tx_samples_payload,
            "channel_contribution_samples": [
                {"real": float(value.real), "imag": float(value.imag)} for value in channel_output
            ],
            "noise_samples": noise_payload,
            "received_samples": received_payload,
        },
        "arms": arm_payloads,
        "array_shapes": {
            "information_bits": [len(bits)],
            "input_pairs": [len(pairs), 2],
            "encoded_output_bits": [len(outputs), 3],
            "phase_indices": [len(phases)],
            "transmitted_symbols": [len(tx_symbols)],
            "transmitted_noise_received_samples": [int(received.size)],
            "predicted_iq_per_arm": [len(pairs), len(HYPOTHESES), 2],
            "candidate_metrics_per_arm": [len(pairs), len(HYPOTHESES)],
            "posterior_per_arm": [len(pairs), len(HYPOTHESES)],
            "sample_predictions_per_arm": [len(pairs), len(HYPOTHESES), 8, 2],
            "viterbi_survivor_metrics_per_arm": [len(pairs), len(STATES)],
            "viterbi_predecessor_ids_per_arm": [len(pairs), len(STATES)],
        },
        "canonical_hypothesis_order": list(range(len(HYPOTHESES))),
        "parameter_registry": build_parameter_registry({"arms": arm_payloads}),
        "pairing": {
            "same_received_sha256": True,
            "received_sha256": hashlib_sha256_complex(received),
            "paired_statistics": "UNAVAILABLE: one deterministic demonstration is not an independent statistical sample",
        },
    }


def hashlib_sha256_complex(values: NDArray[np.complex128]) -> str:
    import hashlib

    return hashlib.sha256(np.asarray(values, dtype="<c16", order="C").tobytes()).hexdigest()


def _group_for_config_path(path: str) -> str:
    if path.startswith("initial.") or path.startswith("transition_model"):
        return "Encoder/TCM"
    if path.startswith("labeling"):
        return "State transition mapping"
    if path.startswith("timebase"):
        return "Waveform and sampling"
    if path.startswith("observation_model"):
        return "Receiver IQ conventions"
    if path.startswith("likelihood"):
        return "Posterior normalization"
    if path.startswith("estimator"):
        return "Estimator recursion"
    if path.startswith("search"):
        return "Viterbi decoding"
    return "Candidate metric"


def _flatten(value: object, prefix: str = "") -> list[tuple[str, object]]:
    if isinstance(value, Mapping):
        return [
            row
            for key, item in value.items()
            for row in _flatten(item, f"{prefix}.{key}".strip("."))
        ]
    if isinstance(value, list):
        return [(prefix, value)]
    return [(prefix, value)]


def _parameter_unit(path: str) -> str:
    key = path.lower()
    if "sample_rate" in key or "symbol_rate" in key:
        return "Hz"
    if "samples_per_symbol" in key:
        return "samples/symbol"
    if "sigma_squared" in key:
        return "normalized complex-sample power"
    if "constellation" in key:
        return "normalized complex symbol"
    if "gamma_b_eff_db" in key:
        return "dB (effective discrete convention)"
    if "phase_offset_rad" in key:
        return "radian"
    if "delay" in key or "sample_index" in key or "sample_origin" in key:
        return "sample"
    if "symbol_index" in key or "symbol_count" in key or "frame_symbols" in key:
        return "symbol"
    if "time_index" in key or "tick" in key:
        return "estimator tick"
    if "beta" in key:
        return "inverse reconstructed metric"
    if "metric" in key:
        return "squared I/Q residual"
    if "posterior" in key or "likelihood" in key or "ber" in key or "ser" in key:
        return "probability / relative weight"
    if "gain" in key or "alpha" in key or "k_tilde" in key or "mu0" in key:
        return "dimensionless coefficient"
    if "bit" in key or "state" in key or "edge" in key or "phase" in key:
        return "bit / index"
    if "count" in key or "width" in key or "length" in key or "beam" in key:
        return "count"
    return "project-defined"


def _parameter_symbol(path: str) -> str:
    """Human-readable mathematical notation for registry-backed settings."""
    key = path.rsplit(".", 1)[-1]
    return {
        "alpha_prime": "α′",
        "k_tilde": "K̃=(K̃I,K̃Q)",
        "mu0": "μ₀",
        "initial_fluctuating_iq": "s₀",
        "initial_full_iq": "full₀",
        "beta": "β",
        "sigma_squared": "σ²",
        "samples_per_symbol": "Nₛ",
        "frame_symbols": "F",
        "switch_symbol_index": "fₛ",
        "switch_sample_index": "nₛ",
        "nominal_gain": "a₀",
        "low_gain": "a_low",
        "high_gain": "a_high",
        "mean_squared_gain_target": "E_frame[a²]",
        "zero_delay": "d=0",
        "channel_memory_L": "L",
        "constellation_size": "M",
        "constellation_points": "Xₘ",
        "candidate_count": "H",
        "equation": "channel model",
        "profile_id": "profile",
        "historical_dataset_roots": "dataset provenance",
        "noise_fixtures": "w[n] fixture",
        "paper_exact": "paper_exact",
        "receiver_enabled": "receiver_enabled",
        "source_mapping_status": "source mapping",
    }.get(key, path)


def build_parameter_registry(demo_trace: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Flatten live project configuration and actual constants with provenance."""
    receiver_config = _receiver_configuration()
    m9_config = json.loads(
        (ROOT / "configs/m9b_evaluation_approved_run.json").read_text(encoding="utf-8")
    )
    m10_config = json.loads(
        (ROOT / "configs/m10b_variable_gain_approved_run.json").read_text(encoding="utf-8")
    )
    entries: list[dict[str, Any]] = []

    def add(
        key: str,
        value: object,
        group: str,
        source: str,
        unit: str = "project-defined",
        status: str = "read_only",
        constraints: str = "No allowed range specified by the repository",
    ) -> None:
        if unit == "project-defined":
            unit = _parameter_unit(key)
        entries.append(
            {
                "parameter": key,
                "symbol": _parameter_symbol(key),
                "value": _json_value(value),
                "unit": unit,
                "default_value": _json_value(value) if status == "demo_editable" else None,
                "type": (
                    "boolean"
                    if isinstance(value, bool)
                    else "integer"
                    if isinstance(value, int)
                    else "number"
                    if isinstance(value, float)
                    else "array"
                    if isinstance(value, (tuple, list, np.ndarray))
                    else "object"
                    if isinstance(value, Mapping)
                    else "string"
                ),
                "allowed_range": "> 0"
                if status == "demo_editable" and key.endswith(".beta")
                else None,
                "source": source,
                "assumption": "Project reconstruction setting unless explicitly labeled otherwise",
                "status": status,
                "constraints": constraints,
                "explanation": f"Value read from {source}; no independent GUI copy is used.",
                "description": f"Value read from {source}; no independent GUI copy is used.",
                "group": group,
            }
        )

    for path, value in _flatten(receiver_config):
        add(path, value, _group_for_config_path(path), "configs/m5i_confirmatory_design_draft.json")
    for key, value in _M9_CONFIGURATION["profile"].items():
        add(
            f"profile.{key}",
            value,
            "Channel and AWGN",
            "configs/m9b_evaluation_approved_run.json",
        )
    for policy in m9_config["policies"]:
        for key in (
            "alpha_prime",
            "k_tilde",
            "mu0",
            "initial_fluctuating_iq",
            "initial_full_iq",
            "beta",
        ):
            add(
                f"{policy['candidate_id']}.{key}",
                policy[key],
                "Estimator recursion",
                "configs/m9b_evaluation_approved_run.json",
                status="demo_editable"
                if policy["candidate_id"] == "anch_a085_k025"
                and key in {"alpha_prime", "k_tilde", "beta"}
                else "read_only",
                constraints="Finite real scalar; beta > 0; K̃ has two real coordinates; demo-only edit"
                if policy["candidate_id"] == "anch_a085_k025"
                and key in {"alpha_prime", "k_tilde", "beta"}
                else "Fixed historical receiver policy; read-only",
            )
    profile = m10_config["channel_profile"]
    for key in (
        "profile_id",
        "equation",
        "channel_memory_L",
        "zero_delay",
        "samples_per_symbol",
        "frame_symbols",
        "switch_symbol_index",
        "switch_sample_index",
        "nominal_gain",
        "low_gain",
        "high_gain",
        "mean_squared_gain_target",
    ):
        add(
            f"channel_profile.{key}",
            profile[key],
            "Channel and AWGN",
            "configs/m10b_variable_gain_approved_run.json",
        )
    for key, value in m10_config["noise"].items():
        add(
            f"noise.{key}",
            value,
            "Channel and AWGN",
            "configs/m10b_variable_gain_approved_run.json",
        )
    for key, value in m10_config["statistics"].items():
        add(
            f"statistics.{key}",
            value,
            "Evaluation/statistics",
            "configs/m10b_variable_gain_approved_run.json",
        )
    for state_index, state in enumerate(STATES):
        add(f"trellis.state[{state_index}]", state, "Encoder/TCM", "hf_tcm.coding.trellis.STATES")
    for hypothesis in HYPOTHESES:
        add(
            f"trellis.edge[{hypothesis.hypothesis_id}]",
            {
                "source": hypothesis.current_state,
                "input": hypothesis.input_bits,
                "output": hypothesis.output_bits,
                "target": hypothesis.next_state,
            },
            "State transition mapping",
            "hf_tcm.coding.hypotheses.HYPOTHESES",
        )
    add(
        "constellation_size",
        len(constellation()),
        "8PSK modulation",
        "hf_tcm.modulation.psk8.constellation",
    )
    add(
        "constellation_points",
        constellation(),
        "8PSK modulation",
        "hf_tcm.modulation.psk8.constellation",
    )
    add(
        "candidate_count",
        len(HYPOTHESES),
        "Candidate prediction",
        "hf_tcm.coding.hypotheses.HYPOTHESES",
    )
    add(
        "historical_dataset_roots",
        build_dataset_coverage()["sources"],
        "Dataset provenance",
        "outputs/M5–M10 manifests and summaries",
    )
    add(
        "noise_fixtures",
        NOISE_FIXTURES,
        "Channel and AWGN",
        "M11 deterministic demo definitions",
        status="demo_editable",
        constraints="Select one explicit deterministic fixture; no RNG",
    )
    add("paper_exact", False, "Scientific limitations", "ADR-010 / reconstruction configuration")
    add(
        "receiver_enabled",
        False,
        "Scientific limitations",
        "ADR-010 / reconstruction configuration",
    )
    add(
        "source_mapping_status",
        "SOURCE_UNRESOLVED",
        "Scientific limitations",
        "docs/ASSUMPTIONS_AND_DECISIONS.md",
    )
    add("SCI-METRIC-02", "OPEN", "Scientific limitations", "docs/M4_OPEN_QUESTIONS.md")
    if demo_trace is not None:
        for arm in demo_trace.get("arms", []):
            add(
                f"runtime.{arm['candidate_id']}.final_state",
                arm["final_state"],
                "Dataset provenance",
                "current deterministic demonstration trace",
            )
            for symbol in arm.get("symbols", []):
                for field in ("pre_state", "post_state", "innovation", "posterior_sum"):
                    add(
                        f"runtime.{arm['candidate_id']}.f{symbol['symbol_index']}.{field}",
                        symbol[field],
                        "Dataset provenance",
                        "current deterministic demonstration trace / actual B4d history",
                    )
    return entries


def build_dataset_coverage() -> dict[str, Any]:
    """Describe source-backed coverage without synthesizing absent histories."""
    sources = {
        "M6b": ROOT / "outputs/m6b_trace_diagnostics/m6b_causal_trace_20261030_v1/summary.json",
        "M6g": ROOT / "outputs/m6g_multistep_feedback_audit/deterministic_trace.json",
        "M6h": ROOT / "outputs/m6h_posterior_clamp/deterministic_trace.json",
        "M5j": ROOT / "outputs/m5j_confirmatory/20261029T-run/summary.json",
        "M7b": ROOT / "outputs/m7b_train/m7_reconstructed_estimator_policy_study_v1/summary.json",
        "M8b": ROOT
        / "outputs/m8b_train_recovery/m8_anchored_reconstructed_adaptation_v1_attempt2/summary.json",
        "M9b": ROOT
        / "outputs/m9b_fixed_policy_evaluation/m9_fixed_anchored_vs_frozen_v1/summary.json",
        "M10b": ROOT / "outputs/m10b_variable_gain/m10_controlled_piecewise_gain_v1/summary.json",
    }
    datasets = ("deterministic_demo", *sources.keys())
    sequence_records = {"M7b", "M8b", "M9b", "M10b"}
    stages: dict[str, dict[str, str]] = {}
    for stage in pipeline_stage_catalog():
        stage_id = stage["stage_id"]
        row: dict[str, str] = {"deterministic_demo": "AVAILABLE_RAW"}
        number = int(stage_id)
        for dataset, path in sources.items():
            if not path.is_file():
                row[dataset] = "UNAVAILABLE"
            elif dataset == "M6b" and 12 <= number <= 25:
                row[dataset] = (
                    "AVAILABLE_RAW" if number <= 20 or number == 25 else "AVAILABLE_DERIVED"
                )
            elif dataset in {"M6g", "M6h"} and 12 <= number <= 22:
                row[dataset] = (
                    "AVAILABLE_RAW" if number <= 20 or number == 22 else "AVAILABLE_DERIVED"
                )
            elif dataset == "M5j" and number in {26, 27, 28}:
                row[dataset] = "AGGREGATE_ONLY"
            elif dataset in sequence_records and number == 1:
                row[dataset] = "AVAILABLE_RAW"
            elif dataset in {"M7b", "M8b", "M9b"} and number in {2, 3, 4, 5, 6, 7, 8, 26}:
                row[dataset] = "AVAILABLE_DERIVED"
            elif dataset in {"M7b", "M8b", "M9b"} and number == 9:
                row[dataset] = "AVAILABLE_RAW"
            elif dataset in sequence_records and number == 25:
                row[dataset] = "AVAILABLE_RAW"
            elif dataset in sequence_records and number == 27:
                row[dataset] = "AVAILABLE_RAW"
            elif dataset in sequence_records and number == 28:
                row[dataset] = "AGGREGATE_ONLY"
            elif dataset == "M10b" and number in {8, 9, 10, 11}:
                row[dataset] = "AVAILABLE_RAW" if number in {8, 10} else "AVAILABLE_DERIVED"
            else:
                row[dataset] = "UNAVAILABLE"
        stages[stage_id] = row
    stage_for_symbol_history = stages["14"]["M5j"]
    assert stage_for_symbol_history == "UNAVAILABLE"
    return {
        "datasets": list(datasets),
        "stages": stages,
        "sources": {
            key: {
                "path": path.relative_to(ROOT).as_posix(),
                "exists": path.is_file(),
                "sha256": _file_sha256(path) if path.is_file() else None,
                "note": "M5j per-symbol estimator history is unavailable; aggregate outputs are not expanded into traces."
                if key == "M5j"
                else "Read-only historical source. Estimator samples/states are unavailable where the run schema stored only decoded arrays and counts.",
            }
            for key, path in sources.items()
        },
        "status_values": ["AVAILABLE_RAW", "AVAILABLE_DERIVED", "AGGREGATE_ONLY", "UNAVAILABLE"],
        "experiments": _research_dashboard_data(sources),
    }


def _research_dashboard_data(sources: Mapping[str, Path]) -> dict[str, Any]:
    """Expose stored aggregate outcomes without decoding or editing artifacts."""
    payload: dict[str, Any] = {}
    for name, path in sources.items():
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        summary: dict[str, Any] = {
            "status": data.get("status", "status unavailable"),
            "classification": data.get("classification", data.get("evidence_status", "")),
            "artifact": path.relative_to(ROOT).as_posix(),
            "sha256": _file_sha256(path),
        }
        if name == "M5j":
            summary["point_estimates"] = data.get("point_estimates")
            summary["bootstrap"] = data.get("bootstrap")
            summary["planned_runs"] = data.get("planned_run_count")
            summary["completed_runs"] = data.get("completed_valid_run_count")
        elif name == "M6b":
            summary["run_count"] = len(data.get("run_results", []))
            summary["performance_evidence"] = False
        elif name == "M6g":
            summary["fixture_sha256"] = data.get("fixture_sha256")
            summary["symbols"] = data.get("received_sample_count", 0) // ADR012_SAMPLES_PER_SYMBOL
            summary["invariant_status"] = data.get("invariant_status")
            summary["decoder_invoked"] = data.get("decoder_invoked")
        elif name == "M6h":
            summary["fixture_sha256"] = data.get("fixture_sha256")
            summary["invariant_status"] = data.get("invariant_status")
            summary["decoder_invoked"] = data.get("decoder_invoked")
        elif name == "M7b":
            summary["planned_runs"] = data.get("planned_run_count")
            summary["completed_runs"] = data.get("completed_run_count")
            summary["policy_records"] = data.get("policy_record_count")
            summary["ranking"] = data.get("ranking")
            summary["selected_candidate_id"] = data.get("selected_candidate_id")
        elif name == "M8b":
            summary["planned_runs"] = data.get("planned_run_count")
            summary["completed_runs"] = data.get("completed_run_count")
            summary["policy_records"] = data.get("policy_record_count")
            summary["ranking"] = data.get("ranking")
            summary["selected_candidate_id"] = data.get("selected_candidate_id")
        elif name == "M9b":
            summary["paired_estimands"] = data.get("paired_estimands")
            m9_bootstrap = dict(data.get("bootstrap", {}))
            for ci_key in ("delta_ber_ci", "delta_ser_ci"):
                if m9_bootstrap.get(ci_key):
                    m9_bootstrap[ci_key] = [round(value, 14) for value in m9_bootstrap[ci_key]]
            summary["bootstrap"] = m9_bootstrap
            m9_ci = m9_bootstrap.get("delta_ber_ci")
            summary["delta_ber_95_ci_contains_zero"] = (
                bool(m9_ci[0] <= 0.0 <= m9_ci[1]) if m9_ci else None
            )
            summary["completed_runs"] = data.get("completed_runs")
            summary["decoder_invocations"] = data.get("decoder_invocations")
        elif name == "M10b":
            statistics = data.get("statistics", {})
            summary["primary_profile"] = statistics.get("primary_profile")
            primary_delta = statistics.get("primary_delta_ber")
            primary_ci = statistics.get("primary_95_percent_ci")
            summary["primary_delta_ber"] = (
                round(primary_delta, 10) if primary_delta is not None else None
            )
            summary["primary_95_percent_ci"] = (
                [round(value, 14) for value in primary_ci] if primary_ci else None
            )
            summary["primary_95_percent_ci_contains_zero"] = (
                bool(primary_ci[0] <= 0.0 <= primary_ci[1]) if primary_ci else None
            )
            summary["profile_results"] = statistics.get("profiles")
            summary["completed_runs"] = data.get("completed_run_clusters")
            summary["decoder_invocations"] = data.get("decoder_invocations")
        payload[name] = summary
    return payload


def _file_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_studio_metadata() -> dict[str, Any]:
    anchored = _default_anchored_policy()
    return {
        "paper_exact": False,
        "receiver_enabled": False,
        "model_status": "RECONSTRUCTED MODEL",
        "stages": pipeline_stage_catalog(),
        "parameters": build_parameter_registry(),
        "coverage": build_dataset_coverage(),
        "states": [list(state) for state in STATES],
        "edges": [
            {
                "edge_id": hypothesis.hypothesis_id,
                "source_state": list(hypothesis.current_state),
                "input_bits": list(hypothesis.input_bits),
                "output_bits": list(hypothesis.output_bits),
                "target_state": list(hypothesis.next_state),
            }
            for hypothesis in HYPOTHESES
        ],
        "demo": {
            "bit_patterns": {key: list(value) for key, value in DEMO_BIT_PATTERNS.items()},
            "noise_fixtures": NOISE_FIXTURES,
            "defense_preset": {
                "id": "defense_f32",
                "symbol_count": 32,
                "bits": list(DEFENSE_DEMO_REQUEST.bits),
                "receiver_mode": "compare",
                "alpha_prime": DEFENSE_DEMO_REQUEST.alpha_prime,
                "k_tilde": list(DEFENSE_DEMO_REQUEST.k_tilde),
                "beta": DEFENSE_DEMO_REQUEST.beta,
                "noise_fixture": DEFENSE_DEMO_REQUEST.noise_fixture,
                "initial_states": {
                    policy["candidate_id"]: {
                        "initial_fluctuating_iq": policy["initial_fluctuating_iq"],
                        "initial_full_iq": policy["initial_full_iq"],
                        "mu0": policy["mu0"],
                    }
                    for policy in (_DEFAULT_FROZEN_POLICY, _DEFAULT_ANCHORED_POLICY)
                },
            },
            "default_receiver_parameters": {
                "alpha_prime": anchored["alpha_prime"],
                "k_tilde": anchored["k_tilde"],
                "beta": anchored["beta"],
            },
            "default_noise_fixture": DEFAULT_NOISE_FIXTURE,
        },
    }
