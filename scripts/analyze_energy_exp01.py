"""Read-only count analysis of completed SCIENTIFIC-EXP-01 trial records.

No receiver calls, array loading, resimulation, or pooling across experiment
phases. Only derived files under ROOT/analysis are written.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from hf_tcm.repro.energy_statistics import aggregate_energy_records, analyze_energy_records

ARMS_UK = {"joint": "Спільний приймач", "b0": "Роздільний B0", "b1": "Роздільний B1"}
SCENARIOS_UK = {"awgn": "AWGN", "static": "Статичний двопроменевий", "rician": "Райсівський"}
PHASES_UK = {"pilot": "Пілот", "confirmatory": "Основна серія", "long": "Довгий кадр"}
SWEEPS_UK = {"amplitude": "Зміна амплітуди", "noise": "Зміна дисперсії шуму"}
COLORS = {"joint": "#007f87", "b0": "#c46a23", "b1": "#8054a6"}
CROSSINGS_UK = {
    "BRACKETED": "є виміряна дужка",
    "EXACT_GRID_POINT": "точне значення на сітці",
    "NO_CROSSING": "немає перетину на сітці",
    "ALL_ZERO_BER": "скрізь 0 помилок",
    "ZERO_BER_BRACKET_UNRESOLVED": "межа містить 0 помилок",
    "AMBIGUOUS_MULTIPLE_CROSSINGS": "неоднозначні перетини",
    "TARGET_PLATEAU": "плато на цілі",
    "UPWARD_CROSSING": "висхідний перетин",
}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def domain_seed(seed: int, *parts: Any) -> int:
    payload = json.dumps([seed, *parts], separators=(",", ":")).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little")


def load_records(root: Path) -> tuple[list[dict], list[dict]]:
    """Snapshot only manifested records and retain hashes/seeds for audit."""
    records, excluded = [], []
    for phase in ("pilot", "confirmatory", "long"):
        for path in sorted((root / phase).rglob("record.json")):
            manifest_path = path.with_name("manifest.json")
            if not manifest_path.exists():
                excluded.append({"path": str(path), "reason": "manifest not committed at snapshot"})
                continue
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest["files"]["record.json"] != digest:
                raise ValueError(f"record hash mismatch: {path}")
            row = json.loads(raw)
            if row["phase"] != phase or row.get("status") != "completed":
                raise ValueError(f"unexpected phase/status: {path}")
            row["source"] = {
                "path": path.relative_to(root).as_posix(),
                "sha256": digest,
                "seeds": row["seeds"],
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "manifest_files": manifest["files"],
            }
            records.append(row)
    return records, excluded


def point_intervals(rows: list[dict], arms: list[str], replicates: int, seed: int) -> dict:
    """Resample whole paired trial rows, using ratio-of-sums for each metric."""
    rng = np.random.default_rng(seed)
    draws = rng.integers(len(rows), size=(replicates, len(rows)))
    result = {}
    for metric, errors_key, denominator_key in (
        ("ber", "bit_errors", "bits"),
        ("ser", "pair_errors", "pairs"),
        ("fer", "frame_errors", None),
    ):
        denominator = np.asarray(
            [row[denominator_key] if denominator_key else 1 for row in rows], dtype=float
        )
        sampled_denominator = denominator[draws].sum(axis=1)
        result[metric] = {}
        for arm in arms:
            errors = np.asarray([row[errors_key][arm] for row in rows], dtype=float)
            samples = errors[draws].sum(axis=1) / sampled_denominator
            result[metric][arm] = np.quantile(samples, [0.025, 0.975]).tolist()
    return result


def linear_ber_crossing(points: list[dict], target: float, arm: str) -> dict:
    """Sensitivity analysis only: adjacent linear BER, including measured zero."""
    hits = []
    for index, point in enumerate(points):
        if point["ber"][arm] == target:
            if index and points[index - 1]["ber"][arm] == target:
                return {"status": "TARGET_PLATEAU", "required_gamma_db": None}
            hits.append(point["gamma_db"])
    for left, right in zip(points, points[1:]):
        y0, y1 = left["ber"][arm], right["ber"][arm]
        if (y0 - target) * (y1 - target) < 0:
            if y1 > y0:
                hits.append(None)
            else:
                hits.append(
                    left["gamma_db"]
                    + (target - y0) / (y1 - y0) * (right["gamma_db"] - left["gamma_db"])
                )
    if len(hits) != 1 or hits[0] is None:
        return {"status": "NO_UNIQUE_DOWNWARD_CROSSING", "required_gamma_db": None}
    return {"status": "SENSITIVITY_ONLY", "required_gamma_db": hits[0]}


def wilson_frame_interval(errors: int, frames: int) -> list[float]:
    """Two-sided score interval for independent frame indicators, not bits."""
    if frames < 1 or not 0 <= errors <= frames:
        raise ValueError("frame error count must be in [0, frames]")
    z = NormalDist().inv_cdf(0.975)
    proportion = errors / frames
    denominator = 1 + z * z / frames
    center = (proportion + z * z / (2 * frames)) / denominator
    width = (
        z
        * math.sqrt(proportion * (1 - proportion) / frames + z * z / (4 * frames * frames))
        / denominator
    )
    return [max(0.0, center - width), min(1.0, center + width)]


def summarize_points(rows: list[dict], replicates: int, seed: int) -> list[dict]:
    points = aggregate_energy_records(rows)
    for point in points:
        trials = [row for row in rows if row["gamma_db"] == point["gamma_db"]]
        arms = sorted(point["ber"])
        point["frames"] = len(trials)
        point["frame_symbols"] = sorted({row["frame_symbols"] for row in trials})
        point["frame_errors"] = {
            arm: sum(row["frame_errors"][arm] for row in trials) for arm in arms
        }
        point["fer"] = {arm: point["frame_errors"][arm] / len(trials) for arm in arms}
        point["ci95"] = point_intervals(
            trials,
            arms,
            replicates,
            domain_seed(
                seed, "point", point["phase"], point["scenario"], point["sweep"], point["gamma_db"]
            ),
        )
        point["zero_error_fer_upper95"] = {
            arm: -math.expm1(math.log(0.05) / len(trials))
            if point["frame_errors"][arm] == 0
            else None
            for arm in arms
        }
        point["zero_error_note"] = (
            "Zero observed BER does not imply zero true BER; a degenerate percentile [0,0] describes resampled observations only. Upper95 is the exact one-sided independent-frame FER bound, not an independent-bit binomial bound."
        )
        point["all_error_fer_lower95"] = {
            arm: 0.05 ** (1 / len(trials)) if point["frame_errors"][arm] == len(trials) else None
            for arm in arms
        }
        point["fer_wilson_ci95"] = {
            arm: wilson_frame_interval(point["frame_errors"][arm], len(trials)) for arm in arms
        }
        point["fer_wilson_method"] = (
            "two-sided 95% Wilson score interval for independent frame error indicators; displayed in FER plots; not an independent-bit interval"
        )
        point["runtime_seconds"] = {}
        for arm in arms:
            values = [row["runtime_seconds"][arm] for row in trials]
            point["runtime_seconds"][arm] = {
                "sum": sum(values),
                "median": float(np.median(values)),
                "max": max(values),
            }
        point["elapsed_seconds"] = sum(row["elapsed_seconds"] for row in trials)
        point["actual_eb_d"] = sorted({row["eb_d"] for row in trials})
        point["amplitudes"] = sorted({row["amplitude"] for row in trials})
        point["noise_variances"] = sorted({row["noise_variance"] for row in trials})
        point["reference_equivalent_eb_d"] = 10 ** (point["gamma_db"] / 10)
        sizes = [
            row["saved_array_bytes"] for row in trials if row.get("saved_array_bytes") is not None
        ]
        peaks = [
            row["peak_working_set_process_bytes"]
            for row in trials
            if row.get("peak_working_set_process_bytes") is not None
        ]
        point["saved_array_bytes"] = {
            "sum": sum(sizes) if sizes else None,
            "max": max(sizes) if sizes else None,
            "measured_trials": len(sizes),
        }
        point["peak_working_set_process_bytes"] = {
            "max": max(peaks) if peaks else None,
            "measured_trials": len(peaks),
            "interpretation": "process cumulative high-water mark, not isolated per-trial allocation",
        }
        point["sources"] = [row["source"] for row in trials]
        point["flags"] = ["LOW_TRIAL_COUNT"] if len(trials) < 20 else []
    return points


def group_title(group: dict) -> str:
    counts = [point["trials"] for point in group["points"]]
    frames = sorted({length for point in group["points"] for length in point["frame_symbols"]})
    title = f"{PHASES_UK[group['phase']]} · {SCENARIOS_UK.get(group['scenario'], group['scenario'])} · {SWEEPS_UK[group['sweep']]}"
    return (
        title
        + f"\nF={','.join(map(str, frames))}, незалежних кадрів/точку: {min(counts)}–{max(counts)}"
    )


def save_plot(fig: Any, directory: Path, name: str) -> None:
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    for suffix in ("png", "svg"):
        fig.savefig(directory / f"{name}.{suffix}", dpi=145, facecolor="white")
    plt.close(fig)


def plot_rate(group: dict, metric: str, directory: Path, *, energy: bool = False) -> None:
    points = group["points"]
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    x = [point["actual_eb_d"][0] if energy else point["gamma_db"] for point in points]
    for arm in sorted(points[0][metric]):
        y = [point[metric][arm] for point in points]
        low, high = np.asarray(
            [
                point["fer_wilson_ci95"][arm] if metric == "fer" else point["ci95"][metric][arm]
                for point in points
            ]
        ).T
        color = COLORS.get(arm)
        ax.plot(x, y, "o--", color=color, label=ARMS_UK.get(arm, arm), linewidth=1.2, markersize=4)
        ax.vlines(x, low, high, color=color, alpha=0.65, linewidth=2)
    if energy:
        ax.set_xscale("log")
    if metric != "fer":
        ax.set_yscale("symlog", linthresh=1e-4)
    ax.set_ylim(bottom=0)
    ax.set_xlabel(
        "Дискретна енергія на біт Eb,d (шумова дисперсія = 1)"
        if energy
        else "Ефективне дискретне γ, дБ"
    )
    ax.set_ylabel(
        {
            "ber": "BER інформаційних бітів",
            "ser": "SER декодованих інформаційних пар",
            "fer": "FER незалежних кадрів",
        }[metric]
    )
    ax.set_title(group_title(group))
    ax.grid(True, alpha=0.22)
    ax.legend()
    caption = (
        "Точки — вимірювання; відрізки — 95% Wilson для незалежних кадрів."
        if metric == "fer"
        else "Точки — вимірювання; відрізки — 95% парний bootstrap."
    )
    fig.text(
        0.02,
        0.012,
        caption + " Нуль помилок не означає нульову ймовірність.",
        fontsize=8,
    )
    save_plot(fig, directory, group["id"] + "_" + metric + ("_energy" if energy else "_gamma"))


def plot_runtime(group: dict, directory: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    for arm in sorted(group["points"][0]["ber"]):
        ax.plot(
            [point["gamma_db"] for point in group["points"]],
            [point["runtime_seconds"][arm]["median"] for point in group["points"]],
            "o--",
            label=ARMS_UK.get(arm, arm),
            color=COLORS.get(arm),
        )
    ax.set(
        xlabel="Ефективне дискретне γ, дБ",
        ylabel="Медіанний час приймача на кадр, с",
        title=group_title(group),
    )
    ax.grid(alpha=0.2)
    ax.legend()
    save_plot(fig, directory, group["id"] + "_runtime")


def plot_gain(group: dict, gains: list[dict], directory: Path) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    labels = []
    for index, result in enumerate(gains):
        labels.append(f"{result['separate_arm'].upper()} / BER={result['target_ber']:g}")
        gain = result["gain_db"]
        interval = result["bootstrap"]["confidence_interval_db"]
        if gain is not None:
            ax.plot(gain, index, "o", color=COLORS.get(result["separate_arm"]))
            if interval is not None:
                ax.hlines(index, *interval, color=COLORS.get(result["separate_arm"]), linewidth=3)
            else:
                ax.annotate(
                    "95% інтервал недоступний",
                    (gain, index),
                    xytext=(7, 6),
                    textcoords="offset points",
                    fontsize=8,
                )
        else:
            statuses = "; ".join(
                f"{key}: {CROSSINGS_UK.get(value['status'], value['status'])}"
                for key, value in result["crossings"].items()
            )
            ax.text(
                0.02,
                index,
                "Перетин не оцінено: " + statuses,
                transform=ax.get_yaxis_transform(),
                fontsize=7,
                va="center",
            )
    ax.set_yticks(range(len(labels)), labels)
    ax.set_ylim(-0.6, max(0.6, len(labels) - 0.4))
    ax.axvline(0, color="black", linewidth=0.8, alpha=0.4)
    ax.set(xlabel="γ роздільного − γ спільного приймача, дБ", title=group_title(group))
    if not any(result["gain_db"] is not None for result in gains):
        ax.set_xticks([])
        ax.set_xlabel("Енергетичний виграш на виміряній сітці не оцінено")
    ax.grid(axis="x", alpha=0.2)
    fig.text(
        0.02,
        0.01,
        "Інтервали подано лише за ≥95% валідних bootstrap-перетинів; екстраполяції немає.",
        fontsize=8,
    )
    save_plot(fig, directory, group["id"] + "_gains")


def plot_missing_design(design: dict, directory: Path) -> None:
    """Explicitly show planned scenarios with no completed observations."""
    fig, ax = plt.subplots(figsize=(9.2, 4.5))
    ax.axis("off")
    ax.set_title(
        f"{PHASES_UK[design['phase']]} · {SCENARIOS_UK[design['scenario']]} · {SWEEPS_UK[design['sweep']]}"
    )
    ax.text(
        0.5, 0.62, "Завершених вимірювань немає", ha="center", fontsize=18, transform=ax.transAxes
    )
    ax.text(
        0.5,
        0.38,
        f"За планом: {design['expected_trials']} незалежних кадрів.\nBER, SER, FER і виграш не оцінено.\nПілотні спостереження не замінюють основну серію.",
        ha="center",
        va="center",
        fontsize=12,
        transform=ax.transAxes,
    )
    save_plot(
        fig,
        directory,
        "_".join((design["phase"], design["scenario"], design["sweep"])) + "_no_data",
    )


def sweep_comparison(groups: list[dict]) -> list[dict]:
    lookup = {(group["phase"], group["scenario"], group["sweep"]): group for group in groups}
    result = []
    for (phase, scenario, sweep), amplitude in lookup.items():
        noise = lookup.get((phase, scenario, "noise"))
        if sweep != "amplitude" or noise is None:
            continue
        noise_points = {point["gamma_db"]: point for point in noise["points"]}
        for point in amplitude["points"]:
            other = noise_points.get(point["gamma_db"])
            if other is None:
                continue
            for arm in sorted(set(point["ber"]) & set(other["ber"])):
                result.append(
                    {
                        "phase": phase,
                        "scenario": scenario,
                        "gamma_db": point["gamma_db"],
                        "arm": arm,
                        "amplitude_trials": point["trials"],
                        "noise_trials": other["trials"],
                        "difference_amplitude_minus_noise": {
                            metric: point[metric][arm] - other[metric][arm]
                            for metric in ("ber", "ser", "fer")
                        },
                        "interpretation": "descriptive independent-trial contrast; no paired sweep or equivalence claim",
                    }
                )
    return result


def export_csv(groups: list[dict], path: Path) -> None:
    rows = []
    for group in groups:
        for point in group["points"]:
            for arm in sorted(point["ber"]):
                row = {
                    key: point[key]
                    for key in (
                        "phase",
                        "scenario",
                        "sweep",
                        "gamma_db",
                        "trials",
                        "bits",
                        "pairs",
                        "frames",
                    )
                }
                row.update(
                    {
                        "arm": arm,
                        "F": json.dumps(point["frame_symbols"]),
                        "actual_eb_d": json.dumps(point["actual_eb_d"]),
                        "reference_equivalent_eb_d": point["reference_equivalent_eb_d"],
                    }
                )
                for metric, numerator in (
                    ("ber", "bit_errors"),
                    ("ser", "pair_errors"),
                    ("fer", "frame_errors"),
                ):
                    row.update(
                        {
                            metric: point[metric][arm],
                            numerator: point[numerator][arm],
                            metric + "_ci95_low": point["ci95"][metric][arm][0],
                            metric + "_ci95_high": point["ci95"][metric][arm][1],
                        }
                    )
                row.update(
                    {
                        "zero_error_fer_upper95": point["zero_error_fer_upper95"][arm],
                        "all_error_fer_lower95": point["all_error_fer_lower95"][arm],
                        "fer_wilson_ci95_low": point["fer_wilson_ci95"][arm][0],
                        "fer_wilson_ci95_high": point["fer_wilson_ci95"][arm][1],
                        "runtime_sum_s": point["runtime_seconds"][arm]["sum"],
                        "runtime_median_s": point["runtime_seconds"][arm]["median"],
                        "runtime_max_s": point["runtime_seconds"][arm]["max"],
                        "saved_array_bytes_max": point["saved_array_bytes"]["max"],
                        "peak_working_set_process_bytes_max": point[
                            "peak_working_set_process_bytes"
                        ]["max"],
                        "source_seed_references": json.dumps(point["sources"], ensure_ascii=False),
                    }
                )
                rows.append(row)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def planned_coverage(root: Path, grouped: dict) -> list[dict]:
    """Keep stopped design coverage distinct from target-bracket coverage."""
    protocol_path = root / "protocol.json"
    if not protocol_path.exists():
        return []
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    designs = []
    for phase in ("pilot", "confirmatory", "long"):
        if phase == "confirmatory":
            plan_path = root / "confirmatory_plan.json"
            if not plan_path.exists():
                continue
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            grid, count = plan["grid"], plan["trials_per_point"]
        elif phase == "pilot":
            grid = {
                scenario: protocol[phase]["gamma_grid"] for scenario in ("awgn", "static", "rician")
            }
            count = protocol[phase]["trials_per_point"]
        else:
            # The frozen EXP-01 runner specifies two one-frame resource checks.
            grid, count = {"awgn": [6.0], "rician": [6.0]}, 1
        for scenario, gamma_grid in grid.items():
            for sweep in ("amplitude",) if phase == "long" else ("amplitude", "noise"):
                rows = grouped.get((phase, scenario, sweep), [])
                counts = {
                    float(gamma): sum(row["gamma_db"] == gamma for row in rows)
                    for gamma in gamma_grid
                }
                expected = len(gamma_grid) * count
                complete = (
                    all(value == count for value in counts.values()) and len(rows) == expected
                )
                designs.append(
                    {
                        "phase": phase,
                        "scenario": scenario,
                        "sweep": sweep,
                        "status": "COMPLETE"
                        if complete
                        else "INCOMPLETE"
                        if rows
                        else "NOT_STARTED",
                        "expected_trials": expected,
                        "observed_trials": len(rows),
                        "expected_trials_per_point": count,
                        "observed_counts_by_gamma": {
                            str(gamma): value for gamma, value in counts.items()
                        },
                        "missing_or_partial_gamma": [
                            gamma for gamma, value in counts.items() if value < count
                        ],
                        "interpretation": "planned-grid completion; separate from measured target-crossing estimability",
                    }
                )
    return designs


def analyze(
    root: Path, targets: list[float], replicates: int, seed: int, *, plots: bool = True
) -> dict:
    rows, excluded = load_records(root)
    if not rows:
        raise ValueError("no completed manifested trial records")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["phase"], row["scenario"], row["sweep"]].append(row)
    coverage = planned_coverage(root, grouped)
    coverage_lookup = {
        (value["phase"], value["scenario"], value["sweep"]): value for value in coverage
    }
    directory = root / "analysis"
    plot_directory = directory / "plots"
    plot_directory.mkdir(parents=True, exist_ok=True)
    groups, gains = [], []
    for (phase, scenario, sweep), trials in sorted(grouped.items()):
        group = {
            "id": "_".join((phase, scenario, sweep)),
            "phase": phase,
            "scenario": scenario,
            "sweep": sweep,
            "points": summarize_points(trials, replicates, seed),
            "design_coverage": coverage_lookup.get((phase, scenario, sweep)),
        }
        groups.append(group)
        local_gains = []
        for arm in sorted(trials[0]["bit_errors"]):
            if arm == "joint":
                continue
            for target in targets:
                result = analyze_energy_records(
                    trials,
                    target,
                    arm=arm,
                    replicates=replicates,
                    seed=domain_seed(seed, "gain", phase, scenario, sweep, arm, target),
                )
                # Aggregates with full sources are already stored once in aggregates.json.
                result.pop("aggregate")
                result.update(
                    {"phase": phase, "scenario": scenario, "sweep": sweep, "group_id": group["id"]}
                )
                result["design_coverage"] = group["design_coverage"]
                if group["design_coverage"] and group["design_coverage"]["status"] != "COMPLETE":
                    result["flags"].append("INCOMPLETE_DESIGN")
                result["required_reference_eb_d"] = {
                    key: 10 ** (value / 10) if value is not None else None
                    for key, value in result["required_gamma_db"].items()
                }
                result["energy_interpretation"] = (
                    "actual amplitude-sweep Eb,d at fixed complex noise variance 1"
                    if sweep == "amplitude"
                    else "equivalent reference Eb,d at noise variance 1; actual transmitted Eb,d remains fixed in this noise sweep"
                )
                linear = {
                    name: linear_ber_crossing(group["points"], target, name)
                    for name in ("joint", arm)
                }
                result["linear_ber_sensitivity"] = {
                    "crossings": linear,
                    "gain_db": linear[arm]["required_gamma_db"]
                    - linear["joint"]["required_gamma_db"]
                    if all(value["required_gamma_db"] is not None for value in linear.values())
                    else None,
                    "interpretation": "alternative interpolation only, no alternative inferential CI or primary claim",
                }
                gains.append(result)
                local_gains.append(result)
        if plots:
            for metric in ("ber", "ser", "fer"):
                plot_rate(group, metric, plot_directory)
            if sweep == "amplitude":
                for metric in ("ber", "ser"):
                    plot_rate(group, metric, plot_directory, energy=True)
            plot_runtime(group, plot_directory)
            plot_gain(group, local_gains, plot_directory)
        print(group["id"], "trials=", len(trials), "points=", len(group["points"]), flush=True)
    if plots:
        for design in coverage:
            if design["status"] == "NOT_STARTED":
                plot_missing_design(design, plot_directory)
            else:
                # Remove this script's obsolete derived placeholder, if data arrived.
                stem = "_".join((design["phase"], design["scenario"], design["sweep"])) + "_no_data"
                for suffix in ("png", "svg"):
                    (plot_directory / f"{stem}.{suffix}").unlink(missing_ok=True)
    meta = {
        "schema": "scientific-exp01-analysis-v1",
        "record_count": len(rows),
        "bootstrap_replicates": replicates,
        "bootstrap_root_seed": seed,
        "targets_ber": targets,
        "phases_are_separate": True,
        "paper_exact": False,
        "plots_refreshed": plots,
        "planned_group_coverage": coverage,
        "planned_phase_coverage": {
            phase: {
                "expected_trials": sum(
                    value["expected_trials"] for value in coverage if value["phase"] == phase
                ),
                "observed_trials": sum(
                    value["observed_trials"] for value in coverage if value["phase"] == phase
                ),
                "status": "COMPLETE"
                if all(
                    value["status"] == "COMPLETE" for value in coverage if value["phase"] == phase
                )
                else "INCOMPLETE",
            }
            for phase in sorted({value["phase"] for value in coverage})
        },
        "ci_interpretation": "pointwise paired trial-cluster percentile 95%; no simultaneous coverage adjustment; low trial counts exploratory",
        "zero_error_policy": "no pseudocount; zero BER is observed count only; independent-frame one-sided FER upper95 reported",
    }
    write_json(directory / "aggregates.json", {**meta, "groups": groups})
    export_csv(groups, directory / "aggregates.csv")
    write_json(directory / "gains.json", {**meta, "analyses": gains})
    write_json(
        directory / "sweep_comparison.json", {**meta, "comparisons": sweep_comparison(groups)}
    )
    manifest = {
        **meta,
        "excluded_uncommitted_records": excluded,
        "source_records": [row["source"] for row in rows],
        "execution_snapshots": {
            phase: json.loads((root / f"{phase}_execution.json").read_text())
            if (root / f"{phase}_execution.json").exists()
            else None
            for phase in ("pilot", "confirmatory", "long")
        },
        "derived_files_sha256": {
            path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.rglob("*"))
            if path.is_file() and path.name != "analysis_manifest.json"
        },
    }
    write_json(directory / "analysis_manifest.json", manifest)
    return {
        "records": len(rows),
        "groups": len(groups),
        "gain_analyses": len(gains),
        "output": str(directory),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("outputs/scientific_exp_01"))
    parser.add_argument("--targets", type=float, nargs="+", default=[0.01, 0.05])
    parser.add_argument("--replicates", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=83201)
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Recount tables only; existing plots are not refreshed",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            analyze(args.root, args.targets, args.replicates, args.seed, plots=not args.no_plots)
        )
    )


if __name__ == "__main__":
    main()
