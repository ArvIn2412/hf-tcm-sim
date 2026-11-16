from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import numpy as np
import pytest

from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.encoder import STATE_ORDER, transition_table
from hf_tcm.repro.finite_viterbi import ViterbiConfig, run_viterbi
from hf_tcm.repro.metric_experiment import (
    MetricStudyConfig,
    MetricTrialSpec,
    run_metric_study,
    run_metric_trial,
)
from hf_tcm.repro.metric_isolation import (
    build_pilot_schedule,
    euclidean_branch_metric_rows,
    hamming_branch_metric_rows,
    run_awgn_direct_frontend,
    run_metric_viterbi,
    run_pilot_frontend,
)


def _observation(received: np.ndarray, *, variance: float = 0.0) -> ReceiverObservation:
    count = len(received)
    return ReceiverObservation(
        received_samples=np.asarray(received, dtype=np.complex128),
        absolute_sample_index=np.arange(count, dtype=np.int64),
        sample_symbol_index=np.arange(count, dtype=np.int64) // 8,
        sample_local_index=np.arange(count, dtype=np.int64) % 8,
        samples_per_symbol=8,
        profile_id="test",
        model_id="test",
        sampling_convention="test",
        boundary_policy="zero_extension",
        output_length_policy="tx_plus_max_delay",
        noise_model="complex_awgn_sample_domain" if variance else "none",
        noise_complex_variance=variance,
    )


def test_phase_label_inverse_is_exact_for_all_eight_coded_triples() -> None:
    edges = transition_table()
    phase_to_triple = []
    for phase in range(8):
        triple = (phase >> 2, (phase >> 1) & 1, phase & 1)
        phase_to_triple.append(triple)
    assert len(set(phase_to_triple)) == 8
    for _edge, _state, _pair, triple, _next in edges:
        assert phase_to_triple[4 * triple[0] + 2 * triple[1] + triple[2]] == triple


def test_interior_pilot_phases_become_known_after_two_state_flush_pairs() -> None:
    schedule = build_pilot_schedule(
        frame_symbols=20,
        preamble_symbols=4,
        pilot_period=8,
        pilot_burst_symbols=4,
    )
    assert schedule.pilot_mask[:4].all()
    assert schedule.pilot_mask[4:8].sum() == 0
    interior = np.flatnonzero(schedule.pilot_mask[8:12]) + 8
    assert len(interior) == 4
    assert schedule.phase_known_mask[interior].tolist() == [False, False, True, True]
    assert schedule.phase_known_mask[:4].all()
    assert not np.any(schedule.phase_known_mask[~schedule.pilot_mask])


def test_awgn_direct_frontend_averages_all_eight_samples_without_channel_equalizer() -> None:
    symbols = np.asarray([1 + 1j, -1 + 1j, 1 - 1j]) / np.sqrt(2)
    noise = np.arange(24, dtype=float).reshape(3, 8) * (0.001 + 0.002j)
    observed = np.repeat(symbols, 8) + noise.ravel()
    result = run_awgn_direct_frontend(_observation(observed), symbol_count=3)
    np.testing.assert_allclose(result.symbols, symbols + noise.mean(axis=1))
    assert result.mode == "awgn_direct_control"
    assert result.clean_sample_count_per_symbol == 8


def test_pilot_frontend_removes_integer_delay_isi_and_estimates_static_composite_gain() -> None:
    schedule = build_pilot_schedule(
        frame_symbols=18,
        preamble_symbols=4,
        pilot_period=9,
        pilot_burst_symbols=4,
    )
    input_pairs = np.zeros((18, 2), dtype=np.int8)
    input_pairs[schedule.pilot_mask] = schedule.pilot_input_pairs[schedule.pilot_mask]
    input_pairs[~schedule.pilot_mask] = np.asarray(
        [[0, 1], [1, 0], [1, 1], [0, 0], [1, 0], [0, 1], [1, 1], [0, 0], [1, 1], [1, 0]],
        dtype=np.int8,
    )[: np.count_nonzero(~schedule.pilot_mask)]
    phase_indices = np.empty(18, dtype=np.int8)
    state = (0, 0)
    for index, pair_array in enumerate(input_pairs):
        pair = tuple(int(bit) for bit in pair_array)
        edge = transition_table()[STATE_ORDER.index(state) * 4 + pair[0] * 2 + pair[1]]
        triple = edge[3]
        phase_indices[index] = 4 * triple[0] + 2 * triple[1] + triple[2]
        state = edge[4]
    constellation = np.exp(1j * phase_indices * np.pi / 4)
    tx = np.repeat(constellation, 8)
    h0, h1 = 0.8 + 0.2j, 0.3 - 0.1j
    rx = np.zeros_like(tx)
    rx += h0 * tx
    rx[3:] += h1 * tx[:-3]
    obs = _observation(rx, variance=0.01)
    result = run_pilot_frontend(
        obs,
        schedule,
        amplitude=1.0,
        path_delays_samples=(0, 3),
        assumed_noise_variance=0.01,
    )
    np.testing.assert_allclose(result.estimated_composite_gain[result.gain_valid_mask], h0 + h1)
    usable = result.valid_symbol_mask & ~schedule.pilot_mask
    np.testing.assert_allclose(result.symbols[usable], constellation[usable], atol=1e-12)
    assert result.clean_sample_count_per_symbol == 5
    assert result.maximum_delay_samples == 3
    assert result.residual_isi_bound == "zero_for_integer_delay_zoh_tail"


