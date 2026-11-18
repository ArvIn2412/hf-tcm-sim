"""Read-only, bounded-page catalog over saved GUI study metadata.

Catalog metadata is not a full historical audit. Opening a result continues to
use its established manifest verifier before any numerical trace is displayed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
_MAX_JSON_BYTES = 4 * 1024 * 1024


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or path.stat().st_size > _MAX_JSON_BYTES:
        raise ValueError("catalog metadata is a link or exceeds size limit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("catalog metadata must be an object")
    return value


def _metadata_verified(folder: Path, summary: Path, config: Path) -> bool:
    manifest = _read_json(folder / "manifest.json")
    files = manifest.get("files", {})
    for path in (summary, config):
        if not path.is_file():
            continue
        expected = files.get(path.name)
        if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("catalog metadata SHA-256 mismatch")
    return bool(files.get(summary.name))


def _metric_counts(summary: dict[str, Any]) -> dict[str, Any]:
    rows = summary.get("aggregates", [])
    bits = sum(int(row.get("bits", 0)) for row in rows)
    values: dict[str, Any] = {}
    for arm, key in (("hamming", "hamming"), ("euclidean", "joint")):
        errors = sum(int(row.get("bit_errors", {}).get(key, 0)) for row in rows)
        values[arm] = {"errors": errors, "bits": bits, "ber": errors / bits if bits else None}
    return values


def _row(folder: Path, kind: str) -> dict[str, Any]:
    summary_path = folder / "summary.json"
    config_path = folder / ("configuration.json" if kind == "energy" else "config.json")
    summary = _read_json(summary_path)
    config = _read_json(config_path) if config_path.is_file() else summary.get("configuration", {})
    if not isinstance(config, dict):
        config = {}
    ident = str(summary.get("experiment_id", summary.get("run_id", folder.name)))
    if not _SAFE_ID.fullmatch(ident):
        raise ValueError("unsafe catalog ID")
    date = datetime.fromtimestamp(summary_path.stat().st_mtime, timezone.utc).isoformat()
    metrics = _metric_counts(summary) if kind == "metric" else {}
    system_comparison = False
    if kind == "run" and summary.get("paired_observation_verified") is True:
        system_comparison = all(isinstance(summary.get(key), dict) for key in ("joint", "separate"))
        if system_comparison:
            metrics = {
                arm: {
                    "ber": summary[key].get("ber"),
                    "errors": summary[key].get("bit_errors"),
                    "bits": summary[key].get("compared_bits"),
                }
                for arm, key in (("hamming", "separate"), ("euclidean", "joint"))
            }
    if kind == "energy" and summary.get("contrast_mode") != "metric":
        arms = summary.get("receiver_arms", config.get("receiver_arms", []))
        system_comparison = "joint" in arms and "b0" in arms
        if system_comparison:
            rows = summary.get("analyses", {}).get("b0", {}).get("aggregate", [])
            metrics = {
                arm: {"ber_range": [min(values), max(values)] if values else None}
                for arm, key in (("hamming", "b0"), ("euclidean", "joint"))
                for values in [
                    [
                        row["ber"][key]
                        for row in rows
                        if isinstance(row.get("ber", {}).get(key), (int, float))
                    ]
                ]
            }
    actual_channel = config.get(
        "scenario", config.get("channel_profile", summary.get("channel_profile", "unknown"))
    )
    if kind == "energy" and system_comparison:
        scenarios = {row.get("scenario") for row in rows if row.get("scenario")}
        if len(scenarios) == 1:
            actual_channel = {"static": "static_multipath", "rician": "rician_ar1_multipath"}.get(
                next(iter(scenarios)), next(iter(scenarios))
            )
    times = []
    if system_comparison and kind == "run":
        times = [summary[key].get("runtime_seconds") for key in ("joint", "separate")]
    elif system_comparison and kind == "energy":
        times = [
            record.get("runtime_seconds", {}).get(arm)
            for record in summary.get("records", [])
            for arm in ("joint", "b0")
        ]
    processing = (
        math.fsum(times)
        if times
        and all(
            isinstance(t, (int, float)) and not isinstance(t, bool) and math.isfinite(t) and t >= 0
            for t in times
        )
        else None
    )
    return {
        "id": ident,
        "kind": kind,
        "date": summary.get("created_at", date),
        "channel": actual_channel,
        "profile": config.get("profile", config.get("frontend_mode", kind)),
        "N": config.get("frame_symbols", summary.get("frame_symbols")),
        "seed": config.get("root_seed", config.get("source_seed", summary.get("source_seed"))),
        "trials": summary.get("completed_trials", 1 if kind == "run" else 0),
        "status": summary.get("status", "completed"),
        "gain_status": summary.get("gain_analysis", {}).get("status", "NOT_RUN"),
        "metrics": metrics,
        "system_comparison": system_comparison,
        "processing_seconds": processing,
        "metadata_verified": _metadata_verified(folder, summary_path, config_path),
        "capabilities": {
            "numerical_results": True,
            "iq": any((folder / "trials").glob("*.npz")) or (folder / "traces.npz").is_file(),
        },
        "parameters": config,
    }


def list_study_catalog(
    outputs_root: Path,
    *,
    page: int = 1,
    size: int = 25,
    q: str = "",
    channel: str = "",
    status: str = "",
    profile: str = "",
    metric: str = "",
    kind: str = "",
    sort: str = "date_desc",
) -> dict[str, Any]:
    """Return only the requested page; no NPZ or per-trial records are loaded."""
    if type(page) is not int or page < 1 or type(size) is not int or not 1 <= size <= 50:
        raise ValueError("page must be >=1 and page size must be 1..50")
    if any(len(value) > 200 for value in (q, channel, status, profile, metric, kind, sort)):
        raise ValueError("catalog query is too long")
    if metric not in {"", "hamming", "euclidean"}:
        raise ValueError("unsupported catalog metric")
    if sort not in {"date_desc", "date_asc", "trials_desc", "trials_asc", "id_asc", "id_desc"}:
        raise ValueError("unsupported catalog sort")
    roots = (
        ("metric", outputs_root / "scientific-exp03a/metric-studies"),
        ("run", outputs_root / "repro09"),
        ("experiment", outputs_root / "repro09/monte-carlo"),
        ("energy", outputs_root / "repro09/energy-studies"),
    )
    rows = []
    rejected = 0
    for category, root in roots:
        if not root.is_dir() or root.is_symlink():
            continue
        for folder in root.iterdir():
            if (
                not folder.is_dir()
                or folder.is_symlink()
                or not (folder / "summary.json").is_file()
            ):
                continue
            try:
                rows.append(_row(folder, category))
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                rejected += 1
    facets = {
        field: sorted({str(row[field]) for row in rows})
        for field in ("channel", "status", "profile", "kind")
    }
    query = q.casefold().strip()
    filtered = [
        row
        for row in rows
        if (
            not query
            or query
            in " ".join(str(row[field]) for field in ("id", "date", "seed", "channel")).casefold()
        )
        and (not channel or str(row["channel"]) == channel)
        and (not status or str(row["status"]) == status)
        and (not profile or str(row["profile"]) == profile)
        and (
            not kind
            or (
                row["system_comparison"] and (kind == "system" or row["kind"] == kind[7:])
                if kind.startswith("system")
                else str(row["kind"]) == kind
            )
        )
        and (not metric or metric in row["metrics"])
    ]
    field = sort.split("_")[0]
    filtered.sort(
        key=lambda row: (row[field] or "") if field != "trials" else int(row[field] or 0),
        reverse=sort.endswith("desc"),
    )
    total = len(filtered)
    offset = (page - 1) * size
    return {
        "items": filtered[offset : offset + size],
        "page": page,
        "page_size": size,
        "total": total,
        "pages": max(1, math.ceil(total / size)),
        "facets": facets,
        "rejected_metadata": rejected,
        "audit_status": "METADATA_ONLY_NOT_FULL_HISTORICAL_AUDIT",
    }
