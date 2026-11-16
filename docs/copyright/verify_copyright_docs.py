from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "copyright"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W, "r": R, "a": A, "wp": WP, "rel": REL}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def para_text(paragraph: ET.Element) -> str:
    return "".join(text.text or "" for text in paragraph.findall(".//w:t", NS))


def main() -> None:
    description_path = Path((OUT / "DESCRIPTION_DOCX_PATH.txt").read_text(encoding="utf-8").strip())
    source_doc_path = Path((OUT / "SOURCE_CODE_DOCX_PATH.txt").read_text(encoding="utf-8").strip())
    source_manifest = json.loads((OUT / "SOURCE_FILES_INCLUDED.json").read_text(encoding="utf-8"))
    screenshot_manifest = json.loads((OUT / "SCREENSHOTS_USED.json").read_text(encoding="utf-8"))

    with zipfile.ZipFile(source_doc_path) as document:
        if document.testzip() is not None:
            raise AssertionError("Source-code DOCX ZIP CRC check failed")
        xml = ET.fromstring(document.read("word/document.xml"))
    body = xml.find("w:body", NS)
    assert body is not None
    paragraphs = [child for child in list(body) if child.tag == f"{{{W}}}p"]
    cursor = 3
    verified_files = []
    for record in source_manifest["files"]:
        path = ROOT / record["path"]
        raw = path.read_bytes()
        if sha256(raw) != record["sha256"]:
            raise AssertionError(f"SHA-256 mismatch for source file {record['path']}")
        source_lines = raw.decode("utf-8").splitlines()
        if len(source_lines) != record["line_count"]:
            raise AssertionError(f"Source line count mismatch for {record['path']}")
        heading = para_text(paragraphs[cursor])
        cursor += 1
        if heading != record["path"]:
            raise AssertionError(f"Wrong printed module heading at {record['path']}: {heading!r}")
        printed = [para_text(paragraph) for paragraph in paragraphs[cursor : cursor + record["line_count"]]]
        cursor += record["line_count"]
        if printed != source_lines:
            mismatch = next((i + 1 for i, (a, b) in enumerate(zip(printed, source_lines)) if a != b), None)
            raise AssertionError(f"Printed source differs at {record['path']}:{mismatch}")
        verified_files.append({"path": record["path"], "lines": len(printed), "sha256": record["sha256"]})
    if cursor != len(paragraphs):
        raise AssertionError(f"Unexpected paragraphs after included source files: {len(paragraphs) - cursor}")

    with zipfile.ZipFile(description_path) as document:
        if document.testzip() is not None:
            raise AssertionError("Description DOCX ZIP CRC check failed")
        desc_xml = ET.fromstring(document.read("word/document.xml"))
        relroot = ET.fromstring(document.read("word/_rels/document.xml.rels"))
        rels = {item.attrib["Id"]: item.attrib["Target"] for item in relroot.findall("rel:Relationship", NS)}
        image_paragraphs = [
            paragraph
            for paragraph in desc_xml.findall(".//w:body/w:p", NS)
            if paragraph.find(".//a:blip", NS) is not None
        ]
        if len(image_paragraphs) != len(screenshot_manifest["screenshots"]) or len(image_paragraphs) != 5:
            raise AssertionError(f"Expected five embedded screenshots, found {len(image_paragraphs)}")
        for paragraph, record in zip(image_paragraphs, screenshot_manifest["screenshots"], strict=True):
            image_element = paragraph.find(".//a:blip", NS)
            assert image_element is not None
            rid = image_element.attrib[f"{{{R}}}embed"]
            target = "word/" + rels[rid].replace("\\", "/").lstrip("/")
            embedded = document.read(target)
            source = (ROOT / record["path"]).read_bytes()
            if sha256(embedded) != record["sha256"] or embedded != source:
                raise AssertionError(f"Embedded screenshot does not match source: {record['path']}")
            with Image.open(io.BytesIO(source)) as image:
                if image.size != (record["width_px"], record["height_px"]):
                    raise AssertionError(f"Screenshot dimensions changed: {record['path']}")
                image.verify()
            extent = paragraph.find(".//wp:extent", NS)
            if extent is None:
                raise AssertionError(f"No drawing extent for {record['path']}")
            ratio_expected = record["width_px"] / record["height_px"]
            ratio_actual = int(extent.attrib["cx"]) / int(extent.attrib["cy"])
            if abs(ratio_actual - ratio_expected) > 0.00001:
                raise AssertionError(f"Screenshot aspect ratio changed: {record['path']}")

    summary = {
        "description_docx": description_path.name,
        "source_code_docx": source_doc_path.name,
        "source_files": len(verified_files),
        "source_lines": sum(item["lines"] for item in verified_files),
        "source_integrity": "PASS",
        "screenshots": 5,
        "screenshot_integrity": "PASS",
        "docx_zip_crc": "PASS",
        "verified_files": verified_files,
    }
    (OUT / "INDEPENDENT_SOURCE_VERIFICATION.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in summary.items() if key != "verified_files"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