def test_pilot_frontend_is_causal_to_received_samples() -> None:
    schedule = build_pilot_schedule(
        frame_symbols=24,
        preamble_symbols=4,
        pilot_period=10,
        pilot_burst_symbols=4,
    )
    samples = np.ones(24 * 8, dtype=np.complex128)
    base = run_pilot_frontend(
        _observation(samples), schedule, amplitude=1.0, path_delays_samples=(0, 3)
    )
    changed_samples = samples.copy()
    changed_samples[12 * 8 :] += 50 + 3j
    changed = run_pilot_frontend(
        _observation(changed_samples), schedule, amplitude=1.0, path_delays_samples=(0, 3)
    )
    np.testing.assert_array_equal(base.symbols[:12], changed.symbols[:12])
    np.testing.assert_array_equal(
        base.estimated_composite_gain[:12], changed.estimated_composite_gain[:12]
    )


def test_metric_rows_are_independent_candidate_costs_with_canonical_edge_order() -> None:
    symbols = np.exp(1j * np.asarray([0, 1, 7]) * np.pi / 4)
    z = symbols + np.asarray([0.01 + 0.01j, -0.03 + 0.02j, 0.02 - 0.01j])
    euclidean = euclidean_branch_metric_rows(z, amplitude=1.0)
    hamming = hamming_branch_metric_rows(z, amplitude=1.0)
    edges = transition_table()
    assert euclidean.shape == hamming.shape == (3, 16)
    for row_index, value in enumerate(z):
        expected_e = [
            abs(value - np.exp(1j * (4 * edge[3][0] + 2 * edge[3][1] + edge[3][2]) * np.pi / 4))
            ** 2
            for edge in edges
        ]
        np.testing.assert_allclose(euclidean[row_index], expected_e)
    assert hamming.dtype.kind in "iu"
    assert np.all((hamming >= 0) & (hamming <= 3))


def test_hard_slicer_uses_candidate_independent_lowest_phase_tie_break() -> None:
    z = np.asarray([np.exp(1j * np.pi / 8)], dtype=np.complex128)
    hamming = hamming_branch_metric_rows(z, amplitude=1.0)
    expected = np.count_nonzero(
        np.asarray([row[3] for row in transition_table()]) != np.asarray([0, 0, 0]), axis=1
    )
    np.testing.assert_array_equal(hamming[0], expected)


def test_unconstrained_metric_viterbi_matches_existing_finite_depth_decoder() -> None:
    rng = np.random.default_rng(44)
    metrics = rng.random((37, 16))
    result = run_metric_viterbi(metrics, traceback_depth=20)
    reference = run_viterbi(
        metrics,
        ViterbiConfig(
            initial_state=(0, 0),
            traceback_depth=20,
            decoder_mode="finite_depth",
            expected_symbol_count=37,
            trace_output_mode="full",
        ),
    )
    np.testing.assert_array_equal(result.decoded_edge_ids, reference.decoded_edge_ids)
    np.testing.assert_array_equal(result.information_pairs, reference.information_pairs)
    np.testing.assert_array_equal(result.survivor_edge_ids, reference.survivor_edge_ids)
    np.testing.assert_allclose(result.state_metrics, reference.state_metrics)


def test_constrained_viterbi_honors_known_pilot_pairs_exactly() -> None:
    rng = np.random.default_rng(1)
    metrics = rng.random((12, 16))
    constraints = np.full((12, 2), -1, dtype=np.int8)
    constraints[0] = (1, 1)
    constraints[6] = (0, 1)
    result = run_metric_viterbi(metrics, allowed_input_pairs=constraints, traceback_depth=20)
    np.testing.assert_array_equal(result.information_pairs[0], constraints[0])
    np.testing.assert_array_equal(result.information_pairs[6], constraints[6])
    assert result.traceback_depth == 20


