from __future__ import annotations

import numpy as np
import pytest

from hf_tcm.repro.adaptive_multipath_config import (
    AdaptiveMultipathReceiverConfig,
    AdaptivePathConfig,
)
from hf_tcm.repro.augmented_trellis import build_augmented_trellis
from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.receiver_config import SeparateReceiverConfig
from hf_tcm.repro.separate_receiver import run_separate_receiver
from hf_tcm.repro.transmitter import run_transmitter


def _observation(frame_symbols: int = 6) -> ReceiverObservation:
    transmitter = run_transmitter(
        TransmitterConfig(
            source_mode="pattern",
            frame_symbols=frame_symbols,
            pattern_id="alternating",
        )
    )
    delay = 3
    received = np.concatenate((transmitter.tx_samples, np.zeros(delay, dtype=np.complex128)))
    indices = np.arange(received.size, dtype=np.int64)
    return ReceiverObservation(
        received_samples=received,
        absolute_sample_index=indices,
        sample_symbol_index=indices // 8,
        sample_local_index=indices % 8,
        samples_per_symbol=8,
        profile_id="test_identity",
        model_id="test_complex_baseband",
        sampling_convention="discrete_complex_baseband_absolute_sample_index",
        boundary_policy="zero_extension",
        output_length_policy="tx_length_plus_max_delay",
        noise_model="none",
        noise_complex_variance=0.0,
    )


def _config(frame_symbols: int = 6) -> AdaptiveMultipathReceiverConfig:
    return AdaptiveMultipathReceiverConfig(
        expected_symbol_count=frame_symbols,
        paths=(
            AdaptivePathConfig(0, prior_mean=0j, prior_variance=100.0),
            AdaptivePathConfig(3, prior_mean=0j, prior_variance=100.0),
        ),
        channel_mode="unknown_static",
        observation_noise_variance=0.01,
        decoder_mode="finite_depth",
        traceback_depth=20,
    )


def test_adaptive_receiver_is_truth_free_and_reports_expanded_eta20() -> None:
    from hf_tcm.repro.adaptive_multipath_receiver import run_adaptive_multipath_receiver

    observation = _observation()
    result = run_adaptive_multipath_receiver(observation, _config())
    assert result.observation_sha256 == observation.sha256
    assert result.trellis_state_count == 17
    assert result.trellis_edge_count == 68
    assert result.branch_metric_rows.shape == (6, 68)
    assert result.decoded_information_bits.shape == (12,)
    assert result.survivor_buffer_max_rows <= 6
    assert result.traceback_depth == 20
    assert np.all(np.isfinite(result.branch_metric_rows[np.isfinite(result.branch_metric_rows)]))
    # This zero-mean pre-update prior makes the first row's four legal outgoing
    # branches predict zero; post-update use would make the row edge-dependent.
    first_legal = result.branch_metric_rows[0, :4]
    np.testing.assert_allclose(first_legal, np.full(4, first_legal[0]), atol=1e-12)
    first_node_means = result.estimator_mean_by_symbol_node[0]
    assert np.unique(first_node_means[np.isfinite(first_node_means.real)].round(9)).size > 1
    trellis = build_augmented_trellis((0, 0), (0, 3))
    previous = np.full(result.trellis_state_count, np.inf)
    previous[trellis.initial_node_id] = 0.0
    for time_index, row in enumerate(result.branch_metric_rows):
        expected = np.full(result.trellis_state_count, np.inf)
        expected_edges = np.full(result.trellis_state_count, -1, dtype=np.int32)
        for edge in trellis.edges:
            candidate = previous[edge.source_node_id] + row[edge.expanded_edge_id]
            if candidate < expected[edge.target_node_id]:
                expected[edge.target_node_id] = candidate
                expected_edges[edge.target_node_id] = edge.expanded_edge_id
        np.testing.assert_allclose(
            result.survivor_path_metrics[time_index], expected, equal_nan=True
        )
        np.testing.assert_array_equal(
            result.diagnostics["survivor_edges_by_symbol_node"][time_index], expected_edges
        )
        previous = expected
    with pytest.raises(TypeError, match="ReceiverObservation"):
        run_adaptive_multipath_receiver(object(), _config())


def test_receiver_is_deterministic_and_rejects_wrong_tail_length() -> None:
    from hf_tcm.repro.adaptive_multipath_receiver import run_adaptive_multipath_receiver

    obs = _observation(5)
    config = _config(5)
    first = run_adaptive_multipath_receiver(obs, config)
    second = run_adaptive_multipath_receiver(obs, config)
    assert first.result_sha256 == second.result_sha256
    assert first.decoded_information_bits.tolist() == second.decoded_information_bits.tolist()
    wrong = ReceiverObservation(
        received_samples=obs.received_samples[:-1],
        absolute_sample_index=obs.absolute_sample_index[:-1],
        sample_symbol_index=obs.sample_symbol_index[:-1],
        sample_local_index=obs.sample_local_index[:-1],
        samples_per_symbol=8,
        profile_id=obs.profile_id,
        model_id=obs.model_id,
        sampling_convention=obs.sampling_convention,
        boundary_policy=obs.boundary_policy,
        output_length_policy=obs.output_length_policy,
        noise_model=obs.noise_model,
        noise_complex_variance=obs.noise_complex_variance,
    )
    with pytest.raises(ValueError, match="exactly"):
        run_adaptive_multipath_receiver(wrong, config)


