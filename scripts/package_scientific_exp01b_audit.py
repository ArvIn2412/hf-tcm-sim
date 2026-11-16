from __future__ import annotations

import hashlib
import io
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs" / "scientific_exp_01b"
ARCHIVE = ROOT / "HF_TCM_SIM_SCIENTIFIC_EXP_01B_FINAL_AUDIT.zip"

README = """# HF-TCM-SIM SCIENTIFIC-EXP-01B audit package

This archive contains the frozen protocol, all 2,160 completed new confirmatory
trials (JSON records, per-trial manifests, NPZ arrays), independent analysis,
bootstrap outputs, figures, tests, and the source needed to inspect the energy
experiment. SCIENTIFIC-EXP-01 historical pilot records were used only to plan
the grid and check seed disjointness; they were not pooled into estimates and
are not included here.

## Start here

1. `docs/research/SCIENTIFIC_EXP_01B_FINAL_REPORT.md`
2. `docs/research/SCIENTIFIC_EXP_01B_ENERGY_GAIN_RESULTS.md`
3. `docs/research/SCIENTIFIC_EXP_01B_STATISTICAL_VALIDATION.md`
4. `configs/SCIENTIFIC_EXP_01B_PROTOCOL.json`
5. `outputs/scientific_exp_01b/analysis/analysis_results.json`
6. `scripts/analyze_energy_exp01b.py` and `tests/repro/test_scientific_exp_01b_analysis.py`

## Findings

The confirmatory run completed 1,160 static two-path trials and 1,000 Rician
AR(1) trials, with 40 independent frames per energy point. At static target
BER=0.05, the discrete model gain estimates are 5.77999 dB for Joint/B0
(paired 95% bootstrap CI 5.39310 to 6.22655 dB) and 2.45606 dB for Joint/B1
(2.26689 to 2.85265 dB). At BER=0.01, Joint/B0 has no measured crossing;
Joint/B1 has insufficient bootstrap crossing support. Rician B0 does not cross
either target in the measured range, so no gain is extrapolated.

The energy axis is a normalized discrete project scale, not validated physical
Eb/N0. The paper's 1.5 dB result is not confirmed. `paper_exact` remains false.
No mathematical transmitter, channel, or receiver backend was changed in this
experiment stage.

Verification: full pytest reported 1,234 passed; focused experiment tests
reported 11 passed; scoped Ruff check and format passed; the historical verifier
reported 694/694 fingerprints. PNG/SVG content validation passed for 8 PNG and
8 SVG plots. Root-wide Ruff remains non-passing because of ACL warnings and
findings elsewhere in the workspace; the exact logs are included.

## Structure

- `configs/`: immutable confirmatory protocol.
- `scripts/`: runner, independent analyzer, archive packager.
- `src/hf_tcm/`: Python backend source for independent code inspection.
- `tests/`: focused regression and analysis tests.
- `outputs/scientific_exp_01b/confirmatory/`: immutable trial records, NPZ
  arrays, and per-trial manifests.
- `outputs/scientific_exp_01b/analysis/`: aggregate CSV/JSON and PNG/SVG plots.
- `outputs/scientific_exp_01b/verification/`: command logs and image checks.
- `docs/research/`: Ukrainian final reports and thesis figure captions.

`AUDIT_MANIFEST.json` lists each archive payload path, size, and SHA-256. The
manifest does not hash itself. Trial NPZ arrays preserve information bits,
decoded bits, transmitted/received samples, channel/noise arrays, seeds,
receiver observation hashes, and per-arm error/runtime measurements.
"""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_manifest(payload_files: list[dict[str, Any]], readme: bytes) -> dict[str, Any]:
    files = [
        *payload_files,
        {
            "path": "README_FOR_CHATGPT.md",
            "size_bytes": len(readme),
            "sha256": sha256_bytes(readme),
        },
    ]
    return {
        "schema": "scientific-exp01b-audit-manifest-v1",
        "hash_scope": "all archive files except this manifest",
        "file_count": len(files) + 1,
        "payload_file_count": len(files),
        "files": files,
    }


