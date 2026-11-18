"""Committed SCIENTIFIC-EXP-04 results bundle and its read-only studio route."""

from __future__ import annotations

import copy
import json
import threading
import urllib.request
from pathlib import Path

import pytest

from hf_tcm.repro.exp04_protocol import (
    DEFAULT_PROTOCOL,
    RESULTS_BUNDLE,
    build_results_bundle,
    load_protocol,
    load_results_bundle,
)
from hf_tcm.studio.server import make_server


def test_committed_bundle_matches_frozen_protocol_and_design() -> None:
    protocol, digest, status = load_protocol(DEFAULT_PROTOCOL)
    bundle = load_results_bundle()
    assert status == "FROZEN"
    assert bundle["protocol_sha256"] == digest
    assert bundle["paper_exact"] is False
    assert [c["id"] for c in bundle["cells"]] == [c["id"] for c in protocol["cells"]]
    total = 0
    for cell, spec in zip(bundle["cells"], protocol["cells"], strict=True):
        assert [p["eb_n0_db"] for p in cell["points"]] == spec["eb_n0_grid_db"]
        assert all(p["trials"] == spec["trials_per_point"] for p in cell["points"])
        assert cell["trials"] == len(spec["eb_n0_grid_db"]) * spec["trials_per_point"]
        assert cell["recount_mismatches"] == 0
        total += cell["trials"]
    assert total == 99_200


def test_primary_hypothesis_holds_in_committed_bundle() -> None:
    bundle = load_results_bundle()
    for cell in bundle["cells"]:
        if cell["role"] != "primary":
            continue
        target = cell["targets"][str(cell["primary_target_ber"])]
        assert target["verdict"] == "PRECISION_CRITERIA_MET"
        assert target["ci95_db"][0] > 0
        required = target["required_eb_n0_db"]
        assert target["gain_db"] == pytest.approx(required["separate"] - required["joint"])


def test_loader_rejects_bundle_from_another_protocol(tmp_path: Path) -> None:
    bundle = json.loads(RESULTS_BUNDLE.read_text(encoding="utf-8"))
    bundle["protocol_sha256"] = "0" * 64
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        load_results_bundle(path)


def test_builder_rejects_failed_recount_and_incomplete_cells() -> None:
    protocol, digest, _ = load_protocol(DEFAULT_PROTOCOL)
    bundle = load_results_bundle()
    analysis = [
        {"cell": c["id"], "trials": c["trials"], "targets": c["targets"]} for c in bundle["cells"]
    ]
    points = {
        "protocol_sha256": digest,
        "cells": {
            c["id"]: {"recount": {"trials": c["trials"], "mismatches": 0}, "points": c["points"]}
            for c in bundle["cells"]
        },
    }
    rebuilt = build_results_bundle(protocol, digest, analysis, points)
    assert rebuilt["cells"] == bundle["cells"]

    bad = copy.deepcopy(points)
    bad["cells"]["A1-awgn"]["recount"]["mismatches"] = 1
    with pytest.raises(ValueError, match="recount"):
        build_results_bundle(protocol, digest, analysis, bad)
    short = copy.deepcopy(analysis)
    short[0]["trials"] -= 1
    with pytest.raises(ValueError, match="incomplete"):
        build_results_bundle(protocol, digest, short, points)
    with pytest.raises(ValueError, match="different protocol"):
        build_results_bundle(protocol, "f" * 64, analysis, points)


def test_studio_serves_exp04_results_read_only() -> None:
    server = make_server(port=0, default_view="scientific")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/api/scientific/exp04-results"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())
        assert response.status == 200
        assert data["protocol_id"] == "SCIENTIFIC-EXP-04"
        assert len(data["cells"]) == 6
        page = f"http://127.0.0.1:{server.server_address[1]}/scientific"
        with urllib.request.urlopen(page, timeout=10) as response:
            assert b"/static/exp04_results.js" in response.read()
    finally:
        server.shutdown()
        server.server_close()


def test_exp04_frames_listing_and_study_roots(tmp_path: Path) -> None:
    from hf_tcm.repro.exp04_protocol import (
        GUI_METRIC_ROOT,
        list_exp04_frames,
        metric_study_root,
    )

    assert metric_study_root("exp04-A1-awgn", tmp_path) == tmp_path / "studies"
    assert metric_study_root("metric-known-1", tmp_path) == GUI_METRIC_ROOT
    assert list_exp04_frames(output_root=tmp_path) == []
    protocol, digest, _ = load_protocol(DEFAULT_PROTOCOL)
    cell = protocol["cells"][0]
    folder = tmp_path / "studies" / f"exp04-{cell['id']}"
    folder.mkdir(parents=True)
    (folder / "summary.json").write_text(
        json.dumps({"protocol_sha256": digest, "status": "completed"}), encoding="utf-8"
    )
    listed = list_exp04_frames(output_root=tmp_path)
    assert [c["cell"] for c in listed] == [cell["id"]]
    assert listed[0]["full_array_stride"] == 100
    assert listed[0]["eb_n0_grid_db"] == cell["eb_n0_grid_db"]
    (folder / "summary.json").write_text(
        json.dumps({"protocol_sha256": "0" * 64, "status": "completed"}), encoding="utf-8"
    )
    assert list_exp04_frames(output_root=tmp_path) == []
