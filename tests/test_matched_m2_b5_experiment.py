from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.posterior import ALLOWED_HYPOTHESIS_TRANSITIONS
from hf_tcm.evaluation.error_metrics import encode_reference_symbol_indices
from hf_tcm.evaluation.matched_m2_b5_experiment import (
    ORACLE_CSI_MATCHED_CONTROL,
    generate_independent_complex_awgn,
    run_matched_m2_b5_experiment,
)
from hf_tcm.modulation.psk8 import constellation
from hf_tcm.receiver.reconstruction_forward import APPROXIMATE_RECTANGULAR_8SPS
from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER


def _configuration(gain: float, *, origin: int = 23, initial_time: int = 41) -> dict[str, object]:
    support = ALLOWED_HYPOTHESIS_TRANSITIONS.astype(np.float64)
    transitions = support / support.sum(axis=1, keepdims=True)
    provenance_fields = (
        "candidate_index_space",
        "candidate_count",
        "labeling",
        "transition_model",
        "initial_state",
        "initial_prior",
        "likelihood_type",
        "beta",
        "alpha_prime",
        "k_tilde",
        "mu0",
        "initial_estimates",
        "estimator_time_index",
        "estimator_time_rule",
        "timebase",
        "samples_per_symbol",
        "sample_rate_hz",
        "symbol_rate_hz",
        "symbol_origin_sample",
        "path_delays_samples",
        "path_count",
        "aggregate_observation_model",
        "prediction_combination",
        "beam_width",
        "decision_lag_symbols",
    )
    return {
        "schema_version": 1,
        "profile": "reconstructed_offline",
        "paper_exact": False,
        "receiver_enabled": False,
        "candidate_index_space": "m4_1_hypothesis_id",
        "candidate_count": 16,
        "labeling": {
            "name": ASSUMED_NATURAL_BINARY,
            "origin": "ADR-002 paired-control setting",
            "bit_order": list(OUTPUT_BIT_ORDER),
            "output_to_b": list(range(8)),
            "phase_offset_rad": 0.0,
        },
        "transition_model": {
            "name": "adr003_uniform_allowed_edges",
            "probabilities": transitions.tolist(),
        },
        "initial": {
            "state": [0, 0],
            "prior": [0.25 if h.current_state == (0, 0) else 0.0 for h in HYPOTHESES],
        },
        "likelihood": {
            "kind": "exp_negative_beta_project_reconstruction_metric",
            "beta": 0.7,
        },
        "estimator": {
            "alpha_prime": 1.0,
            "k_tilde": [[0.0, 0.0]],
            "mu0": [[0.0, 0.0]],
            "initial_time_index": initial_time,
            "time_rule": "one_recursion_step_i_to_i_plus_1",
            "initial_estimates": {
                "fluctuating_iq": [[gain, gain]],
                "full_iq": [[gain, gain]],
            },
        },
        "timebase": {
            "name": APPROXIMATE_RECTANGULAR_8SPS,
            "samples_per_symbol": 8,
            "sample_rate_hz": 8000.0,
            "symbol_rate_hz": 1000.0,
            "symbol_origin_sample": origin,
            "path_count": 1,
            "path_delays_samples": [0],
        },
        "observation_model": {
            "kind": "adr012_l1_real_mean8",
            "prediction_combination": "explicit_project_prediction",
            "iq_rule": "(-Im(received), Re(received))",
            "sample_reduction": "arithmetic_mean_exactly_8",
            "waveform_rule": "rectangular_zoh",
        },
        "search": {"beam_width": 1, "decision_lag_symbols": 0},
        "assumption_provenance": {
            key: {
                "status": "accepted_project_setting",
                "source": "explicit M5d paired control",
                "note": "value is run configuration, not inferred from article",
            }
            for key in provenance_fields
        },
    }


