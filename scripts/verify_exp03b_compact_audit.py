from __future__ import annotations

import csv
import hashlib
import json
import math
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE if (HERE / "05_SOURCE_CODE").is_dir() else HERE.parent
PROTOCOL_SHA = "d553e65fdad020f4887d252bb29bd88311b84b596bbba1e14fd4a806e71068c6"
sys.path.insert(0, str(ROOT / "05_SOURCE_CODE/src"))
from hf_tcm.repro.scientific_exp03b_analysis import (  # noqa: E402
    aggregate_paired_trials,
    estimate_paired_gain,
)

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def as_int(value: str | int | float | None) -> int:
    return int(float(value or 0))


def as_float(value: str | float | int | None) -> float | None:
    return None if value in (None, "") else float(value)


def close(a: float | None, b: float | None, tolerance: float = 1e-10) -> bool:
    return (
        a is not None and b is not None and math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)
    )


def context_seed(root_seed: int, context: str, index: int) -> int:
    digest = hashlib.sha256(context.encode("utf-8")).digest()
    return int(
        np.random.SeedSequence(
            [root_seed, int.from_bytes(digest[:4], "little"), index]
        ).generate_state(1, dtype=np.uint32)[0]
    )


def metric_record(row: dict[str, str]) -> dict:
    return {
        "trial_id": row["trial_id"],
        "scenario": row["scenario"],
        "sweep": row["sweep"],
        "phase": "confirmatory",
        "gamma_db": float(row["gamma_b_discrete_db"]),
        "noise_variance": float(row["noise_complex_variance"]),
        "bits": as_int(row["euclidean_bits"]),
        "pairs": as_int(row["euclidean_pairs"]),
        "bit_errors": {
            "euclidean": as_int(row["euclidean_bit_errors"]),
            "hamming": as_int(row["hamming_bit_errors"]),
        },
        "pair_errors": {
            "euclidean": as_int(row["euclidean_pair_errors"]),
            "hamming": as_int(row["hamming_pair_errors"]),
        },
        "frame_errors": {
            "euclidean": as_int(row["euclidean_fer"]),
            "hamming": as_int(row["hamming_fer"]),
        },
        "tx_energy_discrete": float(row["transmit_energy_discrete"]),
        "payload_signal_symbols": as_int(row["payload_symbols"]),
        "total_signal_symbols": as_int(row["frame_symbols_total"]),
    }


def system_record(row: dict[str, str]) -> dict:
    arms = [arm for arm in ("joint", "b0", "b1") if row.get(f"{arm}_bit_errors", "") != ""]
    return {
        "trial_id": row["trial_id"],
        "scenario": row["scenario"],
        "sweep": row["sweep"],
        "phase": "confirmatory",
        "gamma_db": float(row["gamma_b_discrete_db"]),
        "noise_variance": float(row["noise_complex_variance"]),
        "bits": as_int(row["information_bits"]),
        "pairs": as_int(row["information_pairs"]),
        "bit_errors": {arm: as_int(row[f"{arm}_bit_errors"]) for arm in arms},
        "pair_errors": {arm: as_int(row[f"{arm}_pair_errors"]) for arm in arms},
        "frame_errors": {arm: as_int(row[f"{arm}_frame_errors"]) for arm in arms},
        "tx_energy_discrete": float(row["transmit_energy_discrete"]),
        "payload_signal_symbols": as_int(row["information_bits"]) // 2,
        "total_signal_symbols": as_int(row["frame_symbols"]),
    }


