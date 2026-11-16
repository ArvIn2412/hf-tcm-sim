from __future__ import annotations

import ast
import inspect

import numpy as np
import pytest

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.posterior import ALLOWED_HYPOTHESIS_TRANSITIONS
from hf_tcm.evaluation import reconstruction_smoke_experiment as smoke
from hf_tcm.evaluation.error_metrics import (
    calculate_ber_ser,
    count_bit_errors,
    count_symbol_errors,
)
from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION
from hf_tcm.modulation.psk8 import modulate
from hf_tcm.receiver.reconstruction_forward import APPROXIMATE_RECTANGULAR_8SPS
from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER


def _configuration(
    *,
    coefficient: float,
    symbol_origin: int,
    initial_time: int,
    beta: float = 0.7,
) -> dict[str, object]:
    transition_support = ALLOWED_HYPOTHESIS_TRANSITIONS.astype(np.float64)
    transition_probabilities = transition_support / transition_support.sum(axis=1, keepdims=True)
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
            "origin": "explicit ADR-002 control setting",
            "bit_order": list(OUTPUT_BIT_ORDER),
            "output_to_b": list(range(8)),
            "phase_offset_rad": 0.0,
        },
        "transition_model": {
            "name": "adr003_uniform_allowed_edges",
            "probabilities": transition_probabilities.tolist(),
        },
        "initial": {
            "state": [0, 0],
            "prior": [0.25 if h.current_state == (0, 0) else 0.0 for h in HYPOTHESES],
        },
        "likelihood": {
            "kind": "exp_negative_beta_project_reconstruction_metric",
            "beta": beta,
        },
        "estimator": {
            "alpha_prime": 1.0,
            "k_tilde": [[0.0, 0.0]],
            "mu0": [[0.0, 0.0]],
            "initial_time_index": initial_time,
            "time_rule": "one_recursion_step_i_to_i_plus_1",
            "initial_estimates": {
                "fluctuating_iq": [[coefficient, coefficient]],
                "full_iq": [[coefficient, coefficient]],
            },
        },
        "timebase": {
            "name": APPROXIMATE_RECTANGULAR_8SPS,
            "samples_per_symbol": 8,
            "sample_rate_hz": 8000.0,
            "symbol_rate_hz": 1000.0,
            "symbol_origin_sample": symbol_origin,
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
            name: {
                "status": "accepted_project_setting",
                "source": "explicit M5b smoke fixture",
                "note": "run-level value supplied; not inferred from article",
            }
            for name in provenance_fields
        },
    }


