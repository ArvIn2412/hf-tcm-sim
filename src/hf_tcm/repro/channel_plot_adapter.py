"""Read-only SVG channel plots built strictly from a ChannelResult."""

from __future__ import annotations

import html
import math
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.channel_result import ChannelResult

PALETTE = ("#075985", "#dc2626", "#15803d", "#9333ea", "#c2410c", "#0f766e")


def _polyline_chart(
    *,
    title: str,
    x_label: str,
    y_label: str,
    series: list[tuple[str, NDArray[np.float64], NDArray[np.float64]]],
    selected_symbol: int,
    samples_per_symbol: int,
    window_start_sample: int,
    window_end_sample: int,
) -> str:
    width, height = 1100, 560
    left, right, top, bottom = 100, 30, 75, 105
    plot_w, plot_h = width - left - right, height - top - bottom
    x_all = np.concatenate([np.asarray(item[1], dtype=np.float64) for item in series])
    y_all = np.concatenate([np.asarray(item[2], dtype=np.float64) for item in series])
    x_min, x_max = float(np.min(x_all)), float(np.max(x_all))
    if x_max <= x_min:
        x_max = x_min + 1.0
    y_min, y_max = float(np.min(y_all)), float(np.max(y_all))
    span = y_max - y_min
    pad = span * 0.08 if span else max(abs(y_min) * 0.08, 0.5)
    y_min, y_max = y_min - pad, y_max + pad
    items = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text x="{width / 2:.0f}" y="38" text-anchor="middle" font-size="26" font-family="Arial">{html.escape(title)}</text>',
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#f8fafc" stroke="#334155" stroke-width="2"/>',
    ]
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        x = left + frac * plot_w
        y = top + frac * plot_h
        xv = x_min + frac * (x_max - x_min)
        yv = y_max - frac * (y_max - y_min)
        items.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_h}" stroke="#cbd5e1"/>'
        )
        items.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#cbd5e1"/>'
        )
        items.append(
            f'<text x="{x:.1f}" y="{top + plot_h + 25}" text-anchor="middle" font-size="14" font-family="Arial">{xv:.3g}</text>'
        )
        items.append(
            f'<text x="{left - 12}" y="{y + 5:.1f}" text-anchor="end" font-size="14" font-family="Arial">{yv:.3g}</text>'
        )
    for xmark, label, color in (
        (selected_symbol * samples_per_symbol, "вибраний символ", "#b91c1c"),
        (window_start_sample, "початок вікна", "#7c3aed"),
        (window_end_sample, "кінець вікна", "#7c3aed"),
    ):
        if x_min <= xmark <= x_max:
            px = left + (xmark - x_min) / (x_max - x_min) * plot_w
            items.append(
                f'<line x1="{px:.1f}" y1="{top}" x2="{px:.1f}" y2="{top + plot_h}" stroke="{color}" stroke-width="2" stroke-dasharray="7,5"/>'
            )
            items.append(f"<title>{html.escape(label)}: {xmark}</title>")
    for index, (label, x_values, y_values) in enumerate(series):
        x_values = np.asarray(x_values, dtype=np.float64)
        y_values = np.asarray(y_values, dtype=np.float64)
        if len(x_values) > 1600:
            picks = np.linspace(0, len(x_values) - 1, 1600, dtype=np.int64)
            x_values, y_values = x_values[picks], y_values[picks]
        px = left + (x_values - x_min) / (x_max - x_min) * plot_w
        py = top + (y_max - y_values) / (y_max - y_min) * plot_h
        points = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(px, py, strict=True))
        color = PALETTE[index % len(PALETTE)]
        items.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5"><title>{html.escape(label)}</title></polyline>'
        )
        legend_x = left + (index % 3) * 300
        legend_y = height - 48 + (index // 3) * 20
        items.append(
            f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 32}" y2="{legend_y}" stroke="{color}" stroke-width="4"/>'
        )
        items.append(
            f'<text x="{legend_x + 40}" y="{legend_y + 5}" font-size="15" font-family="Arial">{html.escape(label)}</text>'
        )
    items.extend(
        [
            f'<text x="{left + plot_w / 2:.0f}" y="{height - 10}" text-anchor="middle" font-size="18" font-family="Arial">{html.escape(x_label)}</text>',
            f'<text x="25" y="{top + plot_h / 2:.0f}" text-anchor="middle" transform="rotate(-90 25 {top + plot_h / 2:.0f})" font-size="18" font-family="Arial">{html.escape(y_label)}</text>',
            f'<text x="{left}" y="{top + plot_h + 52}" font-size="14" font-family="Arial">Символ {selected_symbol}; відліки абсолютні. Фіолетові штрихи: вікно 20 символів.</text>',
            "</svg>",
        ]
    )
    return "\n".join(items)


