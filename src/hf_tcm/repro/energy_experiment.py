"""Isolated energy experiment orchestration over verified REPRO algorithms."""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.repro.adaptive_multipath_config import (
    AdaptiveMultipathReceiverConfig,
    AdaptivePathConfig,
)
from hf_tcm.repro.atomic_io import atomic_replace_bytes
from hf_tcm.repro.adaptive_multipath_receiver import run_adaptive_multipath_receiver
from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.receiver_config import ReceiverFrontEndConfig, SeparateReceiverConfig
from hf_tcm.repro.repro08_channel_aware_hard import (
    PublicStaticTap,
    Repro08HardReceiverConfig,
    run_channel_aware_hard_receiver,
)
from hf_tcm.repro.separate_receiver import run_separate_receiver
from hf_tcm.repro.transmitter import run_transmitter


def peak_working_set_bytes():
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (n, ctypes.c_size_t)
            for n in [
                "PeakWorkingSetSize",
                "WorkingSetSize",
                "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage",
                "PagefileUsage",
                "PeakPagefileUsage",
            ]
        ]

    c = Counters()
    c.cb = ctypes.sizeof(c)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(Counters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = kernel.GetCurrentProcess()
    if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(c), c.cb):
        return None
    return int(c.PeakWorkingSetSize)


def digest(b):
    return hashlib.sha256(b).hexdigest()


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def atomic_json(p, x):
    p = Path(p)
    atomic_replace_bytes(p, canonical(x))


