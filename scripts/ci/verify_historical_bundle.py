"""Verify external historical fixtures; missing artifacts never pass."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path("outputs/ci/historical-artifacts.sha256")
EXP01 = "HF_TCM_SIM_SCIENTIFIC_EXP_01_ENERGY_AUDIT.zip"
EXP01_METADATA = Path("outputs/scientific_exp_01/archive_verification.json")


class MissingHistoricalArtifact(FileNotFoundError):
    """An audit is blocked, rather than successful or silently skipped."""


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def required(path: Path) -> None:
    if not path.is_file():
        raise MissingHistoricalArtifact(f"BLOCKED_MISSING_ARTIFACT: {path}")


def verify_bundle(root: Path) -> list[Path]:
    root = root.resolve()
    manifest = root / MANIFEST
    required(manifest)
    verified = []
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            expected, relative = line.strip().split(None, 1)
        except ValueError as error:
            raise ValueError(f"invalid SHA manifest line {number}") from error
        relative = relative.lstrip("* ")
        if len(expected) != 64 or any(c not in "0123456789abcdefABCDEF" for c in expected):
            raise ValueError(f"invalid SHA-256 on line {number}")
        path = root / relative
        if (
            not relative.startswith("outputs/")
            or ".." in Path(relative).parts
            or not path.resolve().is_relative_to(root)
        ):
            raise ValueError(f"manifest path must be a safe outputs/ path: {relative}")
        required(path)
        if digest(path).lower() != expected.lower():
            raise ValueError(f"Historical SHA-256 mismatch: {relative}")
        verified.append(path)
    if not verified:
        raise ValueError("historical manifest contains no entries")
    metadata = root / EXP01_METADATA
    required(metadata)
    if metadata not in verified:
        raise ValueError("EXP-01 provenance must be pinned by the reviewed SHA manifest")
    source = json.loads(metadata.read_text(encoding="utf-8"))
    if source.get("archive_path") != EXP01:
        raise ValueError("unexpected EXP-01 archive reference")
    archive = root / EXP01
    required(archive)
    if archive.stat().st_size != source.get("archive_size") or digest(archive) != source.get(
        "sha256"
    ):
        raise ValueError("EXP-01 archive provenance mismatch")
    return [*verified, archive, manifest]


def install_verified(root: Path, paths: list[Path]) -> None:
    """Materialize only verified fixture paths; refuse to replace different bytes."""
    root = root.resolve()
    for source in paths:
        relative = source.relative_to(root)
        target = ROOT / relative
        if not target.resolve().is_relative_to(ROOT):
            raise ValueError("installation target escapes checkout")
        if target.exists():
            if digest(target) != digest(source):
                raise ValueError(f"refusing to replace existing historical bytes: {relative}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--install", action="store_true")
    options = parser.parse_args()
    try:
        paths = verify_bundle(options.root)
        if options.install:
            install_verified(options.root, paths)
    except MissingHistoricalArtifact as error:
        print(str(error))
        print("HISTORICAL AUDIT: BLOCKED; tests were not reported as passed")
        return 2
    except (ValueError, OSError, KeyError) as error:
        print(f"HISTORICAL AUDIT: FAIL: {error}")
        return 1
    print(f"Verified {len(paths)} inputs; manifest trust must be reviewed independently.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