def _series(
    result: ChannelResult,
    names: list[tuple[str, NDArray[np.complex128]]],
    start: int = 0,
    end: int | None = None,
):
    arrays = [np.asarray(array)[start:end] for _, array in names]
    size = min(map(len, arrays)) if arrays else 0
    x = np.arange(start, start + size, dtype=np.float64)
    result_series: list[tuple[str, NDArray[np.float64], NDArray[np.float64]]] = []
    for (name, _), array in zip(names, arrays, strict=True):
        result_series.append((f"{name} · I", x, np.asarray(array[:size].real, dtype=np.float64)))
        result_series.append((f"{name} · Q", x, np.asarray(array[:size].imag, dtype=np.float64)))
    return result_series


def write_channel_plots(
    result: ChannelResult,
    output_dir: str | Path,
    *,
    selected_symbol: int = 0,
) -> dict[str, Path]:
    """Write 14 actual-data charts, with a synchronized 20-symbol window."""
    if not isinstance(result, ChannelResult):
        raise TypeError("result must be a ChannelResult")
    obs, truth = result.receiver_observation, result.evaluation_truth
    if type(selected_symbol) is not int or selected_symbol < 0:
        raise ValueError("selected_symbol must be a non-negative integer")
    sample_count = len(obs.received_samples)
    transmitter_sample_count = len(truth.transmitter_samples)
    symbol_count = int(math.ceil(transmitter_sample_count / obs.samples_per_symbol))
    if selected_symbol >= symbol_count:
        raise ValueError("selected_symbol is outside the received sample time range")
    window_samples = min(20 * obs.samples_per_symbol, transmitter_sample_count)
    max_start = max(0, transmitter_sample_count - window_samples)
    window_start = min(
        max(0, selected_symbol * obs.samples_per_symbol - window_samples // 2), max_start
    )
    window_end = window_start + window_samples
    sample_start = min(
        max(0, selected_symbol * obs.samples_per_symbol - 10), max(0, transmitter_sample_count - 20)
    )
    sample_end = min(transmitter_sample_count, sample_start + 20)
    sample_x = np.asarray(obs.absolute_sample_index, dtype=np.float64)
    tx_aligned = np.zeros(sample_count, dtype=np.complex128)
    tx_count = min(sample_count, len(truth.transmitter_samples))
    tx_aligned[:tx_count] = truth.transmitter_samples[:tx_count]

    datasets: dict[
        str,
        tuple[str, str, str, list[tuple[str, NDArray[np.float64], NDArray[np.float64]]]],
    ] = {}
    datasets["01_transmitted_iq"] = (
        "Переданий сигнал: I/Q",
        "Абсолютний індекс відліку n",
        "Амплітуда · нормовані комплексні одиниці",
        _series(result, [("Передавач", tx_aligned)]),
    )
    gain_series = []
    phase_series = []
    coefficient_series = []
    for path_index in range(truth.coefficients.shape[0]):
        coeff = truth.coefficients[path_index]
        gain_series.append(
            (f"Промінь {path_index + 1}", sample_x, np.abs(coeff).astype(np.float64))
        )
        phase_series.append(
            (f"Промінь {path_index + 1}", sample_x, np.angle(coeff).astype(np.float64))
        )
        coefficient_series.append(
            (f"Промінь {path_index + 1} · Re", sample_x, coeff.real.astype(np.float64))
        )
        coefficient_series.append(
            (f"Промінь {path_index + 1} · Im", sample_x, coeff.imag.astype(np.float64))
        )
    datasets["02_path_gain_magnitude"] = (
        "Модуль коефіцієнтів променів",
        "Абсолютний індекс відліку n",
        "|hₗ[n]| · безрозмірний",
        gain_series,
    )
    datasets["03_path_gain_phase"] = (
        "Фаза коефіцієнтів променів",
        "Абсолютний індекс відліку n",
        "arg(hₗ[n]) · рад",
        phase_series,
    )
    datasets["04_fading_coefficients"] = (
        "Дійсна та уявна частини fading коефіцієнтів",
        "Абсолютний індекс відліку n",
        "Коефіцієнт · комплексна огинаюча",
        coefficient_series,
    )
    path_ids = np.arange(len(truth.path_delays_samples), dtype=float)
    datasets["05_path_delays"] = (
        "Цілочисельні затримки променів",
        "Номер променя",
        "Затримка dₗ · відліки",
        [("Затримка dₗ", path_ids, np.asarray(truth.path_delays_samples, dtype=float))],
    )
    datasets["06_path_average_power"] = (
        "Середня потужність променів",
        "Номер променя",
        "Середня потужність · відн. до Es",
        [("P̄ₗ", path_ids, np.asarray(truth.path_average_powers, dtype=float))],
    )
    path_names = [
        (f"Промінь {i + 1}", truth.path_contributions[i])
        for i in range(truth.path_contributions.shape[0])
    ]
    datasets["07_path_contributions"] = (
        "Внески окремих променів у вибраному вікні",
        "Абсолютний індекс відліку n",
        "Амплітуда · нормовані комплексні одиниці",
        _series(result, path_names, window_start, window_end),
    )
    datasets["08_faded_sum"] = (
        "Сума променевих внесків",
        "Абсолютний індекс відліку n",
        "Амплітуда · нормовані комплексні одиниці",
        _series(result, [("Σ променів", truth.faded_signal)]),
    )
    datasets["09_noise_iq"] = (
        "Згенерований sample-domain шум",
        "Абсолютний індекс відліку n",
        "Амплітуда · нормовані комплексні одиниці",
        _series(result, [("Шум", truth.noise_samples)]),
    )
    datasets["10_received_iq"] = (
        "Прийняті комплексні відліки",
        "Абсолютний індекс відліку n",
        "Амплітуда · нормовані комплексні одиниці",
        _series(result, [("Прийнятий сигнал", obs.received_samples)]),
    )
    datasets["11_transmit_receive"] = (
        "Переданий і прийнятий сигнал у часовому індексі",
        "Абсолютний індекс відліку n",
        "Амплітуда · нормовані комплексні одиниці",
        _series(
            result,
            [("Переданий (zero-tail aligned)", tx_aligned), ("Прийнятий", obs.received_samples)],
        ),
    )
    datasets["12_received_magnitude"] = (
        "Модуль прийнятого сигналу",
        "Абсолютний індекс відліку n",
        "|y[n]| · нормовані комплексні одиниці",
        [("Модуль", sample_x, np.abs(obs.received_samples).astype(np.float64))],
    )
    datasets["13_received_phase"] = (
        "Фаза прийнятого сигналу",
        "Абсолютний індекс відліку n",
        "arg(y[n]) · рад",
        [("Фаза", sample_x, np.angle(obs.received_samples).astype(np.float64))],
    )
    selected = min(selected_symbol * obs.samples_per_symbol, len(truth.coefficients[0]) - 1)
    impulse = [
        (
            f"|hₗ[n]|; dₗ={','.join(map(str, truth.path_delays_samples))} відліків",
            np.arange(len(truth.path_delays_samples), dtype=float),
            np.abs(truth.coefficients[:, selected]).astype(np.float64),
        )
    ]
    datasets["14_channel_impulse_response"] = (
        "Модельний channel response у вибраному відліку",
        "Номер променя",
        "|hₗ[n]| · безрозмірний",
        impulse,
    )
    datasets["15_sliding_20_symbol_window"] = (
        "Прийнятий сигнал: рухоме вікно до 20 символів",
        "Абсолютний індекс відліку n",
        "Амплітуда · нормовані комплексні одиниці",
        _series(result, [("Прийнятий сигнал", obs.received_samples)], window_start, window_end),
    )
    datasets["16_detail_20_samples"] = (
        "Деталізація 20 комплексних відліків",
        "Абсолютний індекс відліку n",
        "Амплітуда · нормовані комплексні одиниці",
        _series(
            result,
            [
                ("Переданий", tx_aligned),
                ("Шум", truth.noise_samples),
                ("Прийнятий", obs.received_samples),
            ],
            sample_start,
            sample_end,
        ),
    )

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for filename, (title, x_label, y_label, series) in datasets.items():
        text = _polyline_chart(
            title=title,
            x_label=x_label,
            y_label=y_label,
            series=series,
            selected_symbol=selected_symbol,
            samples_per_symbol=obs.samples_per_symbol,
            window_start_sample=window_start,
            window_end_sample=window_end,
        )
        target = root / f"{filename}.svg"
        target.write_text(text, encoding="utf-8")
        paths[filename] = target
    return paths