def test_pilot_schedule_rejects_bursts_too_short_to_recover_encoder_state() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        build_pilot_schedule(
            frame_symbols=20,
            preamble_symbols=4,
            pilot_period=8,
            pilot_burst_symbols=2,
        )


def test_paired_metric_trial_uses_one_observation_and_accounts_for_pilot_overhead() -> None:
    channel = ChannelConfig(
        profile_id="static_multipath",
        paths=(
            ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),
            ChannelPathConfig(3, 0.13, 0.0, constant_coefficient=0.3 - 0.2j),
        ),
        fading_mode="constant",
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=1e-9,
        fading_seed=77,
        noise_seed=78,
        reveal_noise_variance=True,
    )
    result = run_metric_trial(
        MetricTrialSpec(
            trial_id="test-static-000",
            frame_symbols=40,
            source_seed=51,
            channel_config=channel,
            frontend_mode="pilot_equalized",
            amplitude=1.0,
            preamble_symbols=4,
            pilot_period=16,
            pilot_burst_symbols=4,
        )
    )
    record = result.summary
    assert record["contrast_id"] == "metric_isolation"
    assert record["observation_sha256"] == record["paired_observation_sha256"]
    assert record["frontend_output_sha256_euclidean"] == record["frontend_output_sha256_hamming"]
    assert record["pilot_symbols"] > 0
    assert record["payload_symbols"] + record["pilot_symbols"] == 40
    assert record["payload_information_bits"] == 2 * record["payload_symbols"]
    assert record["transmit_energy_discrete"] > record["pilot_energy_discrete"]
    assert record["energy_per_payload_bit_discrete"] == pytest.approx(
        record["transmit_energy_discrete"] / record["payload_information_bits"]
    )
    assert record["frontend_mode"] == "causal_pilot_composite_gain_clean_tail"
    assert record["euclidean"]["bit_errors"] == 0
    assert record["hamming"]["bit_errors"] == 0
    np.testing.assert_array_equal(
        result.decoded_euclidean_pairs[result.schedule.payload_mask].shape,
        result.decoded_hamming_pairs[result.schedule.payload_mask].shape,
    )


def test_awgn_direct_metric_control_has_no_pilots_and_is_labeled_separately() -> None:
    channel = ChannelConfig(
        profile_id="awgn",
        paths=(ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),),
        fading_mode="constant",
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=1e-10,
        fading_seed=5,
        noise_seed=6,
        reveal_noise_variance=True,
    )
    result = run_metric_trial(
        MetricTrialSpec(
            trial_id="test-awgn-000",
            frame_symbols=32,
            source_seed=9,
            channel_config=channel,
            frontend_mode="awgn_direct_control",
            amplitude=1.0,
        )
    )
    assert result.summary["pilot_symbols"] == 0
    assert result.summary["payload_symbols"] == 32
    assert result.summary["frontend_mode"] == "awgn_direct_control"
    assert result.summary["observation_sha256"] == result.summary["paired_observation_sha256"]


def test_noiseless_awgn_metric_control_recovers_both_arms() -> None:
    channel = ChannelConfig(
        profile_id="awgn",
        paths=(ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),),
        fading_mode="constant",
        noise_model="none",
        noise_complex_variance=0.0,
        fading_seed=5,
        noise_seed=6,
        reveal_noise_variance=True,
    )
    result = run_metric_trial(
        MetricTrialSpec(
            trial_id="test-awgn-noiseless-000",
            frame_symbols=64,
            source_seed=1009,
            channel_config=channel,
            frontend_mode="awgn_direct_control",
            amplitude=1.0,
        )
    )
    assert result.summary["euclidean"]["bit_errors"] == 0
    assert result.summary["hamming"]["bit_errors"] == 0


def test_metric_study_stop_resume_reuses_completed_paired_trials(tmp_path) -> None:
    from threading import Event

    channel = ChannelConfig(
        profile_id="awgn",
        paths=(ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),),
        fading_mode="constant",
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=0.05,
        fading_seed=5,
        noise_seed=6,
        reveal_noise_variance=True,
    )
    config = MetricStudyConfig(
        experiment_id="metric-resume-test",
        scenario="awgn",
        phase="validation",
        frame_symbols=24,
        energy_grid_db=(0.0,),
        trials_per_point=2,
        root_seed=991,
        target_ber=0.05,
        time_budget_seconds=30.0,
        sweep="amplitude",
        amplitude=1.0,
        channel_config=channel.to_dict(),
        frontend_mode="awgn_direct_control",
        bootstrap_replicates=100,
    )
    stop = Event()

    def stop_after_first(update: dict) -> None:
        if update["completed_trials"] == 1:
            stop.set()

    first = run_metric_study(config, tmp_path, stop_event=stop, progress_callback=stop_after_first)
    assert first["status"] == "incomplete"
    assert first["completed_trials"] == 1
    resumed = run_metric_study(config, tmp_path)
    assert resumed["status"] == "completed"
    assert resumed["completed_trials"] == 2
    assert resumed["duplicate_trials_skipped"] == 1
    assert resumed["paired_hashes_valid"] is True


