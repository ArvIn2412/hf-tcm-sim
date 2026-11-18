"""Read-only, provenance-checked loader for confirmatory SCIENTIFIC-EXP-03B results."""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Any

from hf_tcm.repro.exp03b_runner import load_frozen_protocol, sha256_file

# Process-local evidence only: never trust a persisted cache as provenance.
# A replacement, edit (including restored mtime), or disappearance invalidates it.
_HASHES: dict[Path, tuple[tuple[int, ...], str]] = {}
_HASH_LOCK = Lock()
_LOAD_LOCK = Lock()

if os.name == "nt":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _FileBasicInfo(ctypes.Structure):
        _fields_ = [
            ("creation", ctypes.c_longlong),
            ("access", ctypes.c_longlong),
            ("write", ctypes.c_longlong),
            ("change", ctypes.c_longlong),
            ("attributes", wintypes.DWORD),
        ]

    _get_info = ctypes.WinDLL("kernel32", use_last_error=True).GetFileInformationByHandleEx
    _get_info.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    _get_info.restype = wintypes.BOOL


def _signature(path: Path) -> tuple[int, ...]:
    stat = path.stat()
    change = stat.st_ctime_ns
    if os.name == "nt":
        # Windows st_ctime is creation time, not metadata-change time.
        with path.open("rb") as stream:
            info = _FileBasicInfo()
            if not _get_info(
                msvcrt.get_osfhandle(stream.fileno()), 0, ctypes.byref(info), ctypes.sizeof(info)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            change = info.change
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, change)


def _checked_sha(path: Path) -> str:
    before = _signature(path)
    with _HASH_LOCK:
        cached = _HASHES.get(path)
    if cached is not None and cached[0] == before:
        return cached[1]
    digest = sha256_file(path)
    if _signature(path) != before:
        raise ValueError(f"archive file changed during integrity verification: {path}")
    with _HASH_LOCK:
        _HASHES[path] = (before, digest)
    return digest


