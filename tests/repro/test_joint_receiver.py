"""Independent contracts for the REPRO-05 joint receiver."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hf_tcm.repro.channel_config import (
    identity_profile,
    multipath_rician_awgn_profile,
    single_path_rician_awgn_profile,
)
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.encoder import transition_table
from hf_tcm.repro.euclidean_metric import euclidean_metric_rows
from hf_tcm.repro.joint_estimator import update_complex_estimate
from hf_tcm.repro.joint_evaluation import compare_joint_and_separate, evaluate_joint_receiver
from hf_tcm.repro.joint_plot_adapter import (
    write_dual_receiver_comparison_plot,
    write_joint_receiver_plots,
)
from hf_tcm.repro.joint_posterior import posterior_weights
from hf_tcm.repro.joint_receiver import run_joint_receiver
from hf_tcm.repro.joint_receiver_config import JointReceiverConfig
from hf_tcm.repro.joint_receiver_io import save_joint_receiver_result
from hf_tcm.repro.joint_viterbi import decode_joint_viterbi
from hf_tcm.repro.separate_receiver import run_separate_receiver
from hf_tcm.repro.transmitter import run_transmitter


def _tx(bits: str, *, phase_offset: float = 0.0):
    symbols = len(bits) // 2
    return run_transmitter(
        TransmitterConfig(
            source_mode="manual",
            frame_symbols=symbols,
            manual_bits=bits,
            phase_offset_rad=phase_offset,
        )
    )


def _config(count: int, **kwargs):
    return JointReceiverConfig(expected_symbol_count=count, **kwargs)


def test_euclidean_profiles_match_independent_complex_scalar_calculation():
    observed = np.asarray([[1 + 2j, -1 + 0.5j]], dtype=np.complex128)
    predicted = np.asarray([[[0 + 1j, -2 + 0.5j], [2 + 2j, 0 + 0j]]], dtype=np.complex128)
    # Independent hand calculation: residual energy is (1+1)+1=3 and 1+1.25=2.25.
    squared = euclidean_metric_rows(observed, predicted, profile="squared_euclidean")
    distance = euclidean_metric_rows(observed, predicted, profile="euclidean")
    np.testing.assert_allclose(squared, [[3.0, 2.25]])
    np.testing.assert_allclose(distance, np.sqrt([[3.0, 2.25]]))


def test_posterior_is_stable_normalized_and_canonical():
    weights = posterior_weights(np.asarray([0.0, 1.0, 1e6] + [1e5] * 13), beta=1e4)
    assert weights.shape == (16,)
    assert np.all(np.isfinite(weights))
    assert np.all(weights >= 0)
    assert weights.sum() == pytest.approx(1.0)
    assert weights[0] > 0.999


def test_estimator_update_uses_hand_computed_posterior_weighted_innovation():
    # weights * residuals = .25*(2+j) + .75*(-2+3j) = -1 + 2.5j
    post, innovation = update_complex_estimate(
        state_pre=1 + 0.5j,
        residuals=np.asarray([[2 + 1j], [-2 + 3j]], dtype=np.complex128),
        weights=np.asarray([0.25, 0.75]),
        alpha_prime=0.5,
        k_tilde=0.2,
        mu0=0.25 - 0.5j,
    )
    assert innovation == pytest.approx(-1 + 2.5j)
    assert post == pytest.approx(0.5 * (1 + 0.5j) + 0.2 * (-1 + 2.5j))


def test_identity_channel_joint_receiver_decodes_without_hard_demod_stage():
    tx = _tx("001101100011")
    observation = run_channel(tx, identity_profile()).receiver_observation
    result = run_joint_receiver(observation, _config(6))
    np.testing.assert_array_equal(result.decoded_information_bits, tx.information_bits)
    assert result.metric_rows.shape == (6, 16)
    assert result.candidate_predictions.shape == (6, 16, 8)
    assert result.candidate_edge_ids.tolist() == list(range(16))
    assert result.candidate_phase_indices.tolist() == [
        4 * row[3][0] + 2 * row[3][1] + row[3][2] for row in transition_table()
    ]
    assert result.candidate_estimator_state_used.shape == (6, 16)
    assert result.sample_indices.shape == (6 * 8,)
    assert result.sample_ranges.tolist() == [[8 * k, 8 * k + 7] for k in range(6)]
    assert result.posterior_weights.shape == (6, 16)
    assert result.decoded_edge_ids.shape == (6,)
    assert result.traceback_mode == "full_frame"
    assert result.decoder_depth is None
    assert result.observation_sha256 == observation.sha256
    assert result.diagnostics["hard_demodulation_used"] is False


def test_joint_receiver_config_round_trips_explicit_finite_depth_settings():
    config = JointReceiverConfig(
        expected_symbol_count=32,
        decoder_mode="finite_depth",
        traceback_depth=20,
        final_state_policy="free",
        trace_output_mode="compact",
    )
    restored = JointReceiverConfig.from_dict(config.to_dict())
    assert restored.decoder_mode == "finite_depth"
    assert restored.traceback_depth == 20
    assert restored.final_state_policy == "free"
    assert restored.trace_output_mode == "compact"


def test_article_oriented_joint_config_selects_eta_twenty():
    config = JointReceiverConfig.article_oriented(expected_symbol_count=32)
    assert config.decoder_mode == "finite_depth"
    assert config.traceback_depth == 20
    assert config.trace_output_mode == "compact"


def test_finite_depth_joint_identity_keeps_metric_and_estimator_traces_causal():
    tx = _tx("001101" * 12)
    observation = run_channel(tx, identity_profile()).receiver_observation
    finite_config = JointReceiverConfig.article_oriented(
        expected_symbol_count=len(tx.phase_indices), estimator_policy="frozen"
    )
    finite = run_joint_receiver(observation, finite_config)
    full = run_joint_receiver(
        observation,
        JointReceiverConfig(expected_symbol_count=len(tx.phase_indices), estimator_policy="frozen"),
    )
    np.testing.assert_array_equal(finite.metric_rows, full.metric_rows)
    np.testing.assert_array_equal(finite.posterior_weights, full.posterior_weights)
    np.testing.assert_array_equal(finite.decoded_information_bits, tx.information_bits)
    assert finite.observation_sha256 == full.observation_sha256 == observation.sha256
    assert finite.diagnostics["decision_records"][0]["decision_available_at"] == 19
    assert finite.diagnostics["survivor_buffer_max_rows"] <= 20


def test_compact_finite_joint_trace_keeps_plots_explicitly_unavailable(tmp_path):
    tx = _tx("001101" * 4)
    observation = run_channel(tx, identity_profile()).receiver_observation
    config = JointReceiverConfig(
        expected_symbol_count=len(tx.phase_indices),
        decoder_mode="finite_depth",
        traceback_depth=3,
        trace_output_mode="compact",
        estimator_policy="frozen",
    )
    result = run_joint_receiver(observation, config)
    assert result.viterbi_state_metrics.shape == (0, 4)
    plots = write_joint_receiver_plots(observation, result, tmp_path)
    metric_plot = next(path for path in plots if path.name == "viterbi_path_metric.svg")
    assert "trace_output_mode=compact" in metric_plot.read_text(encoding="utf-8")


def test_finite_joint_runs_receiver_known_static_and_single_path_rician() -> None:
    from dataclasses import replace

    tx = _tx("001101" * 8)
    gain = 0.6 - 0.8j
    identity = identity_profile()
    static_channel = replace(
        identity,
        paths=(replace(identity.paths[0], constant_coefficient=gain),),
    )
    static_observation = run_channel(tx, static_channel).receiver_observation
    static_result = run_joint_receiver(
        static_observation,
        JointReceiverConfig(
            expected_symbol_count=len(tx.phase_indices),
            decoder_mode="finite_depth",
            traceback_depth=5,
            termination_policy="none",
            channel_mode="known_static_complex_gain",
            known_static_gain=gain,
            estimator_policy="frozen",
        ),
    )
    assert np.all(np.isfinite(static_result.metric_rows))

    rician_observation = run_channel(tx, single_path_rician_awgn_profile()).receiver_observation
    finite_config = JointReceiverConfig(
        expected_symbol_count=len(tx.phase_indices),
        decoder_mode="finite_depth",
        traceback_depth=5,
        termination_policy="none",
        estimator_policy="adaptive_project_v1",
        alpha_prime=0.98,
        k_tilde=0.05,
    )
    first = run_joint_receiver(rician_observation, finite_config)
    second = run_joint_receiver(rician_observation, finite_config)
    assert first.result_sha256 == second.result_sha256
    assert np.all(np.isfinite(first.metric_rows))
    assert np.all(np.isfinite(first.estimator_post))


def test_finite_joint_flush_honors_public_zero_tail_and_payload_contract():
    tx = run_transmitter(
        TransmitterConfig(
            source_mode="manual",
            frame_symbols=36,
            manual_bits="001101" * 12,
            termination_policy="zero_tail_2",
        )
    )
    observation = run_channel(tx, identity_profile()).receiver_observation
    config = JointReceiverConfig.article_oriented(
        expected_symbol_count=len(tx.phase_indices),
        termination_policy="zero_tail_2",
        estimator_policy="frozen",
    )
    result = run_joint_receiver(observation, config)
    np.testing.assert_array_equal(result.decoded_information_bits, tx.information_bits)
    assert result.decoded_frame_information_bits[-4:].tolist() == [0, 0, 0, 0]
    assert result.final_state == (0, 0)


def test_both_finite_receivers_consume_the_same_identity_observation():
    from hf_tcm.repro.receiver_config import SeparateReceiverConfig

    tx = _tx("001101" * 12)
    observation = run_channel(tx, identity_profile()).receiver_observation
    joint = run_joint_receiver(
        observation,
        JointReceiverConfig.article_oriented(
            expected_symbol_count=len(tx.phase_indices), estimator_policy="frozen"
        ),
    )
    separate = run_separate_receiver(
        observation,
        SeparateReceiverConfig.article_oriented(
            expected_symbol_count=len(tx.phase_indices), termination_policy="none"
        ),
    )
    assert joint.observation_sha256 == separate.observation_sha256 == observation.sha256
    np.testing.assert_array_equal(joint.decoded_information_bits, tx.information_bits)
    np.testing.assert_array_equal(separate.decoded_information_bits, tx.information_bits)


def test_all_sixteen_candidates_follow_independent_encoder_and_phase_oracle():
    tx = _tx("0000")
    observation = run_channel(tx, identity_profile()).receiver_observation
    result = run_joint_receiver(observation, _config(2))
    vector_path = (
        Path(__file__).resolve().parents[2] / "docs/repro/REPRO_01_ENCODER_TEST_VECTORS.json"
    )
    oracle = json.loads(vector_path.read_text(encoding="utf-8"))
    assert oracle["oracle_method"].startswith("direct substitution into GF(2)")
    expected = []
    for expected_edge, vector in enumerate(oracle["transitions"]):
        coded = vector["output"]
        phase = 4 * coded[0] + 2 * coded[1] + coded[2]
        expected.append(np.exp(1j * phase * np.pi / 4.0))
        assert expected_edge == len(expected) - 1
    np.testing.assert_allclose(result.candidate_predictions[0, :, 0], expected, atol=1e-14)
    np.testing.assert_allclose(
        result.candidate_predictions[0], np.repeat(np.asarray(expected)[:, None], 8, axis=1)
    )


def test_causal_estimator_metrics_use_pre_update_state():
    tx = _tx("00000000")
    observation = run_channel(tx, identity_profile()).receiver_observation
    config = _config(
        4,
        estimator_policy="adaptive_project_v1",
        initial_state_value=0.2 + 0.1j,
        mu0=0.1 - 0.05j,
        alpha_prime=0.8,
        k_tilde=0.15,
        beta=2.0,
    )
    result = run_joint_receiver(observation, config)
    first_pre = config.mu0 + config.initial_state_value
    np.testing.assert_allclose(result.estimator_pre[0], first_pre)
    np.testing.assert_allclose(
        result.candidate_predictions[0, 0], first_pre * np.exp(0j) * np.ones(8)
    )
    assert result.estimator_post[0] == pytest.approx(result.estimator_pre[1])
    assert not np.array_equal(result.estimator_pre, result.estimator_post)


def test_multipath_profile_is_rejected_instead_of_using_symbol_local_predictor():
    tx = _tx("0011")
    observation = run_channel(tx, multipath_rician_awgn_profile()).receiver_observation
    with pytest.raises(ValueError, match="multipath.*unsupported|MULTIPATH_JOINT_RECEIVER_PARTIAL"):
        run_joint_receiver(observation, _config(2))


def test_single_path_rician_is_finite_reproducible_and_shape_safe():
    tx = _tx("00110110" * 8)
    channel = run_channel(tx, single_path_rician_awgn_profile())
    adaptive = _config(
        len(tx.phase_indices),
        estimator_policy="adaptive_project_v1",
        alpha_prime=0.98,
        k_tilde=0.05,
        beta=0.5,
    )
    first = run_joint_receiver(channel.receiver_observation, adaptive)
    second = run_joint_receiver(channel.receiver_observation, adaptive)
    assert np.all(np.isfinite(first.metric_rows))
    assert np.all(np.isfinite(first.estimator_post))
    assert first.result_sha256 == second.result_sha256


def test_f256_frame_completes_with_bounded_candidate_array_shape():
    tx = run_transmitter(
        TransmitterConfig(source_mode="pattern", frame_symbols=256, pattern_id="alternating")
    )
    observation = run_channel(tx, identity_profile()).receiver_observation
    result = run_joint_receiver(observation, _config(256))
    assert result.candidate_predictions.shape == (256, 16, 8)
    assert result.metric_rows.shape == (256, 16)
    assert result.reproducibility_metadata["array_storage_bytes"] < 2_000_000


def test_receiver_rejects_channel_result_so_evaluation_truth_cannot_leak():
    tx = _tx("0011")
    channel = run_channel(tx, identity_profile())
    with pytest.raises(TypeError, match="ReceiverObservation"):
        run_joint_receiver(channel, _config(2))  # type: ignore[arg-type]


def test_same_observation_is_consumed_by_both_receivers():
    tx = _tx("001101100011")
    observation = run_channel(tx, identity_profile()).receiver_observation
    joint = run_joint_receiver(observation, _config(6))
    separate = run_separate_receiver(observation, _separate_config(6))
    assert joint.observation_sha256 == separate.observation_sha256 == observation.sha256
    np.testing.assert_array_equal(joint.decoded_information_bits, separate.decoded_information_bits)
    comparison = compare_joint_and_separate(joint, separate, tx.information_bits, tx.phase_indices)
    assert comparison.joint_bit_errors == comparison.separate_bit_errors == 0
    assert comparison.joint_ber == comparison.separate_ber == 0.0


def _separate_config(count: int):
    from hf_tcm.repro.receiver_config import SeparateReceiverConfig

    return SeparateReceiverConfig(expected_symbol_count=count)


def test_validation_rejects_nonfinite_metrics_and_unsupported_profiles():
    with pytest.raises(ValueError):
        euclidean_metric_rows(
            np.asarray([[complex(np.nan, 0)]], dtype=np.complex128),
            np.asarray([[[0j]]], dtype=np.complex128),
            profile="squared_euclidean",
        )
    with pytest.raises(ValueError, match="metric_profile"):
        JointReceiverConfig(expected_symbol_count=1, metric_profile="hamming")


def test_float_viterbi_matches_independent_selected_path_and_canonical_tie():
    edges = transition_table()
    expected_edges = []
    rows = np.full((len(expected_edges), 16), 3.0)
    state = (0, 0)
    for _ in range(4):
        edge_id = next(row[0] for row in edges if row[1] == state and row[2] == (1, 0))
        expected_edges.append(edge_id)
        state = edges[edge_id][4]
    rows = np.full((len(expected_edges), 16), 3.0)
    for time_index, edge_id in enumerate(expected_edges):
        rows[time_index, edge_id] = 0.0
    decoded = decode_joint_viterbi(rows, initial_state=(0, 0))
    assert decoded.decoded_edge_ids.tolist() == expected_edges
    assert decoded.final_metric == 0.0
    tied = decode_joint_viterbi(np.zeros((3, 16)), initial_state=(0, 0))
    assert tied.decoded_edge_ids.tolist() == [0, 0, 0]


def test_joint_receiver_honors_nonzero_initial_tcm_state():
    tx = run_transmitter(
        TransmitterConfig(
            source_mode="manual",
            frame_symbols=4,
            manual_bits="01100110",
            initial_state=(1, 0),
        )
    )
    observation = run_channel(tx, identity_profile()).receiver_observation
    result = run_joint_receiver(observation, _config(4, initial_state=(1, 0)))
    np.testing.assert_array_equal(result.decoded_information_bits, tx.information_bits)


def test_static_public_complex_gain_and_symbol_timing_offset():
    tx = _tx("00110110")
    gain = 0.6 - 0.8j
    channel = run_channel(tx, identity_profile())
    obs = channel.receiver_observation
    from dataclasses import replace

    shifted = replace(obs, received_samples=np.concatenate(([0j], gain * obs.received_samples)))
    # Recreate valid timing metadata for the declared one-sample offset.
    indices = np.arange(len(shifted.received_samples), dtype=np.int64)
    shifted = replace(
        shifted,
        absolute_sample_index=indices,
        sample_symbol_index=indices // 8,
        sample_local_index=indices % 8,
    )
    config = _config(
        4,
        timing_offset_samples=1,
        channel_mode="known_static_complex_gain",
        known_static_gain=gain,
    )
    result = run_joint_receiver(shifted, config)
    np.testing.assert_array_equal(result.decoded_information_bits, tx.information_bits)
    assert result.sample_ranges[0].tolist() == [1, 7]


def test_extra_observation_tail_is_explicitly_unprocessed_not_a_new_symbol():
    from dataclasses import replace

    tx = _tx("001101100011")
    observation = run_channel(tx, identity_profile()).receiver_observation
    received = np.concatenate((observation.received_samples, np.zeros(3, dtype=np.complex128)))
    indexes = np.arange(len(received), dtype=np.int64)
    tailed = replace(
        observation,
        received_samples=received,
        absolute_sample_index=indexes,
        sample_symbol_index=indexes // 8,
        sample_local_index=indexes % 8,
    )
    result = run_joint_receiver(tailed, _config(6))
    assert result.candidate_predictions.shape == (6, 16, 8)
    assert result.unprocessed_sample_indices.tolist() == [48, 49, 50]
    assert result.diagnostics["unprocessed_sample_count"] == 3


def test_zero_tail_and_evaluation_are_kept_outside_receiver_decision():
    tx = _tx("001101011110")
    # The configured two-symbol zero tail is encoded explicitly in the source.
    from hf_tcm.repro.config import TransmitterConfig
    from hf_tcm.repro.transmitter import run_transmitter

    terminated = run_transmitter(
        TransmitterConfig(
            source_mode="manual",
            frame_symbols=6,
            manual_bits="001101011110",
            termination_policy="zero_tail_2",
        )
    )
    obs = run_channel(terminated, identity_profile()).receiver_observation
    result = run_joint_receiver(obs, _config(8, termination_policy="zero_tail_2"))
    evaluation = evaluate_joint_receiver(
        result,
        terminated.information_bits,
        terminated.phase_indices[:-2],
    )
    assert evaluation.bit_errors == evaluation.symbol_errors == 0
    assert evaluation.evidence_scope == "single_frame_descriptive_only_not_statistical_evidence"
    assert len(result.decoded_information_bits) == len(terminated.information_bits)
    assert len(tx.information_bits) == 12


def test_joint_result_serializes_with_hashes_and_actual_data_plots(tmp_path):
    tx = _tx("001101100011")
    observation = run_channel(tx, identity_profile()).receiver_observation
    result = run_joint_receiver(observation, _config(6))
    manifest = save_joint_receiver_result(result, tmp_path / "bundle")
    with np.load(tmp_path / "bundle" / "joint_receiver_result.npz", allow_pickle=False) as archive:
        assert archive["decision_symbol_index"].tolist() == list(range(len(tx.phase_indices)))
    assert manifest["observation_sha256"] == observation.sha256
    plots = write_joint_receiver_plots(observation, result, tmp_path / "plots")
    assert len(plots) >= 7
    assert all(path.stat().st_size > 100 for path in plots)
    with np.load(tmp_path / "bundle" / "joint_receiver_result.npz", allow_pickle=False) as archive:
        assert archive["candidate_predictions"].shape == (6, 16, 8)
        assert archive["decoded_information_bits"].tolist() == tx.information_bits.tolist()
    separate = run_separate_receiver(observation, _separate_config(6))
    comparison_path = write_dual_receiver_comparison_plot(
        result, separate, tmp_path / "plots" / "joint_separate.svg"
    )
    assert "Joint Euclidean" in comparison_path.read_text(encoding="utf-8")
