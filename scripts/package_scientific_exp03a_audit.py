"""Build and independently verify the SCIENTIFIC-EXP-03A audit bundle."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "HF_TCM_SIM_SCIENTIFIC_EXP_03A_PREPARATION_AUDIT.zip"
STUDY_IDS = (
    "exp03a-pilot-awgn-direct-v1",
    "exp03a-pilot-awgn-pilot-v1",
    "exp03a-pilot-static-d3-v1",
    "exp03a-pilot-rician-ar1-v1",
    "exp03a-range2-awgn-direct-v1",
    "exp03a-range2-awgn-pilot-v1",
    "exp03a-range2-static-d3-v1",
    "exp03a-range2-rician-ar1-v1",
    "exp03a-range2-rician-pilot8-v1",
    "exp03a-edge-static-1794431241066",
)
EXPLICIT_FILES = (
    "AGENTS.md",
    "README.md",
    "pyproject.toml",
    "PLAN.md",
    "NEXT_TASK.md",
    "docs/BUILD_VERIFICATION.md",
    "docs/research/SCIENTIFIC_EXP_03A_FINAL_REPORT.md",
    "docs/research/SCIENTIFIC_EXP_03A_METRIC_ISOLATION.md",
    "docs/research/SCIENTIFIC_EXP_03A_CHANNEL_ESTIMATION.md",
    "docs/research/SCIENTIFIC_EXP_03A_ENERGY_CONVENTIONS.md",
    "docs/research/SCIENTIFIC_EXP_03B_FROZEN_PROTOCOL.md",
    "docs/research/SCIENTIFIC_EXP_03A_RANGE_FINDING_PLAN.md",
    "docs/research/SCIENTIFIC_EXP_03A_RANGE_EXTENSION_PLAN.md",
    "docs/research/SCIENTIFIC_EXP_02_FINAL_REPORT.md",
    "docs/research/SCIENTIFIC_EXP_02_PRIOR_SENSITIVITY.md",
    "docs/research/SCIENTIFIC_EXP_02_THESIS_RESULTS.md",
    "docs/research/ARTICLE_COMPLIANCE_FINAL_AUDIT.md",
    "docs/research/EXPERIMENT_READINESS_ASSESSMENT.md",
    "docs/repro/REPRO_01_SOURCE_REGISTER.md",
    "docs/repro/REPRO_01_EQUATION_SPEC.md",
    "docs/repro/REPRO_02_FINAL_REPORT.md",
    "docs/repro/REPRO_03_FINAL_REPORT.md",
    "docs/repro/REPRO_06B_FINAL_REPORT.md",
    "docs/repro/REPRO_06C_FINAL_REPORT.md",
    "docs/repro/REPRO_07_FINAL_REPORT.md",
    "docs/repro/REPRO_08_FINAL_REPORT.md",
    "docs/repro/REPRO_08_ARTICLE_CROSSWALK.md",
    "references/README.md",
    "references/SHA256SUMS.txt",
    "references/source_paper_2026.docx",
    "references/Яковів_Гриненко_2026_в7 27-10-26(4).docx",
    "references/alternate_versions/Яковів_Гриненко_2026_в7 27-10-26(6).docx",
    "references/Раздел_4.doc",
    "scripts/run_scientific_exp03a_range_pilot.py",
    "scripts/run_scientific_exp03a_range_extension.py",
    "scripts/benchmark_metric_isolation_runtime.py",
    "scripts/validate_scientific_exp03a_pilot.py",
    "scripts/validate_scientific_exp03a_exports.py",
    "scripts/qa_scientific_exp03a_metric_gui.js",
    "scripts/package_scientific_exp03a_audit.py",
    "tests/repro/test_metric_isolation.py",
    "tests/repro/test_transmitter.py",
    "tests/repro/test_channel.py",
    "tests/repro/test_finite_viterbi.py",
    "tests/repro/test_energy_statistics.py",
    "tests/repro/test_isi_metrics.py",
    "scripts/verify_repro06b_artifacts.py",
    "scripts/verify_scientific_exp02.py",
    "outputs/scientific-exp03a/validation/edge_gui_qa.json",
    "outputs/scientific-exp03a/validation/export_validation.json",
    "outputs/scientific-exp03a/validation/independent_pilot_recount.json",
    "outputs/scientific-exp03a/validation/runtime_benchmark.json",
    "outputs/scientific-exp03a/validation/verification.json",
    "outputs/scientific-exp03a/validation/full_pytest.log",
    "outputs/scientific-exp03a/validation/targeted_pytest.log",
    "outputs/scientific-exp03a/validation/scoped_ruff.log",
    "outputs/scientific-exp03a/validation/scoped_ruff_format.log",
    "outputs/scientific-exp03a/validation/root_ruff.log",
    "outputs/scientific-exp03a/validation/root_ruff_format.log",
    "outputs/scientific-exp03a/validation/node_syntax.log",
    "outputs/scientific-exp03a/validation/historical_verifier.log",
    "outputs/scientific-exp03a/validation/exp02_integrity.log",
    "outputs/scientific-exp03a/validation/pilot_recount.log",
    "outputs/scientific-exp03a/validation/export_validation.log",
    "outputs/scientific-exp03a/validation/edge_gui_qa.log",
    "outputs/scientific-exp03a/validation/pytest_retry_note.md",
    "outputs/scientific-exp03a/gui_exports/edge-1794431240581/exp03a-range2-rician-pilot8-v1-ber.png",
    "outputs/scientific-exp03a/gui_exports/edge-1794431240581/exp03a-range2-rician-pilot8-v1-ber.svg",
    "outputs/scientific-exp03a/gui_exports/edge-1794431240581/exp03a-range2-rician-pilot8-v1-ser.png",
    "outputs/scientific-exp03a/gui_exports/edge-1794431240581/exp03a-range2-rician-pilot8-v1-ser.svg",
    "docs/screenshots/scientific-exp03a-metric-rician-1366x768.png",
    "docs/screenshots/scientific-exp03a-metric-rician-1920x1080.png",
    "src/hf_tcm/channels/rician.py",
    "src/hf_tcm/studio/scientific.py",
    "src/hf_tcm/studio/server.py",
    "src/hf_tcm/studio/energy.py",
    "src/hf_tcm/studio/historical_energy.py",
    "src/hf_tcm/studio/static/scientific.html",
    "src/hf_tcm/studio/static/scientific.css",
    "src/hf_tcm/studio/static/scientific.js",
    "src/hf_tcm/studio/static/scientific_i18n.js",
    "src/hf_tcm/studio/static/scientific_ux.js",
    "src/hf_tcm/studio/static/scientific_metric.js",
)

README = """# README_FOR_CHATGPT — HF-TCM-SIM SCIENTIFIC-EXP-03A

