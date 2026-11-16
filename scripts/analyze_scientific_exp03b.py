"""Independently recount and summarize completed SCIENTIFIC-EXP-03B trials."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from hf_tcm.repro.confirmatory_exp03b import (
    build_metric_trial_spec,
    build_system_trial_spec,
    system_trial_seeds,
)
from hf_tcm.repro.exp03b_runner import (
    load_frozen_protocol,
    sha256_file,
    verify_metric_records,
    verify_system_records,
)
from hf_tcm.repro.scientific_exp03b_analysis import (
    aggregate_paired_trials,
    assess_gain_precision,
    estimate_paired_gain,
)

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs/SCIENTIFIC_EXP_03B_PROTOCOL.json"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _manifest(root: Path, expected: int, protocol_hash: str) -> dict[str, Any]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("protocol_sha256") != protocol_hash:
        raise ValueError(f"protocol hash mismatch in {root}")
    if manifest.get("status") != "completed" or manifest.get("completed_trials") != expected:
        raise ValueError(f"confirmatory series is incomplete: {root}")
    return manifest


def _analysis_bootstrap_settings(protocol: dict[str, Any]) -> tuple[int, int]:
    analysis = protocol["analysis"]
    return int(analysis["bootstrap_seed_root"]), int(analysis["bootstrap_resamples"])


def _analysis_precision_criteria(protocol: dict[str, Any], section_name: str) -> dict[str, Any]:
    section = protocol[section_name]
    criteria = dict(section["precision_criteria"])
    if "per_arm_error_count_at_bracketing_points" not in criteria:
        required_errors = criteria.pop("minimum_errors_per_arm_at_target_bracket")
        if isinstance(required_errors, dict):
            criteria["per_arm_error_count_at_bracketing_points"] = required_errors
        else:
            targets = section.get("targets_ber")
            if targets is None:
                targets = protocol["metric_isolation"]["targets_ber"]
            if isinstance(targets, dict):
                targets = targets.values()
            criteria["per_arm_error_count_at_bracketing_points"] = {
                f"{float(target):g}": int(required_errors) for target in targets
            }
    if (
        "minimum_valid_bootstrap_crossing_fraction" not in criteria
        and "minimum_valid_bootstrap_crossing_fraction" in section
    ):
        criteria["minimum_valid_bootstrap_crossing_fraction"] = section[
            "minimum_valid_bootstrap_crossing_fraction"
        ]
    return criteria


def _system_grid_gamma(
    protocol: dict[str, Any],
    scenario: str,
    point_index: int,
    sidecar_gamma: float,
    record_gamma: float,
    measured_gamma: float,
) -> float:
    """Use the frozen point index while validating recorded/measured energy metadata."""
    grid = protocol["system_comparison"]["energy_grid_gamma_db"][scenario]
    if not 0 <= point_index < len(grid):
        raise ValueError("system trial point index is outside the frozen energy grid")
    expected = float(grid[point_index])
    if not np.isclose(sidecar_gamma, expected, rtol=0.0, atol=1e-12):
        raise ValueError("system sidecar energy point differs from the frozen grid")
    if not np.isclose(record_gamma, expected, rtol=0.0, atol=1e-12):
        raise ValueError("system record energy point differs from the frozen grid")
    if not np.isclose(measured_gamma, expected, rtol=0.0, atol=1e-9):
        raise ValueError("measured energy is outside the frozen point tolerance")
    return expected


def _system_trial_id(scenario: str, point_index: int, trial_index: int) -> str:
    return f"confirmatory-{scenario}-p{point_index:02d}-t{trial_index:04d}"


def _recount_metric_arrays(root: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    energy_checks = 0
    payload_bits = 0
    total_energy = 0.0
    for row in rows:
        array_path = root / "trials" / row["array_file"]
        if sha256_file(array_path) != row["array_file_sha256"]:
            raise ValueError(f"metric array changed during analysis: {array_path}")
        with np.load(array_path, allow_pickle=False) as arrays:
            tx = arrays["transmitted_samples"].astype(np.complex128)
            payload_mask = arrays["payload_mask"].astype(bool)
            pilot_mask = arrays["pilot_mask"].astype(bool)
            reference = arrays["reference_payload_pairs"].astype(np.int8)
            decoded_payload = arrays["decoded_euclidean_pairs"][payload_mask].astype(np.int8)
            if np.any(payload_mask & pilot_mask) or not np.all(payload_mask | pilot_mask):
                raise ValueError("payload/pilot mask does not partition transmitted frame")
            if decoded_payload.shape != reference.shape:
                raise ValueError("decoded payload alignment changed during energy recount")
            energy = float(np.vdot(tx, tx).real)
            bits = int(reference.size)
            eb = energy / bits
            gamma = 10.0 * np.log10(eb / float(row["noise_complex_variance"]))
            if not np.isclose(energy, row["transmit_energy_discrete"], rtol=1e-11, atol=1e-11):
                raise ValueError("transmitted energy disagrees with NPZ samples")
            if not np.isclose(eb, row["energy_per_payload_bit_discrete"], rtol=1e-11, atol=1e-11):
                raise ValueError("energy per payload information bit disagrees with NPZ samples")
            if not np.isclose(gamma, row["gamma_b_discrete_db"], rtol=1e-11, atol=1e-11):
                raise ValueError("discrete energy/noise axis disagrees with NPZ samples")
            symbol_energy = np.abs(tx.reshape(-1, 8)) ** 2
            symbol_energy = symbol_energy.sum(axis=1)
            if len(symbol_energy) != len(payload_mask):
                raise ValueError("sample count is not eight samples per frame symbol")
            payload_energy = float(symbol_energy[payload_mask].sum())
            pilot_energy = float(symbol_energy[pilot_mask].sum())
            if not np.isclose(
                payload_energy, row["payload_energy_discrete"], rtol=1e-11, atol=1e-11
            ):
                raise ValueError("payload energy disagrees with transmitted sample mask")
            if not np.isclose(pilot_energy, row["pilot_energy_discrete"], rtol=1e-11, atol=1e-11):
                raise ValueError("pilot energy disagrees with transmitted sample mask")
            energy_checks += 1
            payload_bits += bits
            total_energy += energy
    return {
        "trial_count": energy_checks,
        "payload_information_bits_recounted": payload_bits,
        "transmit_energy_discrete_recounted": total_energy,
        "tx_energy_and_gamma_recount": "PASS",
    }


def _recount_system_trial_arrays(arrays: Any, record: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Recount each complete receiver's BER, information-pair SER, and FER from saved bits."""
    reference = np.asarray(arrays["information_bits"], dtype=np.int8).reshape(-1)
    if reference.size == 0 or reference.size % 2:
        raise ValueError("full-system information bits must contain complete binary pairs")
    if np.any((reference != 0) & (reference != 1)):
        raise ValueError("full-system reference contains non-binary values")
    pairs = reference.size // 2
    if int(record.get("bits", -1)) != reference.size or int(record.get("pairs", -1)) != pairs:
        raise ValueError("full-system BER/SER denominators disagree with saved information bits")
    arms = set(record.get("bit_errors", {}))
    if (
        not arms
        or arms != set(record.get("pair_errors", {}))
        or arms != set(record.get("frame_errors", {}))
    ):
        raise ValueError("full-system error count arms are inconsistent")
    result: dict[str, dict[str, int]] = {}
    for arm in sorted(arms):
        decoded = np.asarray(arrays[f"{arm}_decoded_bits"], dtype=np.int8).reshape(-1)
        if decoded.shape != reference.shape or np.any((decoded != 0) & (decoded != 1)):
            raise ValueError(f"full-system decoded bits are invalid for {arm}")
        differences = decoded != reference
        bit_errors = int(np.count_nonzero(differences))
        pair_errors = int(np.count_nonzero(differences.reshape(-1, 2).any(axis=1)))
        frame_error = int(bit_errors > 0)
        if (
            bit_errors != int(record["bit_errors"][arm])
            or pair_errors != int(record["pair_errors"][arm])
            or frame_error != int(record["frame_errors"][arm])
        ):
            raise ValueError(f"independent BER/SER/FER recount differs for {arm}")
        if not pair_errors <= bit_errors <= 2 * pair_errors:
            raise ValueError("independent BER and information-pair SER counts are inconsistent")
        result[arm] = {
            "bit_errors": bit_errors,
            "pair_errors": pair_errors,
            "frame_error": frame_error,
        }
    return result