@dataclass(frozen=True)
class EnergyTrialSpec:
    phase: str
    scenario: str
    sweep: str
    gamma_db: float
    point_index: int
    trial_index: int
    frame_symbols: int = 256
    root_seed: int = 83101
    noise_reference_variance: float | None = None
    amplitude_reference: float | None = None
    channel_settings: dict[str, Any] | None = None
    receiver_arms: tuple[str, ...] | None = None

    def __post_init__(self):
        if (
            self.phase not in {"pilot", "confirmatory", "long", "validation", "gui"}
            or self.scenario not in {"awgn", "static", "rician"}
            or self.sweep not in {"amplitude", "noise"}
        ):
            raise ValueError("invalid experiment domain")
        if (
            not np.isfinite(self.gamma_db)
            or self.frame_symbols < 1
            or min(self.root_seed, self.point_index, self.trial_index) < 0
        ):
            raise ValueError("invalid numeric configuration")
        if self.noise_reference_variance is not None and (
            not np.isfinite(self.noise_reference_variance) or self.noise_reference_variance <= 0
        ):
            raise ValueError("noise_reference_variance must be positive and finite")
        if self.amplitude_reference is not None and (
            not np.isfinite(self.amplitude_reference) or self.amplitude_reference <= 0
        ):
            raise ValueError("amplitude_reference must be positive and finite")
        if self.receiver_arms is not None:
            if (
                "joint" not in self.receiver_arms
                or not set(self.receiver_arms) <= {"joint", "b0", "b1"}
                or not set(self.receiver_arms) & {"b0", "b1"}
                or len(set(self.receiver_arms)) != len(self.receiver_arms)
            ):
                raise ValueError("receiver_arms must include joint and at least one of b0/b1")
            if self.scenario == "rician" and "b1" in self.receiver_arms:
                raise ValueError("B1 is unavailable for Rician fading")
        if self.channel_settings is not None:
            self._validate_channel_settings(self.channel_settings)

    def _validate_channel_settings(self, settings: dict[str, Any]) -> None:
        allowed = {
            "channel_profile",
            "delays_samples",
            "path_coefficients",
            "path_powers",
            "rician_k_factors",
            "los_phases_rad",
            "fading_correlation",
        }
        if not isinstance(settings, dict) or set(settings) != allowed:
            raise ValueError(
                "channel_settings must contain the complete scientific GUI channel profile"
            )
        profile = settings["channel_profile"]
        if profile not in {
            "identity",
            "awgn",
            "static_single_path",
            "static_multipath",
            "rician_ar1_multipath",
        }:
            raise ValueError("unsupported GUI channel profile for energy study")
        expected_scenario = (
            "rician"
            if profile == "rician_ar1_multipath"
            else ("static" if profile.startswith("static_") else "awgn")
        )
        if expected_scenario != self.scenario:
            raise ValueError("channel profile does not match the energy scenario")
        delays = settings["delays_samples"]
        count = len(delays)
        if not count or any(type(delay) is not int or delay < 0 for delay in delays):
            raise ValueError("channel delays must be non-negative integer sample indices")
        if profile in {"identity", "awgn"} and tuple(delays) != (0,):
            raise ValueError("identity and AWGN energy profiles require one zero-delay path")
        if profile == "static_single_path" and count != 1:
            raise ValueError("static single-path energy profile requires exactly one path")
        if profile == "static_multipath" and count < 2:
            raise ValueError("static multipath energy profile requires at least two paths")
        path_fields = ("path_powers", "rician_k_factors", "los_phases_rad")
        if profile != "rician_ar1_multipath":
            path_fields = (*path_fields, "path_coefficients")
        if any(len(settings[key]) != count for key in path_fields):
            raise ValueError("energy channel path parameters must match the delay count")
        if profile == "rician_ar1_multipath":
            if any(not np.isfinite(value) or value <= 0 for value in settings["path_powers"]):
                raise ValueError("Rician path powers must be positive and finite")
            if any(not np.isfinite(value) or value < 0 for value in settings["rician_k_factors"]):
                raise ValueError("Rician K factors must be non-negative and finite")
            if not 0 <= float(settings["fading_correlation"]) < 1:
                raise ValueError("fading correlation must be in [0, 1)")
        else:
            for pair in settings["path_coefficients"]:
                if len(pair) != 2 or not all(np.isfinite(value) for value in pair):
                    raise ValueError("static path coefficients must be finite I/Q pairs")
                if complex(*pair) == 0j:
                    raise ValueError("static path coefficients must be nonzero")

    @property
    def amplitude(self):
        if self.sweep == "amplitude":
            variance = self.noise_reference_variance or 1.0
            return float(np.sqrt(variance * 10 ** (self.gamma_db / 10) / 4))
        return float(self.amplitude_reference or 1.0)

    @property
    def variance(self):
        if self.sweep == "amplitude":
            return float(self.noise_reference_variance or 1.0)
        return float(4 * (self.amplitude_reference or 1.0) ** 2 / 10 ** (self.gamma_db / 10))

    @property
    def seeds(self):
        domain = [
            {"pilot": 1, "confirmatory": 2, "long": 3, "validation": 4, "gui": 5}[self.phase],
            {"awgn": 1, "static": 2, "rician": 3}[self.scenario],
            {"amplitude": 1, "noise": 2}[self.sweep],
            self.point_index,
            self.trial_index,
        ]
        return [
            int(
                np.random.SeedSequence([self.root_seed, *domain, i]).generate_state(
                    1, dtype=np.uint64
                )[0]
            )
            for i in range(3)
        ]


