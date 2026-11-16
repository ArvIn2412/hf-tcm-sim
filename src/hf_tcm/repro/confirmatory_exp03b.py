"""Versioned RNG provenance helpers for SCIENTIFIC-EXP-03B confirmatory data."""

from __future__ import annotations

from typing import Any, Literal

import numpy as np

from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.energy_experiment import EnergyTrialSpec
from hf_tcm.repro.metric_experiment import MetricTrialSpec

_METRIC_STREAM_IDS = (0, 1, 2)


def derive_metric_stream_seeds(
    root_seed: int, scenario_id: int, point_index: int, trial_index: int
) -> tuple[int, int, int]:
    """Derive independent bits/channel/noise seeds in the frozen 03B domain."""
    values = (root_seed, scenario_id, point_index, trial_index)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("seed domain fields must be nonnegative integers")
    if root_seed >= 2**64:
        raise ValueError("root_seed must fit an unsigned 64-bit integer")
    seeds = tuple(
        int(
            np.random.SeedSequence(
                [root_seed, 0x03B, scenario_id, point_index, trial_index, stream_id]
            ).generate_state(1, dtype=np.uint64)[0]
        )
        for stream_id in _METRIC_STREAM_IDS
    )
    if len(set(seeds)) != len(seeds):
        raise RuntimeError("derived metric stream seeds collided")
    return seeds


def derive_system_stream_seeds(
    root_seed: int,
    scenario: Literal["awgn", "static", "rician"],
    point_index: int,
    trial_index: int,
) -> tuple[int, int, int]:
    """Derive system-comparison RNG streams in the frozen 03B seed domain."""
    scenario_id = {"awgn": 11, "static": 12, "rician": 13}[scenario]
    return derive_metric_stream_seeds(root_seed, scenario_id, point_index, trial_index)


def validate_frozen_protocol(protocol: dict[str, Any]) -> dict[str, int]:
    """Reject accidental changes to the approved 03B v1.1 design."""
    if protocol.get("schema") != "scientific-exp03b-frozen-protocol-v1.1":
        raise ValueError("unsupported SCIENTIFIC-EXP-03B protocol schema")
    if protocol.get("status") != "FROZEN_BEFORE_03B_DATA":
        raise ValueError("protocol must be frozen before any 03B trial")
    if protocol.get("paper_exact") is not False:
        raise ValueError("paper_exact must remain false")
    metric = protocol.get("metric_isolation", {})
    if metric.get("confirmatory_trials_per_point") != 300:
        raise ValueError("metric confirmatory sample size differs from frozen protocol")
    if metric.get("preflight_trials_per_point") != 10:
        raise ValueError("metric preflight sample size differs from frozen protocol")
    if metric.get("frame_symbols") != 1024 or metric.get("traceback_depth") != 20:
        raise ValueError("metric frame length or traceback depth differs from frozen protocol")
    if set(metric.get("sweeps", [])) != {"amplitude_fixed_noise", "noise_fixed_amplitude"}:
        raise ValueError("both frozen energy sweep methods must be present")
    scenarios = metric.get("scenarios", [])
    expected_metric_ids = {
        "awgn_direct",
        "awgn_pilot",
        "static_pilot",
        "rician_period32",
        "rician_period8",
    }
    if {row.get("id") for row in scenarios} != expected_metric_ids:
        raise ValueError("metric scenarios differ from the frozen protocol")
    metric_cells = sum(len(row.get("energy_offsets_db", [])) for row in scenarios)
    if metric_cells != 38:
        raise ValueError("metric grid must contain the 38 frozen energy cells")
    system = protocol.get("system_comparison", {})
    if system.get("confirmatory_trials_per_point") != 100:
        raise ValueError("system confirmatory sample size differs from frozen protocol")
    if system.get("preflight_trials_per_scenario") != 10 or system.get("frame_symbols") != 256:
        raise ValueError("system preflight or frame length differs from frozen protocol")
    system_grids = system.get("energy_grid_gamma_db", {})
    if set(system_grids) != {"awgn", "static", "rician"}:
        raise ValueError("system comparison must include all three frozen channels")
    system_cells = sum(len(grid) for grid in system_grids.values())
    if system_cells != 83:
        raise ValueError("system energy grids must contain 83 frozen energy cells")
    return {
        "metric_cells_per_sweep": metric_cells,
        "metric_confirmatory_trials": metric_cells
        * len(metric["sweeps"])
        * int(metric["confirmatory_trials_per_point"]),
        "system_cells": system_cells,
        "system_confirmatory_trials": system_cells * int(system["confirmatory_trials_per_point"]),
    }


