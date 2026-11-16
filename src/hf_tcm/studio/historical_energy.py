"""Read-only, provenance-checked views of accepted energy experiments."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from hf_tcm.repro.energy_statistics import aggregate_energy_records, analyze_energy_records
from scripts.analyze_energy_exp01b import paired_bootstrap_gain

LOGGER = logging.getLogger(__name__)


def _read_exp01b_trial(trial_root: Path, source: dict[str, Any]) -> tuple[dict, dict]:
    """Read each trial payload once, while retaining all original hash gates."""
    label = source.get("path", trial_root.name)
    try:
        payloads = {
            name: (trial_root / name).read_bytes()
            for name in ("record.json", "manifest.json", "config.json")
        }
        record = json.loads(payloads["record.json"].decode("utf-8"))
        manifest = json.loads(payloads["manifest.json"].decode("utf-8"))
        config = json.loads(payloads["config.json"].decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("SCIENTIFIC-EXP-01B static trial is unreadable") from exc
    if hashlib.sha256(payloads["record.json"]).hexdigest() != source.get("record_sha256"):
        raise ValueError(f"SCIENTIFIC-EXP-01B record hash mismatch: {label}")
    if hashlib.sha256(payloads["manifest.json"]).hexdigest() != source.get("trial_manifest_sha256"):
        raise ValueError(f"SCIENTIFIC-EXP-01B trial manifest hash mismatch: {label}")
    if manifest.get("config_sha256") != hashlib.sha256(payloads["config.json"]).hexdigest():
        raise ValueError("SCIENTIFIC-EXP-01B trial configuration hash mismatch")
    for name, expected in manifest.get("files", {}).items():
        candidate = (trial_root / name).resolve()
        if trial_root not in candidate.parents:
            raise ValueError("SCIENTIFIC-EXP-01B trial manifest path escapes its frame")
        try:
            data = payloads[name] if name in payloads else candidate.read_bytes()
        except OSError as exc:
            raise ValueError(f"SCIENTIFIC-EXP-01B trial file is missing: {name}") from exc
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"SCIENTIFIC-EXP-01B trial file hash mismatch: {name}")
    return record, config


def _read_exp01b_trials(root: Path, sources: list[dict]) -> list[tuple[str, dict, dict]]:
    """Overlap independent file I/O in four workers; retain source ordering."""

    def read(source: dict) -> tuple[str, dict, dict]:
        relative = Path(str(source.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".json":
            raise ValueError("SCIENTIFIC-EXP-01B contains an unsafe trial path")
        folder = (root / relative).resolve().parent
        if root not in folder.parents:
            raise ValueError("SCIENTIFIC-EXP-01B trial path escapes the result directory")
        record, config = _read_exp01b_trial(folder, source)
        return relative.as_posix(), record, config

    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="exp01b-verify") as pool:
        return list(pool.map(read, sources))


def load_historical_energy_study(
    output_root: str | Path = "outputs/scientific_exp_01",
) -> dict[str, Any]:
    """Recompute the accepted static-amplitude gain from verified trial records.

    Historical source files are never modified. Their manifests, archive,
    source hashes, trial hashes, and stored bootstrap results are checked before
    a GUI-compatible summary is returned.
    """
    root = Path(output_root).resolve()
    verification_path = root / "archive_verification.json"
    analysis_root = root / "analysis"
    manifest_path = analysis_root / "analysis_manifest.json"
    gains_path = analysis_root / "gains.json"
    try:
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        gains_bytes = gains_path.read_bytes()
        gains = json.loads(gains_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("historical energy provenance is incomplete") from exc

    if manifest.get("schema") != "scientific-exp01-analysis-v1":
        raise ValueError("historical energy provenance has an unsupported analysis manifest")
    if hashlib.sha256(gains_bytes).hexdigest() != manifest.get("derived_files_sha256", {}).get(
        "gains.json"
    ):
        raise ValueError("historical energy provenance hash mismatch: gains.json")

    archive_name = str(verification.get("archive_path", ""))
    if not archive_name or Path(archive_name).name != archive_name:
        raise ValueError("historical energy provenance has an invalid archive reference")
    archive_path = root.parent.parent / archive_name
    try:
        archive_bytes = archive_path.read_bytes()
    except OSError as exc:
        raise ValueError("historical energy provenance archive is missing") from exc
    archive_hash = hashlib.sha256(archive_bytes).hexdigest()
    if len(archive_bytes) != verification.get("archive_size") or archive_hash != verification.get(
        "sha256"
    ):
        raise ValueError("historical energy provenance archive hash mismatch")

    selected_analyses = [
        row
        for row in gains.get("analyses", [])
        if row.get("phase") == "confirmatory"
        and row.get("scenario") == "static"
        and row.get("sweep") == "amplitude"
        and row.get("target_ber") == 0.05
        and row.get("separate_arm") in {"b0", "b1"}
    ]
    if {row.get("separate_arm") for row in selected_analyses} != {"b0", "b1"}:
        raise ValueError("historical energy provenance lacks the approved target analysis")

    sources = [
        row
        for row in manifest.get("source_records", [])
        if str(row.get("path", "")).startswith("confirmatory/static/amplitude/")
    ]
    if len(sources) != 140:
        raise ValueError(
            "historical energy provenance does not contain the complete 140-trial series"
        )

    records: list[dict[str, Any]] = []
    observed_trials: set[tuple[int, int]] = set()
    for source in sources:
        relative = Path(str(source.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".json":
            raise ValueError("historical energy provenance contains an unsafe trial path")
        record_path = (root / relative).resolve()
        if root not in record_path.parents:
            raise ValueError("historical energy provenance trial path escapes its archive")
        trial_root = record_path.parent
        try:
            record_bytes = record_path.read_bytes()
            record = json.loads(record_bytes.decode("utf-8"))
            trial_manifest_bytes = (trial_root / "manifest.json").read_bytes()
            trial_manifest = json.loads(trial_manifest_bytes.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("historical energy provenance trial is unreadable") from exc
        if hashlib.sha256(record_bytes).hexdigest() != source.get("sha256"):
            raise ValueError("historical energy provenance record hash mismatch")
        if hashlib.sha256(trial_manifest_bytes).hexdigest() != source.get("manifest_sha256"):
            raise ValueError("historical energy provenance trial manifest hash mismatch")
        expected_files = source.get("manifest_files", {})
        if trial_manifest.get("files") != expected_files:
            raise ValueError("historical energy provenance trial file list mismatch")
        for name, expected_hash in expected_files.items():
            candidate = (trial_root / name).resolve()
            if trial_root not in candidate.parents:
                raise ValueError("historical energy provenance trial file escapes its directory")
            try:
                actual_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
            except OSError as exc:
                raise ValueError(
                    f"historical energy provenance trial file is missing: {name}"
                ) from exc
            if actual_hash != expected_hash:
                raise ValueError(f"historical energy provenance trial file hash mismatch: {name}")
        try:
            config = json.loads((trial_root / "config.json").read_text(encoding="utf-8"))
            point_trial = (int(record["point_index"]), int(record["trial_index"]))
            receiver_hashes = record["receiver_observation_hashes"]
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError("historical energy provenance trial is incomplete") from exc
        if any(
            item.get(key) != expected
            for item in (config, record)
            for key, expected in (
                ("phase", "confirmatory"),
                ("scenario", "static"),
                ("sweep", "amplitude"),
            )
        ):
            raise ValueError("historical energy provenance contains a mixed trial context")
        if point_trial in observed_trials:
            raise ValueError("historical energy provenance contains duplicate trials")
        observed_trials.add(point_trial)
        if set(receiver_hashes) != {"joint", "b0", "b1"} or len(set(receiver_hashes.values())) != 1:
            raise ValueError("historical energy provenance contains unpaired observations")
        records.append(record)

    point_counts: dict[float, int] = {}
    for record in records:
        gamma = float(record["gamma_db"])
        point_counts[gamma] = point_counts.get(gamma, 0) + 1
    if len(point_counts) != 7 or set(point_counts.values()) != {20}:
        raise ValueError("historical energy provenance does not match the frozen 7 x 20 design")

    analyses: dict[str, Any] = {}
    for saved in selected_analyses:
        arm = str(saved["separate_arm"])
        bootstrap = saved.get("bootstrap", {})
        result = analyze_energy_records(
            records,
            target=0.05,
            arm=arm,
            replicates=int(bootstrap.get("total_replicates", 0)),
            seed=int(bootstrap.get("seed", -1)),
        )
        saved_ci = bootstrap.get("confidence_interval_db")
        computed_ci = result.get("bootstrap", {}).get("confidence_interval_db")
        if (
            saved.get("status") != result.get("status")
            or not math.isclose(
                float(saved.get("gain_db")), float(result.get("gain_db")), abs_tol=1e-10
            )
            or saved_ci is None
            or computed_ci is None
            or len(saved_ci) != len(computed_ci)
            or any(
                not math.isclose(float(a), float(b), abs_tol=1e-10)
                for a, b in zip(saved_ci, computed_ci)
            )
        ):
            raise ValueError(f"historical energy provenance does not reproduce the {arm} analysis")
        analyses[arm] = result

    configuration = {
        "sweep": "amplitude",
        "noise_variance": float(records[0]["noise_variance"]),
        "amplitude": float(records[0]["amplitude"]),
        "frame_symbols": int(records[0]["frame_symbols"]),
        "target_ber": 0.05,
    }
    return {
        "schema_version": "gui-energy-study-result-v1",
        "experiment_id": "scientific-exp01-confirmatory-static-amplitude-ber005",
        "configuration_sha256": hashlib.sha256(gains_bytes).hexdigest(),
        "configuration": configuration,
        "physical_energy_gain": None,
        "status": "completed",
        "stop_reason": None,
        "planned_trials": len(records),
        "completed_trials": len(records),
        "elapsed_seconds": sum(float(row.get("elapsed_seconds", 0.0)) for row in records),
        "exploratory": False,
        "target_ber": 0.05,
        "sweep": "amplitude",
        "channel_profile": "static_multipath",
        "receiver_arms": ["joint", "b0", "b1"],
        "records": records,
        "analyses": analyses,
        "energy_gain_status_uk": "Історичні оцінки повторно обчислено з перевірених парних кадрів; енергетична шкала дискретна.",
        "historical": True,
        "provenance": {
            "source": "SCIENTIFIC-EXP-01 confirmatory static amplitude sweep",
            "analysis_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "gains_sha256": hashlib.sha256(gains_bytes).hexdigest(),
            "verified_archive_sha256": archive_hash,
            "verified_trial_records": len(records),
            "target_ber": 0.05,
            "paper_exact": False,
        },
    }


def load_historical_exp01b_energy_study(
    output_root: str | Path = "outputs/scientific_exp_01b",
) -> dict[str, Any]:
    """Verify and recompute the static amplitude results from EXP-01B.

    The loader deliberately selects only static confirmatory amplitude trials.
    Rician records remain a separate scenario and cannot enter these curves.
    Every selected record, trial manifest, configuration, and NPZ is checked
    against the completed study manifest before aggregation.
    """
    began = time.perf_counter()
    LOGGER.info("exp01b_loader phase=start")
    root = Path(output_root).resolve()
    try:
        protocol_snapshot = json.loads(
            (root / "protocol_snapshot.json").read_text(encoding="utf-8")
        )
        manifest_bytes = (root / "study_manifest.json").read_bytes()
        study_manifest = json.loads(manifest_bytes.decode("utf-8"))
        analysis_bytes = (root / "analysis" / "analysis_results.json").read_bytes()
        stored_analysis = json.loads(analysis_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("SCIENTIFIC-EXP-01B historical provenance is incomplete") from exc

    protocol_sha = "75b065c1d0a7f5c1f06af3bc290678a532e35d7c0062fb42f68f3914aaa6a5ab"
    if (
        protocol_snapshot.get("sha256") != protocol_sha
        or study_manifest.get("schema") != "scientific-exp01b-study-manifest-v1"
        or study_manifest.get("experiment_id") != "scientific-exp01b-independent-energy-gain-v1"
        or study_manifest.get("protocol_sha256") != protocol_sha
        or study_manifest.get("status") != "completed"
        or study_manifest.get("planned_pairs") != 2160
        or study_manifest.get("completed_pairs") != 2160
        or len(study_manifest.get("records", [])) != 2160
        or stored_analysis.get("experiment_id") != study_manifest.get("experiment_id")
        or stored_analysis.get("protocol_sha256") != protocol_sha
    ):
        raise ValueError("SCIENTIFIC-EXP-01B manifest does not match the frozen completed design")

    records: list[dict[str, Any]] = []
    seen: set[tuple[float, int]] = set()
    source_rows = [row for row in study_manifest["records"] if row.get("scenario") == "static"]
    if len(source_rows) != 1160:
        raise ValueError("SCIENTIFIC-EXP-01B static source must contain exactly 1160 frames")
    for _, record, config in _read_exp01b_trials(root, source_rows):
        if (
            config.get("phase") != "confirmatory"
            or config.get("scenario") != "static"
            or config.get("sweep") != "amplitude"
            or record.get("phase") != "confirmatory"
            or record.get("scenario") != "static"
            or record.get("sweep") != "amplitude"
        ):
            raise ValueError("SCIENTIFIC-EXP-01B contains a mixed scenario in static records")
        receiver_hashes = record.get("receiver_observation_hashes", {})
        if set(receiver_hashes) != {"joint", "b0", "b1"} or len(set(receiver_hashes.values())) != 1:
            raise ValueError("SCIENTIFIC-EXP-01B static record is not a paired observation")
        pair = (float(record["gamma_db"]), int(record["trial_index"]))
        if pair in seen:
            raise ValueError("SCIENTIFIC-EXP-01B contains duplicate static trials")
        seen.add(pair)
        records.append(record)
    point_counts: dict[float, int] = {}
    for record in records:
        gamma = float(record["gamma_db"])
        point_counts[gamma] = point_counts.get(gamma, 0) + 1
    if len(point_counts) != 29 or set(point_counts.values()) != {40}:
        raise ValueError("SCIENTIFIC-EXP-01B static data do not match the frozen 29 x 40 design")

    target_source = stored_analysis["scenarios"]["static"]["target_gain_analysis"]["0.05"]
    LOGGER.info(
        "exp01b_loader phase=verified trials=%d seconds=%.6f",
        len(records),
        time.perf_counter() - began,
    )
    analyses: dict[str, Any] = {}
    for arm in ("b0", "b1"):
        bootstrap_began = time.perf_counter()
        stored = target_source[arm]
        bootstrap = stored["bootstrap"]
        computed = paired_bootstrap_gain(
            records,
            target_ber=0.05,
            separate_arm=arm,
            replicates=int(bootstrap["total_replicates"]),
            seed=int(bootstrap["seed"]),
            interpolation="log10_ber",
        )
        stored_points = stored_analysis["scenarios"]["static"]["aggregate_points"]
        aggregate = aggregate_energy_records(records)
        if len(aggregate) != len(stored_points):
            raise ValueError("SCIENTIFIC-EXP-01B aggregate point count does not reproduce")
        for actual, expected in zip(aggregate, stored_points, strict=True):
            if (
                actual["gamma_db"] != expected.get("gamma_db")
                or actual["trials"] != expected.get("trials")
                or actual["bit_errors"] != expected.get("bit_errors")
                or actual["pair_errors"] != expected.get("pair_errors")
            ):
                raise ValueError(
                    "SCIENTIFIC-EXP-01B aggregate counts do not reproduce from trial files"
                )
        if (
            computed["status"] != stored.get("status")
            or computed["bootstrap"]["valid_replicates"] != bootstrap.get("valid_replicates")
            or not math.isclose(float(computed["gain_db"]), float(stored["gain_db"]), abs_tol=1e-10)
        ):
            raise ValueError(
                f"SCIENTIFIC-EXP-01B {arm} target result does not reproduce from trial records"
            )
        expected_ci = bootstrap.get("confidence_interval_db")
        actual_ci = computed["bootstrap"].get("confidence_interval_db")
        if (
            expected_ci is None
            or actual_ci is None
            or any(
                not math.isclose(float(a), float(b), abs_tol=1e-10)
                for a, b in zip(expected_ci, actual_ci, strict=True)
            )
        ):
            raise ValueError(f"SCIENTIFIC-EXP-01B {arm} bootstrap interval mismatch")
        computed["aggregate"] = aggregate
        computed["crossings"] = {
            name: {
                "status": crossing["status"],
                "required_gamma_db": crossing["gamma_db"],
                "bracket_gamma_db": crossing.get("bracket_gamma_db"),
            }
            for name, crossing in computed["crossings"].items()
        }
        analyses[arm] = computed
        LOGGER.info(
            "exp01b_loader phase=bootstrap_replay arm=%s seconds=%.6f",
            arm,
            time.perf_counter() - bootstrap_began,
        )

    LOGGER.info("exp01b_loader phase=complete seconds=%.6f", time.perf_counter() - began)

    return {
        "schema_version": "gui-energy-study-result-v1",
        "experiment_id": "scientific-exp01b-confirmatory-static-amplitude",
        "configuration_sha256": protocol_sha,
        "configuration": {
            "sweep": "amplitude",
            "noise_variance": 1.0,
            "amplitude": None,
            "frame_symbols": 256,
            "target_ber": 0.05,
            "delays_samples": [0, 3],
            "path_powers": [0.8, 0.2],
        },
        "physical_energy_gain": None,
        "status": "completed",
        "stop_reason": None,
        "planned_trials": 1160,
        "completed_trials": 1160,
        "elapsed_seconds": sum(float(row.get("elapsed_seconds", 0.0)) for row in records),
        "exploratory": False,
        "target_ber": 0.05,
        "sweep": "amplitude",
        "channel_profile": "static_multipath",
        "receiver_arms": ["joint", "b0", "b1"],
        "records": records,
        "analyses": analyses,
        "energy_gain_status_uk": "Історичні результати повторно обчислено з перевірених парних кадрів; шкала енергії дискретна й модельна.",
        "historical": True,
        "provenance": {
            "source": "SCIENTIFIC-EXP-01B confirmatory static amplitude sweep",
            "verified_total_source_trials": 2160,
            "verified_static_trials": len(records),
            "verified_rician_trials_kept_separate": 1000,
            "study_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "analysis_sha256": hashlib.sha256(analysis_bytes).hexdigest(),
            "protocol_sha256": protocol_sha,
            "target_ber": 0.05,
            "paper_exact": False,
        },
    }
