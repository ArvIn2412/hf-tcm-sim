"""Check real Edge exports and screenshots for visible scientific plot content."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path.cwd()
QA_REPORT = ROOT / "outputs/scientific-exp03a/validation/edge_gui_qa.json"
OUTPUT = ROOT / "outputs/scientific-exp03a/validation/export_validation.json"


def validate_png(path: Path, *, min_width: int, min_height: int) -> dict:
    with Image.open(path) as image:
        image.load()
        rgba = image.convert("RGBA")
        if image.format != "PNG" or image.width < min_width or image.height < min_height:
            raise ValueError(f"invalid PNG dimensions or format: {path}")
        alpha = rgba.getchannel("A")
        if alpha.getextrema()[1] == 0:
            raise ValueError(f"fully transparent PNG: {path}")
        colors = rgba.convert("RGB").getcolors(maxcolors=1_000_000)
        color_count = len(colors) if colors is not None else 1_000_001
        if color_count < 32 or rgba.convert("RGB").getbbox() is None:
            raise ValueError(f"PNG contains no nontrivial visible graph: {path}")
        return {
            "path": str(path.relative_to(ROOT)),
            "format": image.format,
            "width": image.width,
            "height": image.height,
            "alpha_range": list(alpha.getextrema()),
            "unique_rgb_colors": color_count,
            "size_bytes": path.stat().st_size,
        }


def validate_svg(path: Path) -> dict:
    tree = ET.parse(path)
    root = tree.getroot()
    namespace = "{http://www.w3.org/2000/svg}"
    if root.tag != f"{namespace}svg":
        raise ValueError(f"not an SVG document: {path}")
    tags = [element.tag.removeprefix(namespace) for element in root.iter()]
    text = " ".join(
        element.text or "" for element in root.iter() if element.tag == f"{namespace}text"
    )
    if tags.count("path") < 5 or tags.count("circle") < 2:
        raise ValueError(f"SVG has no visible curve content: {path}")
    for expected in ("Нормована дискретна", "метрика", "γ"):
        if expected not in text:
            raise ValueError(f"SVG is missing Ukrainian/math labels {expected!r}: {path}")
    return {
        "path": str(path.relative_to(ROOT)),
        "root": "svg",
        "paths": tags.count("path"),
        "circles": tags.count("circle"),
        "visible_labels": text,
        "size_bytes": path.stat().st_size,
    }


def main() -> int:
    qa = json.loads(QA_REPORT.read_text(encoding="utf-8"))
    pngs, svgs = [], []
    for export in qa["exports"]:
        path = ROOT / Path(export["file"])
        if path.suffix.lower() == ".png":
            pngs.append(validate_png(path, min_width=600, min_height=200))
        elif path.suffix.lower() == ".svg":
            svgs.append(validate_svg(path))
    if len(pngs) != 2 or len(svgs) != 2:
        raise ValueError("expected actual BER/SER PNG and SVG downloads")
    screenshots = []
    for row in qa["screenshots"]:
        screenshot = validate_png(
            ROOT / row["file"], min_width=row["width"] - 20, min_height=row["height"]
        )
        screenshot["browser_viewport"] = f"{row['width']}x{row['height']}"
        screenshots.append(screenshot)
    report = {
        "status": "PASS",
        "browser": qa["browser"],
        "exports": {"png": pngs, "svg": svgs},
        "screenshots": screenshots,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
