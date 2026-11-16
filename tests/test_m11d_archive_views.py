"""Regression oracles for read-only graphics built from immutable study files."""

from __future__ import annotations

import builtins
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from hf_tcm.studio.archive_views import build_archive_views

ROOT = Path(__file__).resolve().parents[1]


def _charts(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    return {chart["id"]: chart for chart in build_archive_views(root=root)["charts"]}


def test_archived_m5j_and_train_rankings_preserve_evidence_categories() -> None:
    charts = _charts()
    historical = charts["m5j-ber"]
    assert historical["series"][0]["values"] == [1079 / 51200, 19793 / 51200]
    assert historical["evidence_category"] == "INDEPENDENT_EVALUATION"
    for chart_id, first_policy, errors in (
        ("m7b-train", "a100_k000", [478, 1903, 3050, 4831, 4871, 7357, 7575, 8093, 8545]),
        (
            "m8-recovery-train",
            "historical_frozen_B",
            [413, 429, 490, 528, 924, 1501, 3000, 7804],
        ),
    ):
        chart = charts[chart_id]
        assert chart["evidence_category"] == "TRAIN"
        assert chart["labels"][0] == first_policy
        assert chart["series"][0]["values"] == [count / 20480 for count in errors]
        assert "TRAIN_SELECTED_NOT_VALIDATED" in chart["caption"]
        assert "not independent validation" in chart["caption"]


def test_m9_archived_ber_and_paired_ci_are_exact_without_rounding() -> None:
    charts = _charts()
    assert charts["m9-ber"]["series"][0]["values"] == [0.0220703125, 0.0209375]
    ci = charts["m9-delta-ber"]
    assert ci["series"][0]["values"] == [
        -0.0032226562500000007,
        -0.0011328125,
        0.0006835937499999994,
    ]
    assert ci["kind"] == "ci"
    assert ci["contains_zero"] is True
    assert ci["evidence_category"] == "INDEPENDENT_EVALUATION"
    assert ci["contrast"] == "anch_a085_k025 - historical_frozen_B"


def test_m10_archived_profile_results_and_primary_ci_are_exact() -> None:
    charts = _charts()
    ber = charts["m10-ber"]
    assert ber["labels"] == ["P0_CONSTANT", "P1_HIGH_TO_LOW", "P2_LOW_TO_HIGH"]
    assert ber["series"] == [
        {
            "name": "historical_frozen_B",
            "values": [1202 / 51200, 4136 / 51200, 4205 / 51200],
        },
        {"name": "anch_a085_k025", "values": [1180 / 51200, 4120 / 51200, 4208 / 51200]},
    ]
    ci = charts["m10-p1-delta-ber"]
    assert ci["labels"] == ["P1_HIGH_TO_LOW"]
    assert ci["series"][0]["values"] == [
        -0.0020512695312500002,
        -0.00031249999999999334,
        0.0014453125,
    ]
    assert ci["contains_zero"] is True
    assert ci["evidence_category"] == "INDEPENDENT_EVALUATION"


def test_gain_plot_only_expands_frozen_config_segments() -> None:
    chart = _charts()["m10-gain-schedules"]
    assert chart["evidence_category"] == "FROZEN_DESIGN"
    assert chart["source_path"] == "configs/m10b_variable_gain_approved_run.json"
    assert chart["interpolation"] == "step"
    assert chart["labels"] == list(range(256))
    assert chart["series"] == [
        {"name": "P0_CONSTANT", "values": [0.75] * 256},
        {"name": "P1_HIGH_TO_LOW", "values": [0.8746427842267951] * 128 + [0.6] * 128},
        {"name": "P2_LOW_TO_HIGH", "values": [0.6] * 128 + [0.8746427842267951] * 128},
    ]


def test_archive_views_are_serializable_and_provenance_matches_source_bytes() -> None:
    payload = build_archive_views()
    assert payload["receiver_invoked"] is False
    assert payload["rng_used"] is False
    assert len(payload["charts"]) == 8
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload
    for chart in payload["charts"]:
        assert chart["status"] == "AVAILABLE"
        assert (
            chart["source_sha256"]
            == hashlib.sha256((ROOT / chart["source_path"]).read_bytes()).hexdigest()
        )
        assert chart["source_fields"]
        assert chart["x_label"] and chart["y_label"] and chart["unit"] and chart["caption"]


def test_missing_archive_never_synthesizes_results(tmp_path: Path) -> None:
    for chart in _charts(tmp_path).values():
        assert chart["status"] == "UNAVAILABLE"
        assert chart["series"] == []
        assert chart["labels"] == []
        assert chart["source_sha256"] is None
        assert chart["unavailable_reason"]


@pytest.mark.parametrize("content", ["not JSON", "[]", "{}", '{"paired_estimands":{"ber_B":NaN}}'])
def test_bad_source_is_unavailable_with_its_actual_hash(tmp_path: Path, content: str) -> None:
    source_path = _charts()["m9-ber"]["source_path"]
    source = tmp_path / source_path
    source.parent.mkdir(parents=True)
    source.write_text(content, encoding="utf-8")
    for chart_id in ("m9-ber", "m9-delta-ber"):
        chart = _charts(tmp_path)[chart_id]
        assert chart["status"] == "UNAVAILABLE"
        assert chart["series"] == []
        assert chart["labels"] == []
        assert chart["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_incomplete_gain_schedule_is_unavailable_without_filling_gaps(tmp_path: Path) -> None:
    source_path = _charts()["m10-gain-schedules"]["source_path"]
    data = json.loads((ROOT / source_path).read_text(encoding="utf-8"))
    data["channel_profile"]["profiles"]["P1_HIGH_TO_LOW"]["segments"][1]["symbol_start"] = 129
    source = tmp_path / source_path
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps(data), encoding="utf-8")
    chart = _charts(tmp_path)["m10-gain-schedules"]
    assert chart["status"] == "UNAVAILABLE"
    assert chart["series"] == []


def test_archive_view_does_not_import_receiver_or_rng_or_write_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__
    original_open = Path.open

    def guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
        assert not name.startswith(("hf_tcm.receiver", "hf_tcm.decoding", "numpy", "random"))
        return original_import(name, *args, **kwargs)

    def read_only_open(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        assert not any(flag in mode for flag in "wax+")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(Path, "open", read_only_open)
    assert all(chart["status"] == "AVAILABLE" for chart in build_archive_views()["charts"])
