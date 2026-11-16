"""Assemble and verify the GUI-ENERGY-01B independent audit archive."""

from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "HF_TCM_SIM_GUI_ENERGY_01B_FINAL_AUDIT.zip"
EDGE_REPORT = ROOT / "tmp/gui-energy-01b-edge-qa.json"
EXPORT_REPORT = ROOT / "docs/repro/GUI_ENERGY_01B_EXPORT_VALIDATION.json"
SCREENSHOTS = (
    "docs/screenshots/gui-energy-01b-energy-1366x768.png",
    "docs/screenshots/gui-energy-01b-energy-1920x1080.png",
)
ACCEPTANCE_STUDIES = (
    "outputs/repro09/energy-studies/gui-energy-01b-edge-1794393263854",
    "outputs/repro09/energy-studies/gui-energy-01b-auto-1794393274194",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def add_file(entries: dict[str, bytes], source: Path, archive_name: str) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    if archive_name in entries:
        raise ValueError(f"duplicate archive path: {archive_name}")
    entries[archive_name] = source.read_bytes()


def add_tree(entries: dict[str, bytes], source: Path, archive_prefix: str) -> None:
    files = sorted(path for path in source.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"empty study output: {source}")
    for path in files:
        relative = path.relative_to(source).as_posix()
        add_file(entries, path, f"{archive_prefix}/{relative}")


def make_readme() -> str:
    return """# HF-TCM-SIM GUI-ENERGY-01B audit package

Цей архів містить реалізацію та результати приймання інтегрованої вкладки
енергетичної ефективності Scientific Workspace.

## Перевірити спочатку

1. `docs/repro/GUI_ENERGY_01B_FINAL_REPORT.md` — підсумок і обмеження.
2. `docs/repro/GUI_ENERGY_01B_VERIFICATION.json` — команди й acceptance status.
3. `src/hf_tcm/studio/historical_energy.py` та `tests/repro/test_scientific_energy_workspace.py` — provenance та незалежне повторне обчислення історичного gain/CI.
4. `historical_source/` — повний валідований SCIENTIFIC-EXP-01 audit ZIP, `archive_verification.json`, `analysis_manifest.json` і `gains.json`.
5. `acceptance_outputs/` — нові короткі GUI acceptance серії; вони відокремлені від історичних SCIENTIFIC-EXP-01 вимірювань.
6. `artifacts/energy_exports/` — чотири PNG та чотири SVG з Edge; `artifacts/screenshots/` — два реальні скриншоти.
7. `AUDIT_MANIFEST.json` — розмір і SHA-256 кожного іншого вкладеного файла.

## Історичні числові результати

Ціль BER=0,05, статичний багатопроменевий amplitude sweep, сім точок і 20
парних кадрів на точку (140 записів). Повторно отримано модельний дискретний
виграш Joint/B0 6,7677914708 dB, 95% CI [6,2097559376; 7,5181654053] dB,
та Joint/B1 2,9641483046 dB, 95% CI [2,7155971812; 3,2287690091] dB.
Ці оцінки умовні для збереженої сітки, перетину й trial-cluster bootstrap.

Збережений початковий SCIENTIFIC-EXP-01 ZIP включений як джерело provenance;
його SHA-256 та розмір звірені з `outputs/scientific_exp_01/archive_verification.json`.

## Межі висновків

- Нову велику confirmatory-серію не запускали.
- GUI acceptance runs — окремі короткі тестові дані, не доказ виграшу.
- `E_b,d` і `gamma_b,d` є дискретними проєктними величинами, не автоматично фізичним Eb/N0.
- `paper_exact:false`; виграш статті 1,5 dB не підтверджено цим етапом.
- SVG зберігає справжній canvas-графік як вбудований PNG, тому plot не є векторно редагованим.
- Маніфест не може містити власний SHA-256 без самореференції; контрольна сума всього ZIP наведена окремо у відповіді Codex.
"""


def collect_entries() -> dict[str, bytes]:
    entries: dict[str, bytes] = {}
    reports = (
        "docs/repro/GUI_ENERGY_01B_FINAL_REPORT.md",
        "docs/repro/GUI_ENERGY_01B_VERIFICATION.json",
        "docs/repro/GUI_ENERGY_01B_EXPORT_VALIDATION.json",
        "docs/repro/GUI_ENERGY_01_FINAL_REPORT.md",
        "docs/repro/REPRO_09_GUI_USER_GUIDE.md",
        "PLAN.md",
        "NEXT_TASK.md",
    )
    for relative in reports:
        add_file(entries, ROOT / relative, relative)

    source_files = (
        "src/hf_tcm/studio/energy.py",
        "src/hf_tcm/studio/historical_energy.py",
        "src/hf_tcm/studio/server.py",
        "src/hf_tcm/studio/static/scientific.js",
        "src/hf_tcm/studio/static/scientific.html",
        "src/hf_tcm/studio/static/energy.css",
        "src/hf_tcm/repro/energy_experiment.py",
        "src/hf_tcm/repro/energy_gain.py",
        "src/hf_tcm/repro/energy_statistics.py",
        "tests/repro/test_scientific_energy_workspace.py",
        "scripts/qa_gui_energy_01b.js",
        "scripts/validate_energy_exports.py",
        "scripts/package_gui_energy_01b_audit.py",
    )
    for relative in source_files:
        add_file(entries, ROOT / relative, relative)
    for relative in ("pyproject.toml", "requirements.txt"):
        candidate = ROOT / relative
        if candidate.is_file():
            add_file(entries, candidate, relative)

    edge = json.loads(EDGE_REPORT.read_text(encoding="utf-8"))
    if len(edge.get("checks", [])) != 8 or any(
        check.get("status") != "PASS" for check in edge["checks"]
    ):
        raise ValueError("Edge acceptance report is incomplete or has failing checks")
    add_file(entries, EDGE_REPORT, "verification/gui-energy-01b-edge-qa.json")

    export_validation = json.loads(EXPORT_REPORT.read_text(encoding="utf-8"))
    if export_validation.get("verification") != "PASS":
        raise ValueError("PNG/SVG content validation did not pass")
    export_dir = ROOT / edge["exportDirectory"].replace("\\", "/")
    exported = sorted(
        path
        for path in export_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".png", ".svg"}
    )
    if len(exported) != 8:
        raise ValueError(f"expected four PNG and four SVG exports, got {len(exported)}")
    for path in exported:
        add_file(entries, path, f"artifacts/energy_exports/{path.name}")

    for relative in SCREENSHOTS:
        add_file(entries, ROOT / relative, f"artifacts/screenshots/{Path(relative).name}")

    for relative in (
        "outputs/scientific_exp_01/archive_verification.json",
        "outputs/scientific_exp_01/analysis/analysis_manifest.json",
        "outputs/scientific_exp_01/analysis/gains.json",
    ):
        add_file(entries, ROOT / relative, f"historical_source/{Path(relative).name}")
    verification = json.loads(
        (ROOT / "outputs/scientific_exp_01/archive_verification.json").read_text(encoding="utf-8")
    )
    original_archive = (ROOT / "outputs/scientific_exp_01").parent.parent / verification[
        "archive_path"
    ]
    original_bytes = original_archive.read_bytes()
    if len(original_bytes) != verification.get("archive_size") or sha256_bytes(
        original_bytes
    ) != verification.get("sha256"):
        raise ValueError(
            "the original SCIENTIFIC-EXP-01 source archive failed integrity validation"
        )
    add_file(
        entries,
        original_archive,
        f"historical_source/{original_archive.name}",
    )

    for relative in ACCEPTANCE_STUDIES:
        add_tree(entries, ROOT / relative, f"acceptance_outputs/{Path(relative).name}")

    readme = make_readme().encode("utf-8")
    entries["README_FOR_CHATGPT.md"] = readme
    manifest: dict[str, Any] = {
        "schema": "hf-tcm-sim-gui-energy-01b-audit-v1",
        "files": [
            {
                "path": name,
                "size_bytes": len(data),
                "sha256": sha256_bytes(data),
            }
            for name, data in sorted(entries.items())
        ],
        "manifest_note": "Self-hash is omitted to avoid self-reference; verify archive SHA-256 separately.",
    }
    entries["AUDIT_MANIFEST.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode(
        "utf-8"
    )
    return entries


