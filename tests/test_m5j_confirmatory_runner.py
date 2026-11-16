from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import hf_tcm.evaluation.m5j_confirmatory_runner as runner
from hf_tcm.evaluation.m5j_confirmatory_runner import (
    M5JExecutionBlocked,
    create_approved_m5j_run_config,
    guard_m5j_execution,
    validate_approved_m5j_run_config,
)

ROOT = Path(__file__).resolve().parents[1]
M5I_CONFIG = ROOT / "configs" / "m5i_confirmatory_design_draft.json"
M5I_MANIFEST = ROOT / "configs" / "m5i_confirmatory_run_manifest_draft.json"


def _synthetic_summary(*, completed: int, failures: int, not_completed: int) -> dict:
    records = [{"status": "complete_valid_output"} for _ in range(completed)] + [
        {"status": "numerical_or_runtime_failure"} for _ in range(failures)
    ]
    return {
        "status": "complete" if failures == 0 and not_completed == 0 else "incomplete",
        "planned_run_count": completed + failures + not_completed,
        "completed_valid_run_count": completed,
        "failure_record_count": failures,
        "not_completed_count": not_completed,
        "records": records,
    }


@pytest.mark.parametrize(
    ("summary", "expected_exit_code"),
    [
        (_synthetic_summary(completed=100, failures=0, not_completed=0), 0),
        (_synthetic_summary(completed=98, failures=1, not_completed=1), 1),
    ],
)
def test_final_summary_print_uses_schema_and_run_completion_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    summary: dict,
    expected_exit_code: int,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "m5j_confirmatory_runner",
            "--worker",
            "--approved",
            "a",
            "--design",
            "d",
            "--manifest",
            "m",
            "--output",
            "o",
        ],
    )
    monkeypatch.setattr(runner, "execute_m5j", lambda *args: summary)

    exit_code = runner.main()

    printed = json.loads(capsys.readouterr().out)
    assert printed == {
        "status": summary["status"],
        "completed_valid_run_count": summary["completed_valid_run_count"],
        "failure_record_count": summary["failure_record_count"],
    }
    assert "failure_count" not in printed
    assert exit_code == expected_exit_code


def test_approved_run_snapshot_pins_design_manifest_code_and_scope(tmp_path: Path) -> None:
    approved_path = tmp_path / "m5j_approved.json"
    approved = create_approved_m5j_run_config(
        M5I_CONFIG,
        M5I_MANIFEST,
        approved_path,
        available_memory_before_bytes=4 * 1024**3,
        approved_at_utc="2026-10-29T19:00:00+00:00",
    )
    loaded = validate_approved_m5j_run_config(approved_path, M5I_CONFIG, M5I_MANIFEST)
    assert approved.config_sha256 == loaded.config_sha256
    assert loaded.data["design_status"] == "approved_confirmatory"
    assert loaded.data["execution_authorized"] is True
    assert loaded.data["execution_scope"] == "m5j_confirmatory_only"
    assert loaded.data["authorization_provenance"]["explicit_user_authorization"] == (
        "explicit user authorization through the current M5j Codex execution instruction"
    )
    assert loaded.data["approved_design_fingerprint"] == loaded.data["design_snapshot_fingerprint"]
    assert len(loaded.data["code_fingerprint"]) >= 10
    assert loaded.data["planned_manifest_fingerprint"]
    assert (
        Path(str(approved_path) + ".sha256").read_text(encoding="utf-8").strip()
        == approved.config_sha256
    )


def test_m5i_mismatch_rejected_before_creating_approval_or_execution(tmp_path: Path) -> None:
    modified = json.loads(M5I_CONFIG.read_text(encoding="utf-8"))
    modified["run_design"]["run_count"] = 99
    changed_path = tmp_path / "changed_m5i.json"
    changed_path.write_text(json.dumps(modified), encoding="utf-8")
    approved_path = tmp_path / "must_not_exist.json"
    with pytest.raises(ValueError):
        create_approved_m5j_run_config(
            changed_path,
            M5I_MANIFEST,
            approved_path,
            available_memory_before_bytes=4 * 1024**3,
            approved_at_utc="2026-10-29T19:00:00+00:00",
        )
    assert not approved_path.exists()


def test_approval_path_is_immutable_and_refuses_overwrite(tmp_path: Path) -> None:
    approved_path = tmp_path / "m5j_approved.json"
    create_approved_m5j_run_config(
        M5I_CONFIG,
        M5I_MANIFEST,
        approved_path,
        available_memory_before_bytes=4 * 1024**3,
        approved_at_utc="2026-10-29T19:00:00+00:00",
    )
    before = approved_path.read_bytes()
    with pytest.raises(FileExistsError):
        create_approved_m5j_run_config(
            M5I_CONFIG,
            M5I_MANIFEST,
            approved_path,
            available_memory_before_bytes=4 * 1024**3,
            approved_at_utc="2026-10-29T19:05:00+00:00",
        )
    assert approved_path.read_bytes() == before


def test_authorization_guard_must_block_before_any_execution_callback(tmp_path: Path) -> None:
    approved_path = tmp_path / "m5j_approved.json"
    approved = create_approved_m5j_run_config(
        M5I_CONFIG,
        M5I_MANIFEST,
        approved_path,
        available_memory_before_bytes=4 * 1024**3,
        approved_at_utc="2026-10-29T19:00:00+00:00",
    )
    unauthorized = dict(approved.data)
    unauthorized["execution_authorized"] = False
    calls: list[str] = []
    with pytest.raises(M5JExecutionBlocked):
        guard_m5j_execution(unauthorized, executor=lambda: calls.append("data/noise/decoder"))
    assert calls == []


def test_pilot_scope_cannot_authorize_confirmatory_execution(tmp_path: Path) -> None:
    approved_path = tmp_path / "m5j_approved.json"
    approved = create_approved_m5j_run_config(
        M5I_CONFIG,
        M5I_MANIFEST,
        approved_path,
        available_memory_before_bytes=4 * 1024**3,
        approved_at_utc="2026-10-29T19:00:00+00:00",
    )
    wrong_scope = dict(approved.data)
    wrong_scope["execution_scope"] = "m5h_pilot_only"
    calls: list[int] = []
    with pytest.raises(M5JExecutionBlocked):
        guard_m5j_execution(wrong_scope, executor=lambda: calls.append(1))
    assert calls == []


def test_approved_config_rejects_modified_code_or_manifest_snapshot(tmp_path: Path) -> None:
    approved_path = tmp_path / "m5j_approved.json"
    create_approved_m5j_run_config(
        M5I_CONFIG,
        M5I_MANIFEST,
        approved_path,
        available_memory_before_bytes=4 * 1024**3,
        approved_at_utc="2026-10-29T19:00:00+00:00",
    )
    changed = json.loads(approved_path.read_text(encoding="utf-8"))
    changed["planned_manifest_fingerprint"] = "0" * 64
    approved_path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_approved_m5j_run_config(approved_path, M5I_CONFIG, M5I_MANIFEST)
