"""Read-only comparison plot for actual full-frame and finite-depth Viterbi results."""

from __future__ import annotations

import html
from pathlib import Path

import numpy as np

from hf_tcm.repro.finite_viterbi import ViterbiResult


def write_viterbi_comparison_plot(
    full_frame: ViterbiResult,
    finite_depth: ViterbiResult,
    branch_metric_rows: object,
    *,
    metric_profile: str,
    output_path: str | Path,
) -> Path:
    if not isinstance(full_frame, ViterbiResult) or not isinstance(finite_depth, ViterbiResult):
        raise TypeError("comparison plot requires two ViterbiResult values")
    if full_frame.decoder_mode != "full_frame" or finite_depth.decoder_mode != "finite_depth":
        raise ValueError("comparison requires full_frame and finite_depth results in that order")
    if full_frame.information_pairs.shape != finite_depth.information_pairs.shape:
        raise ValueError("results must contain the same number of decoded symbols")
    count = len(full_frame.information_pairs)
    if count < 1:
        raise ValueError("cannot plot an empty decoded frame")
    metrics = np.asarray(branch_metric_rows)
    if metrics.shape != (count, 16) or not np.all(np.isfinite(metrics)):
        raise ValueError("branch_metric_rows must be finite with shape (F,16)")
    if not metric_profile:
        raise ValueError("metric_profile must identify the plotted branch cost")
    full_bits = full_frame.information_pairs.reshape(-1)
    finite_bits = finite_depth.information_pairs.reshape(-1)
    mismatch = np.flatnonzero(full_bits != finite_bits)
    records = finite_depth.decisions
    latency = np.asarray(
        [row.decision_available_at - row.symbol_index for row in records], dtype=np.int64
    )
    width, height = 1200, 980
    left, right = 100.0, 1140.0
    plot_width = right - left
    top = 100.0
    panel_height = 225.0
    row_gap = 35.0

    def x(index: int) -> float:
        return left + (index + 0.5) * plot_width / (2 * count)

    bits_markup = []
    for index, (full_bit, finite_bit) in enumerate(zip(full_bits, finite_bits, strict=True)):
        color = "#b91c1c" if full_bit != finite_bit else "#0f766e"
        bits_markup.append(
            f"<line x1='{x(index):.2f}' y1='{top + (1 - int(full_bit)) * 75:.2f}' "
            f"x2='{x(index):.2f}' y2='{top + 105 + (1 - int(finite_bit)) * 75:.2f}' "
            f"stroke='{color}' stroke-width='3'><title>Біт {index}: full={int(full_bit)}, "
            f"finite={int(finite_bit)}</title></line>"
        )
    latency_top = top + 2 * panel_height + 2 * row_gap
    max_latency = max(1, int(np.max(latency)))
    latency_lines = []
    for symbol, value in enumerate(latency):
        xx = left + (symbol + 0.5) * plot_width / count
        yy = latency_top + panel_height - int(value) * (panel_height - 35) / max_latency
        latency_lines.append(
            f"<circle cx='{xx:.2f}' cy='{yy:.2f}' r='4' fill='#1d4ed8'>"
            f"<title>Символ {symbol}; затримка {int(value)} символів; "
            f"доступно при індексі {records[symbol].decision_available_at}</title></circle>"
        )
    metric_top = latency_top + panel_height + row_gap
    minimum_metrics = np.min(metrics, axis=1).astype(np.float64)
    metric_points = " ".join(
        f"{left + (index + 0.5) * plot_width / count:.2f},"
        f"{metric_top + panel_height - value * (panel_height - 45) / max(1.0, float(np.max(minimum_metrics))):.2f}"
        for index, value in enumerate(minimum_metrics)
    )
    mismatch_text = (
        ", ".join(str(int(index)) for index in mismatch[:80]) if len(mismatch) else "немає"
    )
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' role='img'>"
        "<rect width='100%' height='100%' fill='white'/>"
        "<text x='600' y='42' text-anchor='middle' font-size='28'>"
        "Повнокадрове та обмежене декодування Вітербі</text>"
        f"<text x='600' y='73' text-anchor='middle' font-size='17'>"
        f"{count} символів; η={finite_depth.traceback_depth} переходів; "
        f"позиції відмінних бітів: {html.escape(mismatch_text)}</text>"
        f"<rect x='{left}' y='{top}' width='{plot_width}' height='{panel_height}' "
        "fill='#f8fafc' stroke='#334155'/><text x='600' y='122' text-anchor='middle' "
        "font-size='20'>Інформаційні біти: повний кадр (верх) / finite-depth (низ)</text>"
        + "".join(bits_markup)
        + f"<line x1='{left}' y1='{top + panel_height + row_gap}' x2='{right}' "
        f"y2='{top + panel_height + row_gap}' stroke='#334155'/>"
        + f"<text x='600' y='{top + panel_height + row_gap + 24}' text-anchor='middle' "
        "font-size='15'>Абсолютний індекс інформаційного біта</text>"
        + f"<rect x='{left}' y='{latency_top}' width='{plot_width}' height='{panel_height}' "
        "fill='#f8fafc' stroke='#334155'/><text x='600' y='" + f"{latency_top + 25}" + "' "
        "text-anchor='middle' font-size='20'>Реальна затримка рішення по символу</text>"
        + "".join(latency_lines)
        + f"<text x='600' y='{height - 15}' text-anchor='middle' font-size='17'>"
        "Індекс TCM-символу (sample time units не застосовуються)</text>"
        + f"<text x='28' y='{latency_top + panel_height / 2}' transform='rotate(-90 28 "
        f"{latency_top + panel_height / 2})' text-anchor='middle' font-size='17'>Затримка, символи</text>"
        + f"<rect x='{left}' y='{metric_top}' width='{plot_width}' height='{panel_height}' "
        "fill='#f8fafc' stroke='#334155'/><text x='600' y='"
        + f"{metric_top + 25}"
        + "' text-anchor='middle' font-size='20'>"
        + f"Мінімальна branch metric на символ; profile: {html.escape(metric_profile)}</text>"
        + f"<polyline points='{metric_points}' fill='none' stroke='#7c3aed' stroke-width='2.5'/>"
        + f"<text x='28' y='{metric_top + panel_height / 2}' transform='rotate(-90 28 "
        + f"{metric_top + panel_height / 2})' text-anchor='middle' font-size='17'>Мінімальна метрика</text>"
        "</svg>"
    )
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(svg, encoding="utf-8")
    return target