def main() -> int:
    manifest = json.loads((ROOT / "AUDIT_MANIFEST.json").read_text(encoding="utf-8"))
    manifest_files = manifest["files"]
    all_files_ok = len(manifest_files) == manifest["file_count_excluding_manifest"]
    seen_paths: set[str] = set()
    for item in manifest_files:
        p = ROOT / item["path"]
        if (
            item["path"] in seen_paths
            or not p.is_file()
            or p.stat().st_size != item["size_bytes"]
            or sha_file(p) != item["sha256"]
        ):
            all_files_ok = False
            break
        seen_paths.add(item["path"])
    check("all_manifest_sha256", all_files_ok, f"{len(manifest_files)} files")

    protocol_path = ROOT / "01_PROTOCOL/configurations/SCIENTIFIC_EXP_03B_PROTOCOL.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    check("frozen_protocol_sha256", sha_file(protocol_path) == PROTOCOL_SHA)
    metric = load_rows(ROOT / "02_ALL_TRIAL_AGGREGATES/metric_trial_summary.csv")
    system = load_rows(ROOT / "02_ALL_TRIAL_AGGREGATES/system_trial_summary.csv")
    pairing = load_rows(ROOT / "02_ALL_TRIAL_AGGREGATES/observation_pairing_audit.csv")
    trial_ids = [row["trial_id"] for row in metric + system]
    check("metric_trial_count", len(metric) == 22800, str(len(metric)))
    check("system_trial_count", len(system) == 8300, str(len(system)))
    check("total_trial_count", len(trial_ids) == 31100, str(len(trial_ids)))
    check("unique_trial_ids", len(trial_ids) == len(set(trial_ids)), str(len(set(trial_ids))))
    check(
        "trial_protocol_hashes",
        all(row["protocol_sha256"] == PROTOCOL_SHA for row in metric + system),
    )
    check(
        "paired_observation_hashes",
        len(pairing) == 31100
        and all(
            (row.get("observation_hashes_equal") or row.get("receiver_hashes_equal", "")).lower()
            == "true"
            for row in pairing
        ),
        str(len(pairing)),
    )
    check(
        "shared_metric_frontend_hashes",
        all(
            (row.get("frontend_hashes_equal", "true") or "true").lower() == "true"
            for row in pairing
            if row["block"] == "A_metric_isolation"
        ),
    )
    check(
        "source_hashes_present",
        all(
            len(row["record_sha256"]) == 64 and len(row["array_sha256"]) == 64
            for row in metric + system
        ),
    )
    source_manifest_path = ROOT / "07_VERIFICATION/integrity_checks/full_archive_manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_files = {item["path"]: item for item in source_manifest["files"]}
    source_commitments_ok = all(
        row["source_record_path"] in source_files
        and row["source_array_path"] in source_files
        and source_files[row["source_record_path"]]["sha256"] == row["record_sha256"]
        and source_files[row["source_array_path"]]["sha256"] == row["array_sha256"]
        for row in metric + system
    )
    check(
        "trial_hashes_match_full_archive_manifest",
        source_commitments_ok,
        f"{len(metric) + len(system)} record/array pairs checked against {len(source_files)} source manifest entries",
    )

    metric_groups: dict[tuple[str, str, float], dict] = {}
    for row in metric:
        key = (row["scenario"], row["sweep"], float(row["gamma_b_discrete_db"]))
        group = metric_groups.setdefault(
            key,
            {
                "trials": 0,
                "bits": 0,
                "pairs": 0,
                "e": 0,
                "h": 0,
                "ep": 0,
                "hp": 0,
                "ef": 0,
                "hf": 0,
            },
        )
        group["trials"] += 1
        group["bits"] += as_int(row["euclidean_bits"])
        group["pairs"] += as_int(row["euclidean_pairs"])
        group["e"] += as_int(row["euclidean_bit_errors"])
        group["h"] += as_int(row["hamming_bit_errors"])
        group["ep"] += as_int(row["euclidean_pair_errors"])
        group["hp"] += as_int(row["hamming_pair_errors"])
        group["ef"] += as_int(row["euclidean_fer"])
        group["hf"] += as_int(row["hamming_fer"])
    metric_points = load_rows(ROOT / "02_ALL_TRIAL_AGGREGATES/metric_isolation_all_points.csv")
    metric_points_ok = True
    for point in metric_points:
        key = (point["scenario"], point["sweep"], float(point["gamma_b_d_db"]))
        total = metric_groups.get(key)
        if (
            total is None
            or total["trials"] != as_int(point["trials"])
            or total["bits"] != as_int(point["bits_per_arm"])
        ):
            metric_points_ok = False
            break
        for field, col in (
            ("e", "euclidean_bit_errors"),
            ("h", "hamming_bit_errors"),
        ):
            if total[field] != as_int(point[col]):
                metric_points_ok = False
                break
        if not metric_points_ok:
            break
        if not (
            close(total["e"] / total["bits"], float(point["euclidean_ber"]))
            and close(total["h"] / total["bits"], float(point["hamming_ber"]))
            and close(total["ep"] / total["pairs"], float(point["euclidean_pair_ser"]))
            and close(total["hp"] / total["pairs"], float(point["hamming_pair_ser"]))
            and close(total["ef"] / total["trials"], float(point["euclidean_fer"]))
            and close(total["hf"] / total["trials"], float(point["hamming_fer"]))
        ):
            metric_points_ok = False
            break
    check("metric_all_energy_point_recount", metric_points_ok, f"{len(metric_points)} points")

    system_groups: dict[tuple[str, float], dict] = {}
    for row in system:
        key = (row["scenario"], float(row["gamma_b_discrete_db"]))
        group = system_groups.setdefault(key, {"trials": 0, "bits": 0, "pairs": 0, "arms": {}})
        group["trials"] += 1
        group["bits"] += as_int(row["information_bits"])
        group["pairs"] += as_int(row["information_pairs"])
        for arm in ("joint", "b0", "b1"):
            if row.get(f"{arm}_bit_errors", "") == "":
                continue
            acc = group["arms"].setdefault(
                arm, {"bits": 0, "pairs": 0, "errors": 0, "pair_errors": 0, "frame_errors": 0}
            )
            acc["bits"] += as_int(row[f"{arm}_bits"])
            acc["pairs"] += as_int(row[f"{arm}_pairs"])
            acc["errors"] += as_int(row[f"{arm}_bit_errors"])
            acc["pair_errors"] += as_int(row[f"{arm}_pair_errors"])
            acc["frame_errors"] += as_int(row[f"{arm}_frame_errors"])
    system_points = load_rows(ROOT / "02_ALL_TRIAL_AGGREGATES/full_system_all_points.csv")
    system_points_ok = True
    for point in system_points:
        total = system_groups.get((point["scenario"], float(point["gamma_b_d_db"])))
        arm = point["arm"]
        if total is None or total["trials"] != as_int(point["trials"]) or arm not in total["arms"]:
            system_points_ok = False
            break
        acc = total["arms"][arm]
        if acc["errors"] != as_int(point["bit_errors"]) or acc["pair_errors"] != as_int(
            point["information_pair_errors"]
        ):
            system_points_ok = False
            break
        if not (
            close(acc["errors"] / acc["bits"], float(point["ber"]))
            and close(acc["pair_errors"] / acc["pairs"], float(point["pair_ser"]))
            and close(acc["frame_errors"] / total["trials"], float(point["fer"]))
        ):
            system_points_ok = False
            break
    check("system_all_energy_point_recount", system_points_ok, f"{len(system_points)} rows")

    gains = load_rows(ROOT / "03_RESULTS/energy_gain/energy_gain_summary.csv")
    gain_formula_ok = True
    for row in gains:
        gain = as_float(row["gain_db"])
        e1, e2 = as_float(row["energy_1_discrete_eb"]), as_float(row["energy_2_discrete_eb"])
        if gain is not None:
            if (
                e1 is None
                or e2 is None
                or e1 <= 0
                or e2 <= 0
                or not close(10 * math.log10(e2 / e1), gain, 1e-9)
            ):
                gain_formula_ok = False
                break
            low, high = as_float(row["ci95_low_db"]), as_float(row["ci95_high_db"])
            if (low is None) != (high is None):
                gain_formula_ok = False
                break
            if row["status"] == "PRECISION_CRITERIA_MET" and low is None:
                gain_formula_ok = False
                break
    check("gain_formula_and_ci_records", gain_formula_ok, f"{len(gains)} comparison-target rows")

    # Exact independent replay of pooled confidence intervals and crossing bootstrap.
    snapshot = json.loads(
        (ROOT / "03_RESULTS/independent_analysis.json").read_text(encoding="utf-8")
    )
    reps, root_seed = int(snapshot["bootstrap_replicates"]), int(snapshot["bootstrap_seed_root"])
    bootstrap_ok, point_count = True, 0
    bootstrap_failures: list[str] = []
    targets_metric = [float(v) for v in protocol["metric_isolation"]["targets_ber"].values()]
    targets_system = [float(v) for v in protocol["system_comparison"]["targets_ber"]]
    for scenario, sweeps in snapshot["metric_isolation"].items():
        for sweep, section in sweeps.items():
            records = [
                metric_record(row)
                for row in metric
                if row["scenario"] == scenario and row["sweep"] == sweep
            ]
            seed = context_seed(root_seed, f"metric:{scenario}:{sweep}", 0)
            point_results = aggregate_paired_trials(records, replicates=reps, seed=seed)
            expected = section["point_summaries"]
            if len(point_results) != len(expected):
                bootstrap_ok = False
                bootstrap_failures.append(
                    f"metric {scenario}/{sweep} point count {len(point_results)} != {len(expected)}"
                )
                continue
            for actual, saved in zip(point_results, expected):
                point_count += 1
                for arm in ("euclidean", "hamming"):
                    for metric_name in ("ber", "ser_information_pairs", "fer"):
                        if not close(actual[metric_name][arm], saved[metric_name][arm]):
                            bootstrap_ok = False
                            if len(bootstrap_failures) < 5:
                                bootstrap_failures.append(
                                    f"metric {scenario}/{sweep}/{actual['gamma_db']} {metric_name}/{arm} point value"
                                )
                        if any(
                            not close(x, y)
                            for x, y in zip(
                                actual["bootstrap_95ci"][metric_name][arm],
                                saved["bootstrap_95ci"][metric_name][arm],
                            )
                        ):
                            bootstrap_ok = False
                            if len(bootstrap_failures) < 5:
                                bootstrap_failures.append(
                                    f"metric {scenario}/{sweep}/{actual['gamma_db']} {metric_name}/{arm} CI"
                                )
            if sweep == "amplitude_fixed_noise":
                for index, target in enumerate(targets_metric):
                    actual = estimate_paired_gain(
                        records,
                        target=target,
                        euclidean_arm="euclidean",
                        hamming_arm="hamming",
                        replicates=reps,
                        seed=context_seed(root_seed, f"metric-gain:{scenario}", index),
                    )
                    saved = section["metric_gain"][f"{target:g}"]
                    if actual.get("gain_db_log_ber") != saved.get("gain_db_log_ber") and not close(
                        actual.get("gain_db_log_ber"), saved.get("gain_db_log_ber")
                    ):
                        bootstrap_ok = False
                        if len(bootstrap_failures) < 5:
                            bootstrap_failures.append(
                                f"metric {scenario} target {target:g} gain point"
                            )
                    for mode in ("log_ber", "linear_ber"):
                        got, ref = actual["bootstrap"][mode], saved["bootstrap"][mode]
                        if (
                            got["valid_replicates"] != ref["valid_replicates"]
                            or got["valid_fraction"] != ref["valid_fraction"]
                        ):
                            bootstrap_ok = False
                            if len(bootstrap_failures) < 5:
                                bootstrap_failures.append(
                                    f"metric {scenario} target {target:g} {mode} bootstrap"
                                )
                        gi, ri = got.get("gain_db_ci95"), ref.get("gain_db_ci95")
                        if (gi is None) != (ri is None) or (
                            gi is not None and any(not close(x, y, 1e-9) for x, y in zip(gi, ri))
                        ):
                            bootstrap_ok = False
                            if len(bootstrap_failures) < 5:
                                bootstrap_failures.append(
                                    f"metric {scenario} target {target:g} {mode} gain CI"
                                )
    for scenario, section in snapshot["full_system_comparison"].items():
        records = [system_record(row) for row in system if row["scenario"] == scenario]
        point_results = aggregate_paired_trials(
            records, replicates=reps, seed=context_seed(root_seed, f"system:{scenario}", 0)
        )
        expected = section["point_summaries"]
        if len(point_results) != len(expected):
            bootstrap_ok = False
            bootstrap_failures.append(
                f"system {scenario} point count {len(point_results)} != {len(expected)}"
            )
            continue
        for actual, saved in zip(point_results, expected):
            point_count += 1
            for arm in saved["ber"]:
                for metric_name in ("ber", "ser_information_pairs", "fer"):
                    if not close(actual[metric_name][arm], saved[metric_name][arm]) or any(
                        not close(x, y)
                        for x, y in zip(
                            actual["bootstrap_95ci"][metric_name][arm],
                            saved["bootstrap_95ci"][metric_name][arm],
                        )
                    ):
                        bootstrap_ok = False
                        if len(bootstrap_failures) < 5:
                            bootstrap_failures.append(
                                f"system {scenario}/{actual['gamma_db']} {metric_name}/{arm} point/CI"
                            )
        for index, target in enumerate(targets_system):
            for arm in section["energy_gain"][f"{target:g}"]:
                actual = estimate_paired_gain(
                    records,
                    target=target,
                    euclidean_arm="joint",
                    hamming_arm=arm,
                    replicates=reps,
                    seed=context_seed(root_seed, f"system-gain:{scenario}:{arm}", index),
                )
                saved = section["energy_gain"][f"{target:g}"][arm]
                if actual.get("gain_db_log_ber") != saved.get("gain_db_log_ber") and not close(
                    actual.get("gain_db_log_ber"), saved.get("gain_db_log_ber")
                ):
                    bootstrap_ok = False
                    if len(bootstrap_failures) < 5:
                        bootstrap_failures.append(
                            f"system {scenario} target {target:g}/{arm} gain point"
                        )
                for mode in ("log_ber", "linear_ber"):
                    got, ref = actual["bootstrap"][mode], saved["bootstrap"][mode]
                    if (
                        got["valid_replicates"] != ref["valid_replicates"]
                        or got["valid_fraction"] != ref["valid_fraction"]
                    ):
                        bootstrap_ok = False
                        if len(bootstrap_failures) < 5:
                            bootstrap_failures.append(
                                f"system {scenario} target {target:g}/{arm}/{mode} bootstrap"
                            )
                    gi, ri = got.get("gain_db_ci95"), ref.get("gain_db_ci95")
                    if (gi is None) != (ri is None) or (
                        gi is not None and any(not close(x, y, 1e-9) for x, y in zip(gi, ri))
                    ):
                        bootstrap_ok = False
                        if len(bootstrap_failures) < 5:
                            bootstrap_failures.append(
                                f"system {scenario} target {target:g}/{arm}/{mode} gain CI"
                            )
    check(
        "full_trial_cluster_bootstrap_replay",
        bootstrap_ok,
        f"{point_count} energy-point summaries; {reps} resamples; {bootstrap_failures[:5]}",
    )

    sample_manifest = json.loads(
        (ROOT / "06_PRIMARY_DATA_SAMPLES/sample_manifest.json").read_text(encoding="utf-8")
    )
    sample_ok, sample_count = True, 0
    for sample in sample_manifest["samples"]:
        rec_path = ROOT / "06_PRIMARY_DATA_SAMPLES" / sample["included_record_path"]
        arr_path = ROOT / "06_PRIMARY_DATA_SAMPLES" / sample["included_array_path"]
        if (
            sha_file(rec_path) != sample["included_record_sha256"]
            or sha_file(arr_path) != sample["included_array_sha256"]
        ):
            sample_ok = False
            break
        record = json.loads(rec_path.read_text(encoding="utf-8"))
        with np.load(arr_path, allow_pickle=False) as arrays:
            if sample["block"] == "A_metric_isolation":
                mask = arrays["payload_mask"].astype(bool)
                reference_all = arrays["reference_payload_pairs"]
                reference = (
                    reference_all[mask] if len(reference_all) == len(mask) else reference_all
                )
                for arm, key in (
                    ("euclidean", "decoded_euclidean_pairs"),
                    ("hamming", "decoded_hamming_pairs"),
                ):
                    decoded_all = arrays[key]
                    decoded = decoded_all[mask] if len(decoded_all) == len(mask) else decoded_all
                    difference = reference != decoded
                    errors = int(np.count_nonzero(difference))
                    pair_errors = int(np.count_nonzero(np.any(difference, axis=1)))
                    if (
                        errors != record[arm]["bit_errors"]
                        or pair_errors != record[arm]["pair_errors"]
                        or errors > record[arm]["bits"]
                        or len(reference) * 2 != record[arm]["bits"]
                        or len(reference) != record[arm]["pairs"]
                    ):
                        sample_ok = False
                tx = arrays["transmitted_samples"].astype(np.complex128)
                energy = float(np.vdot(tx, tx).real)
                if not close(energy, record["transmit_energy_discrete"], 1e-9) or not close(
                    energy / record["payload_information_bits"],
                    record["energy_per_payload_bit_discrete"],
                    1e-9,
                ):
                    sample_ok = False
            else:
                rec = record["record"]
                bits = arrays["information_bits"].reshape(-1)
                for arm, key in (
                    ("joint", "joint_decoded_bits"),
                    ("b0", "b0_decoded_bits"),
                    ("b1", "b1_decoded_bits"),
                ):
                    if key not in arrays.files:
                        continue
                    diff = bits != arrays[key].reshape(-1)
                    errors = int(np.count_nonzero(diff))
                    pair_errors = int(np.count_nonzero(np.any(diff.reshape(-1, 2), axis=1)))
                    if (
                        errors != rec["bit_errors"][arm]
                        or pair_errors != rec["pair_errors"][arm]
                        or len(bits) != rec["bits"]
                    ):
                        sample_ok = False
                tx = arrays["tx_samples"].astype(np.complex128)
                energy = float(np.vdot(tx, tx).real)
                if not close(energy, rec["tx_energy"], 1e-9) or not close(
                    energy / rec["bits"], rec["eb_d"], 1e-9
                ):
                    sample_ok = False
        sample_count += 1
    check(
        "sample_raw_array_recount",
        sample_ok,
        f"{sample_count}/{len(sample_manifest['samples'])} complete trial arrays",
    )

    figures = [p for p in (ROOT / "04_FIGURES").rglob("*") if p.is_file()]
    figures_ok = bool(figures)
    for path in figures:
        raw = path.read_bytes()
        if path.suffix.lower() == ".png":
            if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                figures_ok = False
            else:
                width, height = struct.unpack(">II", raw[16:24])
                figures_ok &= width >= 600 and height >= 400
        elif path.suffix.lower() == ".svg":
            try:
                ET.fromstring(raw)
            except ET.ParseError:
                figures_ok = False
    check("png_svg_content", figures_ok, f"{len(figures)} exported files")

    for name, passed, detail in CHECKS:
        print(f"{'PASS' if passed else 'FAIL'}\t{name}\t{detail}")
    passed_count = sum(passed for _, passed, _ in CHECKS)
    print(f"SUMMARY: {passed_count}/{len(CHECKS)} checks passed")
    print(
        "COVERAGE: all 31,100 trial counters, all per-energy BER/SER/FER points, all registered cluster bootstrap intervals and gain crossings; direct NPZ recount for the included deterministic sample only."
    )
    return 0 if passed_count == len(CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
