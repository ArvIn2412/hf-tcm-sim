import numpy as np
import pytest

from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.energy_experiment import EnergyTrialSpec, run_energy_trial
from hf_tcm.repro.transmitter import run_transmitter


@pytest.mark.parametrize("amplitude", [0.25, 1.0, 2.5])
def test_discrete_energy_independent_of_payload(amplitude):
    t = run_transmitter(
        TransmitterConfig(
            source_mode="manual", frame_symbols=4, manual_bits="00101101", amplitude=amplitude
        )
    )
    assert np.sum(t.tx_samples.real**2 + t.tx_samples.imag**2) == pytest.approx(32 * amplitude**2)
    assert np.sum(abs(t.tx_samples) ** 2) / 8 == pytest.approx(4 * amplitude**2)


def test_noise_and_paths_independent_of_amplitude():
    tx = [
        run_transmitter(
            TransmitterConfig(source_mode="seeded_random", frame_symbols=2000, seed=7, amplitude=a)
        )
        for a in [1.0, 3.0]
    ]
    c = ChannelConfig(
        profile_id="energy-validation",
        paths=(ChannelPathConfig(0, 0.8, 4), ChannelPathConfig(3, 0.2, 1)),
        fading_mode="rician_ar1",
        correlation=0.98,
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=1.0,
        fading_seed=13,
        noise_seed=17,
    )
    a, b = [run_channel(t, c) for t in tx]
    np.testing.assert_array_equal(
        a.evaluation_truth.noise_samples, b.evaluation_truth.noise_samples
    )
    np.testing.assert_array_equal(a.evaluation_truth.coefficients, b.evaluation_truth.coefficients)
    w = a.evaluation_truth.noise_samples
    n = len(w)
    assert abs(np.mean(abs(w) ** 2) - 1) < 6 / np.sqrt(n)
    assert abs(np.var(w.real) - 0.5) < 6 * np.sqrt(0.5 / n)
    assert sum(p.average_power for p in c.paths) == 1


@pytest.mark.parametrize("scenario", ["awgn", "static", "rician"])
def test_equal_gamma_scaled_observation_and_decoded_pairs(tmp_path, scenario):
    specs = [
        EnergyTrialSpec("validation", scenario, sweep, 12.0, 0, 0, 32)
        for sweep in ["amplitude", "noise"]
    ]
    rows = [run_energy_trial(s, tmp_path, seed_override=[11, 12, 13]) for s in specs]
    base = tmp_path / "validation" / scenario
    a = np.load(base / "amplitude/p00/t0000/arrays.npz")
    b = np.load(base / "noise/p00/t0000/arrays.npz")
    np.testing.assert_allclose(
        a["received_samples"] / specs[0].amplitude, b["received_samples"], rtol=1e-13, atol=1e-13
    )
    np.testing.assert_array_equal(a["coefficients"], b["coefficients"])
    for arm in ["joint", "b0"] + ([] if scenario == "rician" else ["b1"]):
        np.testing.assert_array_equal(a[arm + "_decoded_bits"], b[arm + "_decoded_bits"])
        mismatch = a[arm + "_decoded_bits"] != a["information_bits"]
        assert rows[0]["bit_errors"][arm] == sum(mismatch)
        assert rows[0]["pair_errors"][arm] == sum(
            any(mismatch[j : j + 2]) for j in range(0, len(mismatch), 2)
        )
        assert (
            rows[0]["pair_errors"][arm]
            <= rows[0]["bit_errors"][arm]
            <= 2 * rows[0]["pair_errors"][arm]
        )
    assert rows[0]["receiver_observation_hashes"]["joint"] == rows[0]["observation_sha256"]
    again = run_energy_trial(specs[0], tmp_path, seed_override=[11, 12, 13])
    assert again == rows[0]
    p = base / "amplitude/p00/t0000/arrays.npz"
    p.write_bytes(b"bad")
    with pytest.raises(ValueError, match="corrupt"):
        run_energy_trial(specs[0], tmp_path, seed_override=[11, 12, 13])


def test_independent_seed_domains():
    seeds = [
        EnergyTrialSpec(p, "awgn", s, 6.0, i, t).seeds
        for p in ["pilot", "confirmatory"]
        for s in ["amplitude", "noise"]
        for i in range(2)
        for t in range(2)
    ]
    assert len(set(x for row in seeds for x in row)) == 3 * len(seeds)


def test_resource_probe_preserves_legacy_ctypes_contract():
    import os

    from hf_tcm.evaluation.m5h_pilot_runner import _process_rss_windows
    from hf_tcm.repro.energy_experiment import peak_working_set_bytes

    before = _process_rss_windows(os.getpid())
    measured = peak_working_set_bytes()
    after = _process_rss_windows(os.getpid())
    if os.name == "nt":
        assert before is not None and measured is not None and after is not None
        assert before > 0 and measured > 0 and after > 0
