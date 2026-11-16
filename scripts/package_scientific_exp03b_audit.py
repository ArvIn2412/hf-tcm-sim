"""Package and verify the complete SCIENTIFIC-EXP-03B audit archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "outputs/scientific_exp03b"
PROTOCOL_SHA = "d553e65fdad020f4887d252bb29bd88311b84b596bbba1e14fd4a806e71068c6"
REPORTS = [
    "SCIENTIFIC_EXP_03B_FINAL_REPORT.md",
    "SCIENTIFIC_EXP_03B_METRIC_COMPARISON.md",
    "SCIENTIFIC_EXP_03B_SYSTEM_COMPARISON.md",
    "SCIENTIFIC_EXP_03B_ENERGY_GAIN.md",
    "SCIENTIFIC_EXP_03B_STATISTICAL_VALIDATION.md",
    "SCIENTIFIC_EXP_03B_ARTICLE_COMPARISON.md",
    "THESIS_CHAPTER_4_FINAL_DRAFT.md",
    "THESIS_CHAPTER_4_FIGURES_AND_TABLES.md",
]


def _safe_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if any(
        part in {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}
        for part in path.parts
    ):
        return False
    if path.suffix.lower() in {".pyc", ".pyo", ".lock", ".tmp"}:
        return False
    if path.name.lower() in {".env", ".env.local", "secrets.json", "credentials.json"}:
        return False
    return True


def collect_files() -> list[Path]:
    selected: set[Path] = set()

    def add_file(relative: str) -> None:
        path = ROOT / relative
        if _safe_file(path):
            selected.add(path)
        else:
            raise FileNotFoundError(f"Required audit file missing or excluded: {relative}")

    def add_tree(relative: str) -> None:
        base = ROOT / relative
        if not base.is_dir():
            raise FileNotFoundError(f"Required audit directory missing: {relative}")
        selected.update(path for path in base.rglob("*") if _safe_file(path))

    add_tree("outputs/scientific_exp03b/metric/confirmatory")
    add_tree("outputs/scientific_exp03b/system/confirmatory")
    add_tree("docs/research/figures/SCIENTIFIC_EXP_03B")
    add_tree("docs/research/tables/SCIENTIFIC_EXP_03B")
    add_tree("references")
    add_tree("src/hf_tcm")

    for relative in [
        "README_FOR_CHATGPT.md",
        "configs/SCIENTIFIC_EXP_03B_PROTOCOL.json",
        "outputs/scientific_exp03b/analysis/independent_analysis.json",
        "outputs/scientific_exp03b/analysis/analysis_manifest.json",
        "outputs/scientific_exp03b/confirmatory_execution_state.json",
        "outputs/scientific_exp03b/preflight_execution_state.json",
        "docs/ASSUMPTIONS_AND_DECISIONS.md",
        "docs/BUILD_VERIFICATION.md",
        "docs/research/ARTICLE_COMPLIANCE_FINAL_AUDIT.md",
        "pyproject.toml",
        "scripts/analyze_scientific_exp03b.py",
        "scripts/render_scientific_exp03b_figures.py",
        "scripts/reanalyze_scientific_exp03b_system.py",
        "scripts/write_scientific_exp03b_reports.py",
        "scripts/package_scientific_exp03b_audit.py",
        "scripts/verify_repro06b_artifacts.py",
    ]:
        add_file(relative)

    for path in (ROOT / "docs/research").glob("SCIENTIFIC_EXP_03B*.md"):
        if _safe_file(path):
            selected.add(path)
    for name in REPORTS:
        add_file(f"docs/research/{name}")
    for pattern in ("SCIENTIFIC_EXP_01B*.md", "SCIENTIFIC_EXP_02*.md"):
        selected.update(path for path in (ROOT / "docs/research").glob(pattern) if _safe_file(path))

    test_patterns = (
        "tests/repro/test_*exp03b*.py",
        "tests/repro/test_confirmatory_exp03b.py",
        "tests/studio/test_scientific_exp03b_results.py",
    )
    for pattern in test_patterns:
        selected.update(path for path in ROOT.glob(pattern) if _safe_file(path))
    for candidate in (ROOT / "tests/repro").glob("test_*exp03b*.py"):
        if _safe_file(candidate):
            selected.add(candidate)

    log_dir = ROOT / "outputs/scientific_exp03b/validation_logs"
    if log_dir.is_dir():
        add_tree("outputs/scientific_exp03b/validation_logs")

    return sorted(selected, key=lambda path: path.relative_to(ROOT).as_posix().casefold())


def verify_study_manifests() -> dict[str, int]:
    metric_root = DATA_ROOT / "metric/confirmatory"
    system_root = DATA_ROOT / "system/confirmatory"
    metric_total = 0
    for root in sorted(metric_root.iterdir()):
        if not root.is_dir():
            continue
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("status") != "completed" or manifest.get("protocol_sha256") != PROTOCOL_SHA:
            raise ValueError(f"Incomplete or mismatched metric manifest: {root}")
        if manifest.get("completed_trials") != manifest.get("planned_trials"):
            raise ValueError(f"Metric trial count mismatch: {root}")
        metric_total += int(manifest["completed_trials"])
    if metric_total != 22_800:
        raise ValueError(f"Expected 22,800 metric trials, found {metric_total}")

    system_counts = {"awgn": 2_900, "static": 2_900, "rician": 2_500}
    for scenario, expected in system_counts.items():
        root = system_root / scenario
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        if (
            manifest.get("status") != "completed"
            or manifest.get("protocol_sha256") != PROTOCOL_SHA
            or manifest.get("completed_trials") != expected
            or manifest.get("planned_trials") != expected
        ):
            raise ValueError(f"System series is incomplete or mismatched: {root}")

    analysis = json.loads(
        (DATA_ROOT / "analysis/independent_analysis.json").read_text(encoding="utf-8")
    )
    if analysis.get("protocol_sha256") != PROTOCOL_SHA or analysis.get("preflight_included"):
        raise ValueError("Independent analysis does not match the confirmatory-only protocol")
    analysis_manifest = json.loads(
        (DATA_ROOT / "analysis/analysis_manifest.json").read_text(encoding="utf-8")
    )
    if analysis_manifest.get("independent_system_recount") != "PASS":
        raise ValueError("System independent array recount did not pass")
    return {"metric_trials": metric_total, "system_trials": sum(system_counts.values())}


def _hash_and_write(
    path: Path, archive: zipfile.ZipFile, buffer_size: int = 1024 * 1024
) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    digest = hashlib.sha256()
    size = 0
    info = zipfile.ZipInfo(relative)
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    with path.open("rb") as source, archive.open(info, mode="w", force_zip64=True) as destination:
        while chunk := source.read(buffer_size):
            digest.update(chunk)
            size += len(chunk)
            destination.write(chunk)
    return {"path": relative, "size_bytes": size, "sha256": digest.hexdigest()}


def _verify_archive(path: Path, expected_manifest: dict[str, Any]) -> dict[str, Any]:
    if not zipfile.is_zipfile(path):
        raise ValueError("Output is not a readable ZIP archive")
    seen = set()
    manifest_rows = expected_manifest["files"]
    manifest_by_path = {row["path"]: row for row in manifest_rows}
    total_bytes = 0
    png_count = 0
    svg_count = 0
    with zipfile.ZipFile(path, "r") as archive:
        names = set(archive.namelist())
        if len(names) != len(archive.namelist()):
            raise ValueError("Duplicate ZIP member names")
        if "AUDIT_MANIFEST.json" not in names:
            raise ValueError("Audit manifest missing from ZIP")
        embedded_manifest = json.loads(archive.read("AUDIT_MANIFEST.json"))
        if embedded_manifest != expected_manifest:
            raise ValueError("Embedded audit manifest differs from the package manifest")
        if names - {"AUDIT_MANIFEST.json"} != set(manifest_by_path):
            raise ValueError("Manifest paths do not match ZIP member paths")
        figure_manifest_path = (
            "docs/research/figures/SCIENTIFIC_EXP_03B/FIGURE_EXPORTS_MANIFEST.json"
        )
        figure_manifest = json.loads(archive.read(figure_manifest_path))
        figure_rows = figure_manifest.get("figures", [])
        figure_png_rows = [
            row for row in figure_rows if row.get("path", "").lower().endswith(".png")
        ]
        figure_svg_rows = [
            row for row in figure_rows if row.get("path", "").lower().endswith(".svg")
        ]
        if len(figure_png_rows) != 59 or len(figure_svg_rows) != 59:
            raise ValueError(
                "Figure export manifest must declare 59 PNG and 59 SVG plots; "
                f"found {len(figure_png_rows)} and {len(figure_svg_rows)}"
            )
        for figure_row in figure_rows:
            packaged = manifest_by_path.get(figure_row.get("path"))
            if (
                packaged is None
                or packaged.get("size_bytes") != figure_row.get("bytes")
                or packaged.get("sha256") != figure_row.get("sha256")
            ):
                raise ValueError(f"Figure export manifest mismatch: {figure_row.get('path')}")
        for index, row in enumerate(manifest_rows, start=1):
            digest = hashlib.sha256()
            size = 0
            prefix = bytearray()
            tail = bytearray()
            with archive.open(row["path"], "r") as member:
                while chunk := member.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
                    if len(prefix) < 32:
                        prefix.extend(chunk[: 32 - len(prefix)])
                    if row["path"].lower().endswith(".svg") and len(tail) < 1_000_000:
                        tail.extend(chunk)
            if size != row["size_bytes"] or digest.hexdigest() != row["sha256"]:
                raise ValueError(f"Archive member SHA/size mismatch: {row['path']}")
            if row["path"].lower().endswith(".png"):
                png_count += 1
                if bytes(prefix[:8]) != b"\x89PNG\r\n\x1a\n":
                    raise ValueError(f"Invalid PNG signature in archive: {row['path']}")
                width, height = struct.unpack(">II", prefix[16:24])
                if width < 1000 or height < 600:
                    raise ValueError(f"PNG resolution too small in archive: {row['path']}")
            elif row["path"].lower().endswith(".svg"):
                svg_count += 1
                svg_text = tail.decode("utf-8")
                if "<svg" not in svg_text or "<path" not in svg_text:
                    raise ValueError(f"SVG is not a populated vector plot: {row['path']}")
            total_bytes += size
            seen.add(row["path"])
            if index % 5_000 == 0:
                print(
                    f"verified {index}/{len(manifest_rows)} members ({total_bytes:,} bytes)",
                    flush=True,
                )
    expected_png_count = sum(row["path"].lower().endswith(".png") for row in manifest_rows)
    expected_svg_count = sum(row["path"].lower().endswith(".svg") for row in manifest_rows)
    if png_count != expected_png_count or svg_count != expected_svg_count:
        raise ValueError(
            f"Expected manifest-declared {expected_png_count} PNG + "
            f"{expected_svg_count} SVG files, found {png_count} + {svg_count}"
        )
    return {
        "files_verified": len(seen),
        "payload_bytes_verified": total_bytes,
        "png_files": png_count,
        "svg_files": svg_count,
        "crc": "PASS",
        "sha256": "PASS",
    }


def package(output_path: Path) -> dict[str, Any]:
    trial_counts = verify_study_manifests()
    files = collect_files()
    if any(path.resolve() == output_path.resolve() for path in files):
        raise ValueError("Refusing to include the output ZIP in itself")
    print(f"packaging {len(files)} project files; trial counts {trial_counts}", flush=True)
    rows = []
    with zipfile.ZipFile(
        output_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True
    ) as archive:
        for index, path in enumerate(files, start=1):
            rows.append(_hash_and_write(path, archive))
            if index % 2_000 == 0:
                bytes_done = sum(row["size_bytes"] for row in rows)
                print(f"packed {index}/{len(files)} files ({bytes_done:,} bytes)", flush=True)
        manifest = {
            "schema_version": "scientific-exp03b-full-audit-v1",
            "archive": "HF_TCM_SIM_SCIENTIFIC_EXP_03B_FULL_AUDIT.zip",
            "protocol_sha256": PROTOCOL_SHA,
            "confirmatory_trials": trial_counts,
            "raw_confirmatory_data_included": True,
            "manifest_self_hash_excluded": True,
            "files": rows,
        }
        archive.writestr(
            "AUDIT_MANIFEST.json",
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
            + b"\n",
            compress_type=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        )
    verification = _verify_archive(output_path, manifest)
    return {
        "archive_path": str(output_path),
        "archive_bytes": output_path.stat().st_size,
        "files_count_excluding_manifest": len(rows),
        "manifest_bytes": len(json.dumps(manifest, ensure_ascii=False)),
        "trial_counts": trial_counts,
        "verification": verification,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    result = package(output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"AUDIT PACKAGE FAILED: {exc}", file=sys.stderr)
        raise
