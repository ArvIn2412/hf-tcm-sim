from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest
from test_matched_m2_b5_experiment import _configuration, _reference_bits

from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.evaluation.matched_m2_b5_experiment import ORACLE_CSI_MATCHED_CONTROL
from hf_tcm.evaluation.reconstruction_adaptive_diagnostics import (
    run_adaptive_estimator_diagnostic,
)
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState


def _run(
    *,
    count: int = 4,
    gain: float = 0.75,
    mode: str = "monolithic",
    partition: tuple[int, ...] | None = None,
    alpha: float = 0.8,
    k_tilde: np.ndarray | None = None,
    mu0: np.ndarray | None = None,
    noise: np.ndarray | None = None,
    sigma_squared: float | None = None,
    noise_seed: int | None = None,
    initial_state: ReconstructionEstimatorState | None = None,
) -> object:
    config = _configuration(gain, origin=23, initial_time=41)
    return run_adaptive_estimator_diagnostic(
        run_id=f"adaptive-{count}-{gain}-{mode}",
        reference_information_bits=_reference_bits(count),
        real_channel_gain=gain,
        sigma_squared=sigma_squared,
        noise=(np.zeros(8 * count, dtype=np.complex128) if noise is None else noise)
        if noise_seed is None
        else None,
        noise_seed=noise_seed,
        noise_stream_id="m5e-test-noise" if noise_seed is not None else None,
        noise_provenance="explicit noiseless diagnostic fixture",
        symbol_origin_sample=23,
        first_symbol_index=5,
        initial_estimator_time_index=41,
        configuration=config,
        mismatched_initial_state=(
            ReconstructionEstimatorState([[0.42, 0.91]], [[0.42, 0.91]], 41)
            if initial_state is None
            else initial_state
        ),
        adaptive_alpha_prime=alpha,
        adaptive_k_tilde=np.asarray([[0.35, -0.2]]) if k_tilde is None else k_tilde,
        adaptive_mu0=np.asarray([[0.0, 0.0]]) if mu0 is None else mu0,
        receiver_mode=mode,
        segment_partition=partition,
    )


def test_modes_share_one_received_and_b_c_share_mismatched_initial_state() -> None:
    result = _run()
    oracle, frozen, adaptive = (
        result.oracle_frozen,
        result.mismatched_frozen,
        result.mismatched_adaptive,
    )

    assert oracle.mode == "oracle_frozen"
    assert frozen.mode == "mismatched_frozen"
    assert adaptive.mode == "mismatched_adaptive"
    assert (
        result.received_sha256
        == oracle.received_sha256
        == frozen.received_sha256
        == adaptive.received_sha256
    )
    assert frozen.initial_state.time_index == adaptive.initial_state.time_index == 41
    assert np.array_equal(
        frozen.initial_state.fluctuating_iq, adaptive.initial_state.fluctuating_iq
    )
    assert np.array_equal(frozen.initial_state.full_iq, adaptive.initial_state.full_iq)
    assert not np.array_equal(frozen.initial_state.full_iq, [[0.75, 0.75]])
    assert oracle.initial_csi_provenance == ORACLE_CSI_MATCHED_CONTROL
    assert all(
        np.array_equal(row.pre_state.full_iq, oracle.initial_state.full_iq)
        and np.array_equal(row.post_state.full_iq, oracle.initial_state.full_iq)
        for row in oracle.history
    )


def test_frozen_state_is_invariant_and_adaptive_history_has_manual_a1_step() -> None:
    result = _run(count=4, gain=2.0, alpha=0.85)
    frozen = result.mismatched_frozen
    adaptive = result.mismatched_adaptive

    for row in frozen.history:
        assert np.array_equal(row.pre_state.fluctuating_iq, frozen.initial_state.fluctuating_iq)
        assert np.array_equal(row.post_state.fluctuating_iq, frozen.initial_state.fluctuating_iq)
        assert np.array_equal(row.post_state.full_iq, frozen.initial_state.full_iq)
    first = adaptive.history[0]
    weighted_innovation = np.sum(
        first.posterior[:, None] * (first.observed_iq[None, :] - first.predicted_iq),
        axis=0,
    )
    expected_fluctuating = (
        0.85 * first.pre_state.fluctuating_iq[0]
        + np.asarray([[0.35, -0.2]])[0] * weighted_innovation
    )
    expected_full = expected_fluctuating
    assert np.allclose(first.post_state.fluctuating_iq[0], expected_fluctuating)
    assert np.allclose(first.post_state.full_iq[0], expected_full)
    assert np.allclose(
        first.post_state.full_iq,
        first.post_state.fluctuating_iq,
    )
    assert not np.array_equal(first.post_state.fluctuating_iq, first.pre_state.fluctuating_iq)


