"""Build and verify the self-contained REPRO-10A review archive."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "HF_TCM_SIM_REPRO_10A_AUDIT.zip"
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
README = """# HF-TCM-SIM REPRO-10A audit package

This archive contains the code, focused tests, real outputs, GUI evidence and verification needed for an independent review of REPRO-10A.

## Start here

1. `docs/repro/REPRO_10A_FINAL_REPORT.md`
2. `docs/repro/REPRO_10A_BER_SER_AUDIT.md`
3. `docs/repro/REPRO_10A_EXPORT_VALIDATION.md`
4. `outputs/repro10a/audit/legacy_pair_ser_recount.json`
5. `outputs/repro10a/audit/output_integrity.json`
6. `outputs/repro10a/acceptance/gui_qa_report.json`
7. `src/hf_tcm/repro/information_pair_metrics.py` and its test

## Before / after

| Defect | Before | Cause | After |
|---|---|---|---|
| Generic B0 SER exceeded payload BER in some frames | F=256: 56 bit / 60 reported symbol errors; F=32: 7 bit / 9 symbol errors | `symbol_errors` were hard phase-symbol errors before Viterbi, labeled as pair errors | Same decoded bit arrays give F=256: 56 bit / 47 information-pair errors; F=32: 7 bit / 6 information-pair errors. Phase SER remains a separate measure. |
| Transmitted I/Q PNG was empty | 300×310, alpha 0 for all pixels | Export action raced the asynchronous canvas draw and serialized the untouched initial canvas | Export waits for a rendered marker and drawings start with an opaque background; independently decoded PNGs have non-white plot pixels and verified dimensions. |
| Export label had mojibake | Corrupted button caption | Source literal was double-encoded | Browser displays `Зберегти PNG`; HTML, JavaScript, JSON and SVG UTF-8 paths were checked. |

## Contents and limitations

Project-relative paths are preserved. Selected old F=256/F=32 runs are included as read-only evidence; old manifests, summaries and traces were not rewritten. Three new F=32 controls, a resumed two-point/ten-trial GUI pilot, actual exported PNG/SVG plots, ten screenshots, source, tests and integrity reports are included. The prior empty PNG is included for comparison.

The Monte Carlo pilot is exploratory. `paper_exact:false`; physical Eb/N0 and the article's 1.5 dB gain remain unconfirmed/not estimable. No receiver mathematics changed. The F=20000 archived viewer data lacks I/Q traces and is not represented here as containing them. The historical 694-file baseline and the relevant 76-file REPRO-06B payload are included so the fingerprint check is auditable offline. The archive manifest hashes every payload entry except itself; ZIP CRC, payload hashes, PNG decode/visible-content checks and SVG XML/path checks are run by the package verifier.
"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def payload_paths() -> set[Path]:
    files = {
        Path("AGENTS.md"),
        Path("PLAN.md"),
        Path("NEXT_TASK.md"),
        Path("pyproject.toml"),
        Path("docs/BUILD_VERIFICATION.md"),
        Path("docs/repro/REPRO_09_GUI_USER_GUIDE.md"),
        Path("docs/repro/REPRO_10_FINAL_ACCEPTANCE_REPORT.md"),
        Path("docs/repro/REPRO_10_RELEASE_CHECKLIST.md"),
        Path("docs/repro/REPRO_10A_FINAL_REPORT.md"),
        Path("docs/repro/REPRO_10A_BER_SER_AUDIT.md"),
        Path("docs/repro/REPRO_10A_EXPORT_VALIDATION.md"),
        Path("src/hf_tcm/repro/information_pair_metrics.py"),
        Path("src/hf_tcm/repro/receiver_evaluation.py"),
        Path("src/hf_tcm/repro/paired_experiment.py"),
        Path("src/hf_tcm/studio/scientific.py"),
        Path("src/hf_tcm/studio/server.py"),
        Path("src/hf_tcm/studio/static/scientific.html"),
        Path("src/hf_tcm/studio/static/scientific.css"),
        Path("src/hf_tcm/studio/static/scientific.js"),
        Path("tests/repro/test_information_pair_metrics_10a.py"),
        Path("tests/repro/test_scientific_workspace.py"),
        Path("tests/repro/test_scientific_workspace_09b.py"),
        Path("scripts/qa_repro09b_scientific.js"),
        Path("scripts/audit_repro10a_legacy_pair_ser.py"),
        Path("scripts/run_repro10a_reference_controls.py"),
        Path("scripts/verify_repro10a_outputs.py"),
        Path("scripts/build_repro10a_audit_archive.py"),
        Path("scripts/verify_repro06b_artifacts.py"),
        Path("outputs/repro10a/reference_control_summary.json"),
        Path("outputs/repro10a/audit/legacy_pair_ser_recount.json"),
        Path("outputs/repro10a/audit/output_integrity.json"),
        Path("outputs/repro10a/audit/historical_fingerprint_verification.json"),
        Path("outputs/repro10a/audit/verification_results.json"),
        Path("outputs/repro10a/acceptance/gui_qa_report.json"),
        Path("tmp/m11d-integrity-before.json"),
    }
    for directory in (
        Path("outputs/repro10a/reference_runs"),
        Path("outputs/repro10a/paired_experiment"),
        Path("outputs/repro06b/reference_static_2path"),
    ):
        files.update(
            path.relative_to(ROOT) for path in (ROOT / directory).rglob("*") if path.is_file()
        )

    legacy_run_ids = ("run-20261110-121002-fa58a96e", "run-20261110-115623-ccedf172")
    for run_id in legacy_run_ids:
        directory = Path("outputs/repro09") / run_id
        for name in ("summary.json", "manifest.json", "traces.npz", "evaluation_truth.npz"):
            candidate = directory / name
            if (ROOT / candidate).is_file():
                files.add(candidate)

    qa = json.loads(
        (ROOT / "outputs/repro10a/acceptance/gui_qa_report.json").read_text(encoding="utf-8")
    )
    if not qa.get("passed"):
        raise RuntimeError("GUI QA report is not marked passed")
    files.update(Path(item["file"]) for item in qa["exports"])
    files.update(Path(item) for item in qa["screenshots"])
    return {path for path in files if (ROOT / path).is_file()}