def test_rician_trial_reports_causal_tracking_and_equalizer_noise_diagnostics() -> None:
    channel = ChannelConfig(
        profile_id="rician_ar1_multipath",
        paths=(
            ChannelPathConfig(0, 1.0, 4.0, 0.0),
            ChannelPathConfig(3, 0.25, 1.0, 0.7),
        ),
        fading_mode="rician_ar1",
        correlation=0.98,
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=0.02,
        fading_seed=121,
        noise_seed=122,
        reveal_noise_variance=True,
    )
    result = run_metric_trial(
        MetricTrialSpec(
            trial_id="test-rician-000",
            frame_symbols=40,
            source_seed=123,
            channel_config=channel,
            frontend_mode="pilot_equalized",
            amplitude=1.0,
            preamble_symbols=4,
            pilot_period=16,
            pilot_burst_symbols=4,
        )
    )
    diagnostics = result.summary["diagnostics_evaluator_only"]
    assert result.summary["frontend_mode"] == "causal_pilot_composite_gain_clean_tail"
    assert diagnostics["truth_access_stage"] == "after_both_decoders_completed"
    assert diagnostics["clean_region_residual_isi_rms"] < 1e-12
    assert diagnostics["pilot_composite_gain_rmse_evaluator_only"] >= 0
    assert diagnostics["equalizer_output_noise_variance_empirical_evaluator_only"] >= 0
    assert result.frontend.gain_age_symbols[result.frontend.valid_symbol_mask].max() > 0


def test_oracle_csi_path_is_separately_labeled_diagnostic() -> None:
    channel = ChannelConfig(
        profile_id="static_multipath",
        paths=(
            ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),
            ChannelPathConfig(3, 0.13, 0.0, constant_coefficient=0.3 - 0.2j),
        ),
        fading_mode="constant",
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=1e-9,
        fading_seed=7,
        noise_seed=8,
        reveal_noise_variance=True,
    )
    result = run_metric_trial(
        MetricTrialSpec(
            trial_id="test-oracle-000",
            frame_symbols=32,
            source_seed=17,
            channel_config=channel,
            frontend_mode="oracle_csi",
        )
    )
    assert result.summary["frontend_mode"] == "diagnostic_oracle_csi"
    assert result.summary["scientific_limitations"]
    assert (
        result.summary["diagnostics_evaluator_only"]["pilot_composite_gain_rmse_evaluator_only"]
        is None
    )


def test_scientific_gui_serves_metric_tab_and_rejects_confirmatory_submission() -> None:
    from hf_tcm.studio.server import make_server

    server = make_server("127.0.0.1", 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(f"{base}/scientific", timeout=5) as response:
            html = response.read().decode("utf-8")
        assert 'data-view="metric"' in html
        assert 'src="/static/scientific_metric.js"' in html
        with urllib.request.urlopen(f"{base}/static/scientific_metric.js", timeout=5) as response:
            script = response.read().decode("utf-8")
        assert "exportSvg" in script
        assert 'phase: "range_finding"' in script

        channel = ChannelConfig(
            profile_id="awgn",
            paths=(ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),),
            fading_mode="constant",
            noise_model="complex_awgn_sample_domain",
            noise_complex_variance=0.05,
            fading_seed=1,
            noise_seed=2,
            reveal_noise_variance=True,
        )
        payload = MetricStudyConfig(
            experiment_id="confirmatory-guard-test",
            scenario="awgn",
            phase="range_finding",
            frame_symbols=20,
            energy_grid_db=(0.0,),
            trials_per_point=1,
            root_seed=3,
            target_ber=0.05,
            time_budget_seconds=1.0,
            sweep="amplitude",
            amplitude=1.0,
            channel_config=channel.to_dict(),
            frontend_mode="awgn_direct_control",
            bootstrap_replicates=100,
        ).to_dict()
        payload["phase"] = "confirmatory"
        request = urllib.request.Request(
            f"{base}/api/scientific/metric-studies",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=5)
        assert error.value.code == 400
        message = json.loads(error.value.read().decode("utf-8"))["error"]
        assert "cannot execute confirmatory" in message
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()
