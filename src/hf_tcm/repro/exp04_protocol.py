"""SCIENTIFIC-EXP-04: Hamming (hard, separate) vs Euclidean (soft, joint) in a known tract.

The protocol is a frozen JSON file (``configs/SCIENTIFIC_EXP_04_PROTOCOL.json``)
whose SHA-256 is stored next to it. Confirmatory runs require the operator to
pass that exact digest (``approve_sha256``); preflight never runs a series.
All cells use common random numbers (same bits/fading/noise per trial index at
every energy point, only the amplitude changes) and the common-cluster paired
bootstrap of ``energy_statistics.analyze_energy_records``.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

from hf_tcm.repro.channel_config import (
    ITU_HF_DOPPLER_SPREAD_HZ,
    ChannelConfig,
    ChannelPathConfig,
    itu_hf_doppler_profile,
)
from hf_tcm.repro.energy_statistics import analyze_energy_records
from hf_tcm.repro.metric_experiment import (
    MetricStudyConfig,
    _read_trial_records,
    _trial_config_for_point,
    run_metric_study,
    run_metric_trial,
)
from hf_tcm.repro.metric_isolation import build_pilot_schedule

PROTOCOL_ID = "SCIENTIFIC-EXP-04"
DEFAULT_PROTOCOL = Path("configs/SCIENTIFIC_EXP_04_PROTOCOL.json")
DEFAULT_OUTPUT = Path("outputs/scientific_exp04")


def protocol_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_protocol(path: Path = DEFAULT_PROTOCOL) -> tuple[dict[str, Any], str, str]:
    """Return (protocol, sha256, freeze_status). Status is FROZEN only if the
    sibling ``.sha256`` file exists and matches the protocol bytes."""
    path = Path(path)
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("not a SCIENTIFIC-EXP-04 protocol")
    digest = protocol_sha256(path)
    sidecar = path.with_name(path.name + ".sha256")
    if not sidecar.is_file():
        status = "NOT_FROZEN"
    else:
        recorded = sidecar.read_text(encoding="utf-8").split()[0].strip().lower()
        status = "FROZEN" if recorded == digest else "SHA256_MISMATCH"
    return protocol, digest, status


def reference_gamma_db(cell: dict[str, Any], frame_symbols: int, pilots: dict[str, int]) -> float:
    """Eb/N0 (= gamma_b,d) at amplitude 1 and sigma^2 = 1 for this cell's frame."""
    if cell["frontend_mode"] == "awgn_direct_control":
        payload = frame_symbols
    else:
        schedule = build_pilot_schedule(
            frame_symbols=frame_symbols,
            preamble_symbols=pilots["preamble_symbols"],
            pilot_period=pilots["pilot_period"],
            pilot_burst_symbols=pilots["pilot_burst_symbols"],
        )
        payload = int(schedule.payload_mask.sum())
    return 10.0 * math.log10(8.0 * frame_symbols / (2.0 * payload))


def _channel(cell: dict[str, Any], protocol: dict[str, Any]) -> ChannelConfig:
    channel = cell["channel"]
    variance = float(protocol["design"]["noise_complex_variance"])
    kind = channel["kind"]
    if kind == "awgn":
        return ChannelConfig(
            profile_id="awgn",
            paths=(ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),),
            fading_mode="constant",
            noise_model="complex_awgn_sample_domain",
            noise_complex_variance=variance,
            fading_seed=1,
            noise_seed=2,
            reveal_noise_variance=True,
        )
    if kind == "static":
        paths = tuple(
            ChannelPathConfig(
                int(delay),
                float(re) ** 2 + float(im) ** 2,
                0.0,
                constant_coefficient=complex(float(re), float(im)),
            )
            for delay, (re, im) in zip(
                channel["delays_samples"], channel["coefficients"], strict=True
            )
        )
        return ChannelConfig(
            profile_id="static_multipath",
            paths=paths,
            fading_mode="constant",
            noise_model="complex_awgn_sample_domain",
            noise_complex_variance=variance,
            fading_seed=1,
            noise_seed=2,
            reveal_noise_variance=True,
        )
    if kind == "itu_doppler":
        if channel["condition"] not in ITU_HF_DOPPLER_SPREAD_HZ:
            raise ValueError("unknown ITU condition")
        return itu_hf_doppler_profile(
            channel["condition"],
            noise_complex_variance=variance,
            fading_seed=1,
            noise_seed=2,
            symbol_rate_baud=float(protocol["design"]["symbol_rate_baud"]),
            second_path_delay_samples=int(channel["second_path_delay_samples"]),
        )
    raise ValueError(f"unknown channel kind {kind!r}")


