"""Read-only SVG plots generated solely from a TransmitterResult."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.transmitter import TransmitterResult

WIDTH = 1120
HEIGHT = 620
MAX_POINTS = 1800
COLORS = ("#075985", "#b91c1c", "#047857")


def _thin(x: NDArray, y: NDArray) -> tuple[NDArray, NDArray]:
    if len(x) <= MAX_POINTS:
        return x, y
    indices = np.linspace(0, len(x) - 1, MAX_POINTS, dtype=np.int64)
    return x[indices], y[indices]


def _svg_chart(
    *,
    title: str,
    x_label: str,
    y_label: str,
    series: list[tuple[str, NDArray, NDArray]],
    highlight: tuple[float, float] | None,
    marker: float | None,
    selected_symbol: int,
    sample_window: tuple[int, int],
    scatter: bool = False,
) -> str:
    left, right, top, bottom = 100.0, 1080.0, 70.0, 520.0
    all_x = np.concatenate([np.asarray(row[1], dtype=np.float64) for row in series])
    all_y = np.concatenate([np.asarray(row[2], dtype=np.float64) for row in series])
    x_min, x_max = float(np.min(all_x)), float(np.max(all_x))
    y_min, y_max = float(np.min(all_y)), float(np.max(all_y))
    if x_min == x_max:
        x_min, x_max = x_min - 0.5, x_max + 0.5
    if y_min == y_max:
        margin = max(abs(y_min) * 0.1, 0.5)
        y_min, y_max = y_min - margin, y_max + margin
    x_pad, y_pad = (x_max - x_min) * 0.03, (y_max - y_min) * 0.08
    x_min, x_max = x_min - x_pad, x_max + x_pad
    y_min, y_max = y_min - y_pad, y_max + y_pad

    def px(value: float) -> float:
        return left + (value - x_min) * (right - left) / (x_max - x_min)

    def py(value: float) -> float:
        return bottom - (value - y_min) * (bottom - top) / (y_max - y_min)

    chunks = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" data-selected-symbol="{selected_symbol}" data-window-samples="{sample_window[0]}:{sample_window[1]}">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{WIDTH / 2}" y="34" text-anchor="middle" font-size="25" font-family="Arial,sans-serif" font-weight="700">{html.escape(title)}</text>',
    ]
    for tick in range(6):
        xv = x_min + (x_max - x_min) * tick / 5
        yv = y_min + (y_max - y_min) * tick / 5
        chunks.append(
            f'<line x1="{px(xv):.2f}" y1="{top}" x2="{px(xv):.2f}" y2="{bottom}" stroke="#e2e8f0"/>'
        )
        chunks.append(
            f'<text x="{px(xv):.2f}" y="{bottom + 24}" text-anchor="middle" font-size="14" fill="#334155">{xv:.0f}</text>'
        )
        chunks.append(
            f'<line x1="{left}" y1="{py(yv):.2f}" x2="{right}" y2="{py(yv):.2f}" stroke="#e2e8f0"/>'
        )
        chunks.append(
            f'<text x="{left - 12}" y="{py(yv) + 5:.2f}" text-anchor="end" font-size="14" fill="#334155">{yv:.3g}</text>'
        )
    if highlight is not None:
        x0, x1 = max(x_min, highlight[0]), min(x_max, highlight[1])
        if x0 <= x1:
            chunks.append(
                f'<rect x="{px(x0):.2f}" y="{top}" width="{max(1.0, px(x1) - px(x0)):.2f}" height="{bottom - top}" fill="#facc15" opacity="0.20"><title>Вибране вікно символів</title></rect>'
            )
    chunks.extend(
        [
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#0f172a" stroke-width="2"/>',
            f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#0f172a" stroke-width="2"/>',
        ]
    )
    for series_index, (name, raw_x, raw_y) in enumerate(series):
        x, y = _thin(np.asarray(raw_x), np.asarray(raw_y))
        color = COLORS[series_index % len(COLORS)]
        if scatter:
            points = "".join(
                f'<circle cx="{px(float(a)):.2f}" cy="{py(float(b)):.2f}" r="5" fill="{color}"><title>{html.escape(name)}: I={float(a):.8g}, Q={float(b):.8g}</title></circle>'
                for a, b in zip(x, y, strict=True)
            )
            chunks.append(points)
        else:
            points = " ".join(
                f"{px(float(a)):.2f},{py(float(b)):.2f}" for a, b in zip(x, y, strict=True)
            )
            chunks.append(
                f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.6"><title>{html.escape(name)}</title></polyline>'
            )
        legend_x = left + 18 + series_index * 190
        chunks.append(
            f'<line x1="{legend_x}" y1="{HEIGHT - 46}" x2="{legend_x + 28}" y2="{HEIGHT - 46}" stroke="{color}" stroke-width="4"/>'
        )
        chunks.append(
            f'<text x="{legend_x + 36}" y="{HEIGHT - 41}" font-size="16" fill="#0f172a">{html.escape(name)}</text>'
        )
    if marker is not None and x_min <= marker <= x_max:
        chunks.append(
            f'<line x1="{px(marker):.2f}" y1="{top}" x2="{px(marker):.2f}" y2="{bottom}" stroke="#7c3aed" stroke-width="2" stroke-dasharray="7,5"><title>Вибраний індекс {marker:g}</title></line>'
        )
    chunks.extend(
        [
            f'<text x="{(left + right) / 2}" y="{HEIGHT - 8}" text-anchor="middle" font-size="19" fill="#0f172a">{html.escape(x_label)}</text>',
            f'<text x="24" y="{(top + bottom) / 2}" text-anchor="middle" transform="rotate(-90 24 {(top + bottom) / 2})" font-size="19" fill="#0f172a">{html.escape(y_label)}</text>',
            f'<text x="{WIDTH - 30}" y="58" text-anchor="end" font-size="13" fill="#475569">Символ {selected_symbol}; вікно samples {sample_window[0]}–{sample_window[1]}</text>',
            "</svg>",
        ]
    )
    return "".join(chunks)


def write_transmitter_plots(
    result: TransmitterResult,
    output_dir: str | Path,
    *,
    selected_symbol: int = 0,
    window_symbols: int = 20,
    window_start_symbol: int | None = None,
) -> dict[str, str]:
    """Write ten real-data SVG charts and a plot index JSON."""
    if not isinstance(result, TransmitterResult):
        raise TypeError("result must be a TransmitterResult")
    if type(selected_symbol) is not int or not 0 <= selected_symbol < len(result.symbols):
        raise ValueError("selected_symbol is outside the encoded symbol sequence")
    if type(window_symbols) is not int or window_symbols < 1:
        raise ValueError("window_symbols must be a positive integer")
    if window_start_symbol is None:
        window_start_symbol = min(
            max(0, selected_symbol - window_symbols // 2),
            max(0, len(result.symbols) - window_symbols),
        )
    if type(window_start_symbol) is not int or not 0 <= window_start_symbol < len(result.symbols):
        raise ValueError("window_start_symbol is outside the encoded symbol sequence")
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    start_symbol = window_start_symbol
    end_symbol = min(start_symbol + window_symbols, len(result.symbols))
    sample_start, sample_end = (
        start_symbol * result.samples_per_symbol,
        end_symbol * result.samples_per_symbol - 1,
    )
    sample_window = sample_start, sample_end

    def series_plot(
        filename: str,
        title: str,
        x_label: str,
        y_label: str,
        x: NDArray,
        y: NDArray,
        *,
        points_per_symbol: int,
        marker_symbol: bool = True,
    ) -> tuple[str, str]:
        lo = start_symbol * points_per_symbol
        hi = end_symbol * points_per_symbol - 1
        selection = x[lo : hi + 1]
        highlight = (float(selection[0]), float(selection[-1])) if len(selection) else None
        marker = float(selected_symbol * points_per_symbol) if marker_symbol else None
        content = _svg_chart(
            title=title,
            x_label=x_label,
            y_label=y_label,
            series=[("Передані дані", x, y)],
            highlight=highlight,
            marker=marker,
            selected_symbol=selected_symbol,
            sample_window=sample_window,
        )
        path = directory / filename
        path.write_text(content, encoding="utf-8")
        return filename, str(path)

    frame_symbols = len(result.payload_input_pairs)
    info_x = np.arange(len(result.information_bits), dtype=np.float64)
    code_x = np.arange(result.coded_triples.size, dtype=np.float64)
    symbol_x = np.arange(len(result.symbols), dtype=np.float64)
    state_order = ((0, 0), (1, 0), (0, 1), (1, 1))
    state_ids = np.asarray(
        [
            state_order.index(tuple(int(bit) for bit in state))
            for state in result.state_history[:-1]
        ],
        dtype=np.float64,
    )
    outputs = []
    outputs.append(
        series_plot(
            "01_information_bits.svg",
            "Інформаційні біти передавача",
            "Індекс біта, безрозмірний",
            "Значення біта, {0,1}",
            info_x,
            result.information_bits.astype(np.float64),
            points_per_symbol=2,
        )
    )
    outputs.append(
        series_plot(
            "02_coded_bits.svg",
            "Вихідні кодові біти Encoder A",
            "Індекс кодового біта, безрозмірний",
            "Значення біта, {0,1}",
            code_x,
            result.coded_triples.reshape(-1).astype(np.float64),
            points_per_symbol=3,
        )
    )
    outputs.append(
        series_plot(
            "03_encoder_states.svg",
            "Стан згорткового кодера",
            "Індекс переходу, безрозмірний",
            "ID стану, проєктний порядок",
            symbol_x,
            state_ids,
            points_per_symbol=1,
        )
    )
    outputs.append(
        series_plot(
            "04_trellis_edges.svg",
            "Послідовність переходів TCM",
            "Індекс переходу, безрозмірний",
            "Edge ID, REPRO-02 порядок",
            symbol_x,
            result.edge_ids.astype(np.float64),
            points_per_symbol=1,
        )
    )
    outputs.append(
        series_plot(
            "05_phase_indices.svg",
            "Індекси фаз 8PSK",
            "Індекс символу, безрозмірний",
            "Фазовий індекс b, 0–7",
            symbol_x,
            result.phase_indices.astype(np.float64),
            points_per_symbol=1,
        )
    )
    scatter = _svg_chart(
        title="Передані символи 8PSK до каналу",
        x_label="I, амплітуда комплексної огинаючої",
        y_label="Q, амплітуда комплексної огинаючої",
        series=[("Фактичні символи кадру", result.symbol_i, result.symbol_q)],
        highlight=None,
        marker=None,
        selected_symbol=selected_symbol,
        sample_window=sample_window,
        scatter=True,
    )
    path = directory / "06_8psk_constellation.svg"
    path.write_text(scatter, encoding="utf-8")
    outputs.append((path.name, str(path)))
    outputs.append(
        series_plot(
            "07_symbol_phase.svg",
            "Фаза переданих символів",
            "Індекс символу, безрозмірний",
            "Фаза, rad",
            symbol_x,
            result.phase_values_rad,
            points_per_symbol=1,
        )
    )
    sample_x = result.absolute_sample_index.astype(np.float64)
    outputs.append(
        series_plot(
            "08_tx_i.svg",
            "Передані відліки — квадратура I",
            "Абсолютний індекс відліку, безрозмірний",
            "I, амплітуда огинаючої",
            sample_x,
            result.sample_tx_i,
            points_per_symbol=result.samples_per_symbol,
        )
    )
    outputs.append(
        series_plot(
            "09_tx_q.svg",
            "Передані відліки — квадратура Q",
            "Абсолютний індекс відліку, безрозмірний",
            "Q, амплітуда огинаючої",
            sample_x,
            result.sample_tx_q,
            points_per_symbol=result.samples_per_symbol,
        )
    )
    complex_svg = _svg_chart(
        title="Комплексні відліки rectangular ZOH до каналу",
        x_label="Абсолютний індекс відліку, безрозмірний",
        y_label="Амплітуда огинаючої",
        series=[
            ("I", sample_x, result.sample_tx_i),
            ("Q", sample_x, result.sample_tx_q),
        ],
        highlight=(float(sample_start), float(sample_end)),
        marker=float(selected_symbol * result.samples_per_symbol),
        selected_symbol=selected_symbol,
        sample_window=sample_window,
    )
    path = directory / "10_tx_samples_zoh.svg"
    path.write_text(complex_svg, encoding="utf-8")
    outputs.append((path.name, str(path)))
    index: dict[str, Any] = {
        "plot_count": len(outputs),
        "data_source": "TransmitterResult arrays; no channel/receiver values",
        "frame_symbols": frame_symbols,
        "selected_symbol": selected_symbol,
        "window_start_symbol": start_symbol,
        "window_symbols": min(window_symbols, frame_symbols),
        "absolute_sample_window_inclusive": [sample_start, sample_end],
        "plots": [{"file": name, "path": plot_path} for name, plot_path in outputs],
    }
    (directory / "plot_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {name: plot_path for name, plot_path in outputs}
