"""Portable deterministic provenance and HTTP scheduling controls; no Monte Carlo."""

import hashlib
import json
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from hf_tcm.studio import historical_energy
from hf_tcm.studio import server as server_module


def _fixture(root: Path) -> dict:
    payloads = {
        "record.json": b'{"fixture":"synthetic"}',
        "config.json": b'{"phase":"test"}',
        "arrays.npz": b"deterministic byte fixture, not scientific samples",
    }
    manifest = {
        "files": {k: hashlib.sha256(v).hexdigest() for k, v in payloads.items()},
        "config_sha256": hashlib.sha256(payloads["config.json"]).hexdigest(),
    }
    for name, value in payloads.items():
        (root / name).write_bytes(value)
    manifest_bytes = json.dumps(manifest).encode()
    (root / "manifest.json").write_bytes(manifest_bytes)
    return {
        "record_sha256": manifest["files"]["record.json"],
        "trial_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
    }


def test_verified_trial_reads_each_payload_once_and_rechecks_tampering(tmp_path):
    source = _fixture(tmp_path)
    reads = []
    original = Path.read_bytes

    def observed(path):
        reads.append(path.name)
        return original(path)

    with patch.object(Path, "read_bytes", observed):
        record, config = historical_energy._read_exp01b_trial(tmp_path, source)
    assert record == {"fixture": "synthetic"}
    assert config == {"phase": "test"}
    assert sorted(reads) == ["arrays.npz", "config.json", "manifest.json", "record.json"]
    (tmp_path / "arrays.npz").write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        historical_energy._read_exp01b_trial(tmp_path, source)


def test_verified_trial_rejects_manifest_path_escape(tmp_path):
    source = _fixture(tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_bytes())
    manifest["files"]["../outside"] = "0" * 64
    payload = json.dumps(manifest).encode()
    (tmp_path / "manifest.json").write_bytes(payload)
    source["trial_manifest_sha256"] = hashlib.sha256(payload).hexdigest()
    with pytest.raises(ValueError, match="escapes"):
        historical_energy._read_exp01b_trial(tmp_path, source)


def test_trial_batch_preserves_source_order_without_changing_files(tmp_path):
    rows = []
    for name in ("second", "first"):
        folder = tmp_path / name
        folder.mkdir()
        source = _fixture(folder)
        source["path"] = name + "/record.json"
        rows.append(source)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = historical_energy._read_exp01b_trials(tmp_path, rows)
    assert [row[0] for row in result] == [r["path"] for r in rows]
    assert before == {
        p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }


def test_slow_historical_loader_does_not_block_health_route(monkeypatch, caplog):
    entered, release = threading.Event(), threading.Event()

    def controlled_loader():
        entered.set()
        assert release.wait(5), "test controller did not release loader"
        return {"fixture": "controlled_http_only"}

    monkeypatch.setattr(server_module, "load_historical_exp01b_energy_study", controlled_loader)
    caplog.set_level("INFO")
    server = server_module.make_server(port=0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    address = f"http://127.0.0.1:{server.server_port}"

    def request(path):
        with urllib.request.urlopen(address + path, timeout=5) as response:
            return json.load(response)

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                request, "/api/scientific/energy-studies/historical/exp01b-static-amplitude-005"
            )
            try:
                assert entered.wait(2)
                assert request("/api/health")["status"] == "ready"
            finally:
                release.set()
            assert future.result(timeout=5) == {"fixture": "controlled_http_only"}
        assert any("exp01b_http" in r.message for r in caplog.records)
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        worker.join(2)