def _reference_bits(count: int) -> np.ndarray:
    return np.asarray(
        [(3 * index + index // 2 + 1) % 2 for index in range(2 * count)], dtype=np.int8
    )


def _run(
    *,
    run_id: str = "paired-test",
    count: int = 4,
    gain: float = 0.75,
    noise: np.ndarray | None = None,
    sigma_squared: float | None = None,
    noise_seed: int | None = None,
    stream_id: str | None = None,
    mode: str = "monolithic",
    partition: tuple[int, ...] | None = None,
) -> object:
    return run_matched_m2_b5_experiment(
        run_id=run_id,
        symbol_count=count,
        reference_information_bits=_reference_bits(count),
        real_channel_gain=gain,
        sigma_squared=sigma_squared,
        noise=noise,
        noise_seed=noise_seed,
        noise_stream_id=stream_id,
        noise_provenance=(
            "explicit deterministic complex sample array"
            if noise is not None
            else "PCG64 independent sample AWGN stream"
        ),
        symbol_origin_sample=23,
        first_symbol_index=5,
        initial_estimator_time_index=41,
        configuration=_configuration(gain),
        receiver_mode=mode,
        segment_partition=partition,
        initial_csi_provenance=ORACLE_CSI_MATCHED_CONTROL,
    )


@pytest.mark.parametrize("gain", [0.75, 2.0])
@pytest.mark.parametrize("count", [1, 2, 4])
def test_noiseless_paired_m2_b5_control_has_matching_path(gain: float, count: int) -> None:
    result = _run(count=count, gain=gain, noise=np.zeros(8 * count, dtype=np.complex128))

    assert result.experiment_name.startswith("isolated matched discrete-AWGN paired")
    assert result.receiver_mode == "monolithic"
    assert result.initial_csi_provenance == ORACLE_CSI_MATCHED_CONTROL
    assert result.sigma_squared is None
    assert result.effective_discrete_gamma_b is None
    assert np.array_equal(result.m2_decoded_information_bits, result.b5_decoded_information_bits)
    assert result.m2_decoded_hypothesis_path == result.b5_decoded_hypothesis_path
    assert result.m2_evaluation.counts.bit_errors == 0
    assert result.b5_evaluation.counts.bit_errors == 0
    assert result.m2_evaluation.counts.symbol_errors == 0
    assert result.b5_evaluation.counts.symbol_errors == 0
    assert result.m2_evaluation.counts.total_bits == 2 * count
    assert result.m2_evaluation.counts.total_symbols == count
    assert result.absolute_symbol_indices == tuple(range(5, 5 + count))
    assert result.estimator_time_indices == tuple(range(41, 41 + count))
    assert np.all(result.candidate_metrics >= 0.0)
    assert result.metric_equivalence_max_abs_error < 1e-10


@pytest.mark.parametrize("count", [1, 2, 4])
@pytest.mark.parametrize("gain", [0.75, 2.0])
def test_explicit_small_noise_keeps_one_shared_received_and_equivalent_paths(
    count: int, gain: float
) -> None:
    pattern = np.arange(8 * count, dtype=np.float64)
    noise = (pattern + 1j * pattern[::-1]) * (1e-4 + 2e-4j)
    original = noise.copy()
    result = _run(count=count, gain=gain, noise=noise, sigma_squared=0.01)

    assert np.array_equal(noise, original)
    assert result.received_shape == (8 * count,)
    assert len(result.received_sha256) == 64
    assert result.effective_discrete_gamma_b == pytest.approx(4 * gain**2 / 0.01)
    assert result.m2_observation.effective_symbol_noise_variance == pytest.approx(
        0.01 / (8 * gain**2)
    )
    assert result.metric_equivalence_max_abs_error < 1e-10
    assert all(result.candidate_minimizers_match)
    assert np.array_equal(result.m2_decoded_information_bits, result.b5_decoded_information_bits)
    assert result.m2_decoded_hypothesis_path == result.b5_decoded_hypothesis_path
    assert result.m2_evaluation.counts.total_bits == result.b5_evaluation.counts.total_bits


def test_seeded_awgn_is_deterministic_and_uses_explicit_component_scaling() -> None:
    sigma_squared = 0.04
    first = generate_independent_complex_awgn(
        sample_count=32,
        sigma_squared=sigma_squared,
        seed=712,
        stream_id="paired-control/noise",
    )
    second = generate_independent_complex_awgn(
        sample_count=32,
        sigma_squared=sigma_squared,
        seed=712,
        stream_id="paired-control/noise",
    )
    rng = np.random.Generator(np.random.PCG64(712))
    expected = np.sqrt(sigma_squared / 2.0) * (
        rng.standard_normal(32) + 1j * rng.standard_normal(32)
    )
    assert np.array_equal(first.noise, second.noise)
    assert np.array_equal(first.noise, expected)
    assert first.noise_stream_id == "paired-control/noise"
    assert first.bit_generator == "PCG64"
    assert first.component_variance == sigma_squared / 2.0
    with pytest.raises(ValueError):
        first.noise[0] = 0.0


def test_seeded_run_repeats_received_metrics_and_decodes() -> None:
    kwargs = {
        "count": 4,
        "gain": 2.0,
        "noise_seed": 99,
        "sigma_squared": 1e-5,
        "stream_id": "smoke-99/noise",
    }
    first = _run(run_id="repeat-a", **kwargs)
    second = _run(run_id="repeat-b", **kwargs)
    assert first.received_sha256 == second.received_sha256
    assert np.array_equal(first.candidate_metrics, second.candidate_metrics)
    assert np.array_equal(first.m2_observation.observations, second.m2_observation.observations)
    assert np.array_equal(first.m2_decoded_information_bits, second.m2_decoded_information_bits)
    assert np.array_equal(first.b5_decoded_information_bits, second.b5_decoded_information_bits)


def test_tie_case_reports_both_decoders_without_substituting_reference_symbols() -> None:
    count = 1
    reference = _reference_bits(count)
    reference_symbols = encode_reference_symbol_indices(
        reference,
        profile=ASSUMED_NATURAL_BINARY,
        bit_order=OUTPUT_BIT_ORDER,
    )
    # Cancel the test-side clean waveform so received=0 creates equal costs
    # for all 8PSK labels; this is not an AWGN sample or a gamma_b run.
    clean_symbol = constellation()[int(reference_symbols[0])] * 0.75
    noise = -np.full(8, clean_symbol, dtype=np.complex128)
    result = _run(count=count, gain=0.75, noise=noise)
    assert result.sigma_squared is None
    assert result.m2_decoded_hypothesis_path == result.b5_decoded_hypothesis_path
    assert np.allclose(result.m2_branch_metrics[0], result.m2_branch_metrics[0, 0])
    assert np.array_equal(
        result.m2_decoded_symbol_indices,
        result.b5_decoded_symbol_indices,
    )
    assert reference_symbols.shape == result.m2_decoded_symbol_indices.shape
    assert result.m2_decoded_symbol_indices.shape == (1,)
    assert result.m2_decoded_hypothesis_path == (0,)
    assert result.b5_decoded_hypothesis_path == (0,)
    assert result.m2_decode_result.final_state == (0, 0)


def test_receiver_call_has_no_reference_or_true_channel_argument(monkeypatch) -> None:
    import hf_tcm.evaluation.matched_m2_b5_experiment as experiment

    original = experiment.decode_reconstruction_conditional_sequence
    calls: list[dict[str, object]] = []

    def capture(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(experiment, "decode_reconstruction_conditional_sequence", capture)
    result = _run(count=2, gain=0.75, noise=np.zeros(16, dtype=np.complex128))
    assert len(calls) == 1
    forbidden = {"reference_information_bits", "true_channel_gain", "channel_truth", "true_phase"}
    assert forbidden.isdisjoint(calls[0])
    assert "received" in calls[0] and "initial_estimator_state" in calls[0]
    shared_received = np.asarray(calls[0]["received"]).reshape(2, 8)
    assert np.allclose(
        result.m2_observation.observations,
        np.mean(shared_received, axis=1) / 0.75,
        rtol=0.0,
        atol=1e-15,
    )


def test_experiment_module_does_not_import_channel_truth() -> None:
    module_path = Path(__file__).parents[1] / "src/hf_tcm/evaluation/matched_m2_b5_experiment.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
    assert "ChannelTruth" not in names
    assert all("channels.multipath" not in imported for imported in imports)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"noise": None, "noise_seed": None, "sigma_squared": 0.1},
        {"noise": None, "noise_seed": 1, "sigma_squared": None},
        {"noise": np.zeros(9, dtype=np.complex128), "noise_seed": None, "sigma_squared": 0.1},
        {"noise": np.zeros(8, dtype=np.complex128), "noise_seed": 1, "sigma_squared": 0.1},
        {"noise": np.full(8, complex(np.nan, 0.0)), "noise_seed": None, "sigma_squared": 0.1},
    ],
)
def test_invalid_run_noise_inputs_are_rejected(kwargs) -> None:
    with pytest.raises(ValueError):
        _run(count=1, **kwargs)