def payload_paths() -> list[Path]:
    paths: set[Path] = {
        ROOT / "configs" / "SCIENTIFIC_EXP_01B_PROTOCOL.json",
        ROOT / "scripts" / "run_energy_exp01b.py",
        ROOT / "scripts" / "analyze_energy_exp01b.py",
        ROOT / "scripts" / "package_scientific_exp01b_audit.py",
        ROOT / "tests" / "repro" / "test_scientific_exp_01b_analysis.py",
        ROOT / "pyproject.toml",
    }
    paths.update((ROOT / "docs" / "research").glob("SCIENTIFIC_EXP_01B_*.md"))
    paths.update((ROOT / "src" / "hf_tcm").rglob("*.py"))
    paths.update((OUTPUTS / "confirmatory").rglob("*"))
    paths.update(path for path in OUTPUTS.iterdir() if path.is_file())
    paths.update((OUTPUTS / "analysis").rglob("*"))
    paths.update((OUTPUTS / "verification").rglob("*"))
    selected = sorted(path for path in paths if path.is_file())
    missing = [str(path.relative_to(ROOT)) for path in selected if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Audit input files missing: {missing}")
    return selected


def verify_payload(name: str, data: bytes) -> None:
    if name.endswith(".json"):
        json.loads(data)
    elif name.endswith(".npz"):
        with np.load(io.BytesIO(data), allow_pickle=False) as arrays:
            if not arrays.files:
                raise ValueError(f"Empty NPZ: {name}")
            if any(arrays[key].dtype.hasobject for key in arrays.files):
                raise ValueError(f"Pickled/object array is not allowed: {name}")
    elif name.endswith(".png"):
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)).convert("RGBA") as image:
            alpha = image.getchannel("A")
            colors = image.convert("RGB").getcolors(maxcolors=1_000_000)
            if alpha.histogram()[255] == 0 or len(colors or []) <= 32:
                raise ValueError(f"PNG is blank or transparent: {name}")
    elif name.endswith(".svg"):
        root = ET.fromstring(data)
        if not root.attrib.get("viewBox"):
            raise ValueError(f"SVG has no viewBox: {name}")
        if len(root.findall(".//{http://www.w3.org/2000/svg}path")) <= 2:
            raise ValueError(f"SVG contains no meaningful vector paths: {name}")


def build_archive() -> dict[str, Any]:
    files = payload_paths()
    manifest_files = []
    for path in files:
        data = path.read_bytes()
        manifest_files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size_bytes": len(data),
                "sha256": sha256_bytes(data),
            }
        )
    readme = README.encode("utf-8")
    manifest = _make_manifest(manifest_files, readme)
    with zipfile.ZipFile(ARCHIVE, "w", allowZip64=True, compresslevel=1) as archive:
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            verify_payload(relative, data)
            compression = zipfile.ZIP_STORED if relative.endswith(".npz") else zipfile.ZIP_DEFLATED
            archive.writestr(relative, data, compress_type=compression)
        archive.writestr("README_FOR_CHATGPT.md", readme, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr(
            "AUDIT_MANIFEST.json",
            json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"),
            compress_type=zipfile.ZIP_DEFLATED,
        )
    verify_archive()
    archive_sha256 = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    return {
        "status": "PASS",
        "archive": str(ARCHIVE.relative_to(ROOT)),
        "archive_size_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": archive_sha256,
        "files_count": manifest["file_count"],
        "payload_file_count": manifest["payload_file_count"],
    }


def verify_archive() -> None:
    with zipfile.ZipFile(ARCHIVE) as archive:
        broken = archive.testzip()
        if broken:
            raise ValueError(f"ZIP CRC validation failed at {broken}")
        manifest = json.loads(archive.read("AUDIT_MANIFEST.json"))
        if manifest["payload_file_count"] != len(manifest["files"]):
            raise ValueError("Manifest file count mismatch")
        if manifest["file_count"] != len(archive.namelist()):
            raise ValueError("Archive entry count mismatch")
        for entry in manifest["files"]:
            data = archive.read(entry["path"])
            if len(data) != entry["size_bytes"]:
                raise ValueError(f"Size mismatch: {entry['path']}")
            if sha256_bytes(data) != entry["sha256"]:
                raise ValueError(f"SHA-256 mismatch: {entry['path']}")
            verify_payload(entry["path"], data)
        if "README_FOR_CHATGPT.md" not in archive.namelist():
            raise ValueError("README_FOR_CHATGPT.md missing")


if __name__ == "__main__":
    print(json.dumps(build_archive(), indent=2))
