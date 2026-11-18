"""SCIENTIFIC-EXP-04 report artefacts from stored confirmatory trials (no new trials).

python scripts/report_exp04.py [--output outputs/scientific_exp04] [--figures docs/figures/exp04]

* per-point BER of both arms with Wilson 95% intervals (bits pooled per point;
  descriptive — the gain CI comes from the cluster bootstrap in analysis.json);
* independent recount of bit errors from the stored reference/decoded pairs
  (NPZ) and comparison with the JSON counts of every trial;
* BER-vs-Eb/N0 figure (PNG + SVG) and one CSV per cell.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from hf_tcm.evaluation.theory_curves import qpsk_bit_error_probability, wilson_interval
from hf_tcm.repro.exp04_protocol import DEFAULT_OUTPUT, DEFAULT_PROTOCOL, load_protocol

ARMS = (("hamming", "Хемінг (жорстке рішення)"), ("euclidean", "Евклід (м'яке, спільне)"))


def collect(study_root: Path) -> tuple[dict[int, dict[str, int]], dict[str, int]]:
    points: dict[int, dict[str, int]] = {}
    recount = {"trials": 0, "mismatches": 0}
    trial_dir = study_root / "trials"
    for path in sorted(trial_dir.glob("p*-t*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        point = points.setdefault(
            int(row["point_index"]),
            {"bits": 0, "hamming": 0, "euclidean": 0, "trials": 0, "frames_h": 0, "frames_e": 0},
        )
        point["bits"] += int(row["payload_information_bits"])
        point["trials"] += 1
        for arm, _ in ARMS:
            point[arm] += int(row[arm]["bit_errors"])
        point["frames_h"] += int(row["hamming"]["bit_errors"] > 0)
        point["frames_e"] += int(row["euclidean"]["bit_errors"] > 0)
        with np.load(trial_dir / row["array_file"]) as arrays:
            mask = arrays["payload_mask"]
            reference = arrays["reference_payload_pairs"]
            if reference.shape[0] == mask.shape[0]:
                reference = reference[mask]
            for arm in ("euclidean", "hamming"):
                decoded = arrays[f"decoded_{arm}_pairs"]
                if decoded.shape[0] == mask.shape[0]:
                    decoded = decoded[mask]
                errors = int(np.count_nonzero(decoded != reference))
                recount["mismatches"] += int(errors != int(row[arm]["bit_errors"]))
        recount["trials"] += 1
    return points, recount


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", default=str(DEFAULT_PROTOCOL))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--figures", default="docs/figures/exp04")
    args = parser.parse_args()
    protocol, digest, status = load_protocol(Path(args.protocol))
    output = Path(args.output)
    figures = Path(args.figures)
    figures.mkdir(parents=True, exist_ok=True)

    report: dict[str, object] = {"protocol_sha256": digest, "freeze_status": status, "cells": {}}
    curves = {}
    for cell in protocol["cells"]:
        root = output / "studies" / f"exp04-{cell['id']}"
        points, recount = collect(root)
        rows = []
        for index, eb_n0 in enumerate(cell["eb_n0_grid_db"]):
            point = points[index]
            row = {"eb_n0_db": float(eb_n0), "trials": point["trials"], "bits": point["bits"]}
            for arm, _ in ARMS:
                errors = point[arm]
                low, high = wilson_interval(errors, point["bits"])
                row.update(
                    {
                        f"{arm}_errors": errors,
                        f"{arm}_ber": errors / point["bits"],
                        f"{arm}_lo": low,
                        f"{arm}_hi": high,
                    }
                )
            row["hamming_frames_with_errors"] = point["frames_h"]
            row["euclidean_frames_with_errors"] = point["frames_e"]
            rows.append(row)
        with (figures / f"{cell['id']}_ber.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        curves[cell["id"]] = rows
        report["cells"][cell["id"]] = {"recount": recount, "points": rows}  # type: ignore[index]
        print(
            f"{cell['id']}: {recount['trials']} trials, recount mismatches {recount['mismatches']}"
        )

    (output / "report_points.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    titles = {
        "A1-awgn": "A1: AWGN, прямий тракт",
        "A2-static": "A2: статичні 2 промені, відомий тракт",
        "A3-itu-moderate": "A3: ITU moderate (0,5 Гц), відомий тракт",
        "A4-itu-poor": "A4: ITU poor (1 Гц), відомий тракт",
        "S1-itu-moderate-unweighted": "S1: як A3, незважена метрика",
        "S2-itu-moderate-pilot": "S2: як A3, оцінка за пілотами",
    }
    fig, axes = plt.subplots(3, 2, figsize=(11, 12))
    for axis, cell in zip(axes.flat, protocol["cells"], strict=True):
        rows = curves[cell["id"]]
        x = np.array([row["eb_n0_db"] for row in rows])
        for (arm, label), style in zip(ARMS, ("o-", "s-"), strict=True):
            ber = np.array([row[f"{arm}_ber"] for row in rows])
            positive = ber > 0
            axis.semilogy(x[positive], ber[positive], style, ms=4, label=label)
        xx = np.linspace(x.min(), x.max(), 200)
        axis.semilogy(
            xx,
            [qpsk_bit_error_probability(10 ** (value / 10)) for value in xx],
            "k--",
            lw=0.8,
            label="QPSK без кодування (AWGN)",
        )
        for target in protocol["analysis"]["all_target_ber"]:
            axis.axhline(target, color="0.7", lw=0.6, ls=":")
        axis.set_ylim(1e-6, 0.5)
        axis.set_title(titles[cell["id"]], fontsize=10)
        axis.set_xlabel("Eb/N0, дБ (дискретна модель, N0 = σ²)")
        axis.set_ylabel("BER")
        axis.grid(True, which="both", alpha=0.3)
        axis.legend(fontsize=7)
    fig.suptitle(f"SCIENTIFIC-EXP-04 (підтверджувальна серія, протокол {digest[:12]})")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(figures / f"exp04_ber_curves.{ext}", dpi=150)
    print(f"figures -> {figures}")


if __name__ == "__main__":
    main()