def test_nonzero_mu0_keeps_initial_components_distinct_and_full_decomposition_explicit() -> None:
    state = ReconstructionEstimatorState([[0.36, 0.81]], [[0.45, 0.94]], 41)
    result = _run(count=2, mu0=np.asarray([[0.025, -0.015]]), initial_state=state)
    adaptive = result.mismatched_adaptive
    assert np.array_equal(adaptive.initial_state.fluctuating_iq, state.fluctuating_iq)
    assert np.array_equal(adaptive.initial_state.full_iq, state.full_iq)
    assert not np.array_equal(adaptive.initial_state.fluctuating_iq, adaptive.initial_state.full_iq)
    assert np.allclose(
        adaptive.history[0].post_state.full_iq,
        adaptive.history[0].post_state.fluctuating_iq + np.asarray([[0.025, -0.015]]),
    )


@pytest.mark.parametrize(
    "initial_fluctuating,initial_full",
    [([[0.42, 0.91]], [[0.42, 0.91]]), ([[0.31, 0.83]], [[0.31, 0.83]])],
)
def test_two_explicit_mismatched_initial_estimates_are_preserved_in_b_and_c(
    initial_fluctuating: list[list[float]], initial_full: list[list[float]]
) -> None:
    state = ReconstructionEstimatorState(initial_fluctuating, initial_full, 41)
    result = _run(count=2, initial_state=state)
    for mode in (result.mismatched_frozen, result.mismatched_adaptive):
        assert np.array_equal(mode.initial_state.fluctuating_iq, state.fluctuating_iq)
        assert np.array_equal(mode.initial_state.full_iq, state.full_iq)


def test_causal_metrics_use_pre_state_and_successor_only_affects_later_symbol() -> None:
    result = _run()
    frozen, adaptive = result.mismatched_frozen, result.mismatched_adaptive

    assert np.array_equal(
        frozen.history[0].candidate_metrics, adaptive.history[0].candidate_metrics
    )
    assert np.array_equal(frozen.history[0].posterior, adaptive.history[0].posterior)
    assert np.array_equal(
        adaptive.history[1].pre_state.fluctuating_iq,
        adaptive.history[0].post_state.fluctuating_iq,
    )
    assert not np.array_equal(
        frozen.history[1].candidate_metrics,
        adaptive.history[1].candidate_metrics,
    )
    assert all(np.isclose(row.posterior.sum(), 1.0) for row in adaptive.history)
    assert all(
        row.prediction_cutoff_sample_index < row.first_sample_index for row in adaptive.history
    )
    assert all(
        row.observation_cutoff_sample_index == row.last_sample_index for row in adaptive.history
    )
    validate_hypothesis_edge_path(adaptive.decoded_hypothesis_path, initial_state=(0, 0))
    assert adaptive.evaluation.counts.total_bits == 8
    assert adaptive.evaluation.counts.total_symbols == 4


def test_monolithic_segmented_diagnostics_and_decodes_agree() -> None:
    monolithic = _run(count=4)
    segmented = _run(count=4, mode="segmented", partition=(1, 3))
    for first, second in zip(
        (monolithic.oracle_frozen, monolithic.mismatched_frozen, monolithic.mismatched_adaptive),
        (segmented.oracle_frozen, segmented.mismatched_frozen, segmented.mismatched_adaptive),
        strict=True,
    ):
        assert np.array_equal(first.candidate_metrics, second.candidate_metrics)
        assert np.array_equal(first.final_state.fluctuating_iq, second.final_state.fluctuating_iq)
        assert np.array_equal(first.final_posterior, second.final_posterior)
        assert np.array_equal(first.decoded_information_bits, second.decoded_information_bits)
        assert first.decoded_hypothesis_path == second.decoded_hypothesis_path


@pytest.mark.parametrize("count", [2, 8])
@pytest.mark.parametrize("gain", [0.75, 2.0])
def test_runs_support_requested_short_lengths_and_control_gains(count: int, gain: float) -> None:
    result = _run(count=count, gain=gain)
    assert len(result.mismatched_adaptive.history) == count
    assert result.effective_discrete_gamma_b is None
    assert result.mismatched_adaptive.evaluation.counts.total_bits == 2 * count


