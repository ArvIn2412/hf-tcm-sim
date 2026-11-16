from __future__ import annotations

import numpy as np
import pytest

from hf_tcm.evaluation.controlled_piecewise_real_gain import (
    FRAME_SYMBOLS,
    HIGH_GAIN,
    LOW_GAIN,
    SAMPLES_PER_SYMBOL,
    SWITCH_SYMBOL_INDEX,
    apply_symbol_gain_schedule,
    build_gain_schedule,
    generate_controlled_gain_received,
)


def test_three_schedules_have_exact_switch_and_equal_frame_average_energy() -> None:
    p0 = build_gain_schedule("P0_CONSTANT")
    p1 = build_gain_schedule("P1_HIGH_TO_LOW")
    p2 = build_gain_schedule("P2_LOW_TO_HIGH")

    assert p0.shape == p1.shape == p2.shape == (256,)
    assert np.all(p0 == 0.75)
    assert np.all(p1[:128] == HIGH_GAIN)
    assert np.all(p1[128:] == LOW_GAIN)
    assert np.all(p2[:128] == LOW_GAIN)
    assert np.all(p2[128:] == HIGH_GAIN)
    assert p1[127] == HIGH_GAIN and p1[128] == LOW_GAIN
    assert p2[127] == LOW_GAIN and p2[128] == HIGH_GAIN
    assert np.all(np.isfinite(np.stack((p0, p1, p2))))
    assert np.all(np.stack((p0, p1, p2)) > 0.0)
    assert np.mean(p0 * p0) == pytest.approx(0.75**2, abs=1e-15)
    assert np.mean(p1 * p1) == pytest.approx(0.75**2, abs=1e-15)
    assert np.mean(p2 * p2) == pytest.approx(0.75**2, abs=1e-15)
    assert np.array_equal(np.sort(p1), np.sort(p2))
    assert SWITCH_SYMBOL_INDEX == 128
    assert FRAME_SYMBOLS == 256


def test_short_explicit_fixture_matches_independent_scalar_channel_oracle() -> None:
    waveform = np.asarray([1 + 2j, -1 + 0.5j, 0.25 - 1j, 2 - 0.25j], dtype=np.complex128)
    noise = np.asarray([0.1 - 0.2j, -0.3 + 0.4j, 0.5 + 0.1j, -0.2 - 0.6j])
    gains = np.asarray([0.5, 0.5, 1.25, 1.25], dtype=np.float64)
    repeated = np.repeat(gains, SAMPLES_PER_SYMBOL)
    waveform_samples = np.repeat(waveform, SAMPLES_PER_SYMBOL)
    noise_samples = np.repeat(noise, SAMPLES_PER_SYMBOL)

    received = apply_symbol_gain_schedule(waveform_samples, noise_samples, gains)
    expected = np.asarray(
        [repeated[n] * waveform_samples[n] + noise_samples[n] for n in range(32)],
        dtype=np.complex128,
    )

    np.testing.assert_array_equal(received, expected)
    assert received.shape == (32,)
    assert received.dtype == np.complex128
    assert received.flags.writeable is False