## Мета архіву

Цей пакет містить підготовку контрольованого порівняння евклідової та Хемінгової метрик у TCM/8PSK, фактичні bounded range-finding records, початковий код, тести й відтворювані GUI evidence. Основна confirmatory-серія SCIENTIFIC-EXP-03B **не запускалася**.

## Що зроблено

- Додано окремий A-E/A-H metric-isolation adapter із спільним observation і pilot/equalizer frontend; AWGN direct без equalizer є базовим контролем.
- Oracle CSI відокремлено як діагностику. Joint/B0/B1 лишилися окремим системним порівнянням.
- Збережені 205 paired pilot trials у дев'яти frozen range-finding study namespaces та одна коротка GUI smoke пара.
- Незалежно відновлено observation SHA-256 з received samples, перераховано BER/information-pair SER з decoded arrays і discrete energy.
- Edge перевірив реальний запуск з GUI, завантаження історичної Rician серії, серійні перемикачі й PNG/SVG export.

## Головні обмеження

Clean-tail combiner є exact лише для 8-sample zero-order hold, causal integer delays `D<8`, без fractional delay і clock/pulse mismatch. У Rician AR(1) старіння/noise channel estimate лишає часовий та signal-dependent residual; effective noise не слід вважати iid. Period-32 не перетнув BER=0.05 у виміряному Rician діапазоні; period-8 має 50% overhead і перетину для Hamming теж не має. Це не доказ error floor.

`paper_exact:false` залишається. Дискретна енергетична шкала не підтверджує фізичне Eb/N0. Статейні 1.5 dB не перевірялися як очікуване значення й не підтверджені.

## Перевірити першими

1. `docs/research/SCIENTIFIC_EXP_03A_FINAL_REPORT.md` — фактичний стан і числові результати.
2. `docs/research/SCIENTIFIC_EXP_03A_METRIC_ISOLATION.md` — математичні межі A-E/A-H.
3. `docs/research/SCIENTIFIC_EXP_03A_CHANNEL_ESTIMATION.md` — причинність, tracking та effective noise.
4. `docs/research/SCIENTIFIC_EXP_03B_FROZEN_PROTOCOL.md` — candidate protocol; execution is not authorized.
5. `outputs/scientific-exp03a/validation/independent_pilot_recount.json` — всі nine pilot curve points and counts.
6. `src/hf_tcm/repro/metric_isolation.py`, `metric_experiment.py`, `tests/repro/test_metric_isolation.py`.
7. Edge QA and exported figures under `outputs/scientific-exp03a/validation/`, `gui_exports/`, and `docs/screenshots/`.

## Наукові джерела

Архів включає локальну редакцію статті 2026 (v7 filename), альтернативну редакцію, `Раздел_4.doc`, source register та SHA-256 list. Відмінності різних encoder documents треба перевіряти за crosswalk: не переносити код/параметри допоміжного розділу 4 на основну TCM/8PSK статтю.

## Тестові результати

Фактичні команди та exit statuses у `outputs/scientific-exp03a/validation/verification.json` і logs поруч. Root-wide Ruff check/format не проходять через denied paths, scratch files та format traversal panic; scoped checks покривають зміни цього етапу. Історичний fingerprint verifier і SCIENTIFIC-EXP-02 integrity verifier logs додаються.