def _run(
    *,
    run_id: str = "smoke-1",
    length: int = 4,
    coefficient: float = 0.75,
    mode: str = "monolithic",
    partition: tuple[int, ...] | None = None,
    perturbation: np.ndarray | None = None,
    sequence_variant: int = 0,
) -> smoke.ReconstructionSmokeExperimentResult:
    reference_bits = np.asarray(
        [
            ((3 * index + index // 2 + 1 + sequence_variant * (index + 1)) % 2)
            for index in range(2 * length)
        ],
        dtype=np.int8,
    )
    symbol_origin = 23
    first_symbol = 5
    initial_time = 41
    if perturbation is None:
        perturbation = np.zeros(8 * length, dtype=np.complex128)
    return smoke.run_reconstruction_smoke_experiment(
        run_id=run_id,
        symbol_count=length,
        reference_information_bits=reference_bits,
        real_channel_gain=coefficient,
        perturbation=perturbation,
        perturbation_provenance="explicit deterministic complex array; no noise law claimed",
        symbol_origin_sample=symbol_origin,
        first_symbol_index=first_symbol,
        initial_estimator_time_index=initial_time,
        configuration=_configuration(
            coefficient=coefficient,
            symbol_origin=symbol_origin,
            initial_time=initial_time,
        ),
        receiver_mode=mode,
        segment_partition=partition,
        initial_csi_provenance="oracle-initialized control experiment",
    )


@pytest.mark.parametrize("coefficient", [0.75, 2.0])
@pytest.mark.parametrize("length", [1, 2, 4, 6])
def test_noiseless_real_channel_control_recovers_information_and_symbols(
    coefficient: float, length: int
) -> None:
    result = _run(length=length, coefficient=coefficient)

    assert result.experiment_name == smoke.EXPERIMENT_NAME
    assert result.receiver_mode == "monolithic"
    assert result.run_id == "smoke-1"
    assert result.initial_csi_provenance == "oracle-initialized control experiment"
    assert result.evaluation.counts.bit_errors == 0
    assert result.evaluation.counts.total_bits == 2 * length
    assert result.evaluation.counts.symbol_errors == 0
    assert result.evaluation.counts.total_symbols == length
    assert result.evaluation.ber == 0.0
    assert result.evaluation.ser == 0.0
    assert result.receiver_result.best_conditional_path_cost == 0.0
    assert result.decoded_path_valid
    assert result.absolute_symbol_indices == tuple(range(5, 5 + length))
    assert result.estimator_time_indices == tuple(range(41, 41 + length))
    assert result.absolute_sample_indices == tuple(range(63, 63 + 8 * length))
    assert result.prediction_cutoff_sample_indices == tuple(63 + 8 * i - 1 for i in range(length))
    assert result.observation_cutoff_sample_indices == tuple(63 + 8 * i + 7 for i in range(length))


def test_received_generator_matches_independent_m1_modulator_and_zoh() -> None:
    result = _run(length=2, coefficient=0.75)
    labels = [tuple(map(int, f"{index:03b}")) for index in result.reference_symbol_indices]
    clean_symbols = modulate(labels, profile=BASELINE_ASSUMPTION)
    independent_received = np.repeat(0.75 * clean_symbols, 8)

    np.testing.assert_array_equal(result.clean_received, independent_received)
    np.testing.assert_array_equal(result.received, independent_received)


def test_multiple_explicit_information_sequences_are_decoded_separately() -> None:
    first = _run(length=4, coefficient=0.75, sequence_variant=0)
    second = _run(length=4, coefficient=0.75, sequence_variant=1)

    assert not np.array_equal(first.reference_information_bits, second.reference_information_bits)
    np.testing.assert_array_equal(first.decoded_information_bits, first.reference_information_bits)
    np.testing.assert_array_equal(
        second.decoded_information_bits, second.reference_information_bits
    )


@pytest.mark.parametrize("position", [0, 5, 15])
def test_explicit_deterministic_complex_perturbations_are_evaluated(position: int) -> None:
    perturbation = np.zeros(16, dtype=np.complex128)
    perturbation[position] = 0.035 + 0.012j
    result = _run(length=2, perturbation=perturbation)

    assert result.received.shape == (16,)
    np.testing.assert_array_equal(result.received, result.clean_received + perturbation)
    assert result.perturbation_provenance.startswith("explicit deterministic")
    assert result.evaluation.counts.bit_errors == count_bit_errors(
        result.reference_information_bits, result.decoded_information_bits
    )
    assert result.evaluation.counts.symbol_errors == count_symbol_errors(
        result.reference_symbol_indices, result.decoded_symbol_indices
    )
    assert (
        result.evaluation.ber
        == result.evaluation.counts.bit_errors / result.evaluation.counts.total_bits
    )
    assert (
        result.evaluation.ser
        == result.evaluation.counts.symbol_errors / result.evaluation.counts.total_symbols
    )


def test_monolithic_and_segmented_smoke_runs_are_identical() -> None:
    monolithic = _run(length=6, coefficient=2.0)
    segmented = _run(length=6, coefficient=2.0, mode="segmented", partition=(1, 2, 3))

    np.testing.assert_array_equal(
        monolithic.decoded_information_bits, segmented.decoded_information_bits
    )
    assert monolithic.decoded_hypothesis_path == segmented.decoded_hypothesis_path
    np.testing.assert_array_equal(monolithic.candidate_metrics, segmented.candidate_metrics)
    np.testing.assert_array_equal(monolithic.final_posterior, segmented.final_posterior)
    np.testing.assert_array_equal(
        monolithic.final_estimator_state.full_iq, segmented.final_estimator_state.full_iq
    )
    np.testing.assert_array_equal(
        monolithic.final_estimator_state.fluctuating_iq,
        segmented.final_estimator_state.fluctuating_iq,
    )
    assert monolithic.evaluation == segmented.evaluation
    assert monolithic.evaluation.ber == segmented.evaluation.ber
    assert monolithic.evaluation.ser == segmented.evaluation.ser
    np.testing.assert_array_equal(monolithic.received, segmented.received)
    assert monolithic.final_estimator_state.time_index == segmented.final_estimator_state.time_index


def test_zero_perturbation_matches_clean_control_and_repeat_is_deterministic() -> None:
    first = _run(run_id="repeat-a", length=4, coefficient=0.75)
    second = _run(run_id="repeat-b", length=4, coefficient=0.75)

    np.testing.assert_array_equal(first.received, second.received)
    np.testing.assert_array_equal(first.candidate_metrics, second.candidate_metrics)
    np.testing.assert_array_equal(first.decoded_information_bits, second.decoded_information_bits)
    assert first.evaluation == second.evaluation


def test_small_run_aggregation_pools_counts_and_retains_each_run() -> None:
    short = _run(
        run_id="perturbed-length-2",
        length=2,
        coefficient=0.75,
        perturbation=np.full(16, 10.0 + 10.0j, dtype=np.complex128),
    )
    long = _run(run_id="clean-length-6", length=6, coefficient=2.0)
    aggregate = smoke.aggregate_reconstruction_smoke_runs((short, long))
    expected = calculate_ber_ser(aggregate.error_counts)

    assert (short.bit_errors, short.total_bits, short.symbol_errors, short.total_symbols) == (
        3,
        4,
        2,
        2,
    )
    assert (long.bit_errors, long.total_bits, long.symbol_errors, long.total_symbols) == (
        0,
        12,
        0,
        6,
    )
    assert aggregate.run_ids == ("perturbed-length-2", "clean-length-6")
    assert aggregate.error_counts.total_bits == 16
    assert aggregate.error_counts.total_symbols == 8
    assert len(aggregate.run_records) == 2
    assert aggregate.ber == expected.ber
    assert aggregate.ser == expected.ser
    assert aggregate.ber == pytest.approx(3 / 16)
    assert aggregate.ser == pytest.approx(2 / 8)
    assert aggregate.ber != pytest.approx((short.evaluation.ber + long.evaluation.ber) / 2)
    assert aggregate.ser != pytest.approx((short.evaluation.ser + long.evaluation.ser) / 2)
    assert aggregate.statistical_claim_status == "smoke_only_not_monte_carlo"


def test_config_time_alignment_and_segment_partition_are_explicit() -> None:
    with pytest.raises(ValueError, match="symbol_origin_sample"):
        smoke.run_reconstruction_smoke_experiment(
            run_id="bad-origin",
            symbol_count=1,
            reference_information_bits=[0, 1],
            real_channel_gain=0.75,
            perturbation=np.zeros(8, dtype=np.complex128),
            perturbation_provenance="explicit zero",
            symbol_origin_sample=24,
            first_symbol_index=5,
            initial_estimator_time_index=41,
            configuration=_configuration(coefficient=0.75, symbol_origin=23, initial_time=41),
            receiver_mode="monolithic",
            segment_partition=None,
            initial_csi_provenance="oracle-initialized control experiment",
        )
    with pytest.raises(ValueError, match="partition"):
        _run(length=4, mode="segmented", partition=(2, 1))
    with pytest.raises(ValueError, match="partition"):
        _run(length=4, mode="monolithic", partition=(4,))
    with pytest.raises(ValueError, match="initial_estimator_time_index"):
        smoke.run_reconstruction_smoke_experiment(
            run_id="bad-time",
            symbol_count=1,
            reference_information_bits=[0, 1],
            real_channel_gain=0.75,
            perturbation=np.zeros(8, dtype=np.complex128),
            perturbation_provenance="explicit zero",
            symbol_origin_sample=23,
            first_symbol_index=5,
            initial_estimator_time_index=42,
            configuration=_configuration(coefficient=0.75, symbol_origin=23, initial_time=41),
            receiver_mode="monolithic",
            segment_partition=None,
            initial_csi_provenance="oracle-initialized control experiment",
        )
    altered_phase = _configuration(coefficient=0.75, symbol_origin=23, initial_time=41)
    altered_phase["labeling"]["phase_offset_rad"] = 0.25  # type: ignore[index]
    with pytest.raises(ValueError, match="phase_offset_rad"):
        smoke.run_reconstruction_smoke_experiment(
            run_id="bad-phase",
            symbol_count=1,
            reference_information_bits=[0, 1],
            real_channel_gain=0.75,
            perturbation=np.zeros(8, dtype=np.complex128),
            perturbation_provenance="explicit zero",
            symbol_origin_sample=23,
            first_symbol_index=5,
            initial_estimator_time_index=41,
            configuration=altered_phase,
            receiver_mode="monolithic",
            segment_partition=None,
            initial_csi_provenance="oracle-initialized control experiment",
        )


def test_invalid_run_values_are_rejected_before_receiver_call() -> None:
    with pytest.raises(ValueError, match="2F"):
        smoke.run_reconstruction_smoke_experiment(
            run_id="bad-bit-count",
            symbol_count=2,
            reference_information_bits=[0, 1],
            real_channel_gain=0.75,
            perturbation=np.zeros(16, dtype=np.complex128),
            perturbation_provenance="explicit zero",
            symbol_origin_sample=23,
            first_symbol_index=5,
            initial_estimator_time_index=41,
            configuration=_configuration(coefficient=0.75, symbol_origin=23, initial_time=41),
            receiver_mode="monolithic",
            segment_partition=None,
            initial_csi_provenance="oracle-initialized control experiment",
        )
    with pytest.raises(ValueError, match="2F"):
        smoke.run_reconstruction_smoke_experiment(
            run_id="out-of-range-bit",
            symbol_count=1,
            reference_information_bits=[256, 1],
            real_channel_gain=0.75,
            perturbation=np.zeros(8, dtype=np.complex128),
            perturbation_provenance="explicit zero",
            symbol_origin_sample=23,
            first_symbol_index=5,
            initial_estimator_time_index=41,
            configuration=_configuration(coefficient=0.75, symbol_origin=23, initial_time=41),
            receiver_mode="monolithic",
            segment_partition=None,
            initial_csi_provenance="oracle-initialized control experiment",
        )
    with pytest.raises(ValueError, match="finite"):
        _run(perturbation=np.full(32, complex(np.inf, 0), dtype=np.complex128))
    with pytest.raises(ValueError, match="shape"):
        _run(perturbation=np.zeros(31, dtype=np.complex128))
    with pytest.raises(ValueError, match="2F"):
        smoke.run_reconstruction_smoke_experiment(
            run_id="fractional-bit",
            symbol_count=1,
            reference_information_bits=[0.0, 0.5],
            real_channel_gain=0.75,
            perturbation=np.zeros(8, dtype=np.complex128),
            perturbation_provenance="explicit zero",
            symbol_origin_sample=23,
            first_symbol_index=5,
            initial_estimator_time_index=41,
            configuration=_configuration(coefficient=0.75, symbol_origin=23, initial_time=41),
            receiver_mode="monolithic",
            segment_partition=None,
            initial_csi_provenance="oracle-initialized control experiment",
        )


@pytest.mark.parametrize("mode", ["monolithic", "segmented"])
def test_reference_bits_never_cross_into_receiver_api(monkeypatch, mode: str) -> None:
    captured: dict[str, object] = {}
    is_segmented = mode == "segmented"
    target_name = (
        "decode_reconstruction_segmented_sequence"
        if is_segmented
        else "decode_reconstruction_conditional_sequence"
    )
    original = getattr(smoke, target_name)

    def capture(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(smoke, target_name, capture)
    result = _run(
        length=2,
        mode=mode,
        partition=(1, 1) if is_segmented else None,
    )

    assert "reference_information_bits" not in captured
    assert "reference_symbol_indices" not in captured
    assert captured["received"] is not result.reference_information_bits


def test_reference_perturbation_and_received_inputs_are_immutable() -> None:
    reference = np.asarray([0, 1, 1, 0], dtype=np.int8)
    perturbation = np.zeros(16, dtype=np.complex128)
    reference_before = reference.copy()
    perturbation_before = perturbation.copy()
    result = smoke.run_reconstruction_smoke_experiment(
        run_id="immutable-inputs",
        symbol_count=2,
        reference_information_bits=reference,
        real_channel_gain=0.75,
        perturbation=perturbation,
        perturbation_provenance="explicit zero array",
        symbol_origin_sample=23,
        first_symbol_index=5,
        initial_estimator_time_index=41,
        configuration=_configuration(coefficient=0.75, symbol_origin=23, initial_time=41),
        receiver_mode="monolithic",
        segment_partition=None,
        initial_csi_provenance="oracle-initialized control experiment",
    )
    np.testing.assert_array_equal(reference, reference_before)
    np.testing.assert_array_equal(perturbation, perturbation_before)
    with pytest.raises(ValueError):
        result.received[0] = 1.0 + 2.0j
    with pytest.raises(ValueError):
        result.reference_information_bits[0] = 1
    with pytest.raises(ValueError):
        result.candidate_metrics[0, 0] = 1.0


def test_smoke_harness_has_no_truth_dependency_and_decoded_path_is_valid() -> None:
    source = inspect.getsource(smoke)
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "ChannelTruth" not in names | attributes
    assert "truth" not in {name.lower() for name in names | attributes}
    assert _run(length=4).decoded_path_valid
