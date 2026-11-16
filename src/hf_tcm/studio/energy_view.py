"""Read-only FER view over manifest-verified saved metric trial records."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from hf_tcm.repro.metric_experiment import load_metric_study


def load_energy_view(studies_root: Path, study_id: str) -> dict[str, Any]:
    """Enrich saved aggregates without rewriting any trial or analysis result."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", study_id):
        raise ValueError("invalid study ID")
    root = studies_root.resolve()
    folder = (root / study_id).resolve()
    if folder.parent != root:
        raise ValueError("study path escapes its root")
    summary = load_metric_study(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if not {"config.json", "summary.json"}.issubset(manifest["files"]):
        raise ValueError("energy view requires manifest-pinned config and summary")
    groups: dict[int, list[dict[str, Any]]] = {}
    for relative in manifest["files"]:
        if not re.fullmatch(r"trials/p\d+-t\d+\.json", relative):
            continue
        record = json.loads((folder / relative).read_text(encoding="utf-8"))
        gamma = record.get("gamma_b_discrete_db")
        if gamma is None:
            continue
        if not isinstance(gamma, (int, float)) or not math.isfinite(gamma):
            raise ValueError("trial gamma is not finite")
        groups.setdefault(record["point_index"], []).append(record)
    for aggregate in summary.get("aggregates", []):
        candidates = [
            trials
            for trials in groups.values()
            if all(
                abs(row["gamma_b_discrete_db"] - aggregate["gamma_db"]) <= 1e-9 for row in trials
            )
        ]
        if len(candidates) != 1:
            raise ValueError("energy aggregate has no unique measured trial group")
        trials = candidates[0]
        if len(trials) != aggregate["trials"]:
            raise ValueError("energy aggregate trial count differs from its source records")
        counts = {}
        for stored_arm, visible_arm in (("hamming", "hamming"), ("euclidean", "joint")):
            failed_frames = 0
            for trial in trials:
                value = trial[stored_arm]
                frame_error = value["fer"]
                if frame_error not in (0, 1) or frame_error != int(value["bit_errors"] > 0):
                    raise ValueError("stored FER differs from its integer bit-error event")
                failed_frames += frame_error
            counts[visible_arm] = failed_frames
        aggregate["frame_errors"] = counts
        aggregate["fer"] = {arm: count / len(trials) for arm, count in counts.items()}
        aggregate["fer_source"] = "manifest_verified_trial_frame_error_events"
    summary["view_only_enrichment"] = True
    return summary
