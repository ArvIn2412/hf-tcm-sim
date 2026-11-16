"""Package and verify the SCIENTIFIC-EXP-02 independent-audit archive."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "HF_TCM_SIM_SCIENTIFIC_EXP_02_AUDIT.zip"
OUTPUT_ROOT = ROOT / "outputs" / "scientific_exp_02"

README = """# HF-TCM-SIM — SCIENTIFIC-EXP-02 audit bundle

Цей архів містить матеріали для незалежної перевірки аудиту початкової оцінки
каналу, exploratory prior sensitivity, дисертаційних числових результатів
SCIENTIFIC-EXP-01B та відкриття перевіреної статичної серії у GUI.

## Що перевіряти спочатку

1. `docs/research/SCIENTIFIC_EXP_02_FINAL_REPORT.md` — підсумок і межі висновків.
2. `docs/research/SCIENTIFIC_EXP_02_PRIOR_SENSITIVITY.md` та
   `configs/SCIENTIFIC_EXP_02_PRIOR_SENSITIVITY.json` — frozen exploratory design.
3. `outputs/scientific_exp_02/prior_sensitivity/independent_verification.json`
   та `outputs/scientific_exp_02/prior_sensitivity/analysis.json` — незалежний
   recount із 48 однакових observations × 6 prior variants.
4. `docs/research/SCIENTIFIC_EXP_02_THESIS_RESULTS.md` і
   `outputs/scientific_exp_02/thesis_tables/` — таблиці/джерела графіків.
5. `outputs/scientific_exp_02/gui_acceptance.json` — реальна Edge-перевірка
   відкриття EXP-01B, plots і gain/CI без повторного запуску кадрів.

## Методичні межі

- EXP-02 чутливість є розвідувальною: 8 раніше записаних кадрів на точку,
  не confirmatory і не новий energy-gain estimate.
- Не змінено 2160 кадрів EXP-01B; джерельне дерево пройшло до/після SHA audit.
- У статичних EXP-01B записах Joint prior mean збігається з номінальними
  відкритими taps. Joint/B0 та Joint/B1 тому не ізолюють ефект метрики.
- Виграші 5,779989 та 2,456063 дБ є модельними відношеннями дискретної
  `E_b,d`, не фізичним Eb/N0. Статейні 1,5 дБ не підтверджені;
  `paper_exact:false`.
- Повні 2160 NPZ кадри не дублюються в архіві. Вкладено повний study manifest,
  агреговані джерельні дані та 48 paired source frames, потрібні для відтворення
  prior sensitivity; решта вихідних даних лишаються в оригінальному репозиторії.

## Структура

- `src/hf_tcm/repro/` — новий prior adapter та релевантні transmitter/channel/
  receiver/metric/statistics алгоритми для огляду.
- `src/hf_tcm/studio/` — provenance-перевірений read-only loader і GUI route.
- `scripts/` та `tests/repro/test_scientific_exp_02.py` — запуск, незалежна
  перевірка, plotting, Edge QA та тести.
- `outputs/scientific_exp_02/` — frozen protocol, selected source frames,
  288 decode records, числові таблиці, PNG/SVG та manifests.
- `docs/screenshots/` — актуальні Edge screenshots.
- `AUDIT_MANIFEST.json` — відносні шляхи, розміри й SHA-256 усіх файлів архіву,
  окрім самого manifest (самохешування було б циклічним). Перевірте також
  SHA-256 зовнішнього ZIP із фінальної відповіді.