def verify_archive(entries: dict[str, bytes]) -> dict[str, Any]:
    with zipfile.ZipFile(ARCHIVE, "r") as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise ValueError(f"corrupt archive member: {corrupt}")
        names = set(archive.namelist())
        if names != set(entries):
            raise ValueError("ZIP members differ from the prepared audit file list")
        manifest = json.loads(archive.read("AUDIT_MANIFEST.json").decode("utf-8"))
        for row in manifest["files"]:
            data = archive.read(row["path"])
            if len(data) != row["size_bytes"] or sha256_bytes(data) != row["sha256"]:
                raise ValueError(f"manifest verification failed for {row['path']}")
        pngs = [name for name in names if name.lower().endswith(".png")]
        svgs = [name for name in names if name.lower().endswith(".svg")]
        if len([name for name in pngs if "energy_exports/" in name]) != 4 or len(svgs) != 4:
            raise ValueError("archive must contain all four PNG and four SVG energy plots")
        for name in pngs:
            with Image.open(BytesIO(archive.read(name))) as image:
                image.load()
                if image.width < 300 or image.height < 150:
                    raise ValueError(f"undersized image: {name}")
                if image.convert("RGBA").getchannel("A").getextrema() == (0, 0):
                    raise ValueError(f"fully transparent image: {name}")
        for name in svgs:
            root = ElementTree.fromstring(archive.read(name))
            if not root.tag.endswith("svg"):
                raise ValueError(f"invalid SVG root element: {name}")
            if not any(element.tag.endswith("image") for element in root.iter()):
                raise ValueError(f"SVG is missing its rendered plot: {name}")
        return {
            "files_count": len(names),
            "manifest_entries": len(manifest["files"]),
            "png_count": len(pngs),
            "svg_count": len(svgs),
            "verification": "PASS",
            "archive_size_bytes": ARCHIVE.stat().st_size,
            "archive_sha256": sha256_bytes(ARCHIVE.read_bytes()),
        }


def main() -> None:
    entries = collect_entries()
    with zipfile.ZipFile(
        ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for name, data in sorted(entries.items()):
            compression = zipfile.ZIP_STORED if name.endswith(".zip") else zipfile.ZIP_DEFLATED
            archive.writestr(name, data, compress_type=compression)
    result = verify_archive(entries)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
