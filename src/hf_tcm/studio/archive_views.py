"""Read-only M11d chart adapter for frozen M5–M10 files.

[ПРОЄКТ] These views preserve stored estimates and intervals. The only expansion
is the explicit M10 configuration's constant gain segments into symbol values.
No receiver, decoder, RNG, bootstrap, or simulation module is imported or run.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SOURCES = {
    "M5j": "outputs/m5j_confirmatory/20261029T-run/summary.json",
    "M7b": "outputs/m7b_train/m7_reconstructed_estimator_policy_study_v1/summary.json",
    "M8": "outputs/m8b_train_recovery/m8_anchored_reconstructed_adaptation_v1_attempt2/summary.json",
    "M9": "outputs/m9b_fixed_policy_evaluation/m9_fixed_anchored_vs_frozen_v1/summary.json",
    "M10": "outputs/m10b_variable_gain/m10_controlled_piecewise_gain_v1/summary.json",
    "M10_config": "configs/m10b_variable_gain_approved_run.json",
}
POLICIES = ("historical_frozen_B", "anch_a085_k025")
PROFILES = ("P0_CONSTANT", "P1_HIGH_TO_LOW", "P2_LOW_TO_HIGH")


def _number(value: Any) -> int | float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("a finite archived numeric value is required")
    return value


def _ber(value: Any) -> int | float:
    result = _number(value)
    if not 0 <= result <= 1:
        raise ValueError("archived BER must be between zero and one")
    return result


def _series(name: str, values: list[int | float]) -> dict[str, Any]:
    return {"name": name, "values": values}


def _m5j(data: dict[str, Any]) -> dict[str, Any]:
    points = data["point_estimates"]
    return {
        "labels": ["historical_frozen_B", "historical_combined_C"],
        "series": [_series("BER", [_ber(points["ber_b"]), _ber(points["ber_c"])])],
        "source_fields": ["point_estimates.ber_b", "point_estimates.ber_c"],
    }


def _ranking(data: dict[str, Any]) -> dict[str, Any]:
    ranking = data["ranking"]
    if not isinstance(ranking, list) or not ranking:
        raise ValueError("stored TRAIN ranking is unavailable")
    labels = [row["candidate_id"] for row in ranking]
    if any(not isinstance(label, str) or not label for label in labels):
        raise ValueError("stored TRAIN candidate IDs are unavailable")
    return {
        "labels": labels,
        "series": [_series("TRAIN BER", [_ber(row["pooled_ber"]) for row in ranking])],
        "source_fields": ["ranking[].candidate_id", "ranking[].pooled_ber"],
    }


def _m9_ber(data: dict[str, Any]) -> dict[str, Any]:
    points = data["paired_estimands"]
    return {
        "labels": list(POLICIES),
        "series": [_series("BER", [_ber(points["ber_B"]), _ber(points["ber_anchored"])])],
        "source_fields": ["paired_estimands.ber_B", "paired_estimands.ber_anchored"],
    }


def _ci(label: str, point: Any, interval: Any, fields: list[str]) -> dict[str, Any]:
    if not isinstance(interval, list) or len(interval) != 2:
        raise ValueError("stored two-sided interval is unavailable")
    low, high = (_number(value) for value in interval)
    if low > high:
        raise ValueError("stored interval bounds are reversed")
    return {
        "labels": [label],
        "series": [_series("DeltaBER (95% CI)", [low, _number(point), high])],
        "source_fields": fields,
        "contrast": "anch_a085_k025 - historical_frozen_B",
        "contains_zero": low <= 0 <= high,
        "confidence_level": 0.95,
    }


def _m9_ci(data: dict[str, Any]) -> dict[str, Any]:
    return _ci(
        "M9 fixed policies",
        data["paired_estimands"]["delta_ber"],
        data["bootstrap"]["delta_ber_ci"],
        ["paired_estimands.delta_ber", "bootstrap.delta_ber_ci"],
    )


def _m10_ber(data: dict[str, Any]) -> dict[str, Any]:
    profiles = data["statistics"]["profiles"]
    return {
        "labels": list(PROFILES),
        "series": [
            _series(policy, [_ber(profiles[profile][policy]["ber"]) for profile in PROFILES])
            for policy in POLICIES
        ],
        "source_fields": [
            f"statistics.profiles.{profile}.{policy}.ber"
            for policy in POLICIES
            for profile in PROFILES
        ],
    }


def _m10_ci(data: dict[str, Any]) -> dict[str, Any]:
    statistics = data["statistics"]
    if statistics["primary_profile"] != "P1_HIGH_TO_LOW":
        raise ValueError("the stored primary profile is not P1_HIGH_TO_LOW")
    return _ci(
        statistics["primary_profile"],
        statistics["primary_delta_ber"],
        statistics["primary_95_percent_ci"],
        ["statistics.primary_delta_ber", "statistics.primary_95_percent_ci"],
    )


def _gains(data: dict[str, Any]) -> dict[str, Any]:
    channel = data["channel_profile"]
    count = channel["frame_symbols"]
    if type(count) is not int or not 1 <= count <= 100_000:
        raise ValueError("stored frame length is unavailable or unsupported")
    series = []
    for profile in PROFILES:
        values: list[int | float] = []
        for segment in channel["profiles"][profile]["segments"]:
            start, stop = segment["symbol_start"], segment["symbol_stop_exclusive"]
            if (
                type(start) is not int
                or type(stop) is not int
                or start != len(values)
                or not start < stop <= count
            ):
                raise ValueError("stored gain segments have gaps, overlap, or invalid boundaries")
            values.extend([_number(segment["gain"])] * (stop - start))
        if len(values) != count:
            raise ValueError("stored gain segments do not cover the complete frame")
        series.append(_series(profile, values))
    return {
        "labels": list(range(count)),
        "series": series,
        "interpolation": "step",
        "source_fields": [
            "channel_profile.frame_symbols",
            "channel_profile.profiles.*.segments",
        ],
    }


def build_archive_views(*, root: Path = ROOT) -> dict[str, Any]:
    """Load archived chart values, with explicit unavailable entries on missing data.

    Source hashes identify exactly the bytes parsed by this request. Values are
    not rounded or re-estimated; callers may format their presentation only.
    ``root`` permits isolated read-only fixtures and missing-artifact checks.
    """
    charts: list[dict[str, Any]] = []

    def add(
        chart_id: str,
        title: str,
        source: str,
        builder: Callable[[dict[str, Any]], dict[str, Any]],
        caption: str,
        *,
        kind: str = "bar",
        category: str = "INDEPENDENT_EVALUATION",
    ) -> None:
        gain = category == "FROZEN_DESIGN"
        ci = kind == "ci"
        chart: dict[str, Any] = {
            "id": chart_id,
            "title": title,
            "kind": kind,
            "evidence_category": category,
            "x_label": "Symbol index f" if gain else "Profile" if source == "M10" else "Policy",
            "y_label": "Real gain a[f]" if gain else "DeltaBER (anchored - B)" if ci else "BER",
            "unit": "dimensionless gain" if gain else "bit error fraction",
            "caption": caption,
            "source_path": SOURCES[source],
            "source_sha256": None,
            "source_fields": [],
            "series": [],
            "labels": [],
            "status": "UNAVAILABLE",
        }
        try:
            raw = (root / SOURCES[source]).read_bytes()
            chart["source_sha256"] = hashlib.sha256(raw).hexdigest()
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("the archived JSON root is not an object")
            values = builder(data)
        except (OSError, UnicodeError, ValueError, KeyError, TypeError, IndexError) as exc:
            chart["unavailable_reason"] = f"Archived data unavailable: {type(exc).__name__}: {exc}"
        else:
            chart.update(values)
            chart["status"] = "AVAILABLE"
        charts.append(chart)

    add(
        "m5j-ber",
        "M5j: historical B versus C",
        "M5j",
        _m5j,
        "Archived 100 paired runs at fixed 5 dB effective discrete gamma_b. "
        "Historical C is not the later anchored policy. Narrow reconstructed L=1 comparison; "
        "no physical HF or paper-exact claim. Per-symbol estimator history is unavailable.",
    )
    add(
        "m7b-train",
        "M7b: exploratory TRAIN ranking",
        "M7b",
        _ranking,
        "TRAIN_SELECTED_NOT_VALIDATED: 40 TRAIN sequences, nine policies; "
        "not independent validation. Stored ranking is preserved; frozen B ranked first.",
        category="TRAIN",
    )
    add(
        "m8-recovery-train",
        "M8 recovery: exploratory TRAIN ranking",
        "M8",
        _ranking,
        "TRAIN_SELECTED_NOT_VALIDATED: technical recovery reused the same 40 input IDs/seeds; "
        "not independent validation or a new independent sample. Frozen B ranked first.",
        category="TRAIN",
    )
    add(
        "m9-ber",
        "M9: independent fixed-policy BER",
        "M9",
        _m9_ber,
        "Archived prospective fixed-policy comparison on 100 independent paired sequences. "
        "Not M8 validation; lower anchored point estimate does not establish superiority.",
    )
    add(
        "m9-delta-ber",
        "M9: paired DeltaBER and 95% CI",
        "M9",
        _m9_ci,
        "Stored ADR-014 paired cluster-bootstrap interval, anchored minus frozen B. "
        "The interval includes zero; superiority, equivalence and noninferiority are not established.",
        kind="ci",
    )
    add(
        "m10-gain-schedules",
        "M10: frozen P0/P1/P2 gain schedules",
        "M10_config",
        _gains,
        "Exact expansion of the frozen approved configuration's piecewise constant segments. "
        "A design schedule, not a generated observation or physical HF channel. "
        "P1/P2 switch at f=128; the gain schedule is not passed to the receiver.",
        kind="line",
        category="FROZEN_DESIGN",
    )
    add(
        "m10-ber",
        "M10: archived BER by profile and policy",
        "M10",
        _m10_ber,
        "Archived 100 independent run clusters, each containing all three profiles and both "
        "policies with shared bits/noise. P1 is primary; profile contrasts are not independent "
        "samples. Controlled real-gain variation, not physical HF evidence.",
    )
    add(
        "m10-p1-delta-ber",
        "M10 P1: primary paired DeltaBER and 95% CI",
        "M10",
        _m10_ci,
        "Stored ADR-014 paired full-run cluster-bootstrap interval for primary P1, "
        "anchored minus frozen B. The interval includes zero; no superiority or equivalence claim.",
        kind="ci",
    )
    return {
        "schema_version": "m11d.archive-views.v1",
        "classification": "ARCHIVED SCIENTIFIC RESULTS",
        "receiver_invoked": False,
        "rng_used": False,
        "paper_exact": False,
        "receiver_enabled": False,
        "charts": charts,
    }
