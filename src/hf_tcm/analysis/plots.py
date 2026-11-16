"""Small dependency-free SVG plots for the first M2 BER curves."""

import html
import math
from collections.abc import Sequence
from pathlib import Path


def _validated_curve(
    ebn0_db: Sequence[float], bit_errors: Sequence[int], bits_checked: Sequence[int]
) -> tuple[list[float], list[int], list[int]]:
    xs = [float(value) for value in ebn0_db]
    errors = list(bit_errors)
    totals = list(bits_checked)
    if not xs or not (len(xs) == len(errors) == len(totals)):
        raise ValueError("Eb/N0 values and raw BER counts must have equal nonzero lengths")
    if any(not math.isfinite(value) for value in xs):
        raise ValueError("Eb/N0 values must be finite")
    if any(
        type(total) is not int or type(error) is not int or total <= 0 or not 0 <= error <= total
        for error, total in zip(errors, totals, strict=True)
    ):
        raise ValueError("BER counts must satisfy integer 0 <= errors <= positive total")
    return xs, errors, totals


def save_ber_svg(
    path: str | Path,
    ebn0_db: Sequence[float],
    bit_errors: Sequence[int],
    bits_checked: Sequence[int],
    *,
    title: str = "BER over AWGN",
) -> Path:
    """Write a log-y BER SVG; zero-error points are marked at the axis floor.

    The SVG labels each zero-error point as ``0/N`` and notes that its marker
    is displayed at the floor only for visibility, not as a nonzero BER value.
    """
    xs, errors, totals = _validated_curve(ebn0_db, bit_errors, bits_checked)
    rates = [error / total for error, total in zip(errors, totals, strict=True)]
    positives = [rate for rate in rates if rate > 0.0]
    smallest = min(positives) if positives else 1.0 / max(totals)
    y_floor = 10.0 ** max(-15, math.floor(math.log10(smallest)) - 1)
    width, height = 800, 500
    left, right, top, bottom = 92, 28, 56, 76
    plot_width, plot_height = width - left - right, height - top - bottom
    min_x, max_x = min(xs), max(xs)
    if min_x == max_x:
        min_x -= 0.5
        max_x += 0.5
    min_log, max_log = math.log10(y_floor), 0.0

    def x_position(value: float) -> float:
        return left + (value - min_x) / (max_x - min_x) * plot_width

    def y_position(rate: float) -> float:
        plotted = max(rate, y_floor)
        return top + (max_log - math.log10(plotted)) / (max_log - min_log) * plot_height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2:g}" y="30" text-anchor="middle" font-size="20">'
        f"{html.escape(title)}</text>",
    ]
    decade = math.floor(min_log)
    while 10.0**decade <= 1.0:
        rate = 10.0**decade
        if rate >= y_floor:
            y = y_position(rate)
            parts.extend(
                [
                    f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" '
                    f'y2="{y:.2f}" stroke="#dddddd"/>',
                    f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" '
                    f'font-size="12">{rate:g}</text>',
                ]
            )
        decade += 1
    parts.extend(
        [
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" stroke="#222222"/>',
            f'<line x1="{left}" y1="{height - bottom}" x2="{width - right}" '
            f'y2="{height - bottom}" stroke="#222222"/>',
            f'<text x="{left + plot_width / 2:g}" y="{height - 22}" text-anchor="middle" '
            'font-size="14">Eb/N0 (dB)</text>',
            f'<text x="22" y="{top + plot_height / 2:g}" text-anchor="middle" '
            'font-size="14" transform="rotate(-90 22 '
            f'{top + plot_height / 2:g})">BER</text>',
        ]
    )
    points = [(x_position(x), y_position(rate)) for x, rate in zip(xs, rates, strict=True)]
    polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    parts.append(f'<polyline points="{polyline}" fill="none" stroke="#1769aa" stroke-width="2"/>')
    for index, ((x, y), error, total) in enumerate(zip(points, errors, totals, strict=True)):
        if error == 0:
            parts.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="white" '
                f'stroke="#d1495b" stroke-width="2"><title>0/{total} errors</title></circle>'
            )
            parts.append(f'<text x="{x + 7:.2f}" y="{y - 7:.2f}" font-size="11">0/{total}</text>')
        else:
            parts.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#1769aa">'
                f"<title>{error}/{total} errors; point {index + 1}</title></circle>"
            )
    parts.append(
        f'<text x="{left}" y="{height - 48}" font-size="11" fill="#555555">'
        "Open markers show 0/N, plotted at the axis floor for visibility.</text>"
    )
    parts.append("</svg>")
    target = Path(path)
    target.write_text("\n".join(parts), encoding="utf-8")
    return target
