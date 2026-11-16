from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "copyright"
ARCHIVE = ROOT / "HF_TCM_SIM_COPYRIGHT_DOCS_01_AUDIT.zip"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def add_file(entries: dict[str, bytes], archive_path: str, source: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    entries[archive_path] = source.read_bytes()


def main() -> None:
    source_manifest = json.loads((DOCS / "SOURCE_FILES_INCLUDED.json").read_text("utf-8"))
    screenshot_manifest = json.loads((DOCS / "SCREENSHOTS_USED.json").read_text("utf-8"))
    description_path = Path((DOCS / "DESCRIPTION_DOCX_PATH.txt").read_text("utf-8").strip())
    source_doc_path = Path((DOCS / "SOURCE_CODE_DOCX_PATH.txt").read_text("utf-8").strip())

    entries: dict[str, bytes] = {}
    add_file(entries, description_path.name, description_path)
    add_file(entries, source_doc_path.name, source_doc_path)

    report_files = (
        "COPYRIGHT_DOCS_01_VERIFICATION.md",
        "SOURCE_FILES_INCLUDED.json",
        "INDEPENDENT_SOURCE_VERIFICATION.json",
        "SCREENSHOTS_USED.json",
        "TEMPLATE_STYLE_ANALYSIS.md",
        "build_copyright_docs.py",
        "verify_copyright_docs.py",
    )
    for name in report_files:
        add_file(entries, f"docs/copyright/{name}", DOCS / name)
    add_file(entries, "README_FOR_CHATGPT.md", DOCS / "README_FOR_CHATGPT.md")

    for record in source_manifest["files"]:
        relative = record["path"]
        source = ROOT / relative
        payload = source.read_bytes()
        if sha256(payload) != record["sha256"]:
            raise ValueError(f"Source changed after document verification: {relative}")
        entries[f"source_snapshot/{relative}"] = payload

    for record in screenshot_manifest["screenshots"]:
        relative = record["path"]
        source = ROOT / relative
        payload = source.read_bytes()
        if sha256(payload) != record["sha256"]:
            raise ValueError(f"Screenshot changed after document verification: {relative}")
        entries[f"screenshots/{relative}"] = payload

    for name in ("description_preview.pdf", "source_code_preview.pdf"):
        preview = DOCS / name
        if preview.is_file() and preview.stat().st_size > 0:
            entries[f"previews/{name}"] = preview.read_bytes()

    file_records = [
        {"path": name, "size_bytes": len(payload), "sha256": sha256(payload)}
        for name, payload in sorted(entries.items())
    ]
    manifest = {
        "format": "HF-TCM-SIM copyright docs audit manifest",
        "manifest_scope": "Every archive member except AUDIT_MANIFEST.json itself; self-exclusion avoids a recursive hash.",
        "file_count_excluding_manifest": len(file_records),
        "source_file_count": len(source_manifest["files"]),
        "screenshot_count": len(screenshot_manifest["screenshots"]),
        "files": file_records,
    }
    entries["AUDIT_MANIFEST.json"] = json.dumps(
        manifest, ensure_ascii=False, indent=2
    ).encode("utf-8")

    temporary = ARCHIVE.with_suffix(".zip.tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as archive:
        for name, payload in sorted(entries.items()):
            archive.writestr(name, payload)
    temporary.replace(ARCHIVE)

    with zipfile.ZipFile(ARCHIVE) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"ZIP CRC failure: {bad_member}")
        names = set(archive.namelist())
        if len(names) != len(entries):
            raise ValueError("ZIP has duplicate or missing members")
        stored_manifest = json.loads(archive.read("AUDIT_MANIFEST.json"))
        for record in stored_manifest["files"]:
            payload = archive.read(record["path"])
            if len(payload) != record["size_bytes"] or sha256(payload) != record["sha256"]:
                raise ValueError(f"Archive member hash/size mismatch: {record['path']}")

    print(
        json.dumps(
            {
                "archive": str(ARCHIVE),
                "size_bytes": ARCHIVE.stat().st_size,
                "sha256": sha256(ARCHIVE.read_bytes()),
                "files_count_including_manifest": len(entries),
                "crc": "PASS",
                "manifest_hashes": "PASS",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
