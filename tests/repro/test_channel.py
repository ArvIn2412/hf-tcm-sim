from __future__ import annotations

from dataclasses import fields, replace

import numpy as np
import pytest

from hf_tcm.repro.channel_config import (
    ChannelConfig,
    ChannelPathConfig,
    identity_profile,
    multipath_rician_awgn_profile,
    single_path_rician_awgn_profile,
)
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.multipath_channel import apply_integer_delay_paths
from hf_tcm.repro.noise import generate_complex_noise
from hf_tcm.repro.rician_fading import generate_path_coefficients
from hf_tcm.repro.transmitter import run_transmitter


def _tx(bits: str = "001101"):
    return run_transmitter(
        TransmitterConfig(source_mode="manual", frame_symbols=len(bits) // 2, manual_bits=bits)
    )


def _constant_path(delay: int, coefficient: complex) -> ChannelPathConfig:
    return ChannelPathConfig(
        delay_samples=delay,
        average_power=abs(coefficient) ** 2,
        k_factor=0.0,
        los_phase_rad=0.0,
        constant_coefficient=coefficient,
    )


def _config(*paths: ChannelPathConfig, noise_variance: float = 0.0, noise_seed: int = 7):
    return ChannelConfig(
        profile_id="test_project_custom_v1",
        paths=tuple(paths),
        fading_mode="constant",
        noise_model="complex_awgn_sample_domain" if noise_variance else "none",
        noise_complex_variance=noise_variance,
        fading_seed=11,
        noise_seed=noise_seed,
    )


def test_identity_channel_is_exact_and_has_separated_truth() -> None:
    tx = _tx()
    result = run_channel(tx, _config(_constant_path(0, 1 + 0j)))
    np.testing.assert_array_equal(result.receiver_observation.received_samples, tx.tx_samples)
    assert result.evaluation_truth.path_contributions.shape == (1, len(tx.tx_samples))
    assert result.evaluation_truth.noise_samples.shape == tx.tx_samples.shape
    assert not result.receiver_observation.received_samples.flags.writeable
    truth_names = {field.name for field in fields(result.evaluation_truth)}
    observation_names = {field.name for field in fields(result.receiver_observation)}
    assert "coefficients" in truth_names and "noise_samples" in truth_names
    assert not observation_names.intersection(truth_names)
    assert not {
        "coefficients",
        "path_contributions",
        "noise_samples",
        "information_bits",
    }.intersection(observation_names)


def test_constant_complex_gain_uses_independent_scalar_oracle() -> None:
    tx = _tx()
    gain = 0.25 - 0.75j
    expected = np.asarray([gain * complex(value) for value in tx.tx_samples])
    result = run_channel(tx, _config(_constant_path(0, gain)))
    np.testing.assert_allclose(result.evaluation_truth.faded_signal, expected, rtol=0, atol=1e-14)


def test_integer_delay_uses_zero_extension_and_delayed_tail() -> None:
    tx = _tx("0000")
    result = run_channel(tx, _config(_constant_path(3, 1 + 0j)))
    got = result.evaluation_truth.path_contributions[0]
    expected = np.zeros(len(tx.tx_samples) + 3, dtype=np.complex128)
    expected[3:] = tx.tx_samples
    np.testing.assert_array_equal(got, expected)
    assert len(result.receiver_observation.received_samples) == len(tx.tx_samples) + 3
    assert result.evaluation_truth.source_sample_indices[0, :3].tolist() == [-3, -2, -1]


def test_two_path_sum_matches_manual_convolution() -> None:
    tx = _tx("0000")
    first, second = 0.5 + 0.25j, -0.125 + 0.75j
    result = run_channel(
        tx,
        _config(_constant_path(0, first), _constant_path(2, second)),
    )
    expected = np.zeros(len(tx.tx_samples) + 2, dtype=np.complex128)
    for n in range(len(expected)):
        expected[n] = first * (tx.tx_samples[n] if n < len(tx.tx_samples) else 0j)
        if n >= 2:
            source_index = n - 2
            if source_index < len(tx.tx_samples):
                expected[n] += second * tx.tx_samples[source_index]
    np.testing.assert_allclose(result.evaluation_truth.faded_signal, expected, atol=1e-14)
    np.testing.assert_allclose(
        result.receiver_observation.received_samples,
        result.evaluation_truth.faded_signal + result.evaluation_truth.noise_samples,
        rtol=0,
        atol=0,
    )


def test_saved_two_path_reference_fixture_matches_independent_values() -> None:
    import json
    from pathlib import Path

    fixture_path = (
        Path(__file__).resolve().parents[2] / "configs/repro03/two_path_reference_fixture.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    source = np.asarray([complex(*pair) for pair in fixture["source_samples"]])
    delays = tuple(fixture["path_delays_samples"])
    coefficients = np.asarray(
        [complex(*pair) for pair in fixture["path_coefficients"]], dtype=np.complex128
    )
    coeff_history = np.repeat(coefficients[:, None], fixture["output_length"], axis=1)
    _, faded, _ = apply_integer_delay_paths(source, coeff_history, delays)
    expected = np.asarray(
        [complex(*pair) for pair in fixture["expected_received_samples"]], dtype=np.complex128
    )
    np.testing.assert_array_equal(faded, expected)


def test_repro01_sixteen_transition_vectors_have_independent_equation_oracle() -> None:
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "docs/repro/REPRO_01_ENCODER_TEST_VECTORS.json"
    vectors = json.loads(path.read_text(encoding="utf-8"))["transitions"]
    state_order = ((0, 0), (1, 0), (0, 1), (1, 1))
    input_order = ((0, 0), (0, 1), (1, 0), (1, 1))
    assert len(vectors) == 16
    for edge_id, vector in enumerate(vectors):
        state, pair = tuple(vector["state"]), tuple(vector["input"])
        assert state == state_order[edge_id // 4]
        assert pair == input_order[edge_id % 4]
        p1, p2 = state
        u0, u1 = pair
        independently_expected_output = (u0, u1 ^ p2, p1)
        independently_expected_next = (u1, p1)
        assert tuple(vector["output"]) == independently_expected_output
        assert tuple(vector["next"]) == independently_expected_next
        assert state in state_order and pair in input_order


def test_awgn_statistics_match_complex_variance_convention() -> None:
    count, variance = 300_000, 0.4
    noise = generate_complex_noise(count, complex_variance=variance, seed=417)
    i, q = noise.real, noise.imag
    mean_tolerance = 6.0 * np.sqrt(variance / (2 * count))
    variance_tolerance = 6.0 * variance / np.sqrt(2 * count)
    assert abs(float(i.mean())) < mean_tolerance
    assert abs(float(q.mean())) < mean_tolerance
    assert abs(float(i.var() - variance / 2)) < variance_tolerance
    assert abs(float(q.var() - variance / 2)) < variance_tolerance
    assert abs(float(np.mean((i - i.mean()) * (q - q.mean())))) < variance_tolerance
    assert abs(float(np.mean((i[:-1] - i.mean()) * (i[1:] - i.mean())))) < variance_tolerance


def test_zero_variance_noise_and_independent_seeds() -> None:
    assert np.array_equal(generate_complex_noise(20, complex_variance=0.0, seed=1), np.zeros(20))
    path = ChannelPathConfig(delay_samples=0, average_power=1, k_factor=4, los_phase_rad=0.3)
    first = generate_path_coefficients(100, path, fading_mode="rician_ar1", correlation=0.8, seed=4)
    same = generate_path_coefficients(100, path, fading_mode="rician_ar1", correlation=0.8, seed=4)
    other = generate_path_coefficients(100, path, fading_mode="rician_ar1", correlation=0.8, seed=5)
    np.testing.assert_array_equal(first, same)
    assert not np.array_equal(first, other)
    assert not np.array_equal(
        generate_complex_noise(100, complex_variance=0.2, seed=8),
        generate_complex_noise(100, complex_variance=0.2, seed=9),
    )
    path_noise_a = generate_complex_noise(100, complex_variance=0.2, seed=61)
    path_noise_b = generate_complex_noise(100, complex_variance=0.2, seed=61)
    np.testing.assert_array_equal(path_noise_a, path_noise_b)


def test_rician_power_k_factor_and_ar1_correlation() -> None:
    count, power, k, rho, phase = 250_000, 0.75, 3.0, 0.72, 0.4
    path = ChannelPathConfig(delay_samples=0, average_power=power, k_factor=k, los_phase_rad=phase)
    coeff = generate_path_coefficients(
        count, path, fading_mode="rician_ar1", correlation=rho, seed=20261106
    )
    los_mean = np.sqrt(power * k / (k + 1)) * np.exp(1j * phase)
    diffuse_power = float(np.mean(np.abs(coeff - los_mean) ** 2))
    assert abs(diffuse_power - power / (k + 1)) < 0.012
    assert abs(float(np.mean(np.abs(coeff) ** 2)) - power) < 0.02
    diffuse = coeff - los_mean
    corr = np.vdot(diffuse[:-1], diffuse[1:]) / np.vdot(diffuse[:-1], diffuse[:-1])
    assert abs(corr.real - rho) < 0.015
    assert abs(corr.imag) < 0.01
    normalized = diffuse / np.sqrt(power / (k + 1))
    for quadrature in (normalized.real, normalized.imag):
        centered = quadrature - quadrature.mean()
        std = quadrature.std()
        skew = float(np.mean(centered**3) / std**3)
        excess_kurtosis = float(np.mean(centered**4) / std**4 - 3.0)
        assert abs(float(quadrature.mean())) < 0.01
        assert abs(float(quadrature.var()) - 0.5) < 0.01
        assert abs(skew) < 0.03
        assert abs(excess_kurtosis) < 0.04


def test_static_rician_is_constant_and_single_path_profile_runs() -> None:
    path = ChannelPathConfig(delay_samples=0, average_power=1.0, k_factor=2.0, los_phase_rad=0.4)
    coeff = generate_path_coefficients(
        120, path, fading_mode="rician_static", correlation=0.0, seed=81
    )
    assert np.all(coeff == coeff[0])
    tx = _tx()
    result = run_channel(tx, single_path_rician_awgn_profile())
    assert result.evaluation_truth.coefficients.shape == (1, len(tx.tx_samples))
    assert not np.array_equal(result.receiver_observation.received_samples, tx.tx_samples)


def test_named_profiles_are_explicitly_reconstructed_and_delay_powers() -> None:
    identity = identity_profile()
    single = single_path_rician_awgn_profile()
    multi = multipath_rician_awgn_profile()
    assert identity.noise_model == "none"
    assert single.paths[0].delay_samples == 0
    assert len(multi.paths) == 2
    assert multi.paths[1].delay_samples == 3
    assert multi.paths[1].average_power == 0.25


def test_public_observation_has_only_configured_public_noise_value() -> None:
    tx = _tx()
    config = ChannelConfig(
        profile_id="test_reveal_noise_v1",
        paths=(_constant_path(0, 1 + 0j),),
        fading_mode="constant",
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=0.01,
        fading_seed=1,
        noise_seed=2,
        reveal_noise_variance=True,
    )
    observation = run_channel(tx, config).receiver_observation
    assert observation.noise_complex_variance == 0.01
    assert observation.profile_id == config.profile_id


def test_config_rejects_fractional_delay_and_bad_power() -> None:
    with pytest.raises(ValueError, match="delay_samples"):
        ChannelPathConfig(delay_samples=0.5, average_power=1, k_factor=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="average_power"):
        ChannelPathConfig(delay_samples=0, average_power=0, k_factor=1)


def test_channel_arrays_are_reproducible_and_seeds_are_separated() -> None:
    tx = _tx()
    path = ChannelPathConfig(delay_samples=1, average_power=1, k_factor=2, los_phase_rad=0.2)
    base = ChannelConfig(
        profile_id="seed_separation_v1",
        paths=(path,),
        fading_mode="rician_ar1",
        correlation=0.5,
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=0.02,
        fading_seed=11,
        noise_seed=22,
    )
    a, b = run_channel(tx, base), run_channel(tx, base)
    np.testing.assert_array_equal(a.evaluation_truth.coefficients, b.evaluation_truth.coefficients)
    np.testing.assert_array_equal(
        a.evaluation_truth.noise_samples, b.evaluation_truth.noise_samples
    )
    changed_noise = run_channel(tx, replace(base, noise_seed=23))
    np.testing.assert_array_equal(
        a.evaluation_truth.coefficients, changed_noise.evaluation_truth.coefficients
    )
    assert not np.array_equal(
        a.evaluation_truth.noise_samples, changed_noise.evaluation_truth.noise_samples
    )
    changed_fading = run_channel(tx, replace(base, fading_seed=12))
    np.testing.assert_array_equal(
        a.evaluation_truth.noise_samples, changed_fading.evaluation_truth.noise_samples
    )
    assert not np.array_equal(
        a.evaluation_truth.coefficients, changed_fading.evaluation_truth.coefficients
    )
