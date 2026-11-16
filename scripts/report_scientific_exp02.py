"""Prepare thesis tables and figures from EXP-01B and EXP-02 measured data."""

from __future__ import annotations

import csv
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EXP01B = ROOT / "outputs" / "scientific_exp_01b"
EXP02 = ROOT / "outputs" / "scientific_exp_02"
FIGURES = EXP02 / "thesis_figures"
TABLES = EXP02 / "thesis_tables"
PRIOR = EXP02 / "prior_sensitivity"


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _save_prior_figures(analysis: dict[str, Any]) -> None:
    variants = analysis["points"][0]["metrics"].keys()
    labels = {
        "exact": "Точний номінальний prior",
        "neutral": "Нейтральний prior",
        "amplitude_minus_10pct": "Амплітуда prior −10%",
        "amplitude_plus_10pct": "Амплітуда prior +10%",
        "phase_minus_15deg": "Фаза prior −15°",
        "phase_plus_15deg": "Фаза prior +15°",
    }
    colors = {
        "exact": "#087f8c",
        "neutral": "#b42318",
        "amplitude_minus_10pct": "#3b6fb6",
        "amplitude_plus_10pct": "#7956a8",
        "phase_minus_15deg": "#d17c00",
        "phase_plus_15deg": "#2d7d46",
    }
    x = np.asarray([point["gamma_db"] for point in analysis["points"]], dtype=float)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 12,
            "svg.fonttype": "none",
        }
    )
    fig, ax = plt.subplots(figsize=(9.5, 5.6), constrained_layout=True)
    for variant in variants:
        y = np.asarray([point["metrics"][variant]["ber"] for point in analysis["points"]])
        ax.plot(
            x,
            y,
            marker="o",
            linewidth=1.8,
            markersize=5,
            label=labels[variant],
            color=colors[variant],
        )
    ax.set_title("Чутливість спільного приймача до початкових оцінок каналу")
    ax.set_xlabel("Нормована дискретна енергетична шкала γᵦ,ᵈ (дБ)")
    ax.set_ylabel("BER інформаційних бітів (частка 0–1)")
    ax.set_ylim(0, 0.72)
    ax.set_xticks(x)
    ax.grid(True, alpha=0.25)
    ax.legend(ncols=2, frameon=True, fontsize=8, loc="upper right")
    ax.text(
        0.01,
        0.01,
        "Дослідницька підвибірка: 8 парних кадрів на точку, F=256; без оцінки energy gain.",
        transform=ax.transAxes,
        fontsize=8,
        va="bottom",
    )
    fig.savefig(FIGURES / "prior_sensitivity_ber.png", dpi=220)
    fig.savefig(FIGURES / "prior_sensitivity_ber.svg")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.5, 5.6), constrained_layout=True)
    for variant in variants:
        if variant == "exact":
            continue
        means = np.asarray(
            [
                point["metrics"][variant]["mean_paired_ber_delta_vs_exact"]
                for point in analysis["points"]
            ]
        )
        intervals = np.asarray(
            [
                point["metrics"][variant]["paired_frame_cluster_bootstrap_95_ci_ber_delta"]
                for point in analysis["points"]
            ],
            dtype=float,
        )
        lower, upper = means - intervals[:, 0], intervals[:, 1] - means
        ax.errorbar(
            x,
            means,
            yerr=np.vstack((lower, upper)),
            marker="o",
            capsize=3,
            linewidth=1.4,
            label=labels[variant],
            color=colors[variant],
        )
    ax.axhline(0, color="#263238", linewidth=1)
    ax.set_title("Парна зміна BER відносно точного номінального prior")
    ax.set_xlabel("Нормована дискретна енергетична шкала γᵦ,ᵈ (дБ)")
    ax.set_ylabel("ΔBER на тому самому кадрі (частка)")
    ax.set_xticks(x)
    ax.grid(True, alpha=0.25)
    ax.legend(ncols=2, frameon=True, fontsize=8, loc="best")
    ax.text(
        0.01,
        0.01,
        "Вуса: 95% bootstrap за цілими кадрами; n=8, розвідувальна оцінка.",
        transform=ax.transAxes,
        fontsize=8,
        va="bottom",
    )
    fig.savefig(FIGURES / "prior_sensitivity_paired_delta.png", dpi=220)
    fig.savefig(FIGURES / "prior_sensitivity_paired_delta.svg")
    plt.close(fig)