def cell_config(
    protocol: dict[str, Any], cell_id: str, digest: str, *, phase: str = "confirmatory"
) -> MetricStudyConfig:
    cells = {cell["id"]: cell for cell in protocol["cells"]}
    if cell_id not in cells:
        raise ValueError(f"unknown EXP-04 cell {cell_id!r}")
    cell = cells[cell_id]
    design = protocol["design"]
    frame = int(design["frame_symbols"])
    pilots = design["pilots"]
    reference = reference_gamma_db(cell, frame, pilots)
    grid = tuple(float(value) - reference for value in cell["eb_n0_grid_db"])
    scenario = {"awgn": "awgn", "static": "static", "itu_doppler": "rician"}[
        cell["channel"]["kind"]
    ]
    return MetricStudyConfig(
        experiment_id=f"exp04-{cell_id}",
        scenario=scenario,  # type: ignore[arg-type]
        phase=phase,  # type: ignore[arg-type]
        frame_symbols=frame,
        energy_grid_db=grid,
        trials_per_point=int(cell["trials_per_point"]),
        root_seed=int(cell["root_seed"]),
        target_ber=float(protocol["analysis"]["primary_target_ber"][cell["primary_target_key"]]),
        time_budget_seconds=float(cell["time_budget_seconds"]),
        sweep="amplitude",
        amplitude=1.0,
        channel_config=_channel(cell, protocol).to_dict(),
        frontend_mode=cell["frontend_mode"],
        preamble_symbols=int(pilots["preamble_symbols"]),
        pilot_period=int(pilots["pilot_period"]),
        pilot_burst_symbols=int(pilots["pilot_burst_symbols"]),
        bootstrap_replicates=int(protocol["analysis"]["bootstrap_replicates"]),
        euclidean_metric=cell["euclidean_metric"],
        common_random_numbers=True,
        protocol_sha256=digest if phase == "confirmatory" else "",
        full_array_stride=int(design.get("array_storage", {}).get("full_array_stride", 1)),
    )


def preflight(protocol: dict[str, Any], digest: str, *, timing_trials: int = 3) -> dict[str, Any]:
    """Validate every cell, check the energy axis and time a few trials. No series is run."""
    rows = []
    total_seconds = 0.0
    for cell in protocol["cells"]:
        config = cell_config(protocol, cell["id"], digest, phase="range_finding")
        middle = len(config.energy_grid_db) // 2
        started = time.perf_counter()
        gammas = []
        for trial in range(timing_trials):
            spec = _trial_config_for_point(config, config.energy_grid_db[middle], middle, trial)
            gammas.append(run_metric_trial(spec).summary["gamma_b_discrete_db"])
        per_trial = (time.perf_counter() - started) / timing_trials
        expected = float(cell["eb_n0_grid_db"][middle])
        axis_error = max(abs(value - expected) for value in gammas)
        planned = len(config.energy_grid_db) * config.trials_per_point
        estimate = per_trial * planned
        total_seconds += estimate
        rows.append(
            {
                "cell": cell["id"],
                "role": cell["role"],
                "points": len(config.energy_grid_db),
                "trials_per_point": config.trials_per_point,
                "planned_trials": planned,
                "seconds_per_trial": per_trial,
                "estimated_seconds": estimate,
                "time_budget_seconds": config.time_budget_seconds,
                "fits_budget": estimate <= config.time_budget_seconds,
                "eb_n0_axis_max_error_db": axis_error,
                "eb_n0_axis_ok": axis_error < 1e-9,
            }
        )
    return {
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": digest,
        "cells": rows,
        "estimated_total_seconds": total_seconds,
        "series_executed": False,
    }


