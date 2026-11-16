from __future__ import annotations

import numpy as np

from hf_tcm.repro.augmented_trellis import build_augmented_trellis
from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.isi_metrics import (
    branch_sample_indices,
    build_branch_metric_matrix,
    build_branch_metric_row,
)
from hf_tcm.repro.multipath_receiver_config import (
    MultipathPathConfig,
    MultipathReceiverConfig,
)


def _observation(values: np.ndarray) -> ReceiverObservation:
    indices = np.arange(len(values), dtype=np.int64)
    return ReceiverObservation(
        received_samples=np.asarray(values, dtype=np.complex128),
        absolute_sample_index=indices,
        sample_symbol_index=indices // 8,
        sample_local_index=indices % 8,
        samples_per_symbol=8,
        profile_id="repro06b_known_static_isi_test",
        model_id="repro03_discrete_complex_baseband_v1",
        sampling_convention="discrete_complex_baseband_absolute_sample_index",
        boundary_policy="zero_extension",
        output_length_policy="tx_plus_max_delay",
        noise_model="none",
        noise_complex_variance=None,
    )


def _phase_symbol(phase: int, config: MultipathReceiverConfig) -> complex:
    return np.exp(1j * (config.phase_offset_rad + phase * np.pi / 4.0))


def test_branch_metric_uses_manual_delayed_waveform_and_final_tail_samples() -> None:
    config = MultipathReceiverConfig(
        expected_symbol_count=2,
        paths=(
            MultipathPathConfig(0, 1 + 0.2j),
            MultipathPathConfig(3, 0.5 - 0.25j),
        ),
        metric_profile="squared_euclidean",
    )
    trellis = build_augmented_trellis((0, 0), (0, 3))
    first = next(
        edge
        for edge in trellis.edges
        if edge.source_node_id == trellis.initial_node_id and edge.base_edge_id == 0
    )
    second = next(
        edge
        for edge in trellis.edges
        if edge.source_node_id == first.target_node_id and edge.base_edge_id == 1
    )
    tx = np.repeat(
        np.asarray(
            [_phase_symbol(first.phase_index, config), _phase_symbol(second.phase_index, config)],
            dtype=np.complex128,
        ),
        8,
    )
    channel = np.zeros(19, dtype=np.complex128)
    for n in range(len(channel)):
        if 0 <= n < len(tx):
            channel[n] += (1 + 0.2j) * tx[n]
        if 0 <= n - 3 < len(tx):
            channel[n] += (0.5 - 0.25j) * tx[n - 3]
    residual = np.linspace(0.1, 1.1, 19) + 1j * np.linspace(-0.7, 0.5, 19)
    observation = _observation(channel + residual)

    row0 = build_branch_metric_row(observation, 0, trellis, config)
    row1 = build_branch_metric_row(observation, 1, trellis, config)

    assert np.isclose(row0[first.expanded_edge_id], np.vdot(residual[:8], residual[:8]).real)
    assert row1[second.expanded_edge_id] == np.vdot(residual[8:], residual[8:]).real
    assert row1.shape == (68,)
    assert branch_sample_indices(0, 2, 3).tolist() == list(range(8))
    assert branch_sample_indices(1, 2, 3).tolist() == list(range(8, 19))


def test_euclidean_profile_takes_one_norm_after_combining_symbol_and_tail() -> None:
    config_sq = MultipathReceiverConfig(
        expected_symbol_count=1,
        paths=(MultipathPathConfig(0, 1 + 0j), MultipathPathConfig(3, 0.3 + 0j)),
    )
    config_l2 = MultipathReceiverConfig(
        expected_symbol_count=1,
        paths=config_sq.paths,
        metric_profile="euclidean",
    )
    trellis = build_augmented_trellis((0, 0), (0, 3))
    tx = np.full(8, _phase_symbol(0, config_sq), dtype=np.complex128)
    predicted = np.zeros(11, dtype=np.complex128)
    for n in range(len(predicted)):
        if n < len(tx):
            predicted[n] += tx[n]
        if 0 <= n - 3 < len(tx):
            predicted[n] += 0.3 * tx[n - 3]
    observation = _observation(predicted + (1 + 1j))
    squared = build_branch_metric_row(observation, 0, trellis, config_sq)
    norm = build_branch_metric_row(observation, 0, trellis, config_l2)
    edge = next(edge for edge in trellis.edges if edge.base_edge_id == 0)
    expected_sq = 22.0

    assert np.isclose(squared[edge.expanded_edge_id], expected_sq)
    assert np.isclose(norm[edge.expanded_edge_id], np.sqrt(expected_sq))


def test_branch_metrics_require_exact_observation_length_and_receiver_only_type() -> None:
    config = MultipathReceiverConfig(
        expected_symbol_count=2,
        paths=(MultipathPathConfig(0, 1 + 0j), MultipathPathConfig(3, 0.1 + 0j)),
    )
    trellis = build_augmented_trellis((0, 0), (0, 3))
    observation = _observation(np.zeros(16, dtype=np.complex128))
    import pytest

    with pytest.raises(ValueError, match="observation length must equal 19"):
        build_branch_metric_row(observation, 0, trellis, config)
    with pytest.raises(TypeError, match="ReceiverObservation"):
        build_branch_metric_row(object(), 0, trellis, config)


def test_precomputed_metric_matrix_matches_independent_per_row_builder_d3_and_d9() -> None:
    rng = np.random.default_rng(711)
    for delays in ((0, 3), (1, 9)):
        frame = 5
        config = MultipathReceiverConfig(
            expected_symbol_count=frame,
            paths=(
                MultipathPathConfig(delays[0], 0.7 + 0.1j),
                MultipathPathConfig(delays[1], -0.2 + 0.4j),
            ),
        )
        trellis = build_augmented_trellis((0, 0), delays)
        observation = _observation(
            rng.normal(size=frame * 8 + max(delays)) + 1j * rng.normal(size=frame * 8 + max(delays))
        )
        actual = build_branch_metric_matrix(observation, trellis, config)
        expected = np.vstack(
            [build_branch_metric_row(observation, k, trellis, config) for k in range(frame)]
        )

        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-12)