def build() -> dict[str, Any]:
    FIGURES.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    original = _json(EXP01B / "analysis" / "analysis_results.json")
    sensitivity = _json(PRIOR / "analysis.json")
    static = original["scenarios"]["static"]
    rician = original["scenarios"]["rician"]

    for name in (
        "static_ber",
        "static_ser",
        "static_energy_gain",
        "static_runtime",
        "rician_ber",
        "rician_ser",
        "rician_energy_gain",
        "rician_runtime",
    ):
        for extension in ("png", "svg"):
            source = EXP01B / "analysis" / "plots" / f"{name}.{extension}"
            if not source.is_file():
                raise FileNotFoundError(source)
            shutil.copyfile(source, FIGURES / source.name)

    _save_prior_figures(sensitivity)

    static_rows = []
    for point in static["aggregate_points"]:
        for arm in ("joint", "b0", "b1"):
            static_rows.append(
                {
                    "scenario": "static multipath [0,3]",
                    "gamma_b_d_db": point["gamma_db"],
                    "E_b_d": point["eb_d"],
                    "independent_trials": point["trials"],
                    "bits": point["bits"],
                    "receiver": arm,
                    "bit_errors": point["bit_errors"][arm],
                    "BER": point["ber"][arm],
                    "information_pair_errors": point["pair_errors"][arm],
                    "information_pairs": point["pairs"],
                    "information_pair_SER": point["ser"][arm],
                    "frame_errors": point["frame_errors"][arm],
                    "FER": point["fer"][arm],
                }
            )
    _write_csv(TABLES / "static_ber_ser_by_energy.csv", list(static_rows[0]), static_rows)

    rician_rows = []
    for point in rician["aggregate_points"]:
        for arm in ("joint", "b0"):
            rician_rows.append(
                {
                    "scenario": "Rician AR(1) multipath",
                    "gamma_b_d_db": point["gamma_db"],
                    "E_b_d": point["eb_d"],
                    "independent_trials": point["trials"],
                    "bits": point["bits"],
                    "receiver": arm,
                    "bit_errors": point["bit_errors"][arm],
                    "BER": point["ber"][arm],
                    "information_pair_errors": point["pair_errors"][arm],
                    "information_pairs": point["pairs"],
                    "information_pair_SER": point["ser"][arm],
                    "frame_errors": point["frame_errors"][arm],
                    "FER": point["fer"][arm],
                }
            )
    _write_csv(TABLES / "rician_ber_ser_by_energy.csv", list(rician_rows[0]), rician_rows)

    runtime_rows = []
    for scenario_name, scenario_data, arms in (
        ("Static multipath [0,3]", static, ("joint", "b0", "b1")),
        ("Rician AR(1) multipath", rician, ("joint", "b0")),
    ):
        for arm in arms:
            samples = np.asarray(
                [
                    value
                    for point in scenario_data["aggregate_points"]
                    for value in point["runtime_seconds"][arm]
                ],
                dtype=float,
            )
            runtime_rows.append(
                {
                    "scenario": scenario_name,
                    "receiver": arm,
                    "measured_receiver_calls": int(samples.size),
                    "median_runtime_seconds": float(np.median(samples)),
                    "p90_runtime_seconds": float(np.quantile(samples, 0.9)),
                    "mean_runtime_seconds": float(np.mean(samples)),
                }
            )
    _write_csv(TABLES / "receiver_runtime_summary.csv", list(runtime_rows[0]), runtime_rows)

    gain_rows = []
    for target, comparisons in static["target_gain_analysis"].items():
        for arm, result in comparisons.items():
            interval = result["bootstrap"].get("confidence_interval_db")
            gain_rows.append(
                {
                    "scenario": "static multipath [0,3]",
                    "target_BER": float(target),
                    "comparison": f"Joint/{arm.upper()}",
                    "gamma_joint_db": result["required_gamma_db"]["joint"],
                    "gamma_separate_db": result["required_gamma_db"]["separate"],
                    "E_b_d_joint": result["required_eb_d"]["joint"],
                    "E_b_d_separate": result["required_eb_d"]["separate"],
                    "model_gain_db": result["gain_db"],
                    "CI95_low_db": interval[0] if interval else None,
                    "CI95_high_db": interval[1] if interval else None,
                    "valid_bootstrap_fraction": result["bootstrap"]["valid_fraction"],
                    "valid_bootstrap_replicates": result["bootstrap"]["valid_replicates"],
                    "total_bootstrap_replicates": result["bootstrap"]["total_replicates"],
                    "status": result["status"],
                }
            )
    _write_csv(TABLES / "static_required_energy_and_gain.csv", list(gain_rows[0]), gain_rows)

    sensitivity_rows = []
    for point in sensitivity["points"]:
        for variant, metrics in point["metrics"].items():
            ci = metrics["paired_frame_cluster_bootstrap_95_ci_ber_delta"]
            sensitivity_rows.append(
                {
                    "gamma_b_d_db": point["gamma_db"],
                    "frames": metrics["trials"],
                    "prior_variant": variant,
                    "bit_errors": metrics["bit_errors"],
                    "bits": metrics["bits"],
                    "BER": metrics["ber"],
                    "information_pair_errors": metrics["pair_errors"],
                    "information_pairs": metrics["pairs"],
                    "information_pair_SER": metrics["information_pair_ser"],
                    "frame_errors": metrics["frame_errors"],
                    "FER": metrics["fer"],
                    "paired_mean_delta_BER_vs_exact": metrics["mean_paired_ber_delta_vs_exact"],
                    "paired_bootstrap95_low": ci[0] if ci else None,
                    "paired_bootstrap95_high": ci[1] if ci else None,
                    "mean_runtime_seconds": metrics["mean_runtime_seconds"],
                }
            )
    _write_csv(TABLES / "prior_sensitivity.csv", list(sensitivity_rows[0]), sensitivity_rows)

    image_checks = []
    for path in sorted(FIGURES.iterdir()):
        if path.suffix == ".png":
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                rgb = image.convert("RGB")
                extrema = rgb.getextrema()
                visible = len(set(rgb.resize((120, 80)).getdata()))
                if visible < 8 or not any(high > low for low, high in extrema):
                    raise ValueError(f"PNG figure lacks visible chart content: {path.name}")
                image_checks.append(
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "format": "PNG",
                        "size": list(image.size),
                        "sampled_unique_colors": visible,
                        "nonblank": True,
                    }
                )
        elif path.suffix == ".svg":
            tree = ET.parse(path)
            root = tree.getroot()
            elements = list(root.iter())
            paths = sum(
                element.tag.endswith("path") or element.tag.endswith("polyline")
                for element in elements
            )
            texts = sum(element.tag.endswith("text") for element in elements)
            if paths < 5 or texts < 5:
                raise ValueError(f"SVG figure lacks expected plotted content: {path.name}")
            image_checks.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "format": "SVG",
                    "viewBox": root.get("viewBox"),
                    "paths_or_lines": paths,
                    "text_nodes": texts,
                    "nonblank": True,
                }
            )
    validation = {"status": "PASS", "figure_count": len(image_checks), "figures": image_checks}
    (FIGURES / "figure_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return validation


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, sort_keys=True))
