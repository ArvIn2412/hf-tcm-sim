"""Independent checks for the narrow ADR-012 causal one-path bridge."""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_estimator_step import advance_reconstruction_estimator_state


def _profile_args(symbol: int, origin: int, buffer_start: int, length: int) -> dict[str, object]:
    indices = np.arange(buffer_start, buffer_start + length, dtype=np.int64)
    return {
        "absolute_sample_indices": indices,
        "received_start_sample": buffer_start,
        "symbol_origin_sample": origin,
        "target_symbol_index": symbol,
        "profile": "reconstructed_offline",
        "adr_profile": "adr012_l1_real_mean8",
        "path_count": 1,
        "path_delays_samples": (0,),
        "samples_per_symbol": 8,
        "iq_rule": "adr012_minus_imaginary_real_mean8",
        "waveform_rule": "rectangular_zoh",
    }


def _state(time_index: int = 0) -> ReconstructionEstimatorState:
    return ReconstructionEstimatorState(
        fluctuating_iq=np.array([[0.4, -0.3]]),
        full_iq=np.array([[0.9, 0.2]]),
        time_index=time_index,
    )


def _operand_cutoff_args(symbol: int, origin: int) -> dict[str, int]:
    cutoff = origin + 8 * (symbol + 1) - 1
    return {
        "prediction_data_cutoff_sample": cutoff,
        "posterior_data_cutoff_sample": cutoff,
    }


def test_real_channel_iq_bridge_all_phases_and_two_gains() -> None:
    from hf_tcm.receiver.reconstruction_observation import extract_adr012_observed_iq

    for gain in (0.75, 2.0):
        for b in range(8):
            phase = b * np.pi / 4.0
            samples = gain * np.exp(1j * phase) * np.ones(8, dtype=np.complex128)
            indices = np.arange(101, 109)
            got = extract_adr012_observed_iq(
                samples,
                **_profile_args(0, 101, 101, 8),
            )
            expected = np.array(
                [-np.imag(gain * np.exp(1j * phase)), np.real(gain * np.exp(1j * phase))]
            )
            np.testing.assert_allclose(got, expected, atol=1e-14)
            np.testing.assert_array_equal(indices, np.arange(101, 109))


def test_adapter_means_exactly_eight_nonidentical_samples_at_absolute_origin() -> None:
    from hf_tcm.receiver.reconstruction_observation import extract_adr012_observed_iq

    received = np.array([complex(k, 2 * k + 1) for k in range(32)], dtype=np.complex128)
    got = extract_adr012_observed_iq(
        received,
        **_profile_args(3, 500, 500, 32),
    )
    np.testing.assert_allclose(got, [-np.mean(received[24:32].imag), np.mean(received[24:32].real)])


@pytest.mark.parametrize(
    ("received", "kwargs"),
    [
        (np.ones(7, dtype=np.complex128), _profile_args(0, 100, 100, 7)),
        (np.ones(8, dtype=np.complex128), {**_profile_args(0, 100, 100, 8), "path_count": 2}),
        (
            np.ones(8, dtype=np.complex128),
            {**_profile_args(0, 100, 100, 8), "path_delays_samples": (2,)},
        ),
        (
            np.ones(8, dtype=np.complex128),
            {**_profile_args(0, 100, 100, 8), "profile": "source_faithful"},
        ),
        (
            np.ones(8, dtype=np.complex128),
            {**_profile_args(0, 100, 100, 8), "adr_profile": "other"},
        ),
        (
            np.ones(8, dtype=np.complex128),
            {**_profile_args(0, 100, 100, 8), "samples_per_symbol": 4},
        ),
        (np.array([np.nan + 0j] + [1 + 0j] * 7), _profile_args(0, 100, 100, 8)),
        (np.array([np.inf + 0j] + [1 + 0j] * 7), _profile_args(0, 100, 100, 8)),
    ],
)
def test_observation_adapter_rejects_invalid_windows_and_profiles(received, kwargs) -> None:
    from hf_tcm.receiver.reconstruction_observation import extract_adr012_observed_iq

    with pytest.raises(ValueError):
        extract_adr012_observed_iq(received, **kwargs)