def run_energy_trial(spec: EnergyTrialSpec, output_root: Path, *, seed_override=None):
    cfg = {key: value for key, value in asdict(spec).items() if value is not None}
    cfg["seed_override"] = seed_override
    cfg_hash = digest(canonical(cfg))
    dest = (
        Path(output_root)
        / spec.phase
        / spec.scenario
        / spec.sweep
        / f"p{spec.point_index:02d}"
        / f"t{spec.trial_index:04d}"
    )
    if (dest / "manifest.json").exists():
        m = json.loads((dest / "manifest.json").read_text())
        if m["config_sha256"] != cfg_hash:
            raise ValueError("immutable trial config mismatch")
        for n, h in m["files"].items():
            if digest((dest / n).read_bytes()) != h:
                raise ValueError("corrupt trial payload")
        return json.loads((dest / "record.json").read_text())
    wall_started_ns = time.perf_counter_ns()
    cpu_started_ns = time.process_time_ns()
    bits_seed, fading_seed, noise_seed = seed_override or spec.seeds
    A = spec.amplitude
    variance = spec.variance
    tx = run_transmitter(
        TransmitterConfig(
            source_mode="seeded_random",
            frame_symbols=spec.frame_symbols,
            seed=bits_seed,
            amplitude=A,
        )
    )
    settings = spec.channel_settings
    if settings is None:
        powers = (1.0,) if spec.scenario == "awgn" else (0.8, 0.2)
        delays = (0,) if spec.scenario == "awgn" else (0, 3)
        phases = (0.0,) if spec.scenario == "awgn" else (0.0, 0.7)
        ks = (4.0, 1.0)
        gains = tuple(np.sqrt(p) * np.exp(1j * ph) for p, ph in zip(powers, phases))
        channel_profile = "energy01_" + spec.scenario
    else:
        delays = tuple(settings["delays_samples"])
        phases = tuple(float(value) for value in settings["los_phases_rad"])
        ks = tuple(float(value) for value in settings["rician_k_factors"])
        gains = tuple(complex(*pair) for pair in settings["path_coefficients"])
        powers = (
            tuple(float(value) for value in settings["path_powers"])
            if spec.scenario == "rician"
            else tuple(float(abs(value) ** 2) for value in gains)
        )
        channel_profile = "energy_gui_" + str(settings["channel_profile"])
    is_rician = spec.scenario == "rician"
    if is_rician:
        paths = tuple(
            ChannelPathConfig(d, p, k, ph) for d, p, k, ph in zip(delays, powers, ks, phases)
        )
        ap = tuple(
            AdaptivePathConfig(d, average_power=p, k_factor=k, los_phase_rad=ph)
            for d, p, k, ph in zip(delays, powers, ks, phases)
        )
    else:
        paths = tuple(
            ChannelPathConfig(d, p, 0.0, ph, constant_coefficient=complex(h))
            for d, p, ph, h in zip(delays, powers, phases, gains)
        )
        ap = tuple(
            AdaptivePathConfig(d, prior_mean=complex(h), prior_variance=1.0 if settings else 0.25)
            for d, h in zip(delays, gains)
        )
    cc = ChannelConfig(
        profile_id=channel_profile,
        paths=paths,
        fading_mode="rician_ar1" if spec.scenario == "rician" else "constant",
        correlation=(float(settings["fading_correlation"]) if settings else 0.98)
        if is_rician
        else 0.0,
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=variance,
        fading_seed=fading_seed,
        noise_seed=noise_seed,
    )
    channel = run_channel(tx, cc)
    obs = channel.receiver_observation
    jc = AdaptiveMultipathReceiverConfig(
        expected_symbol_count=spec.frame_symbols,
        paths=ap,
        channel_mode="rician_ar1" if spec.scenario == "rician" else "unknown_static",
        observation_noise_variance=variance,
        correlation=(float(settings["fading_correlation"]) if settings else 0.98)
        if is_rician
        else 1.0,
        amplitude=A,
        trace_output_mode="compact",
    )
    bc = SeparateReceiverConfig(
        expected_symbol_count=spec.frame_symbols,
        front_end=ReceiverFrontEndConfig(amplitude=A),
        decoder_mode="finite_depth",
        traceback_depth=20,
        trace_output_mode="compact",
    )
    results = {}
    runtime = {}
    receiver_cpu_runtime = {}
    available = {
        "joint": (run_adaptive_multipath_receiver, jc),
        "b0": (run_separate_receiver, bc),
    }
    active_arms = spec.receiver_arms or (("joint", "b0") if is_rician else ("joint", "b0", "b1"))
    for arm in active_arms:
        if arm not in available:
            continue
        fn, config = available[arm]
        wall_start_ns = time.perf_counter_ns()
        cpu_start_ns = time.process_time_ns()
        results[arm] = fn(obs, config)
        runtime[arm] = (time.perf_counter_ns() - wall_start_ns) / 1e9
        receiver_cpu_runtime[arm] = (time.process_time_ns() - cpu_start_ns) / 1e9
    if "b1" in active_arms:
        b1c = Repro08HardReceiverConfig(
            spec.frame_symbols,
            tuple(PublicStaticTap(d, complex(h)) for d, h in zip(delays, gains, strict=True)),
            amplitude=A,
        )
        wall_start_ns = time.perf_counter_ns()
        cpu_start_ns = time.process_time_ns()
        results["b1"] = run_channel_aware_hard_receiver(obs, b1c)
        runtime["b1"] = (time.perf_counter_ns() - wall_start_ns) / 1e9
        receiver_cpu_runtime["b1"] = (time.process_time_ns() - cpu_start_ns) / 1e9
    reference = tx.information_bits
    bits = reference.size
    pairs = bits // 2
    be = {}
    pe = {}
    fer = {}
    arrays = {
        "information_bits": reference,
        "tx_samples": tx.tx_samples,
        "received_samples": obs.received_samples,
        "noise_samples": channel.evaluation_truth.noise_samples,
        "coefficients": channel.evaluation_truth.coefficients,
    }
    hashes = {}
    for arm, result in results.items():
        decoded = result.decoded_information_bits
        if decoded.shape != reference.shape:
            raise ValueError("payload alignment mismatch")
        errors = decoded != reference
        be[arm] = int(errors.sum())
        pe[arm] = int(errors.reshape(-1, 2).any(axis=1).sum())
        fer[arm] = int(be[arm] > 0)
        assert pe[arm] <= be[arm] <= 2 * pe[arm]
        arrays[arm + "_decoded_bits"] = decoded
        hashes[arm] = result.observation_sha256
        if hashes[arm] != obs.sha256:
            raise ValueError("paired observation violation")
    energy = float(np.vdot(tx.tx_samples, tx.tx_samples).real)
    eb = energy / bits
    assert np.isclose(eb, 4 * A * A)
    receiver_configs = {
        arm: available[arm][1].to_dict() for arm in ("joint", "b0") if arm in results
    }
    if "b1" in results:
        receiver_configs["b1"] = results["b1"].receiver_config
    raw_wall_elapsed_seconds = (time.perf_counter_ns() - wall_started_ns) / 1e9
    process_cpu_seconds = (time.process_time_ns() - cpu_started_ns) / 1e9
    record = {
        **cfg,
        "amplitude": A,
        "noise_variance": variance,
        "tx_energy": energy,
        "eb_d": eb,
        "gamma_measured_db": float(10 * np.log10(eb / variance)),
        "bits": bits,
        "pairs": pairs,
        "bit_errors": be,
        "pair_errors": pe,
        "frame_errors": fer,
        "ber": {a: v / bits for a, v in be.items()},
        "ser": {a: v / pairs for a, v in pe.items()},
        "runtime_seconds": runtime,
        "receiver_process_cpu_seconds": receiver_cpu_runtime,
        "elapsed_seconds": raw_wall_elapsed_seconds,
        "raw_wall_elapsed_seconds": raw_wall_elapsed_seconds,
        "process_cpu_seconds": process_cpu_seconds,
        "seeds": {"bits": bits_seed, "fading": fading_seed, "noise": noise_seed},
        "observation_sha256": obs.sha256,
        "receiver_observation_hashes": hashes,
        "empirical_noise_power": float(np.mean(abs(channel.evaluation_truth.noise_samples) ** 2)),
        "empirical_path_powers": np.mean(
            abs(channel.evaluation_truth.coefficients) ** 2, axis=1
        ).tolist(),
        "path_powers": powers,
        "delays": delays,
        "rician_k": ks if is_rician else None,
        "correlation": (float(settings["fading_correlation"]) if settings else 0.98)
        if is_rician
        else None,
        "paper_exact": False,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "status": "completed",
        "peak_working_set_process_bytes": peak_working_set_bytes(),
        "saved_array_bytes": sum(v.nbytes for v in arrays.values()),
        "receiver_configs": receiver_configs,
        "channel_config": cc.to_dict(),
    }
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    atomic_replace_bytes(dest / "arrays.npz", buffer.getvalue())
    atomic_json(dest / "record.json", record)
    atomic_json(dest / "config.json", cfg)
    atomic_json(
        dest / "manifest.json",
        {
            "config_sha256": cfg_hash,
            "files": {
                n: digest((dest / n).read_bytes())
                for n in ["record.json", "arrays.npz", "config.json"]
            },
        },
    )
    return json.loads(canonical(record))
