"""Validate energy plot exports for decoded, non-empty chart content."""

from __future__ import annotations

import argparse
import base64
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from PIL import Image


def validate_png(path: Path) -> dict[str, Any]:
    with Image.open(path) as source:
        source.load()
        image = source.convert("RGBA")
    width, height = image.size
    alpha = image.getchannel("A")
    nontransparent = sum(1 for value in alpha.getdata() if value > 0)
    visible = sum(
        1
        for red, green, blue, opacity in image.getdata()
        if opacity > 0 and min(red, green, blue) < 242
    )
    colors = len(image.convert("RGB").getcolors(maxcolors=width * height) or [])
    if width < 400 or height < 200:
        raise ValueError(f"{path.name}: unexpected dimensions {width}x{height}")
    if nontransparent != width * height or visible < width * height * 0.002 or colors < 12:
        raise ValueError(f"{path.name}: image is transparent or visually empty")
    return {
        "path": str(path),
        "format": "PNG",
        "width": width,
        "height": height,
        "nontransparent_pixels": nontransparent,
        "visible_pixels": visible,
        "distinct_colors": colors,
    }


def validate_svg(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    if not root.tag.endswith("svg"):
        raise ValueError(f"{path.name}: root element is not SVG")
    image = next((element for element in root.iter() if element.tag.endswith("image")), None)
    if image is None:
        raise ValueError(f"{path.name}: embedded rendered graph is missing")
    href = image.attrib.get("href") or image.attrib.get("{http://www.w3.org/1999/xlink}href", "")
    prefix = "data:image/png;base64,"
    if not href.startswith(prefix):
        raise ValueError(f"{path.name}: SVG does not contain the rendered chart PNG")
    embedded = base64.b64decode(href[len(prefix) :], validate=True)
    rendered = validate_png_bytes(path, embedded)
    return {
        "path": str(path),
        "format": "SVG",
        "width": root.attrib.get("width"),
        "height": root.attrib.get("height"),
        "embedded_render": rendered,
    }


def validate_png_bytes(source_path: Path, payload: bytes) -> dict[str, Any]:
    with Image.open(io.BytesIO(payload)) as source:
        source.load()
        image = source.convert("RGBA")
    width, height = image.size
    nontransparent = sum(1 for value in image.getchannel("A").getdata() if value > 0)
    visible = sum(
        1
        for red, green, blue, opacity in image.getdata()
        if opacity > 0 and min(red, green, blue) < 242
    )
    colors = len(image.convert("RGB").getcolors(maxcolors=width * height) or [])
    if width < 400 or height < 200 or nontransparent != width * height:
        raise ValueError(
            f"{source_path.name}: embedded graph has invalid dimensions or transparency"
        )
    if visible < width * height * 0.002 or colors < 12:
        raise ValueError(f"{source_path.name}: embedded graph is visually empty")
    return {
        "width": width,
        "height": height,
        "nontransparent_pixels": nontransparent,
        "visible_pixels": visible,
        "distinct_colors": colors,
    }


def validate_directory(directory: Path) -> dict[str, Any]:
    pngs = sorted(directory.glob("*.png"))
    svgs = sorted(directory.glob("*.svg"))
    if len(pngs) < 4 or len(svgs) < 4:
        raise ValueError("expected PNG and SVG exports for four energy plots")
    return {
        "png_count": len(pngs),
        "svg_count": len(svgs),
        "files": [*(validate_png(path) for path in pngs), *(validate_svg(path) for path in svgs)],
        "verification": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_directory(args.directory)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