def main() -> None:
    paths = sorted(payload_paths(), key=lambda item: item.as_posix().casefold())
    entries = []
    for path in paths:
        data = (ROOT / path).read_bytes()
        entries.append({"path": path.as_posix(), "size_bytes": len(data), "sha256": sha256(data)})
    manifest = {
        "schema_version": "hf-tcm-repro10a-audit-v1",
        "payload_file_count": len(entries) + 1,
        "manifest_self_hash": "omitted: recursive self-hashing is undefined",
        "files": entries,
    }
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        archive.writestr("README_FOR_CHATGPT.md", README.encode("utf-8"))
        for path in paths:
            archive.write(ROOT / path, path.as_posix())
        archive.writestr(
            "AUDIT_MANIFEST.json",
            (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
        )

    size = ARCHIVE.stat().st_size
    if size > MAX_ARCHIVE_BYTES:
        raise RuntimeError(f"Archive is {size} bytes (>512 MiB); it must be split before delivery")
    with zipfile.ZipFile(ARCHIVE, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC verification failed")
        members = set(archive.namelist())
        if "README_FOR_CHATGPT.md" not in members or "AUDIT_MANIFEST.json" not in members:
            raise RuntimeError("Required audit package files are missing")
        read_manifest = json.loads(archive.read("AUDIT_MANIFEST.json"))
        expected_members = {"README_FOR_CHATGPT.md", "AUDIT_MANIFEST.json"} | {
            item["path"] for item in read_manifest["files"]
        }
        if members != expected_members:
            raise RuntimeError("ZIP members do not exactly match audit manifest")
        for item in read_manifest["files"]:
            data = archive.read(item["path"])
            if len(data) != item["size_bytes"] or sha256(data) != item["sha256"]:
                raise RuntimeError(f"Manifest mismatch: {item['path']}")
            if item["path"].lower().endswith(".png"):
                with Image.open(BytesIO(data)) as image:
                    rgba = image.convert("RGBA")
                    alpha_min, alpha_max = rgba.getchannel("A").getextrema()
                    visible = any(
                        pixel[:3] != (255, 255, 255) and pixel[3] > 250 for pixel in rgba.getdata()
                    )
                    if alpha_max == 0 or not visible:
                        raise RuntimeError(f"PNG is empty or fully transparent: {item['path']}")
            elif item["path"].lower().endswith(".svg"):
                root = ET.fromstring(data)
                if root.tag != "{http://www.w3.org/2000/svg}svg":
                    raise RuntimeError(f"Invalid SVG namespace: {item['path']}")

    print(
        json.dumps(
            {
                "archive": ARCHIVE.name,
                "archive_size_bytes": size,
                "archive_sha256": sha256(ARCHIVE.read_bytes()),
                "files_count": len(paths) + 2,
                "payload_count": len(paths),
                "manifest_entries": len(entries),
                "zip_test": "PASS",
                "manifest_sha256_checks": "PASS",
                "png_svg_validation": "PASS",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
