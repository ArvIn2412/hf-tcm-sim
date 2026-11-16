import hashlib
import json

import pytest

from hf_tcm.studio.energy_view import load_energy_view


def _bundle(root):
    folder = root / "energy-test"
    (folder / "trials").mkdir(parents=True)
    values = {
        "config.json": {"experiment_id": "energy-test"},
        "summary.json": {
            "experiment_id": "energy-test",
            "contrast_id": "metric_isolation",
            "aggregates": [{"gamma_db": 2.0, "trials": 2}],
        },
    }
    for trial, errors in enumerate(((3, 0), (0, 2))):
        values[f"trials/p000-t{trial:04d}.json"] = {
            "point_index": 0,
            "gamma_b_discrete_db": 2.0,
            "hamming": {"fer": int(errors[0] > 0), "bit_errors": errors[0]},
            "euclidean": {"fer": int(errors[1] > 0), "bit_errors": errors[1]},
        }
    hashes = {}
    for relative, value in values.items():
        data = json.dumps(value).encode("utf-8")
        (folder / relative).write_bytes(data)
        hashes[relative] = hashlib.sha256(data).hexdigest()
    (folder / "manifest.json").write_text(
        json.dumps({"schema_version": "scientific-exp03a-metric-manifest-v1", "files": hashes}),
        encoding="utf-8",
    )
    return folder


def test_fer_view_pools_integer_events_without_writing_sources(tmp_path):
    folder = _bundle(tmp_path)
    before = {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    result = load_energy_view(tmp_path, "energy-test")
    assert result["aggregates"][0]["fer"] == {"hamming": 0.5, "joint": 0.5}
    assert result["aggregates"][0]["frame_errors"] == {"hamming": 1, "joint": 1}
    assert before == {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def test_fer_view_rejects_changed_trial_before_reading_counts(tmp_path):
    folder = _bundle(tmp_path)
    (folder / "trials/p000-t0000.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        load_energy_view(tmp_path, "energy-test")


@pytest.mark.parametrize("identifier", ["../escape", "/absolute", "a/b", ""])
def test_fer_view_rejects_path_inputs(tmp_path, identifier):
    with pytest.raises(ValueError, match="study ID"):
        load_energy_view(tmp_path, identifier)