def run_cells(
    protocol_path: Path,
    cells: list[str],
    *,
    approve_sha256: str,
    output_root: Path = DEFAULT_OUTPUT,
) -> list[dict[str, Any]]:
    """Run confirmatory cells; refuses unless the protocol is frozen and approved."""
    protocol, digest, status = load_protocol(protocol_path)
    if status != "FROZEN":
        raise PermissionError(f"protocol is {status}; freeze it before a confirmatory run")
    if approve_sha256.strip().lower() != digest:
        raise PermissionError("approval digest does not match the frozen protocol SHA-256")
    summaries = []
    for cell_id in cells:
        config = cell_config(protocol, cell_id, digest)
        summaries.append(run_metric_study(config, Path(output_root) / "studies"))
    return summaries


def analyze_cell(protocol: dict[str, Any], cell_id: str, study_root: Path) -> dict[str, Any]:
    """Gain at every protocol target BER from stored trial records (no new trials)."""
    records = _read_trial_records(Path(study_root))
    if not records:
        raise ValueError("no stored trials for this cell")
    by_point: dict[int, list[float]] = {}
    for row in records:
        by_point.setdefault(int(row["point_index"]), []).append(float(row["gamma_b_discrete_db"]))
    rows = [
        {
            "scenario": row["scenario"],
            "sweep": row["sweep"],
            "phase": row["phase"],
            "gamma_db": float(sorted(by_point[int(row["point_index"])])[0]),
            "trial_index": int(row["trial_index"]),
            "bits": int(row["payload_information_bits"]),
            "pairs": int(row["payload_symbols"]),
            "bit_errors": {
                "joint": int(row["euclidean"]["bit_errors"]),
                "hamming": int(row["hamming"]["bit_errors"]),
            },
            "pair_errors": {
                "joint": int(row["euclidean"]["pair_errors"]),
                "hamming": int(row["hamming"]["pair_errors"]),
            },
        }
        for row in records
    ]
    analysis = protocol["analysis"]
    seed = int(analysis["bootstrap_seed"])
    results = {}
    for target in analysis["all_target_ber"]:
        result = analyze_energy_records(
            rows,
            float(target),
            arm="hamming",
            replicates=int(analysis["bootstrap_replicates"]),
            seed=seed,
            common_clusters=True,
        )
        ci = result["bootstrap"]["confidence_interval_db"]
        half_width = None if ci is None else (ci[1] - ci[0]) / 2.0
        if result["gain_db"] is None:
            verdict = "ENERGY_GAIN_NOT_ESTIMABLE"
        elif ci is None:
            verdict = "INSUFFICIENT_PRECISION"
        elif half_width <= float(analysis["max_ci_half_width_db"]):
            verdict = "PRECISION_CRITERIA_MET"
        else:
            verdict = "INSUFFICIENT_PRECISION"
        results[str(target)] = {
            "gain_db": result["gain_db"],
            "ci95_db": ci,
            "ci_half_width_db": half_width,
            "valid_fraction": result["bootstrap"]["valid_fraction"],
            "required_eb_n0_db": result["required_gamma_db"],
            "flags": result["flags"],
            "verdict": verdict,
        }
    return {"cell": cell_id, "trials": len(records), "targets": results}


RESULTS_BUNDLE = Path("docs/research/SCIENTIFIC_EXP_04_RESULTS.json")
BUNDLE_SCHEMA = "scientific-exp04-results-bundle-v1"
_POINT_KEYS = (
    "eb_n0_db",
    "trials",
    "bits",
    "hamming_errors",
    "euclidean_errors",
    "hamming_frames_with_errors",
    "euclidean_frames_with_errors",
)