"""


EXPLICIT_FILES = [
    "pyproject.toml",
    "configs/SCIENTIFIC_EXP_01B_PROTOCOL.json",
    "configs/SCIENTIFIC_EXP_02_PRIOR_SENSITIVITY.json",
    "docs/BUILD_VERIFICATION.md",
    "docs/repro/REPRO_09_GUI_USER_GUIDE.md",
    "docs/research/SCIENTIFIC_EXP_01B_FINAL_REPORT.md",
    "docs/research/SCIENTIFIC_EXP_02_FINAL_REPORT.md",
    "docs/research/SCIENTIFIC_EXP_02_PRIOR_SENSITIVITY.md",
    "docs/research/SCIENTIFIC_EXP_02_THESIS_RESULTS.md",
    "docs/screenshots/scientific-exp02-exp01b-energy-overview-1366x768.png",
    "docs/screenshots/scientific-exp02-exp01b-energy-results-1366x768.png",
    "docs/screenshots/scientific-exp02-exp01b-energy-results-1920x1080.png",
    "docs/screenshots/scientific-exp02-exp01b-energy-fullpage.png",
    "outputs/scientific_exp_01b/study_manifest.json",
    "outputs/scientific_exp_01b/analysis/analysis_results.json",
    "outputs/scientific_exp_01b/analysis/static_aggregates.csv",
    "outputs/scientific_exp_01b/analysis/rician_aggregates.csv",
    "outputs/scientific_exp_01b/verification/historical_fingerprints.log",
    "outputs/scientific_exp_02/gui_acceptance.json",
    "outputs/scientific_exp_02/prior_sensitivity/independent_verification.json",
    "outputs/scientific_exp_02/prior_sensitivity/source_immutability.json",
    "outputs/scientific_exp_02/verification/verification_summary.json",
    "src/hf_tcm/repro/exp02_prior_sensitivity.py",
    "src/hf_tcm/studio/historical_energy.py",
    "src/hf_tcm/studio/server.py",
    "src/hf_tcm/studio/static/scientific.js",
    "scripts/run_scientific_exp02_prior_sensitivity.py",
    "scripts/verify_scientific_exp02.py",
    "scripts/report_scientific_exp02.py",
    "scripts/qa_gui_exp02_historical_open.js",
    "scripts/package_scientific_exp02_audit.py",
    "tests/repro/test_scientific_exp_02.py",
    "outputs/scientific_exp_01b/analysis/plots/static_ber.png",
    "outputs/scientific_exp_01b/analysis/plots/static_ber.svg",
    "outputs/scientific_exp_01b/analysis/plots/static_ser.png",
    "outputs/scientific_exp_01b/analysis/plots/static_ser.svg",
    "outputs/scientific_exp_01b/analysis/plots/static_energy_gain.png",
    "outputs/scientific_exp_01b/analysis/plots/static_energy_gain.svg",
    "outputs/scientific_exp_01b/analysis/plots/rician_ber.png",
    "outputs/scientific_exp_01b/analysis/plots/rician_ber.svg",
    "outputs/scientific_exp_01b/analysis/plots/rician_ser.png",
    "outputs/scientific_exp_01b/analysis/plots/rician_ser.svg",
]

CODE_FILES = [
    "src/hf_tcm/repro/encoder.py",
    "src/hf_tcm/repro/labeling.py",
    "src/hf_tcm/repro/modulator.py",
    "src/hf_tcm/repro/transmitter.py",
    "src/hf_tcm/repro/waveform.py",
    "src/hf_tcm/repro/multipath_channel.py",
    "src/hf_tcm/repro/noise.py",
    "src/hf_tcm/repro/rician_fading.py",
    "src/hf_tcm/repro/channel_config.py",
    "src/hf_tcm/repro/channel_result.py",
    "src/hf_tcm/repro/channel_runner.py",
    "src/hf_tcm/repro/receiver_config.py",
    "src/hf_tcm/repro/separate_receiver.py",
    "src/hf_tcm/repro/repro08_channel_aware_hard.py",
    "src/hf_tcm/repro/joint_receiver.py",
    "src/hf_tcm/repro/multipath_joint_receiver.py",
    "src/hf_tcm/repro/joint_receiver_config.py",
    "src/hf_tcm/repro/survivor_channel_estimator.py",
    "src/hf_tcm/repro/euclidean_metric.py",
    "src/hf_tcm/repro/hamming_metric.py",
    "src/hf_tcm/repro/hamming_viterbi.py",
    "src/hf_tcm/repro/finite_viterbi.py",
    "src/hf_tcm/repro/joint_viterbi.py",
    "src/hf_tcm/repro/energy_experiment.py",
    "src/hf_tcm/repro/energy_gain.py",
    "src/hf_tcm/repro/energy_statistics.py",
    "src/hf_tcm/repro/information_pair_metrics.py",
    "src/hf_tcm/repro/paired_experiment.py",
    "src/hf_tcm/repro/serialization.py",
    "src/hf_tcm/repro/channel_serialization.py",
    "src/hf_tcm/repro/multipath_receiver_io.py",
    "src/hf_tcm/repro/receiver_evaluation.py",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_files() -> dict[str, Path]:
    paths = set(EXPLICIT_FILES + CODE_FILES)
    paths.update(
        path.relative_to(ROOT).as_posix()
        for path in OUTPUT_ROOT.rglob("*")
        if path.is_file() and path.name != "archive_verification.json"
    )
    files: dict[str, Path] = {}
    for relative in sorted(paths):
        path = ROOT / Path(relative)
        if not path.is_file():
            raise FileNotFoundError(path)
        if any(
            part in {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
            for part in Path(relative).parts
        ):
            raise ValueError(f"Excluded path in bundle selection: {relative}")
        files[Path(relative).as_posix()] = path
    return files


def verify_image(name: str, data: bytes) -> None:
    if name.lower().endswith(".png"):
        from io import BytesIO

        image = Image.open(BytesIO(data)).convert("RGB")
        colors = image.getcolors(maxcolors=2_000_000)
        if not colors or len(colors) < 8:
            raise ValueError(f"PNG lacks nontrivial visible content: {name}")
    elif name.lower().endswith(".svg"):
        ElementTree.fromstring(data)


def build() -> dict[str, object]:
    files = collect_files()
    manifest_entries = []
    for relative, path in files.items():
        manifest_entries.append(
            {"path": relative, "size_bytes": path.stat().st_size, "sha256": sha256(path)}
        )
    readme_bytes = README.encode("utf-8")
    readme_entry = {
        "path": "README_FOR_CHATGPT.md",
        "size_bytes": len(readme_bytes),
        "sha256": hashlib.sha256(readme_bytes).hexdigest(),
    }
    entries = [readme_entry, *manifest_entries]
    manifest_bytes = (
        json.dumps(
            {
                "schema": "scientific-exp02-audit-manifest-v1",
                "files_count": len(entries),
                "files": entries,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")

    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        archive.writestr("README_FOR_CHATGPT.md", readme_bytes)
        for relative, path in files.items():
            archive.write(path, relative)
        archive.writestr("AUDIT_MANIFEST.json", manifest_bytes)

    with zipfile.ZipFile(ARCHIVE, "r") as archive:
        bad_entry = archive.testzip()
        if bad_entry:
            raise ValueError(f"ZIP CRC failed for {bad_entry}")
        manifest = json.loads(archive.read("AUDIT_MANIFEST.json"))
        for item in manifest["files"]:
            content = archive.read(item["path"])
            if (
                len(content) != item["size_bytes"]
                or hashlib.sha256(content).hexdigest() != item["sha256"]
            ):
                raise ValueError(f"ZIP content/hash mismatch: {item['path']}")
            verify_image(item["path"], content)
        if len(archive.namelist()) != len(manifest["files"]) + 1:
            raise ValueError("ZIP contains unmanifested entries or duplicates")

    archive_sha = sha256(ARCHIVE)
    result = {
        "status": "PASS",
        "archive": ARCHIVE.name,
        "archive_size_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": archive_sha,
        "files_count": len(entries),
        "zip_entries_validated": len(entries) + 1,
        "manifest_entries_validated": len(entries),
        "png_svg_content_validation": "PASS",
    }
    verification_path = OUTPUT_ROOT / "archive_verification.json"
    verification_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