def test_explicit_8psk_symbol_zoh_fixture_matches_scalar_profile_oracle() -> None:
    from hf_tcm.modulation.psk8 import constellation
    from hf_tcm.receiver.iq import symbols_to_iq_waveform

    points = constellation()
    symbol_indices = (0, 3, 7, 2)
    symbols = points[np.asarray(symbol_indices, dtype=np.intp)]
    in_phase, quadrature = symbols_to_iq_waveform(symbols, samples_per_symbol=8)
    waveform = in_phase + 1j * quadrature
    noise_by_symbol = np.asarray(
        [0.01 - 0.02j, -0.03 + 0.04j, 0.05 + 0.01j, -0.02 - 0.06j],
        dtype=np.complex128,
    )
    noise = np.repeat(noise_by_symbol, 8)
    gains = np.asarray([HIGH_GAIN, HIGH_GAIN, LOW_GAIN, LOW_GAIN])

    received = apply_symbol_gain_schedule(waveform, noise, gains)
    expected = np.asarray(
        [gains[n // 8] * waveform[n] + noise[n] for n in range(32)],
        dtype=np.complex128,
    )

    np.testing.assert_array_equal(received, expected)
    for symbol_index in range(4):
        assert np.all(waveform[symbol_index * 8 : (symbol_index + 1) * 8] == symbols[symbol_index])


def test_constant_profile_matches_existing_constant_gain_expression_exactly() -> None:
    waveform = np.asarray(
        [complex((index - 8) / 13, (index % 5 - 2) / 7) for index in range(256 * 8)],
        dtype=np.complex128,
    )
    noise = np.asarray(
        [complex((index % 3 - 1) / 19, (index % 4 - 2) / 23) for index in range(256 * 8)],
        dtype=np.complex128,
    )
    expected = np.asarray(0.75 * waveform + noise, dtype=np.complex128)

    actual = generate_controlled_gain_received(waveform, noise, "P0_CONSTANT")

    np.testing.assert_array_equal(actual, expected)
    assert np.array_equal(actual[1024:1032], expected[1024:1032])


def test_zero_noise_oracle_is_exact_piecewise_gain_times_waveform() -> None:
    waveform = np.asarray(
        [complex((index - 1024) / 97, (index % 19 - 9) / 83) for index in range(2048)],
        dtype=np.complex128,
    )
    zero_noise = np.zeros(2048, dtype=np.complex128)

    for profile_id in ("P0_CONSTANT", "P1_HIGH_TO_LOW", "P2_LOW_TO_HIGH"):
        gains = build_gain_schedule(profile_id)
        actual = generate_controlled_gain_received(waveform, zero_noise, profile_id)
        expected = np.asarray(
            [gains[index // SAMPLES_PER_SYMBOL] * waveform[index] for index in range(2048)],
            dtype=np.complex128,
        )
        np.testing.assert_array_equal(actual, expected)


def test_profile_application_reuses_exact_waveform_and_noise_without_rng(monkeypatch) -> None:
    waveform = np.asarray([complex(index / 10, -index / 17) for index in range(256 * 8)])
    noise = np.asarray([complex((index % 5) / 31, -(index % 7) / 37) for index in range(256 * 8)])

    def forbidden_rng(*args, **kwargs):
        raise AssertionError("M10a channel adapter must not create random streams")

    monkeypatch.setattr(np.random, "default_rng", forbidden_rng)
    received = {
        profile: generate_controlled_gain_received(waveform, noise, profile)
        for profile in ("P0_CONSTANT", "P1_HIGH_TO_LOW", "P2_LOW_TO_HIGH")
    }

    assert all(value.shape == (2048,) for value in received.values())
    assert all(value.dtype == np.complex128 for value in received.values())
    assert all(not value.flags.writeable for value in received.values())
    expected_p1_at_switch = LOW_GAIN * waveform[1024] + noise[1024]
    expected_p2_at_switch = HIGH_GAIN * waveform[1024] + noise[1024]
    assert received["P1_HIGH_TO_LOW"][1024] == expected_p1_at_switch
    assert received["P2_LOW_TO_HIGH"][1024] == expected_p2_at_switch


@pytest.mark.parametrize(
    ("waveform", "noise", "gains"),
    [
        (np.ones(7, dtype=np.complex128), np.zeros(7, dtype=np.complex128), np.ones(1)),
        (np.ones(8, dtype=np.complex128), np.zeros(8, dtype=np.complex128), np.asarray([0.0])),
        (np.ones(8, dtype=np.complex128), np.zeros(8, dtype=np.complex128), np.asarray([np.nan])),
    ],
)
def test_symbol_gain_adapter_rejects_partial_symbol_or_invalid_gain(
    waveform: np.ndarray, noise: np.ndarray, gains: np.ndarray
) -> None:
    with pytest.raises(ValueError):
        apply_symbol_gain_schedule(waveform, noise, gains)


def test_unknown_gain_profile_is_not_silently_defaulted() -> None:
    with pytest.raises(ValueError, match="unknown gain profile"):
        build_gain_schedule("P3_GRADUAL")


def test_real_receiver_sees_only_received_samples_and_keeps_causal_clocks() -> None:
    from hf_tcm.evaluation.m9b_fixed_policy_evaluation_runner import (
        _receiver_configuration,
        _receiver_kwargs,
        resolve_m9_clock_origins,
    )
    from hf_tcm.receiver.reconstruction_conditional_decode import (
        decode_reconstruction_conditional_sequence,
    )

    waveform = np.asarray(
        [complex((index % 29 - 14) / 47, (index % 17 - 8) / 53) for index in range(2048)],
        dtype=np.complex128,
    )
    noise = np.asarray(
        [complex((index % 7 - 3) / 101, (index % 11 - 5) / 107) for index in range(2048)],
        dtype=np.complex128,
    )
    policies = (
        {
            "candidate_id": "historical_frozen_B",
            "alpha_prime": 1.0,
            "k_tilde": [0.0, 0.0],
            "mu0": [0.0, 0.0],
            "initial_fluctuating_iq": [0.42, 0.91],
            "initial_full_iq": [0.42, 0.91],
            "beta": 0.7,
        },
        {
            "candidate_id": "anch_a085_k025",
            "alpha_prime": 0.85,
            "k_tilde": [0.0875, -0.05],
            "mu0": [0.42, 0.91],
            "initial_fluctuating_iq": [0.0, 0.0],
            "initial_full_iq": [0.42, 0.91],
            "beta": 0.7,
        },
    )
    receiver_config = _receiver_configuration()
    clocks = resolve_m9_clock_origins(receiver_config)
    forbidden = {
        "channel_truth",
        "ChannelTruth",
        "true_gain",
        "gain_schedule",
        "switch_index",
        "reference_bits",
    }

    outputs = {}
    invocations = {}
    for profile_id in ("P0_CONSTANT", "P1_HIGH_TO_LOW", "P2_LOW_TO_HIGH"):
        received = generate_controlled_gain_received(waveform, noise, profile_id)
        for policy in policies:
            kwargs = _receiver_kwargs(
                policy=policy,
                received=received,
                receiver_configuration=receiver_config,
                clocks=clocks,
            )
            assert forbidden.isdisjoint(kwargs)
            outputs[(profile_id, policy["candidate_id"])] = (
                decode_reconstruction_conditional_sequence(**kwargs)
            )
            invocations[(profile_id, policy["candidate_id"])] = kwargs

    for profile_id, result in outputs.items():
        assert result.candidate_metrics.shape == (256, 16)
        assert result.final_posterior.shape == (16,)
        assert np.isclose(np.sum(result.final_posterior), 1.0, rtol=0.0, atol=1e-12)
        assert invocations[profile_id]["initial_estimator_time_index"] == 0
        assert invocations[profile_id]["first_symbol_index"] == 0
        assert invocations[profile_id]["received_start_sample"] == 0
        assert all(
            row.absolute_symbol_index == index
            and row.estimator_time_index == index
            and row.sample_indices == tuple(range(index * 8, index * 8 + 8))
            and row.prediction_cutoff_sample_index == index * 8 - 1
            and row.observation_cutoff_sample_index == index * 8 + 7
            for index, row in enumerate(result.metric_provenance)
        )

    for profile_id in ("P0_CONSTANT", "P1_HIGH_TO_LOW", "P2_LOW_TO_HIGH"):
        b = outputs[(profile_id, "historical_frozen_B")]
        anchored = outputs[(profile_id, "anch_a085_k025")]
        np.testing.assert_array_equal(b.candidate_metrics[0], anchored.candidate_metrics[0])

    p1 = invocations[("P1_HIGH_TO_LOW", "historical_frozen_B")]
    changed_tail = np.array(p1["received"], copy=True)
    changed_tail[20 * SAMPLES_PER_SYMBOL :] += 0.25 - 0.125j
    changed_tail.setflags(write=False)
    p1_tail_changed = dict(p1)
    p1_tail_changed["received"] = changed_tail
    changed_result = decode_reconstruction_conditional_sequence(**p1_tail_changed)
    np.testing.assert_array_equal(
        changed_result.candidate_metrics[:20],
        outputs[("P1_HIGH_TO_LOW", "historical_frozen_B")].candidate_metrics[:20],
    )