def test_observation_adapter_rejects_noncontiguous_or_misaligned_sample_labels() -> None:
    from hf_tcm.receiver.reconstruction_observation import extract_adr012_observed_iq

    args = _profile_args(2, 11, 11, 24)
    args["absolute_sample_indices"] = np.array([11, 12, 13, 14, 15, 16, 17, 19, *range(20, 36)])
    with pytest.raises(ValueError, match="absolute_sample_indices"):
        extract_adr012_observed_iq(np.ones(24, dtype=np.complex128), **args)


def test_causal_step_uses_explicit_operands_and_returns_next_symbol_snapshot() -> None:
    from hf_tcm.receiver.reconstruction_causal_step import advance_real_one_path_symbol

    start = 240
    received = np.array([1 + 2j] * 8, dtype=np.complex128)
    result = advance_real_one_path_symbol(
        _state(0),
        received,
        **_profile_args(0, start, start, 8),
        **_operand_cutoff_args(0, start),
        time_index=0,
        alpha_prime=0.5,
        k_tilde=[[0.25, 0.5]],
        mu0=[[0.1, -0.2]],
        predicted_iq=[[0.0, 0.0], [1.0, 1.0]],
        posterior=[0.25, 0.75],
    )
    assert result.previous_time_index == 0
    assert result.processed_symbol_index == 0
    assert result.available_after_sample_index == 247
    assert result.prediction_data_cutoff_sample == 247
    assert result.posterior_data_cutoff_sample == 247
    assert result.next_usable_symbol_index == 1
    assert result.next_state.time_index == 1
    np.testing.assert_allclose(result.observed_iq, [-2.0, 1.0])
    expected = advance_reconstruction_estimator_state(
        _state(0),
        time_index=0,
        next_time_index=1,
        alpha_prime=0.5,
        k_tilde=[[0.25, 0.5]],
        mu0=[[0.1, -0.2]],
        observed_iq=[-2.0, 1.0],
        predicted_iq=[[0.0, 0.0], [1.0, 1.0]],
        posterior=[0.25, 0.75],
    )
    np.testing.assert_array_equal(result.next_state.full_iq, expected.full_iq)
    np.testing.assert_array_equal(
        result.forward_snapshot.estimated_path_coefficients, expected.full_iq
    )
    assert result.forward_snapshot.estimator_time_index == 1


def test_two_symbol_causal_clock_old_state_and_future_samples_are_isolated() -> None:
    from hf_tcm.receiver.reconstruction_causal_step import advance_real_one_path_symbol

    initial = _state(0)
    received = np.array([1 + 2j] * 8 + [3 - 1j] * 8 + [np.nan + 0j] * 8, dtype=np.complex128)
    first = advance_real_one_path_symbol(
        initial,
        received,
        **_profile_args(0, 40, 40, 24),
        **_operand_cutoff_args(0, 40),
        time_index=0,
        alpha_prime=0.5,
        k_tilde=[[0.2, 0.3]],
        mu0=[[0.0, 0.0]],
        predicted_iq=[[0.0, 0.0]],
        posterior=[1.0],
    )
    second = advance_real_one_path_symbol(
        first.next_state,
        received,
        **_profile_args(1, 40, 40, 24),
        **_operand_cutoff_args(1, 40),
        time_index=1,
        alpha_prime=0.25,
        k_tilde=[[0.1, 0.4]],
        mu0=[[0.3, -0.2]],
        predicted_iq=[[0.0, 0.0]],
        posterior=[1.0],
    )
    assert first.next_state.time_index == 1
    assert second.previous_time_index == 1
    assert second.next_state.time_index == 2
    assert second.next_usable_symbol_index == 2
    assert initial.time_index == 0
    np.testing.assert_array_equal(initial.fluctuating_iq, [[0.4, -0.3]])

    changed_future = received.copy()
    changed_future[16:] = 999 + 999j
    first_changed_future = advance_real_one_path_symbol(
        initial,
        changed_future,
        **_profile_args(0, 40, 40, 24),
        **_operand_cutoff_args(0, 40),
        time_index=0,
        alpha_prime=0.5,
        k_tilde=[[0.2, 0.3]],
        mu0=[[0.0, 0.0]],
        predicted_iq=[[0.0, 0.0]],
        posterior=[1.0],
    )
    np.testing.assert_array_equal(first.next_state.full_iq, first_changed_future.next_state.full_iq)