def _verify_study(
    root: Path, protocol_hash: str, expected_trials: int, expected_manifest_hash: str
) -> None:
    started = time.perf_counter()
    logging.getLogger(__name__).info("Verifying archive %s (%d trials)", root.name, expected_trials)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file() or _checked_sha(manifest_path) != expected_manifest_hash:
        raise ValueError(f"confirmatory study manifest SHA-256 mismatch: {root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("status") != "completed"
        or manifest.get("protocol_sha256") != protocol_hash
        or int(manifest.get("completed_trials", -1)) != expected_trials
        or int(manifest.get("planned_trials", -1)) != expected_trials
    ):
        raise ValueError(f"confirmatory study manifest is incomplete or inconsistent: {root}")
    checkpoint = root / "checkpoint.jsonl"
    checkpoint_hash = _checked_sha(checkpoint)
    if checkpoint_hash != manifest.get("checkpoint_sha256"):
        raise ValueError(f"confirmatory study checkpoint SHA-256 mismatch: {root}")
    lines = [line for line in checkpoint.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != expected_trials:
        raise ValueError(f"confirmatory study checkpoint has the wrong trial count: {root}")
    ids = []
    root_resolved = root.resolve()

    def verify_line(line: str) -> str:
        entry = json.loads(line)
        if not all(
            isinstance(entry.get(key), str)
            for key in ("trial_id", "record_path", "record_sha256", "array_path", "array_sha256")
        ):
            raise ValueError(f"confirmatory study checkpoint entry is malformed: {root}")
        for path_key, hash_key, description in (
            ("record_path", "record_sha256", "record"),
            ("array_path", "array_sha256", "array"),
        ):
            payload_path = (root_resolved / entry[path_key]).resolve()
            if not payload_path.is_relative_to(root_resolved):
                raise ValueError(f"confirmatory study {description} path escapes its root: {root}")
            if not payload_path.is_file() or _checked_sha(payload_path) != entry[hash_key]:
                raise ValueError(
                    f"confirmatory study {description} SHA-256 mismatch: {payload_path}"
                )
        return entry["trial_id"]

    # Bound disk pressure; preserve every original digest and path/count gate.
    with ThreadPoolExecutor(max_workers=4) as workers:
        ids = list(workers.map(verify_line, lines))
    if len(ids) != len(set(ids)):
        raise ValueError(f"confirmatory study checkpoint has duplicate trial IDs: {root}")
    logging.getLogger(__name__).info(
        "Verified %s in %.3fs", root.name, time.perf_counter() - started
    )


def load_exp03b_analysis(
    analysis_path: str | Path,
    protocol_path: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    # Serialize concurrent cold requests; followers reuse verified file digests
    # while still checking current metadata and all provenance relationships.
    with _LOAD_LOCK:
        return _load_exp03b_analysis(analysis_path, protocol_path, output_root)


def _load_exp03b_analysis(
    analysis_path: str | Path,
    protocol_path: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    """Load the frozen analysis only if its digest and every source manifest still match."""
    path = Path(analysis_path).resolve()
    outputs = Path(output_root).resolve()
    protocol, _, protocol_hash, _ = load_frozen_protocol(protocol_path)
    if not path.is_file():
        raise FileNotFoundError("confirmatory SCIENTIFIC-EXP-03B analysis is not available")
    manifest_path = path.with_name("analysis_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    analysis_hash = _checked_sha(path)
    if manifest.get("analysis_sha256") != analysis_hash:
        raise ValueError("analysis SHA-256 does not match its manifest")
    if manifest.get("protocol_sha256") != protocol_hash:
        raise ValueError("analysis manifest refers to a different frozen protocol")
    if manifest.get("confirmatory_only") is not True:
        raise ValueError("analysis manifest is not marked confirmatory-only")
    result = json.loads(path.read_text(encoding="utf-8"))
    if (
        result.get("protocol_sha256") != protocol_hash
        or result.get("preflight_included") is not False
    ):
        raise ValueError("analysis provenance is not confirmatory-only under the frozen protocol")
    expected_metric = {row["id"]: row for row in protocol["metric_isolation"]["scenarios"]}
    if set(result.get("metric_isolation", {})) != set(expected_metric):
        raise ValueError("confirmatory analysis is missing a metric scenario")
    for scenario_key, sweeps in result["metric_isolation"].items():
        if set(sweeps) != set(protocol["metric_isolation"]["sweeps"]):
            raise ValueError("confirmatory analysis is missing an energy sweep")
        for sweep, section in sweeps.items():
            expected = len(expected_metric[scenario_key]["energy_offsets_db"]) * int(
                protocol["metric_isolation"]["confirmatory_trials_per_point"]
            )
            study_id = f"confirmatory-{scenario_key}-{sweep}"
            expected_hash = section["provenance"].get("manifest_sha256")
            if not isinstance(expected_hash, str) or len(expected_hash) != 64:
                raise ValueError("confirmatory study manifest provenance is missing")
            _verify_study(
                outputs / "metric" / "confirmatory" / study_id,
                protocol_hash,
                expected,
                expected_hash,
            )
    grids = protocol["system_comparison"]["energy_grid_gamma_db"]
    if set(result.get("full_system_comparison", {})) != set(grids):
        raise ValueError("confirmatory analysis is missing a full-system scenario")
    for scenario, section in result["full_system_comparison"].items():
        expected = len(grids[scenario]) * int(
            protocol["system_comparison"]["confirmatory_trials_per_point"]
        )
        expected_hash = section["provenance"].get("manifest_sha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise ValueError("full-system manifest provenance is missing")
        _verify_study(
            outputs / "system" / "confirmatory" / scenario, protocol_hash, expected, expected_hash
        )
    result["analysis_sha256"] = analysis_hash
    result["provenance_verified"] = True
    return result