def build_metric_trial_spec(
    protocol: dict[str, Any],
    scenario_key: str,
    sweep: Literal["amplitude_fixed_noise", "noise_fixed_amplitude"],
    point_index: int,
    trial_index: int,
    stage: Literal["preflight", "confirmatory"],
) -> MetricTrialSpec:
    """Build one A-E/A-H paired trial from immutable protocol fields."""
    validate_frozen_protocol(protocol)
    scenario = next(
        (row for row in protocol["metric_isolation"]["scenarios"] if row["id"] == scenario_key),
        None,
    )
    if scenario is None:
        raise ValueError("unknown frozen metric scenario")
    if sweep not in protocol["metric_isolation"]["sweeps"]:
        raise ValueError("unknown frozen metric sweep")
    trial_limit = (
        protocol["metric_isolation"]["preflight_trials_per_point"]
        if stage == "preflight"
        else protocol["metric_isolation"]["confirmatory_trials_per_point"]
    )
    if stage not in {"preflight", "confirmatory"} or not 0 <= trial_index < trial_limit:
        raise ValueError("trial index is outside the frozen stage")
    grid = scenario["energy_offsets_db"]
    if not 0 <= point_index < len(grid):
        raise ValueError("point index is outside the frozen energy grid")
    offset_db = float(grid[point_index])
    root_key = "root_seed" if stage == "confirmatory" else "preflight_root_seed"
    source_seed, fading_seed, noise_seed = derive_metric_stream_seeds(
        int(scenario[root_key]),
        int(scenario["scenario_id"]),
        point_index,
        trial_index,
    )
    base_variance = float(protocol["energy_convention"]["noise_complex_variance_amplitude_sweep"])
    amplitude = (
        10.0 ** (offset_db / 20.0)
        if sweep == "amplitude_fixed_noise"
        else float(protocol["energy_convention"]["noise_sweep_fixed_amplitude"])
    )
    noise_variance = (
        base_variance
        if sweep == "amplitude_fixed_noise"
        else base_variance * 10.0 ** (-offset_db / 10.0)
    )
    scenario_key_to_channel = {
        "awgn_direct": "awgn",
        "awgn_pilot": "awgn",
        "static_pilot": "static",
        "rician_period32": "rician",
        "rician_period8": "rician",
    }
    channel_kind = scenario_key_to_channel[scenario_key]
    if channel_kind == "awgn":
        paths = (ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),)
        fading_mode = "constant"
        correlation = 0.0
        profile_id = "awgn" if scenario_key == "awgn_direct" else "exp03b_awgn_pilot"
    elif channel_kind == "static":
        paths = (
            ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),
            ChannelPathConfig(3, 0.13, 0.0, constant_coefficient=0.3 - 0.2j),
        )
        fading_mode = "constant"
        correlation = 0.0
        profile_id = "exp03b_static_0_3"
    else:
        paths = (
            ChannelPathConfig(0, 1.0, 4.0, 0.0),
            ChannelPathConfig(3, 0.25, 1.0, 0.7),
        )
        fading_mode = "rician_ar1"
        correlation = 0.98
        profile_id = "exp03b_rician_ar1_0_3"
    channel = ChannelConfig(
        profile_id=profile_id,
        paths=paths,
        fading_mode=fading_mode,  # type: ignore[arg-type]
        correlation=correlation,
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=noise_variance,
        fading_seed=fading_seed,
        noise_seed=noise_seed,
        reveal_noise_variance=True,
    )
    frontend_mode = scenario["frontend_mode"]
    return MetricTrialSpec(
        trial_id=f"exp03b-{stage}-{scenario_key}-{sweep}-p{point_index:02d}-t{trial_index:04d}",
        frame_symbols=int(protocol["metric_isolation"]["frame_symbols"]),
        source_seed=source_seed,
        channel_config=channel,
        frontend_mode=frontend_mode,
        amplitude=amplitude,
        preamble_symbols=int(protocol["metric_isolation"]["preamble_symbols"]),
        pilot_period=int(scenario["pilot_period"]),
        pilot_burst_symbols=int(protocol["metric_isolation"]["pilot_burst_symbols"]),
        traceback_depth=20,
    )


def build_system_trial_spec(
    protocol: dict[str, Any],
    scenario: Literal["awgn", "static", "rician"],
    point_index: int,
    trial_index: int,
    stage: Literal["preflight", "confirmatory"],
) -> EnergyTrialSpec:
    """Build one full Joint/B0/B1 system trial in its separate seed domain."""
    validate_frozen_protocol(protocol)
    system = protocol["system_comparison"]
    if scenario not in system["energy_grid_gamma_db"]:
        raise ValueError("unknown frozen full-system channel scenario")
    trials = (
        system["preflight_trials_per_scenario"]
        if stage == "preflight"
        else system["confirmatory_trials_per_point"]
    )
    grid = system["energy_grid_gamma_db"][scenario]
    if stage not in {"preflight", "confirmatory"} or not 0 <= trial_index < trials:
        raise ValueError("system trial index is outside the frozen stage")
    if not 0 <= point_index < len(grid):
        raise ValueError("system point index is outside the frozen energy grid")
    root_map = (
        {"awgn": 830096, "static": 830097, "rician": 830098}
        if stage == "preflight"
        else system["seed_policy_roots"]
    )
    root_seed = int(root_map[scenario])
    channel = system["channel_profiles"][scenario]
    settings = {
        "channel_profile": {
            "awgn": "awgn",
            "static": "static_multipath",
            "rician": "rician_ar1_multipath",
        }[scenario],
        "delays_samples": channel["delays_samples"],
        "path_powers": channel["path_powers"],
        "los_phases_rad": channel.get("los_phases_rad", [0.0] * len(channel["delays_samples"])),
        "rician_k_factors": channel.get("rician_k_factors", [0.0] * len(channel["delays_samples"])),
        "fading_correlation": float(channel.get("fading_correlation", 0.0)),
    }
    if scenario != "rician":
        settings["path_coefficients"] = channel["path_coefficients"]
    else:
        settings["path_coefficients"] = []
    return EnergyTrialSpec(
        phase="confirmatory" if stage == "confirmatory" else "validation",
        scenario=scenario,
        sweep="amplitude",
        gamma_db=float(grid[point_index]),
        point_index=point_index,
        trial_index=trial_index,
        frame_symbols=int(system["frame_symbols"]),
        root_seed=root_seed,
        noise_reference_variance=float(system["noise_complex_variance"]),
        channel_settings=settings,
        receiver_arms=tuple(channel["receiver_arms"]),
    )


def system_trial_seeds(spec: EnergyTrialSpec, scenario: str) -> tuple[int, int, int]:
    """Return the protocol-defined stream seeds for one complete-system trial."""
    return derive_system_stream_seeds(
        spec.root_seed,
        scenario,
        spec.point_index,
        spec.trial_index,  # type: ignore[arg-type]
    )