def test_clock_must_map_pre_observation_estimator_index_to_target_symbol() -> None:
    from hf_tcm.receiver.reconstruction_causal_step import advance_real_one_path_symbol

    with pytest.raises(ValueError, match="time_index.*state.time_index"):
        advance_real_one_path_symbol(
            _state(1),
            np.ones(8, dtype=np.complex128),
            **_profile_args(1, 0, 8, 8),
            **_operand_cutoff_args(1, 0),
            time_index=2,
            alpha_prime=0.5,
            k_tilde=[[0.0, 0.0]],
            mu0=[[0.0, 0.0]],
            predicted_iq=[[0.0, 0.0]],
            posterior=[1.0],
        )


def test_symbol_and_estimator_clock_origins_are_explicit_and_not_converted() -> None:
    from hf_tcm.receiver.reconstruction_causal_step import advance_real_one_path_symbol

    result = advance_real_one_path_symbol(
        _state(10),
        np.array([2.0 + 3.0j] * 8),
        **_profile_args(2, 700, 716, 8),
        **_operand_cutoff_args(2, 700),
        time_index=10,
        alpha_prime=0.5,
        k_tilde=[[0.1, 0.2]],
        mu0=[[0.0, 0.0]],
        predicted_iq=[[0.0, 0.0]],
        posterior=[1.0],
    )
    assert result.processed_symbol_index == 2
    assert result.previous_time_index == 10
    assert result.next_state.time_index == 11
    assert result.next_usable_symbol_index == 3
    assert result.forward_snapshot.estimator_time_index == 11


@pytest.mark.parametrize(
    ("prediction_cutoff", "posterior_cutoff", "error_field"),
    [(108, 107, "prediction_data_cutoff_sample"), (107, 108, "posterior_data_cutoff_sample")],
)
def test_future_dated_prediction_or_posterior_operands_are_rejected(
    prediction_cutoff: int, posterior_cutoff: int, error_field: str
) -> None:
    from hf_tcm.receiver.reconstruction_causal_step import advance_real_one_path_symbol

    with pytest.raises(ValueError, match=error_field):
        advance_real_one_path_symbol(
            _state(0),
            np.ones(8, dtype=np.complex128),
            **_profile_args(0, 100, 100, 8),
            time_index=0,
            alpha_prime=0.5,
            k_tilde=[[0.0, 0.0]],
            mu0=[[0.0, 0.0]],
            predicted_iq=[[0.0, 0.0]],
            posterior=[1.0],
            prediction_data_cutoff_sample=prediction_cutoff,
            posterior_data_cutoff_sample=posterior_cutoff,
        )


def test_truth_like_fixture_metadata_is_not_an_observation_operand() -> None:
    from hf_tcm.receiver.reconstruction_observation import extract_adr012_observed_iq

    received = np.array([0.5 + 1.25j] * 8, dtype=np.complex128)
    first_truth, second_truth = {"h": 0.75}, {"h": -900.0}
    args = _profile_args(0, 7, 7, 8)
    first = extract_adr012_observed_iq(received, **args)
    second = extract_adr012_observed_iq(received, **args)
    np.testing.assert_array_equal(first, second)
    np.testing.assert_allclose(first, [-1.25, 0.5])
    del first_truth, second_truth
    assert "truth" not in inspect.signature(extract_adr012_observed_iq).parameters
    assert "channel_coefficient" not in inspect.signature(extract_adr012_observed_iq).parameters
