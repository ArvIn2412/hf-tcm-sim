from __future__ import annotations

import numpy as np

from hf_tcm.repro.adaptive_multipath_config import (
    AdaptiveMultipathReceiverConfig,
    AdaptivePathConfig,
)
from hf_tcm.repro.augmented_trellis import build_augmented_trellis
from hf_tcm.repro.survivor_channel_estimator import (
    EstimatorState,
    build_delayed_regressor,
    predict_estimator_sample,
    update_estimator_sample,
)


def _static_config(noise_variance: float = 0.3) -> AdaptiveMultipathReceiverConfig:
    return AdaptiveMultipathReceiverConfig(
        expected_symbol_count=3,
        paths=(
            AdaptivePathConfig(0, prior_mean=0j, prior_variance=1.0),
            AdaptivePathConfig(3, prior_mean=0j, prior_variance=2.0),
        ),
        channel_mode="unknown_static",
        observation_noise_variance=noise_variance,
    )


def test_complex_rls_update_matches_hand_computed_conjugate_oracle() -> None:
    config = _static_config()
    mean = np.asarray([0.2 + 0.1j, -0.3 + 0.2j], dtype=np.complex128)
    covariance = np.diag([1.0, 2.0]).astype(np.complex128)
    state = EstimatorState(mean, covariance, last_sample_index=-1)
    regressor = np.asarray([1.0 + 1.0j, 2.0 - 1.0j], dtype=np.complex128)
    received = 0.7 - 0.4j

    z = np.conjugate(regressor)
    innovation = received - np.vdot(z, mean)
    projected = covariance @ z
    denominator = 0.3 + np.vdot(z, projected).real
    gain = projected / denominator
    expected_mean = mean + gain * innovation
    expected_covariance = covariance - np.outer(gain, np.conjugate(z) @ covariance)

    actual, actual_innovation = update_estimator_sample(
        state, regressor, received, config, sample_index=0
    )

    np.testing.assert_allclose(actual.mean, expected_mean, rtol=1e-13, atol=1e-13)
    np.testing.assert_allclose(actual.covariance, expected_covariance, rtol=1e-13, atol=1e-13)
    assert actual_innovation == innovation
    assert np.allclose(actual.covariance, actual.covariance.conj().T)


def test_rician_ar1_prior_prediction_is_sample_level_and_hand_computed() -> None:
    config = AdaptiveMultipathReceiverConfig(
        expected_symbol_count=2,
        paths=(
            AdaptivePathConfig(
                0,
                average_power=1.0,
                k_factor=3.0,
                los_phase_rad=0.0,
            ),
        ),
        channel_mode="rician_ar1",
        correlation=0.9,
        observation_noise_variance=0.01,
    )
    state = EstimatorState(
        mean=np.asarray([0.5 + 0.4j], dtype=np.complex128),
        covariance=np.asarray([[0.25 + 0j]], dtype=np.complex128),
        last_sample_index=0,
    )
    predicted, predicted_covariance = predict_estimator_sample(state, config, sample_index=1)
    expected_mean = config.paths[0].public_mean + 0.9 * (
        state.mean[0] - config.paths[0].public_mean
    )
    expected_q = (1 - 0.9**2) * config.paths[0].diffuse_variance

    assert predicted.mean[0] == expected_mean
    assert np.isclose(predicted_covariance[0, 0].real, 0.9**2 * 0.25 + expected_q)
    assert predicted.last_sample_index == 1


def test_rank_deficient_delayed_regressors_keep_finite_hermitian_covariance() -> None:
    config = _static_config(noise_variance=1e-12)
    state = EstimatorState(
        np.zeros(2, dtype=np.complex128),
        np.eye(2, dtype=np.complex128),
        last_sample_index=-1,
    )
    regressor = np.asarray([1 + 0j, 1 + 0j], dtype=np.complex128)
    for sample in range(40):
        state, _ = update_estimator_sample(
            state, regressor, 0.5 + 0.25j, config, sample_index=sample
        )

    assert np.all(np.isfinite(state.mean))
    assert np.all(np.isfinite(state.covariance))
    np.testing.assert_allclose(state.covariance, state.covariance.conj().T, atol=1e-12)
    assert np.linalg.eigvalsh(state.covariance).min() >= -1e-10
    assert abs(state.mean[0] - state.mean[1]) < 1e-10


def test_d3_candidate_regressor_uses_current_and_previous_zoh_symbol() -> None:
    trellis = build_augmented_trellis((0, 0), (0, 3))
    transition = next(
        edge
        for edge in trellis.edges
        if trellis.nodes[edge.source_node_id].phase_history == (2,) and edge.phase_index == 5
    )
    indices = np.arange(8, 16, dtype=np.int64)

    design = build_delayed_regressor(
        transition,
        trellis,
        symbol_index=1,
        frame_symbols=3,
        delays_samples=(0, 3),
        sample_indices=indices,
        amplitude=1.0,
        phase_offset_rad=0.0,
        phase_increment_rad=np.pi / 4,
    )

    current = np.exp(1j * 5 * np.pi / 4)
    previous = np.exp(1j * 2 * np.pi / 4)
    expected_delayed = np.asarray([previous] * 3 + [current] * 5)
    np.testing.assert_allclose(design[:, 0], current)
    np.testing.assert_allclose(design[:, 1], expected_delayed)


def test_estimator_updates_return_independent_survivor_states() -> None:
    config = _static_config()
    source = EstimatorState(np.zeros(2, dtype=np.complex128), np.eye(2, dtype=np.complex128), -1, 7)
    first, _ = update_estimator_sample(
        source, np.asarray([1 + 0j, 0 + 0j]), 1 + 0j, config, sample_index=0
    )
    second, _ = update_estimator_sample(
        source, np.asarray([0 + 0j, 1 + 0j]), 1j, config, sample_index=0
    )

    assert not np.shares_memory(first.mean, second.mean)
    assert not np.shares_memory(first.covariance, second.covariance)
    assert first.hypothesis_node_id == second.hypothesis_node_id == 7
    np.testing.assert_array_equal(source.mean, np.zeros(2, dtype=np.complex128))
    assert not np.allclose(first.mean, second.mean)