@pytest.mark.parametrize(
    "alpha,k_tilde",
    [(0.85, [[0.35, -0.2]]), (0.95, [[0.08, 0.04]])],
)
def test_two_explicit_adaptive_parameter_profiles_are_recorded_and_run(
    alpha: float, k_tilde: list[list[float]]
) -> None:
    result = _run(count=4, alpha=alpha, k_tilde=np.asarray(k_tilde))
    assert result.mismatched_adaptive.alpha_prime == (alpha,) * 4
    assert all(
        np.array_equal(value, np.asarray(k_tilde)) for value in result.mismatched_adaptive.k_tilde
    )
    assert np.any(
        result.mismatched_adaptive.history[-1].post_state.full_iq
        != result.mismatched_adaptive.initial_state.full_iq
    )


def test_invalid_nonfinite_adaptive_parameters_are_rejected() -> None:
    with pytest.raises(ValueError):
        _run(k_tilde=np.asarray([[float("nan"), 0.0]]))
    with pytest.raises(ValueError):
        _run(mu0=np.asarray([[0.0, float("inf")]]))


@pytest.mark.parametrize("gain,count", [(0.75, 2), (2.0, 4), (0.75, 8)])
def test_shared_explicit_noise_runs_are_deterministic_and_change_estimator_operands(
    gain: float, count: int
) -> None:
    pattern = np.arange(8 * count, dtype=np.float64)
    noise = (pattern + 1j * pattern[::-1]) * (0.002 + 0.001j)
    first = _run(count=count, gain=gain, noise=noise)
    second = _run(count=count, gain=gain, noise=noise.copy())
    assert first.received_sha256 == second.received_sha256
    assert np.array_equal(
        first.mismatched_adaptive.candidate_metrics,
        second.mismatched_adaptive.candidate_metrics,
    )
    assert np.array_equal(
        first.mismatched_adaptive.decoded_information_bits,
        second.mismatched_adaptive.decoded_information_bits,
    )
    assert first.effective_discrete_gamma_b is None
    assert first.absolute_sample_indices[0] == 23 + 8 * 5
    assert first.mismatched_adaptive.history[0].estimator_time_index == 41
    if count > 1:
        assert not np.array_equal(
            first.mismatched_frozen.candidate_metrics[1],
            first.mismatched_adaptive.candidate_metrics[1],
        )


def test_seeded_adr015_awgn_is_shared_and_repeatable() -> None:
    first = _run(count=4, gain=0.75, noise_seed=731, sigma_squared=0.025)
    repeated = _run(count=4, gain=0.75, noise_seed=731, sigma_squared=0.025)
    other_seed = _run(count=4, gain=0.75, noise_seed=732, sigma_squared=0.025)
    assert first.noise_mode == "seeded_independent_circular_complex_sample_awgn"
    assert first.received_sha256 == repeated.received_sha256
    assert first.received_sha256 != other_seed.received_sha256
    assert first.effective_discrete_gamma_b == pytest.approx(4 * 0.75**2 / 0.025)


def test_receiver_diagnostic_module_has_no_truth_import_or_reference_operand() -> None:
    path = (
        Path(__file__).parents[1] / "src/hf_tcm/evaluation/reconstruction_adaptive_diagnostics.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    identifiers = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "ChannelTruth" not in identifiers
    assert all("channels.multipath" not in imported for imported in imports)


def test_estimator_receives_only_shared_received_and_explicit_state(monkeypatch) -> None:
    import hf_tcm.evaluation.reconstruction_adaptive_diagnostics as diagnostics

    original = diagnostics.run_reconstruction_posterior_estimator_sequence
    calls: list[dict[str, object]] = []

    def capture(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(diagnostics, "run_reconstruction_posterior_estimator_sequence", capture)
    result = _run(count=2)
    assert len(calls) == 3
    assert all("reference_information_bits" not in call for call in calls)
    assert all(
        "real_channel_gain" not in call and "true_channel_gain" not in call for call in calls
    )
    assert all(
        np.shares_memory(np.asarray(call["received"]), np.asarray(calls[0]["received"]))
        for call in calls
    )
    assert all(np.array_equal(calls[0]["received"], call["received"]) for call in calls)
    assert all(not call["received"].flags.writeable for call in calls)
    assert result.received_sha256 == result.oracle_frozen.received_sha256
