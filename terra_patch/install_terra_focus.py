#!/usr/bin/env python3
"""Install or remove the optional Terra Focus UI overlay in an HF-TCM-SIM checkout.

Default is inspection only. Use --apply for installation and --undo for reversal.
Scientific Python modules, archives, and experiment results are never touched.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

LINK = '  <link rel="stylesheet" href="/static/terra_focus.css">'
SCRIPT = '  <script src="/static/terra_focus.js" defer></script>'
FILES = ("terra_focus.css", "terra_focus.js")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true", help="Install the optional UX overlay")
    group.add_argument("--undo", action="store_true", help="Remove the overlay references")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="HF-TCM-SIM repository root")
    args = parser.parse_args()
    root = args.root.resolve()
    directory = root / "src" / "hf_tcm" / "studio" / "static"
    html = directory / "scientific.html"
    if not html.is_file():
        parser.error(f"Cannot find {html}; run in HF-TCM-SIM repository root")
    text = html.read_text(encoding="utf-8-sig")
    if args.undo:
        updated = text.replace(LINK + "\n", "").replace(SCRIPT + "\n", "")
        if updated == text:
            print("No Terra Focus references found; nothing changed")
        else:
            html.write_text(updated, encoding="utf-8")
            print("Removed Terra Focus references; additional files were left untouched")
        return 0

    needed = ('data-view="parameters"', 'data-view="transmitter"',
              'data-view="constellation"', 'data-view="viterbi"',
              'data-view="metric"', 'data-view="saved"')
    missing = [marker for marker in needed if marker not in text]
    if missing:
        parser.error("Source HTML is incompatible: " + ", ".join(missing))
    if "</body>" not in text:
        parser.error("Cannot locate </body>")
    source_dir = Path(__file__).resolve().parent
    for name in FILES:
        if not (source_dir / name).is_file():
            parser.error(f"Missing overlay file: {source_dir / name}")
    print("Checked scientific.html; 6 original section links exist")
    print("Changes: append one CSS link and one JS script, copy 2 overlay files")
    print("Unchanged: all existing UI modules, APIs, simulation code and data")
    if not args.apply:
        print("Dry run only. Run again with --apply to install")
        return 0
    backup = html.with_suffix(".html.terra-before")
    if not backup.exists():
        shutil.copy2(html, backup)
    for name in FILES:
        destination = directory / name
        source = source_dir / name
        if destination.resolve() != source.resolve():
            if destination.exists():
                parser.error(f"Refusing to overwrite existing file: {destination}")
            shutil.copy2(source, destination)
    lines = []
    if LINK not in text:
        lines.append(LINK)
    if SCRIPT not in text:
        lines.append(SCRIPT)
    if lines:
        new_text = text.replace("</body>", "\n".join(lines) + "\n</body>", 1)
        html.write_text(new_text, encoding="utf-8")
        print(f"Installed Terra Focus in {html}")
        print(f"HTML backup: {backup}")
    else:
        print("Overlay already installed; nothing to change")
    return 0


if __name__ == "__main__":
    sys.exit(main())
