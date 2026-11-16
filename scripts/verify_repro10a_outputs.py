"""Verify REPRO-10A run manifests, paired pilot, images, SVG and screenshots."""

from __future__ import annotations

import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from hf_tcm.repro.paired_experiment import verify_experiment
from hf_tcm.studio.scientific import load_run_summary

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    audit_dir = ROOT / "outputs" / "repro10a" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    verified: list[dict[str, object]] = []

    run_ids = (
        "repro10a-identity-f32",
        "repro10a-static-multipath-f32",
        "repro10a-rician-ar1-f32",
    )
    run_root = ROOT / "outputs" / "repro10a" / "reference_runs"
    for run_id in run_ids:
        run_dir = run_root / run_id
        summary = load_run_summary(run_dir)
        verified.append(
            {
                "kind": "single_run",
                "run_id": run_id,
                "manifest_sha256": sha256(run_dir / "manifest.json"),
                "observation_sha256": summary["receiver_observation_sha256"],
                "paired_observation_verified": summary["paired_observation_verified"],
            }
        )

    qa_path = ROOT / "outputs" / "repro10a" / "acceptance" / "gui_qa_report.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    if not qa.get("passed") or not all(check.get("passed") for check in qa["checks"]):
        raise AssertionError("Edge acceptance report contains a failed check")
    mc_check = next(
        check
        for check in qa["checks"]
        if check["name"].startswith("two-level five-trial paired Monte Carlo")
    )
    experiment_id = mc_check["detail"]["experimentId"]
    source_experiment = ROOT / "outputs" / "repro09" / "monte-carlo" / experiment_id
    verified_trials = verify_experiment(source_experiment)
    copied_experiment = ROOT / "outputs" / "repro10a" / "paired_experiment" / experiment_id
    if not copied_experiment.exists():
        copied_experiment.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_experiment, copied_experiment)
    copied_trials = verify_experiment(copied_experiment)
    if set(verified_trials) != set(copied_trials):
        raise AssertionError("Copied paired experiment file inventory differs")
    mc_summary = json.loads((copied_experiment / "summary.json").read_text(encoding="utf-8"))
    verified.append(
        {
            "kind": "paired_monte_carlo",
            "experiment_id": experiment_id,
            "status": mc_summary["status"],
            "completed_trials": mc_summary["completed_trials"],
            "files_verified": len(copied_trials),
            "manifest_sha256": sha256(copied_experiment / "manifest.json"),
        }
    )

    image_results = []
    for record in qa["exports"]:
        path = ROOT / record["file"]
        if path.suffix.lower() == ".png":
            with Image.open(path) as image:
                rgba = image.convert("RGBA")
                alpha = rgba.getchannel("A")
                opaque = sum(1 for value in alpha.getdata() if value > 250)
                non_white = sum(
                    1
                    for red, green, blue, opacity in rgba.getdata()
                    if opacity > 250 and (red < 245 or green < 245 or blue < 245)
                )
                if image.size != (record["width"], record["height"]):
                    raise AssertionError(f"PNG size changed: {path}")
                if opaque < image.width * image.height * 0.95 or non_white < 100:
                    raise AssertionError(f"PNG is transparent or visually empty: {path}")
                image_results.append(
                    {
                        "path": record["file"],
                        "sha256": sha256(path),
                        "width": image.width,
                        "height": image.height,
                        "opaque_pixels": opaque,
                        "non_white_pixels": non_white,
                    }
                )
        elif path.suffix.lower() == ".svg":
            root = ET.parse(path).getroot()
            count = len(root.findall(".//{http://www.w3.org/2000/svg}path"))
            if count != record["paths"] or count == 0:
                raise AssertionError(f"SVG paths missing: {path}")
            image_results.append(
                {"path": record["file"], "sha256": sha256(path), "svg_paths": count}
            )

    screenshot_results = []
    for relative in qa["screenshots"]:
        path = ROOT / relative
        with Image.open(path) as image:
            if image.size not in {(1366, 768), (1920, 1080)}:
                raise AssertionError(f"Unexpected GUI screenshot size: {path} {image.size}")
            screenshot_results.append(
                {
                    "path": relative,
                    "sha256": sha256(path),
                    "width": image.width,
                    "height": image.height,
                }
            )

    report = {
        "status": "PASS",
        "edge_checks_passed": len(qa["checks"]),
        "verified": verified,
        "exported_images": image_results,
        "screenshots": screenshot_results,
    }
    output = audit_dir / "output_integrity.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
