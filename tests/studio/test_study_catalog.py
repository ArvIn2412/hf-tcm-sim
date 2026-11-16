from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hf_tcm.studio.study_catalog import list_study_catalog


def _study(root: Path, index: int) -> Path:
    folder = root / "scientific-exp03a/metric-studies" / f"study-{index:03d}"
    folder.mkdir(parents=True)
    summary = {
        "experiment_id": folder.name,
        "status": "completed" if index % 2 else "incomplete",
        "completed_trials": index,
        "aggregates": [{"bits": 100, "bit_errors": {"hamming": index % 3, "joint": 0}}],
    }
    config = {
        "frame_symbols": 20_000,
        "root_seed": index,
        "scenario": "awgn",
        "frontend_mode": "awgn_direct_control",
    }
    for name, value in (("summary.json", summary), ("config.json", config)):
        (folder / name).write_text(json.dumps(value), encoding="utf-8")
    files = {
        name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
        for name in ("summary.json", "config.json")
    }
    (folder / "manifest.json").write_text(json.dumps({"files": files}), encoding="utf-8")
    return folder


def test_catalog_pages_hundreds_of_records_and_keeps_zero_ber_distinct(tmp_path: Path) -> None:
    for index in range(231):
        _study(tmp_path, index)
    page = list_study_catalog(tmp_path, page=2, size=20, sort="id_asc")
    assert page["total"] == 231
    assert page["pages"] == 12
    assert len(page["items"]) == 20
    assert page["items"][0]["id"] == "study-020"
    assert page["items"][-1]["id"] == "study-039"
    assert page["items"][0]["metrics"]["euclidean"] == {"errors": 0, "bits": 100, "ber": 0.0}
    assert "outputs" not in page["items"][0]


def test_catalog_search_filters_sort_and_rejects_modified_metadata(tmp_path: Path) -> None:
    folders = [_study(tmp_path, index) for index in range(12)]
    response = list_study_catalog(
        tmp_path,
        q="study-00",
        status="completed",
        channel="awgn",
        metric="hamming",
        sort="trials_desc",
    )
    assert [row["id"] for row in response["items"]] == [
        "study-009",
        "study-007",
        "study-005",
        "study-003",
        "study-001",
    ]
    (folders[9] / "config.json").write_text('{"frame_symbols":2}', encoding="utf-8")
    response = list_study_catalog(tmp_path, q="study-009")
    assert response["items"] == []
    assert response["rejected_metadata"] == 1


@pytest.mark.parametrize(
    "kwargs", [{"page": 0}, {"size": 51}, {"metric": "joint"}, {"sort": "path"}, {"q": "x" * 201}]
)
def test_catalog_rejects_invalid_queries(tmp_path: Path, kwargs: dict) -> None:
    with pytest.raises(ValueError):
        list_study_catalog(tmp_path, **kwargs)


def test_catalog_never_changes_source_files(tmp_path: Path) -> None:
    folder = _study(tmp_path, 1)
    before = {file.name: file.read_bytes() for file in folder.iterdir()}
    list_study_catalog(tmp_path)
    after = {file.name: file.read_bytes() for file in folder.iterdir()}
    assert before == after
