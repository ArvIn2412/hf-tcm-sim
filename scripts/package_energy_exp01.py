"""Package the completed energy study with hash and graphical-content validation."""

import hashlib
import io
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from PIL import Image

R = Path.cwd()
AUDIT_OUTPUT = R / "outputs/scientific_exp_01"
payload = {}


def add(p):
    p = Path(p)
    if p.is_file() and not any(
        x in p.parts for x in ["__pycache__", ".git", ".venv", "node_modules", ".pytest_cache"]
    ):
        payload[p.relative_to(R).as_posix()] = p.read_bytes()


for d in ["src/hf_tcm", "tests/repro", "outputs/scientific_exp_01"]:
    for p in (R / d).rglob("*"):
        if (
            p.suffix.lower()
            in {".py", ".json", ".npz", ".md", ".csv", ".png", ".svg", ".log", ".txt"}
            and p.name != "archive_verification.json"
        ):
            add(p)
for p in (R / "docs/research").glob("SCIENTIFIC_EXP_01*.md"):
    add(p)
for p in (R / "scripts").glob("*energy*exp01.py"):
    add(p)
for name in [
    "pyproject.toml",
    "PLAN.md",
    "NEXT_TASK.md",
    "docs/BUILD_VERIFICATION.md",
    "references/Яковів_Гриненко_2026_в7 27-10-26(4).docx",
    "references/alternate_versions/Яковів_Гриненко_2026_в7 27-10-26(6).docx",
    "references/SHA256SUMS.txt",
    "docs/research/ARTICLE_COMPLIANCE_FINAL_AUDIT.md",
    "scripts/diagnose_energy_scaling.py",
    "docs/repro/REPRO_02_ENCODER_VERIFICATION.md",
    "docs/repro/REPRO_03_NOISE_CONVENTIONS.md",
]:
    add(R / name)
for name in [
    "scientific_exp_01_pilot.log",
    "scientific_exp_01_confirmatory.log",
    "scientific_exp_01_long.log",
    "scientific_exp_01_tests.log",
    "scientific_exp_01_format.log",
]:
    if (R / "outputs" / name).exists():
        add(R / "outputs" / name)
for p in (R / "docs/repro").rglob("*.json"):
    add(p)
readme = """# SCIENTIFIC-EXP-01 energy audit\n\nStart with docs/research/SCIENTIFIC_EXP_01_FINAL_REPORT.md and ENERGY_GAIN_RESULTS, STATISTICAL_VALIDATION, ARTICLE_COMPARISON. Protocol, METHOD.md and frozen main plan are in outputs/scientific_exp_01.\n\nThis is an actual bounded study, not article-exact reproduction. Approved squared-complex-residual metric and REPRO03 complex iid Gaussian noise were retained. No encoder/channel/receiver algorithm changed. New energy trial runner sets the same nominal amplitude in all receiver configurations. Static Joint has explicit public nominal priors and adapts; B1 has exact public static taps; Rician priors use public distribution parameters, never hidden coefficients. B0 lacks ISI compensation, so Joint/B0 is a full-system comparison.\n\nPilot90pairs F256, main461/680 pairs F256 stopped at the frozen1000s budget, long2pairs F20000. Pilot and confirmatory seeds and statistics are separate. Main Rician is not completed; its pilot is exploratory. Records, configs, input/decoded bits, actual Tx/Rx/noise/coefficients and SHA manifests are included. Evaluation truth arrays were saved only after decoding and never passed to receivers. Validation contains one early F32 control and eighteen F256 records forming nine posthoc paired-scaling diagnostics; all nineteen are excluded from inferential estimates.\n\nPrimary BER target .01, secondary .05. Eb,d=4A^2; gamma=10log10(Eb,d/sigma_c^2), not calibrated physical Eb/N0. The amplitude sweep fixes sigma=1; the noise sweep fixes A=1. Independent-sweep contrasts and exact same-seed scaling tests are included. Gains use measured-bracket log-BER interpolation, never extrapolation or zero pseudocount. Paired trial-cluster bootstrap recalculates crossings. Conditional quantiles are not unconditional confidence intervals; insufficient valid crossings are explicit. Negative or unavailable gain is not replaced by1.5dB.\n\nNew orchestration bugs found during validation: cached tuple/list representation, and a Windows metadata probe modifying global ctypes signatures. Both were fixed; receiver numerical algorithms and persisted scientific arrays were unchanged. Historical694/694 preserved. Main RAM high-water fields may be unavailable from its earlier-loaded diagnostic probe; long-frame OS peak readings are available. Single timing measurements are not statistical benchmarks.\n\nRecompute: python scripts/audit_energy_exp01.py; python scripts/analyze_energy_exp01.py --replicates 1000; python scripts/report_energy_exp01.py; python scripts/supplement_energy_exp01.py; python scripts/finalize_energy_exp01.py. Existing trials are validated before skip by run_energy_exp01.py; additional resume invocations spend another wall budget and were not automatically used to extend the main series. Final tests/lint/fingerprint logs are in outputs/scientific_exp_01/logs.\n\nAudit every bit/pair/frame error from NPZ, inspect observation hash replay, compare required-energy brackets with measured points, check bootstrap valid fractions and main planned coverage. PNGs and SVGs have actual measured points/CI or explicit no-data annotations; zeros are retained. Manifest hashes all payload files (including this README), except itself. Relative project paths are preserved; no environments/caches/historical large output collections included.\n"""
payload["README_FOR_CHATGPT.md"] = readme.encode("utf8")
manifest = {
    "files": [
        {"path": n, "size_bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        for n, b in sorted(payload.items())
    ]
}
p = R / "HF_TCM_SIM_SCIENTIFIC_EXP_01_ENERGY_AUDIT.zip"
with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for n, b in payload.items():
        z.writestr(n, b)
    z.writestr("AUDIT_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
images = []
with zipfile.ZipFile(p) as z:
    assert z.testzip() is None
    for row in manifest["files"]:
        b = z.read(row["path"])
        assert len(b) == row["size_bytes"] and hashlib.sha256(b).hexdigest() == row["sha256"]
        if row["path"].endswith(".png"):
            im = Image.open(io.BytesIO(b)).convert("RGBA")
            assert im.getchannel("A").getextrema()[0] == 255
            assert len(im.getcolors(im.width * im.height) or []) > 8
            images.append(row["path"])
        if row["path"].endswith(".svg"):
            ET.fromstring(b)
result = {
    "archive_path": p.name,
    "archive_size": p.stat().st_size,
    "files_count": len(payload) + 1,
    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
    "png_count": len(images),
    "verification": "PASS",
}
(AUDIT_OUTPUT / "archive_verification.json").write_text(json.dumps(result, indent=2), "utf8")
print(json.dumps(result, indent=2))