def build_results_bundle(
    protocol: dict[str, Any],
    digest: str,
    analysis: list[dict[str, Any]],
    points: dict[str, Any],
) -> dict[str, Any]:
    """Compact, version-controlled summary of the confirmatory series.

    ``analysis`` is the output of ``analyze_cell`` for every cell and ``points``
    the ``report_points.json`` written by ``scripts/report_exp04.py``. Only error
    counts are stored; BER values are derived from them by the reader.
    """
    if points.get("protocol_sha256") != digest:
        raise ValueError("report points belong to a different protocol digest")
    by_cell = {item["cell"]: item for item in analysis}
    cells = []
    for cell in protocol["cells"]:
        cell_id = cell["id"]
        if cell_id not in by_cell or cell_id not in points["cells"]:
            raise ValueError(f"cell {cell_id} lacks analysis or points")
        report = points["cells"][cell_id]
        if report["recount"]["mismatches"] != 0:
            raise ValueError(f"cell {cell_id} failed the independent recount")
        planned = len(cell["eb_n0_grid_db"]) * int(cell["trials_per_point"])
        if by_cell[cell_id]["trials"] != planned:
            raise ValueError(f"cell {cell_id} is incomplete")
        cells.append(
            {
                "id": cell_id,
                "role": cell["role"],
                "channel": cell["channel"],
                "frontend_mode": cell["frontend_mode"],
                "euclidean_metric": cell["euclidean_metric"],
                "primary_target_ber": protocol["analysis"]["primary_target_ber"][
                    cell["primary_target_key"]
                ],
                "trials": by_cell[cell_id]["trials"],
                "recount_mismatches": 0,
                "points": [{key: row[key] for key in _POINT_KEYS} for row in report["points"]],
                "targets": by_cell[cell_id]["targets"],
            }
        )
    return {
        "schema_version": BUNDLE_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": digest,
        "phase": "confirmatory",
        "paper_exact": False,
        "article_reference_target_ber": protocol["analysis"]["article_reference_target_ber"],
        "all_target_ber": protocol["analysis"]["all_target_ber"],
        "bootstrap_replicates": protocol["analysis"]["bootstrap_replicates"],
        "max_ci_half_width_db": protocol["analysis"]["max_ci_half_width_db"],
        "report": "docs/research/SCIENTIFIC_EXP_04_RESULTS_UK.md",
        "cells": cells,
    }


def load_results_bundle(
    bundle_path: Path = RESULTS_BUNDLE, protocol_path: Path = DEFAULT_PROTOCOL
) -> dict[str, Any]:
    """Read the bundle and check it against the frozen protocol it claims."""
    _, digest, status = load_protocol(protocol_path)
    if status != "FROZEN":
        raise ValueError(f"protocol is {status}")
    bundle = json.loads(Path(bundle_path).read_text(encoding="utf-8"))
    if bundle.get("schema_version") != BUNDLE_SCHEMA:
        raise ValueError("unsupported EXP-04 results bundle")
    if bundle.get("protocol_sha256") != digest:
        raise ValueError("results bundle does not match the frozen protocol SHA-256")
    for cell in bundle["cells"]:
        for row in cell["points"]:
            if not 0 <= row["hamming_errors"] <= row["bits"]:
                raise ValueError("invalid error counts")
            if not 0 <= row["euclidean_errors"] <= row["bits"]:
                raise ValueError("invalid error counts")
    return bundle


GUI_METRIC_ROOT = Path("outputs/scientific-exp03a/metric-studies")


def metric_study_root(study_id: str, output_root: Path = DEFAULT_OUTPUT) -> Path:
    """Folder that holds a metric study: EXP-04 cells live under the protocol output."""
    if study_id.startswith("exp04-"):
        return Path(output_root) / "studies"
    return GUI_METRIC_ROOT


def list_exp04_frames(
    protocol_path: Path = DEFAULT_PROTOCOL, output_root: Path = DEFAULT_OUTPUT
) -> list[dict[str, Any]]:
    """Locally stored confirmatory cells whose sampled frames can be opened read-only."""
    protocol, digest, _status = load_protocol(protocol_path)
    stride = int(protocol["design"].get("array_storage", {}).get("full_array_stride", 1))
    cells = []
    for cell in protocol["cells"]:
        root = Path(output_root) / "studies" / f"exp04-{cell['id']}"
        summary_path = root / "summary.json"
        if not summary_path.is_file():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("protocol_sha256") != digest or summary.get("status") != "completed":
            continue
        cells.append(
            {
                "experiment_id": f"exp04-{cell['id']}",
                "cell": cell["id"],
                "eb_n0_grid_db": cell["eb_n0_grid_db"],
                "trials_per_point": int(cell["trials_per_point"]),
                "full_array_stride": stride,
            }
        )
    return cells