Архівний `AUDIT_MANIFEST.json` SHA-256-хешує кожен payload file, крім самого manifest і зовнішнього ZIP. `scripts/package_scientific_exp03a_audit.py` виконує ZIP CRC, hashes, JSON/NPZ parse, PNG opacity/content та SVG XML/path checks.
"""


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def payload_paths() -> list[Path]:
    paths = {ROOT / name for name in EXPLICIT_FILES}
    paths.update((ROOT / "src/hf_tcm/repro").glob("*.py"))
    for study in STUDY_IDS:
        paths.update(
            path
            for path in (ROOT / "outputs/scientific-exp03a/metric-studies" / study).rglob("*")
            if path.is_file()
        )
    return sorted(paths)


def make_entries() -> dict[str, bytes]:
    entries: dict[str, bytes] = {"README_FOR_CHATGPT.md": README.encode("utf-8")}
    missing: list[str] = []
    for path in payload_paths():
        if not path.is_file():
            missing.append(path.relative_to(ROOT).as_posix())
            continue
        entries[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    if missing:
        raise FileNotFoundError("required audit files are missing: " + ", ".join(missing))
    for module in (
        "metric_isolation.py",
        "metric_experiment.py",
        "channel_runner.py",
        "channel_config.py",
        "channel_result.py",
        "encoder.py",
        "transmitter.py",
        "finite_viterbi.py",
        "energy_statistics.py",
    ):
        relative = f"src/hf_tcm/repro/{module}"
        if relative not in entries:
            entries[relative] = (ROOT / relative).read_bytes()
    return dict(sorted(entries.items()))


def verify_entries(entries: dict[str, bytes]) -> dict[str, int]:
    json_count = npz_count = png_count = svg_count = 0
    for name, payload in entries.items():
        if name.endswith(".json"):
            json.loads(payload)
            json_count += 1
        elif name.endswith(".npz"):
            with np.load(io.BytesIO(payload), allow_pickle=False) as arrays:
                if not arrays.files:
                    raise ValueError(f"empty NPZ: {name}")
                for key in arrays.files:
                    if arrays[key].dtype.hasobject:
                        raise ValueError(f"object dtype in NPZ: {name}:{key}")
            npz_count += 1
        elif name.endswith(".png"):
            with Image.open(io.BytesIO(payload)) as image:
                image.verify()
            with Image.open(io.BytesIO(payload)) as image:
                rgba = image.convert("RGBA")
                alpha = rgba.getchannel("A")
                colors = rgba.getcolors(rgba.width * rgba.height) or []
                if alpha.getextrema() != (255, 255) or len(colors) < 20:
                    raise ValueError(f"PNG is transparent or visually empty: {name}")
            png_count += 1
        elif name.endswith(".svg"):
            root = ElementTree.fromstring(payload)
            has_paths = any(node.tag.endswith("path") for node in root.iter())
            if not root.tag.endswith("svg") or not has_paths:
                raise ValueError(f"SVG has no visible path geometry: {name}")
            svg_count += 1
    return {"json": json_count, "npz": npz_count, "png": png_count, "svg": svg_count}


def main() -> None:
    entries = make_entries()
    content_counts = verify_entries(entries)
    manifest = {
        "schema_version": "hf-tcm-sim-scientific-exp03a-audit-manifest-v1",
        "archive": ARCHIVE.name,
        "manifest_excludes_itself": True,
        "files": [
            {"path": name, "size_bytes": len(payload), "sha256": sha256(payload)}
            for name, payload in entries.items()
        ],
        "content_validation": content_counts,
    }
    entries["AUDIT_MANIFEST.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode(
        "utf-8"
    )
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as bundle:
        for name, payload in sorted(entries.items()):
            bundle.writestr(name, payload)

    with zipfile.ZipFile(ARCHIVE, "r") as bundle:
        if bundle.testzip() is not None:
            raise ValueError("ZIP CRC verification failed")
        archived_manifest = json.loads(bundle.read("AUDIT_MANIFEST.json"))
        expected_members = {row["path"] for row in archived_manifest["files"]}
        expected_members.add("AUDIT_MANIFEST.json")
        if set(bundle.namelist()) != expected_members:
            raise ValueError("archive members do not match manifest entries")
        for row in archived_manifest["files"]:
            payload = bundle.read(row["path"])
            if len(payload) != row["size_bytes"] or sha256(payload) != row["sha256"]:
                raise ValueError(f"archive manifest hash mismatch: {row['path']}")
        for study in STUDY_IDS[:9]:
            prefix = f"outputs/scientific-exp03a/metric-studies/{study}/trials/"
            if not any(
                name.startswith(prefix) and name.endswith(".npz") for name in bundle.namelist()
            ):
                raise ValueError(f"pilot arrays missing from archive: {study}")

    archive_bytes = ARCHIVE.read_bytes()
    print(
        json.dumps(
            {
                "status": "PASS",
                "archive": ARCHIVE.name,
                "size_bytes": len(archive_bytes),
                "sha256": sha256(archive_bytes),
                "files_count": len(entries),
                "payload_content_validation": content_counts,
                "zip_crc": "PASS",
                "manifest_hashes": "PASS",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