def test_paired_separate_and_adaptive_arms_use_identical_public_observation() -> None:
    from hf_tcm.repro.adaptive_multipath_receiver import run_adaptive_multipath_receiver

    symbols = 8
    tx = run_transmitter(
        TransmitterConfig(source_mode="pattern", frame_symbols=symbols, pattern_id="alternating")
    )
    channel = run_channel(
        tx,
        ChannelConfig(
            profile_id="repro06c_test_static_pair",
            paths=(
                ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),
                ChannelPathConfig(3, 0.1, 0.0, constant_coefficient=0.3 + 0.1j),
            ),
            fading_mode="constant",
            noise_model="none",
            noise_complex_variance=0.0,
            fading_seed=3,
            noise_seed=4,
        ),
    )
    observation = channel.receiver_observation
    adaptive = run_adaptive_multipath_receiver(
        observation,
        AdaptiveMultipathReceiverConfig(
            expected_symbol_count=symbols,
            paths=(
                AdaptivePathConfig(0, prior_mean=0j, prior_variance=100.0),
                AdaptivePathConfig(3, prior_mean=0j, prior_variance=100.0),
            ),
            channel_mode="unknown_static",
            observation_noise_variance=0.01,
            traceback_depth=20,
        ),
    )
    separate = run_separate_receiver(
        observation,
        SeparateReceiverConfig(
            expected_symbol_count=symbols,
            decoder_mode="finite_depth",
            traceback_depth=20,
            trace_output_mode="compact",
        ),
    )
    assert adaptive.observation_sha256 == observation.sha256
    assert separate.observation_sha256 == observation.sha256
    assert adaptive.branch_metric_rows.shape == (symbols, 68)
    assert separate.decoded_information_bits.shape == tx.information_bits.shape


@pytest.mark.parametrize(
    ("mode", "rho"),
    [("slow_fading_rician_ar1", 0.995), ("rician_ar1", 0.85)],
)
def test_sample_level_rician_two_path_profile_runs_without_truth(mode: str, rho: float) -> None:
    from hf_tcm.repro.adaptive_multipath_receiver import run_adaptive_multipath_receiver

    symbols = 8
    tx = run_transmitter(
        TransmitterConfig(source_mode="pattern", frame_symbols=symbols, pattern_id="alternating")
    )
    channel = run_channel(
        tx,
        ChannelConfig(
            profile_id="repro06c_test_rician",
            paths=(
                ChannelPathConfig(0, 1.0, 4.0, los_phase_rad=0.1),
                ChannelPathConfig(3, 0.2, 2.0, los_phase_rad=-0.4),
            ),
            fading_mode="rician_ar1",
            noise_model="complex_awgn_sample_domain",
            noise_complex_variance=0.01,
            fading_seed=71,
            noise_seed=72,
            correlation=rho,
            reveal_noise_variance=True,
        ),
    )
    config = AdaptiveMultipathReceiverConfig(
        expected_symbol_count=symbols,
        paths=(
            AdaptivePathConfig(0, average_power=1.0, k_factor=4.0, los_phase_rad=0.1),
            AdaptivePathConfig(3, average_power=0.2, k_factor=2.0, los_phase_rad=-0.4),
        ),
        channel_mode=mode,  # type: ignore[arg-type]
        observation_noise_variance=0.01,
        correlation=rho,
        traceback_depth=20,
    )
    first = run_adaptive_multipath_receiver(channel.receiver_observation, config)
    second = run_adaptive_multipath_receiver(channel.receiver_observation, config)
    assert first.observation_sha256 == channel.receiver_observation.sha256
    assert first.result_sha256 == second.result_sha256
    assert np.all(np.isfinite(first.decoded_information_bits))
    assert np.all(np.isfinite(first.branch_metric_rows[np.isfinite(first.branch_metric_rows)]))
    # The receiver API is passed the public observation only; truth may be independently removed.
    assert channel.evaluation_truth.coefficients.shape[1] == len(
        channel.receiver_observation.received_samples
    )


def test_eta20_first_regular_decision_and_flush_cover_complete_payload() -> None:
    from hf_tcm.repro.adaptive_multipath_receiver import run_adaptive_multipath_receiver

    symbols = 32
    observation = _observation(symbols)
    result = run_adaptive_multipath_receiver(observation, _config(symbols))
    assert result.decisions[0].symbol_index == 0
    assert result.decisions[0].decision_available_at == 19
    assert result.decisions[0].traceback_depth_used == 20
    assert [row.symbol_index for row in result.decisions] == list(range(symbols))
    assert result.decisions[-1].decision_policy == "frame_flush"
    assert result.survivor_buffer_max_rows == 20