def _validate_system_observation_pair(record: dict[str, Any]) -> None:
    """Require every full-system receiver to reference the exact same observation."""
    observation_hash = record.get("observation_sha256")
    receiver_hashes = record.get("receiver_observation_hashes")
    if not isinstance(observation_hash, str) or len(observation_hash) != 64:
        raise ValueError("full-system observation hash is missing or malformed")
    if not isinstance(receiver_hashes, dict) or not receiver_hashes:
        raise ValueError("full-system per-receiver observation hashes are missing")
    if set(receiver_hashes.values()) != {observation_hash}:
        raise ValueError("full-system receiver observation hashes are not paired")


def _load_metric_series(
    output_root: Path, protocol: dict[str, Any], protocol_hash: str, scenario_key: str, sweep: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scenario = next(
        item for item in protocol["metric_isolation"]["scenarios"] if item["id"] == scenario_key
    )
    grid = scenario["energy_offsets_db"]
    planned = len(grid) * int(protocol["metric_isolation"]["confirmatory_trials_per_point"])
    study_id = f"confirmatory-{scenario_key}-{sweep}"
    root = output_root / "metric" / "confirmatory" / study_id
    manifest = _manifest(root, planned, protocol_hash)
    verification = verify_metric_records(root)
    if verification["record_count"] != planned:
        raise ValueError(f"missing paired metric trial records in {root}")
    paths = sorted((root / "trials").glob("*.json"))
    rows = []
    for path in paths:
        original = json.loads(path.read_text(encoding="utf-8"))
        expected = build_metric_trial_spec(
            protocol,
            scenario_key,
            sweep,
            int(original["point_index"]),
            int(original["trial_index"]),
            "confirmatory",
        )
        if original["trial_id"] != expected.trial_id:
            raise ValueError("metric trial ID is outside the frozen grid")
        expected_seeds = [
            expected.source_seed,
            expected.channel_config.fading_seed,
            expected.channel_config.noise_seed,
        ]
        if original.get("derived_seeds") != expected_seeds:
            raise ValueError("metric trial seeds differ from frozen seed policy")
        if (
            original.get("stage") != "confirmatory"
            or original.get("protocol_sha256") != protocol_hash
        ):
            raise ValueError("metric trial provenance does not identify this confirmatory protocol")
        rows.append(
            {
                "trial_id": original["trial_id"],
                "scenario": scenario_key,
                "sweep": sweep,
                "phase": "confirmatory",
                "gamma_db": float(original["gamma_b_discrete_db"]),
                "noise_variance": float(original["noise_complex_variance"]),
                "bits": int(original["euclidean"]["bits"]),
                "pairs": int(original["euclidean"]["pairs"]),
                "bit_errors": {
                    "euclidean": int(original["euclidean"]["bit_errors"]),
                    "hamming": int(original["hamming"]["bit_errors"]),
                },
                "pair_errors": {
                    "euclidean": int(original["euclidean"]["pair_errors"]),
                    "hamming": int(original["hamming"]["pair_errors"]),
                },
                "frame_errors": {
                    "euclidean": int(original["euclidean"]["fer"]),
                    "hamming": int(original["hamming"]["fer"]),
                },
                "observation_sha256": original["observation_sha256"],
                "frontend_sha256": original["frontend_output_sha256_euclidean"],
                "tx_energy_discrete": float(original["transmit_energy_discrete"]),
                "payload_signal_symbols": int(original["payload_symbols"]),
                "total_signal_symbols": int(original["frame_symbols_total"]),
            }
        )
    energy = _recount_metric_arrays(
        root, [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    )
    return rows, {
        "study_id": study_id,
        "root": root,
        "manifest": manifest,
        "manifest_sha256": sha256_file(root / "manifest.json"),
        "verification": verification,
        "energy_audit": energy,
    }


def _load_system_series(
    output_root: Path, protocol: dict[str, Any], protocol_hash: str, scenario: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grid = protocol["system_comparison"]["energy_grid_gamma_db"][scenario]
    planned = len(grid) * int(protocol["system_comparison"]["confirmatory_trials_per_point"])
    root = output_root / "system" / "confirmatory" / scenario
    manifest = _manifest(root, planned, protocol_hash)
    verification = verify_system_records(root)
    if verification["record_count"] != planned:
        raise ValueError(f"missing paired complete-system trial records in {root}")
    rows = []
    recounted_counts = {
        arm: {"bit_errors": 0, "pair_errors": 0, "frame_errors": 0}
        for arm in protocol["system_comparison"]["channel_profiles"][scenario]["receiver_arms"]
    }
    paths = sorted((root / "trials").glob("*.json"))
    for path in paths:
        sidecar = json.loads(path.read_text(encoding="utf-8"))
        point_index = int(sidecar["point_index"])
        trial_index = int(sidecar["trial_index"])
        spec = build_system_trial_spec(protocol, scenario, point_index, trial_index, "confirmatory")
        expected_seeds = system_trial_seeds(spec, scenario)
        expected_seed_map = dict(zip(("bits", "fading", "noise"), expected_seeds, strict=True))
        record = sidecar["record"]
        grid_gamma = _system_grid_gamma(
            protocol,
            scenario,
            point_index,
            float(sidecar["gamma_db"]),
            float(record["gamma_db"]),
            float(record["gamma_measured_db"]),
        )
        _validate_system_observation_pair(record)
        if (
            sidecar["protocol_sha256"] != protocol_hash
            or sidecar["derived_seeds"] != expected_seed_map
        ):
            raise ValueError("full-system trial provenance or seed domain differs from protocol")
        if record["seeds"] != expected_seed_map:
            raise ValueError("backend did not consume the frozen full-system seed streams")
        array_path = root / sidecar["array_path"]
        if sha256_file(array_path) != sidecar["array_sha256"]:
            raise ValueError("full-system NPZ SHA-256 mismatch during analysis")
        with np.load(array_path, allow_pickle=False) as arrays:
            tx = arrays["tx_samples"].astype(np.complex128)
            bits = arrays["information_bits"].astype(np.int8).reshape(-1)
            bit_recount = _recount_system_trial_arrays(arrays, record)
            energy = float(np.vdot(tx, tx).real)
            eb = energy / bits.size
            expected_eb = 4.0 * float(record["amplitude"]) ** 2
            expected_gamma = 10.0 * np.log10(eb / float(record["noise_variance"]))
            if not np.isclose(energy, record["tx_energy"], rtol=1e-11, atol=1e-11):
                raise ValueError("full-system transmit energy disagrees with samples")
            if not np.isclose(eb, record["eb_d"], rtol=1e-11, atol=1e-11) or not np.isclose(
                eb, expected_eb, rtol=1e-11, atol=1e-11
            ):
                raise ValueError("full-system discrete energy-per-bit check failed")
            if not np.isclose(expected_gamma, record["gamma_measured_db"], rtol=1e-11, atol=1e-11):
                raise ValueError("full-system measured gamma does not match samples/noise")
            empirical_noise = float(np.mean(np.abs(arrays["noise_samples"]) ** 2))
            if not np.isclose(
                empirical_noise, record["empirical_noise_power"], rtol=1e-11, atol=1e-11
            ):
                raise ValueError("full-system noise sample statistic differs from stored record")
        for arm, counts in bit_recount.items():
            recounted_counts[arm]["bit_errors"] += counts["bit_errors"]
            recounted_counts[arm]["pair_errors"] += counts["pair_errors"]
            recounted_counts[arm]["frame_errors"] += counts["frame_error"]
        rows.append(
            {
                "trial_id": sidecar["trial_id"],
                "scenario": scenario,
                "sweep": "amplitude",
                "phase": "confirmatory",
                "gamma_db": grid_gamma,
                "noise_variance": float(record["noise_variance"]),
                "bits": int(record["bits"]),
                "pairs": int(record["pairs"]),
                "bit_errors": {key: int(value) for key, value in record["bit_errors"].items()},
                "pair_errors": {key: int(value) for key, value in record["pair_errors"].items()},
                "frame_errors": {key: int(value) for key, value in record["frame_errors"].items()},
                "observation_sha256": record["observation_sha256"],
                "energy_per_bit": eb,
                "tx_energy_discrete": energy,
                "payload_signal_symbols": int(record["bits"] // 2),
                "total_signal_symbols": int(record["frame_symbols"]),
                "runtime_seconds": record["runtime_seconds"],
                "receiver_process_cpu_seconds": record["receiver_process_cpu_seconds"],
                "empirical_path_powers": record["empirical_path_powers"],
            }
        )
    return rows, {
        "study_id": f"confirmatory-{scenario}-full-receivers",
        "root": root,
        "manifest": manifest,
        "manifest_sha256": sha256_file(root / "manifest.json"),
        "verification": verification,
        "independent_count_replay": "PASS",
        "recounted_counts": recounted_counts,
    }


def _context_seed(root_seed: int, context: str, index: int) -> int:
    digest = __import__("hashlib").sha256(context.encode("utf-8")).digest()
    return int(
        np.random.SeedSequence(
            [root_seed, int.from_bytes(digest[:4], "little"), index]
        ).generate_state(1, dtype=np.uint32)[0]
    )


_LABELS = {
    "euclidean": "Вітербі — евклідова метрика",
    "hamming": "Вітербі — метрика Хемінга",
    "joint": "Спільна демодуляція й декодування — Евклід",
    "b0": "Роздільне приймання B0 — Хемінг",
    "b1": "Роздільне приймання B1 — Хемінг",
}
_SCENARIO_LABELS = {
    "awgn_direct": "AWGN без пілотів",
    "awgn_pilot": "AWGN зі спільним пілотним обробленням",
    "static_pilot": "Статичний двопроменевий канал, затримки 0 і 3 відліки",
    "rician_period32": "Райсівський AR(1), пілоти кожні 32 символи",
    "rician_period8": "Райсівський AR(1), пілоти кожні 8 символів",
    "awgn": "AWGN",
    "static": "Статичний двопроменевий канал, затримки 0 і 3 відліки",
    "rician": "Райсівський AR(1), багатопроменевий канал",
}
_TARGET_MARKERS = {0.05: "o", 0.01: "s", 0.001: "^"}


def _visible_rgb_values(pixels: np.ndarray) -> int:
    """Count colors in a bounded thumbnail, avoiding full-resolution sorting."""
    from PIL import Image

    height, width = pixels.shape[:2]
    scale = min(160.0 / width, 160.0 / height, 1.0)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    thumbnail = Image.fromarray(np.asarray(pixels, dtype=np.uint8)).resize(size)
    sampled = np.asarray(thumbnail).reshape(-1, 3)
    return int(np.unique(sampled, axis=0).shape[0])


def _save_figure(fig: Any, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    png = destination.with_suffix(".png")
    svg = destination.with_suffix(".svg")
    fig.savefig(png, dpi=300, facecolor="white", bbox_inches="tight")
    fig.savefig(svg, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    from PIL import Image

    with Image.open(png) as image:
        image.verify()
    with Image.open(png) as image:
        width, height = image.size
        alpha = np.asarray(image.convert("RGBA").getchannel("A"))
        visible_rgb_values = _visible_rgb_values(np.asarray(image.convert("RGB")))
        if width < 1000 or height < 600:
            raise ValueError(f"figure PNG is below publication dimensions: {png}")
        if not np.any(alpha > 0) or visible_rgb_values < 8:
            raise ValueError(f"figure PNG has no visible nontrivial content: {png}")
    svg_text = svg.read_text(encoding="utf-8")
    if "<svg" not in svg_text or "<path" not in svg_text:
        raise ValueError(f"SVG does not contain vector drawing/text elements: {svg}")
    return {
        "png": png.as_posix(),
        "svg": svg.as_posix(),
        "width": width,
        "height": height,
        "visible_rgb_values_in_thumbnail": visible_rgb_values,
        "opaque_pixels": int(np.count_nonzero(alpha == 255)),
        "svg_bytes": svg.stat().st_size,
    }


def _plot_metric(
    points: list[dict[str, Any]],
    scenario: str,
    sweep: str,
    metric: str,
    destination: Path,
    gain_estimates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fig, ax = plt.subplots(figsize=(9.4, 6.2), layout="constrained")
    colors = {"euclidean": "#087f8c", "hamming": "#d97706"}
    if metric == "delta_ber":
        arm = "euclidean_minus_hamming"
        y = np.asarray([point["paired_delta_ber"][arm] for point in points], dtype=float)
        intervals = np.asarray(
            [point["bootstrap_95ci"]["paired_delta_ber"][arm] for point in points], dtype=float
        ).T
        ax.errorbar(
            [point["gamma_db"] for point in points],
            y,
            yerr=np.vstack((np.maximum(0, y - intervals[0]), np.maximum(0, intervals[1] - y))),
            marker="o",
            color="#6b4c9a",
            label="ΔBER = BER_E − BER_H",
        )
        ax.axhline(0, color="#555555", linewidth=1, linestyle="--")
    else:
        metric_key = {"ber": "ber", "ser": "ser_information_pairs", "fer": "fer"}[metric]
        ci_key = metric_key
        for arm in ("euclidean", "hamming"):
            x = np.asarray([point["gamma_db"] for point in points], dtype=float)
            y = np.asarray([point[metric_key][arm] for point in points], dtype=float)
            intervals = np.asarray(
                [point["bootstrap_95ci"][ci_key][arm] for point in points], dtype=float
            ).T
            yerr = np.vstack((np.maximum(0, y - intervals[0]), np.maximum(0, intervals[1] - y)))
            ax.errorbar(
                x,
                y,
                yerr=yerr,
                marker="o",
                linewidth=1.8,
                markersize=5,
                capsize=3,
                color=colors[arm],
                label=_LABELS[arm],
            )
        ax.set_yscale("symlog", linthresh=1e-4)
        ax.set_ylim(0, 1)
        for target, marker in _TARGET_MARKERS.items():
            ax.axhline(
                target,
                color="#333333" if target == 0.05 else "#777777",
                linestyle="--" if target == 0.05 else ":",
                linewidth=1.2 if target == 0.05 else 1.0,
                label=f"Ціль BER={target:g}",
            )
            target_estimate = (gain_estimates or {}).get(f"{target:g}", {})
            observed = target_estimate.get("observed", {}).get("log_ber", {})
            for arm in ("euclidean", "hamming"):
                crossing = observed.get(arm, {})
                if crossing.get("gamma_db") is not None:
                    ax.scatter(
                        [crossing["gamma_db"]],
                        [target],
                        marker=marker,
                        s=64,
                        facecolors=colors[arm],
                        edgecolors="white",
                        linewidths=0.8,
                        zorder=6,
                        label="_nolegend_",
                    )
    xlabel = (
        "Дискретна шкала γ_b,d (дБ), змінювали амплітуду"
        if sweep == "amplitude_fixed_noise"
        else "Дискретна шкала γ_b,d (дБ), змінювали дисперсію шуму"
    )
    ylabel = {
        "ber": "BER інформаційних бітів (частка, 0–1; symlog із точним нулем)",
        "ser": "SER інформаційних пар (частка, 0–1; symlog із точним нулем)",
        "fer": "FER кадрів з помилками (частка, 0–1; symlog із точним нулем)",
        "delta_ber": "Парна різниця ΔBER = BER_E − BER_H (частка)",
    }[metric]
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    sweep_label = (
        "амплітуда за фіксованого шуму"
        if sweep == "amplitude_fixed_noise"
        else "шум за фіксованої амплітуди"
    )
    ax.set_title(
        f"{_SCENARIO_LABELS.get(scenario, scenario)} · {sweep_label} · {metric.upper()} · "
        "300 незалежних кадрів на точку"
    )
    ax.grid(True, which="both", alpha=0.24)
    ax.legend(fontsize=9, loc="best")
    return _save_figure(fig, destination)


def _plot_gain(gains: dict[str, Any], title: str, destination: Path) -> dict[str, Any]:
    fig, ax = plt.subplots(figsize=(8.8, 5.8), layout="constrained")
    targets_with_ci = []
    values_with_ci = []
    lower = []
    upper = []
    targets_without_ci = []
    values_without_ci = []
    for target, estimate in sorted(gains.items(), key=lambda pair: float(pair[0])):
        value = estimate.get("gain_db_log_ber")
        if value is None:
            continue
        ci = estimate["bootstrap"]["log_ber"].get("gain_db_ci95")
        if ci is None:
            targets_without_ci.append(float(target))
            values_without_ci.append(float(value))
        else:
            targets_with_ci.append(float(target))
            values_with_ci.append(float(value))
            lower.append(max(0.0, float(value - ci[0])))
            upper.append(max(0.0, float(ci[1] - value)))
    if values_with_ci:
        ax.errorbar(
            targets_with_ci,
            values_with_ci,
            yerr=np.asarray([lower, upper]),
            marker="o",
            linewidth=1.8,
            capsize=4,
            color="#087f8c",
            label="Модельний виграш із 95% ДІ",
        )
    if values_without_ci:
        ax.scatter(
            targets_without_ci,
            values_without_ci,
            marker="o",
            facecolors="none",
            edgecolors="#d97706",
            linewidths=1.8,
            label="Точкова оцінка; 95% ДІ недостатньо надійний",
        )
    if not values_with_ci and not values_without_ci:
        ax.text(
            0.5,
            0.5,
            "Недостатньо даних для оцінювання перетину цільового BER",
            transform=ax.transAxes,
            ha="center",
            va="center",
            wrap=True,
        )
    ax.axhline(0, color="#555555", linestyle="--", linewidth=1)
    ax.set_xlabel("Цільова BER інформаційних бітів (частка)")
    ax.set_ylabel("Модельний енергетичний виграш (дБ)")
    ax.set_title(title)
    ax.grid(True, alpha=0.25)
    if values_with_ci or values_without_ci:
        ax.legend(fontsize=9, loc="best")
    return _save_figure(fig, destination)


def render_figures(result: dict[str, Any], destination: Path) -> list[dict[str, Any]]:
    exports: list[dict[str, Any]] = []
    for scenario, sweeps in result["metric_isolation"].items():
        for sweep, section in sweeps.items():
            for metric in ("ber", "ser", "fer"):
                exports.append(
                    _plot_metric(
                        section["point_summaries"],
                        scenario,
                        sweep,
                        metric,
                        destination / "metric" / scenario / sweep / metric,
                        gain_estimates=section["metric_gain"]
                        if sweep == "amplitude_fixed_noise" and metric == "ber"
                        else None,
                    )
                )
            if sweep == "amplitude_fixed_noise":
                exports.append(
                    _plot_metric(
                        section["point_summaries"],
                        scenario,
                        sweep,
                        "delta_ber",
                        destination / "metric" / scenario / sweep / "paired_delta_ber",
                    )
                )
                exports.append(
                    _plot_gain(
                        section["metric_gain"],
                        f"{scenario} · A-E/A-H · модельний виграш",
                        destination / "metric" / scenario / sweep / "energy_gain",
                    )
                )
    for scenario, section in result["full_system_comparison"].items():
        points = section["point_summaries"]
        arms = section["arms"]
        for metric in ("ber", "ser", "fer"):
            metric_key = {"ber": "ber", "ser": "ser_information_pairs", "fer": "fer"}[metric]
            ci_key = metric_key
            fig, ax = plt.subplots(figsize=(9.4, 6.2), layout="constrained")
            colors = {"joint": "#087f8c", "b0": "#d97706", "b1": "#6b4c9a"}
            for arm in section["arms"]:
                x = np.asarray([point["gamma_db"] for point in points], dtype=float)
                y = np.asarray([point[metric_key][arm] for point in points], dtype=float)
                intervals = np.asarray(
                    [point["bootstrap_95ci"][ci_key][arm] for point in points], dtype=float
                ).T
                ax.errorbar(
                    x,
                    y,
                    yerr=np.vstack(
                        (np.maximum(0, y - intervals[0]), np.maximum(0, intervals[1] - y))
                    ),
                    marker="o",
                    linewidth=1.8,
                    capsize=3,
                    color=colors[arm],
                    label=_LABELS[arm],
                )
            if metric == "ber":
                ax.set_yscale("symlog", linthresh=1e-4)
                ax.set_ylim(0, 1)
                for target, marker in _TARGET_MARKERS.items():
                    ax.axhline(
                        target,
                        color="#333333" if target == 0.05 else "#777777",
                        linestyle="--" if target == 0.05 else ":",
                        linewidth=1.2 if target == 0.05 else 1.0,
                        label=f"Ціль BER={target:g}",
                    )
                    crossing_arms = section["energy_gain"].get(f"{target:g}", {})
                    for arm in arms:
                        estimate_arm = "euclidean" if arm == "joint" else "hamming"
                        crossing = (
                            crossing_arms.get(arm, {})
                            .get("observed", {})
                            .get("log_ber", {})
                            .get(estimate_arm, {})
                        )
                        if crossing.get("gamma_db") is not None:
                            ax.scatter(
                                [crossing["gamma_db"]],
                                [target],
                                marker=marker,
                                s=64,
                                facecolors=colors[arm],
                                edgecolors="white",
                                linewidths=0.8,
                                zorder=6,
                                label="_nolegend_",
                            )
            else:
                ax.set_yscale("symlog", linthresh=1e-4)
                ax.set_ylim(0, 1)
            ax.set_xlabel("Дискретна енергія γ_b,d (дБ)")
            ax.set_ylabel(
                {
                    "ber": "BER інформаційних бітів (частка, 0–1)",
                    "ser": "SER інформаційних пар (частка, 0–1)",
                    "fer": "FER кадрів (частка, 0–1)",
                }[metric]
            )
            ax.set_title(
                f"{_SCENARIO_LABELS.get(scenario, scenario)} · повні алгоритми · "
                "100 незалежних кадрів на точку"
            )
            ax.grid(True, which="both", alpha=0.24)
            ax.legend(fontsize=9, loc="best")
            exports.append(_save_figure(fig, destination / "system" / scenario / metric))
        for arm in (candidate for candidate in arms if candidate != "joint"):
            arm_gains = {target: per_arm[arm] for target, per_arm in section["energy_gain"].items()}
            exports.append(
                _plot_gain(
                    arm_gains,
                    f"{_SCENARIO_LABELS.get(scenario, scenario)} · спільне / {arm}",
                    destination / "system" / scenario / f"gain_joint_{arm}",
                )
            )
        fig, ax = plt.subplots(figsize=(8.6, 5.6), layout="constrained")
        positions = np.arange(len(arms))
        means = [section["runtime"][arm]["wall_seconds_mean"] for arm in arms]
        ax.bar(
            positions,
            means,
            color=[{"joint": "#087f8c", "b0": "#d97706", "b1": "#6b4c9a"}[arm] for arm in arms],
        )
        ax.set_xticks(positions, [_LABELS[arm] for arm in arms], rotation=12, ha="right")
        ax.set_ylabel("Час декодування на кадр (середнє, с)")
        ax.set_title(
            f"{_SCENARIO_LABELS.get(scenario, scenario)} · виміряний час приймачів · "
            f"{sum(point['trials'] for point in points)} кадрів"
        )
        ax.grid(axis="y", alpha=0.25)
        exports.append(_save_figure(fig, destination / "system" / scenario / "runtime"))
        fig, ax = plt.subplots(figsize=(8.6, 5.6), layout="constrained")
        for arm in arms:
            x = [point["gamma_db"] for point in points]
            y = [point["information_efficiency_bits_per_symbol"][arm] for point in points]
            ax.plot(x, y, marker="o", label=_LABELS[arm])
        ax.set_xlabel("Дискретна енергетична шкала γ_b,d (дБ)")
        ax.set_ylabel("Коректно декодовані інформаційні біти на переданий елемент (біт/елемент)")
        ax.set_title(
            f"{_SCENARIO_LABELS.get(scenario, scenario)} · дискретна інформаційна ефективність"
        )
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=9)
        exports.append(
            _save_figure(fig, destination / "system" / scenario / "information_efficiency")
        )
    return exports


def analyze(output_root: Path, destination: Path) -> dict[str, Any]:
    protocol, _, protocol_hash, _ = load_frozen_protocol(PROTOCOL_PATH)
    root_seed, replicates = _analysis_bootstrap_settings(protocol)
    metric_precision = _analysis_precision_criteria(protocol, "metric_isolation")
    system_precision = _analysis_precision_criteria(protocol, "system_comparison")
    targets = [float(value) for value in protocol["metric_isolation"]["targets_ber"].values()]
    result: dict[str, Any] = {
        "schema_version": "scientific-exp03b-independent-analysis-v1",
        "protocol_sha256": protocol_hash,
        "inference_uses_confirmatory_trials_only": True,
        "preflight_included": False,
        "bootstrap_replicates": replicates,
        "bootstrap_seed_root": root_seed,
        "metric_isolation": {},
        "full_system_comparison": {},
    }
    for scenario in protocol["metric_isolation"]["scenarios"]:
        scenario_id = scenario["id"]
        result["metric_isolation"][scenario_id] = {}
        for sweep_index, sweep in enumerate(protocol["metric_isolation"]["sweeps"]):
            rows, provenance = _load_metric_series(
                output_root, protocol, protocol_hash, scenario_id, sweep
            )
            context_seed = _context_seed(root_seed, f"metric:{scenario_id}:{sweep}", 0)
            points = aggregate_paired_trials(rows, replicates=replicates, seed=context_seed)
            section: dict[str, Any] = {
                "provenance": {
                    key: str(value) if isinstance(value, Path) else value
                    for key, value in provenance.items()
                },
                "point_summaries": points,
                "metric_gain": None,
            }
            if sweep == "amplitude_fixed_noise":
                gain_by_target = {}
                for target_index, target in enumerate(targets):
                    estimate = estimate_paired_gain(
                        rows,
                        target=target,
                        euclidean_arm="euclidean",
                        hamming_arm="hamming",
                        replicates=replicates,
                        seed=_context_seed(root_seed, f"metric-gain:{scenario_id}", target_index),
                    )
                    estimate["precision_assessment"] = assess_gain_precision(
                        estimate,
                        points,
                        target=target,
                        arms=("euclidean", "hamming"),
                        precision_criteria=metric_precision,
                    )
                    gain_by_target[f"{target:g}"] = estimate
                section["metric_gain"] = gain_by_target
            section["paired_observation_hashes_unique"] = len(
                {row["observation_sha256"] for row in rows}
            )
            section["frontend_hashes_unique"] = len({row["frontend_sha256"] for row in rows})
            result["metric_isolation"][scenario_id][sweep] = section
    for scenario in ("awgn", "static", "rician"):
        rows, provenance = _load_system_series(output_root, protocol, protocol_hash, scenario)
        context_seed = _context_seed(root_seed, f"system:{scenario}", 0)
        points = aggregate_paired_trials(rows, replicates=replicates, seed=context_seed)
        arms = tuple(sorted(rows[0]["bit_errors"]))
        separate_arms = [arm for arm in arms if arm != "joint"]
        gains: dict[str, Any] = {}
        for target_index, target in enumerate(targets):
            gains[f"{target:g}"] = {}
            for arm in separate_arms:
                estimate = estimate_paired_gain(
                    rows,
                    target=target,
                    euclidean_arm="joint",
                    hamming_arm=arm,
                    replicates=replicates,
                    seed=_context_seed(root_seed, f"system-gain:{scenario}:{arm}", target_index),
                )
                estimate["precision_assessment"] = assess_gain_precision(
                    estimate,
                    points,
                    target=target,
                    arms=("joint", arm),
                    estimate_arms=("euclidean", "hamming"),
                    precision_criteria=system_precision,
                )
                gains[f"{target:g}"][arm] = estimate
        runtime = {
            arm: {
                "wall_seconds_mean": float(np.mean([row["runtime_seconds"][arm] for row in rows])),
                "wall_seconds_median": float(
                    np.median([row["runtime_seconds"][arm] for row in rows])
                ),
                "cpu_seconds_mean": float(
                    np.mean([row["receiver_process_cpu_seconds"][arm] for row in rows])
                ),
            }
            for arm in arms
        }
        result["full_system_comparison"][scenario] = {
            "provenance": {
                key: str(value) if isinstance(value, Path) else value
                for key, value in provenance.items()
            },
            "point_summaries": points,
            "energy_gain": gains,
            "runtime": runtime,
            "arms": list(arms),
            "paired_observation_hashes_unique": len({row["observation_sha256"] for row in rows}),
        }
    _write_json(destination, result)
    result["figure_exports"] = render_figures(result, destination.parent / "figures")
    _write_json(destination, result)
    analysis_manifest = {
        "schema_version": "scientific-exp03b-analysis-manifest-v1",
        "analysis_sha256": sha256_file(destination),
        "protocol_sha256": protocol_hash,
        "confirmatory_only": True,
    }
    _write_json(destination.with_name("analysis_manifest.json"), analysis_manifest)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs/scientific_exp03b")
    parser.add_argument(
        "--destination",
        type=Path,
        default=ROOT / "outputs/scientific_exp03b/analysis/independent_analysis.json",
    )
    args = parser.parse_args()
    result = analyze(args.output_root, args.destination)
    print(
        json.dumps(
            {
                "destination": str(args.destination),
                "metric_scenarios": len(result["metric_isolation"]),
                "system_scenarios": len(result["full_system_comparison"]),
                "protocol_sha256": result["protocol_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
