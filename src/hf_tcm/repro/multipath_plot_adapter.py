"""Read-only actual-data SVG plots for the REPRO-06B receiver and evaluation."""

from __future__ import annotations

import html
from pathlib import Path

import numpy as np

from hf_tcm.repro.channel_result import EvaluationTruth, ReceiverObservation
from hf_tcm.repro.multipath_evaluation import MultipathReceiverEvaluation
from hf_tcm.repro.multipath_joint_receiver import MultipathJointReceiverResult
from hf_tcm.repro.separate_receiver import SeparateReceiverResult


def _svg_header(title: str, width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width / 2:.0f}" y="34" text-anchor="middle" font-size="22" font-family="sans-serif">{html.escape(title)}</text>',
    ]


def _line_plot(
    path: Path,
    title: str,
    x_label: str,
    y_label: str,
    x: np.ndarray,
    series: tuple[tuple[str, np.ndarray, str], ...],
    *,
    width: int = 1100,
    height: int = 520,
) -> None:
    values = [np.asarray(row[1], dtype=np.float64) for row in series]
    finite = [row[np.isfinite(row)] for row in values if np.any(np.isfinite(row))]
    if not finite:
        raise ValueError("plot needs at least one finite series")
    y_min = min(float(np.min(row)) for row in finite)
    y_max = max(float(np.max(row)) for row in finite)
    if y_min == y_max:
        y_min -= 1.0
        y_max += 1.0
    x_values = np.asarray(x, dtype=np.float64)
    x_min, x_max = float(x_values.min()), float(x_values.max())
    if x_min == x_max:
        x_max = x_min + 1.0
    left, right, top, bottom = 100.0, width - 40.0, 70.0, height - 75.0
    parts = _svg_header(title, width, height)
    parts.extend(
        [
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#222" stroke-width="2"/>',
            f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#222" stroke-width="2"/>',
            f'<text x="{(left + right) / 2:.0f}" y="{height - 22}" text-anchor="middle" font-size="18" font-family="sans-serif">{html.escape(x_label)}</text>',
            f'<text x="24" y="{(top + bottom) / 2:.0f}" text-anchor="middle" font-size="18" transform="rotate(-90 24 {(top + bottom) / 2:.0f})" font-family="sans-serif">{html.escape(y_label)}</text>',
            f'<text x="{left}" y="{bottom + 22}" font-size="13" font-family="sans-serif">{x_min:g}</text>',
            f'<text x="{right}" y="{bottom + 22}" text-anchor="end" font-size="13" font-family="sans-serif">{x_max:g}</text>',
            f'<text x="{left - 10}" y="{bottom}" text-anchor="end" font-size="13" font-family="sans-serif">{y_min:.4g}</text>',
            f'<text x="{left - 10}" y="{top + 5}" text-anchor="end" font-size="13" font-family="sans-serif">{y_max:.4g}</text>',
        ]
    )
    for idx, (name, values_y, color) in enumerate(series):
        y = np.asarray(values_y, dtype=np.float64)
        if y.shape != x_values.shape:
            continue
        px = left + (x_values - x_min) * (right - left) / (x_max - x_min)
        py = bottom - (y - y_min) * (bottom - top) / (y_max - y_min)
        points = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(px, py, strict=True))
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5"/>'
        )
        legend_y = top + 20 + idx * 22
        parts.append(
            f'<line x1="{right - 220}" y1="{legend_y}" x2="{right - 190}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>'
        )
        parts.append(
            f'<text x="{right - 184}" y="{legend_y + 5}" font-size="14" font-family="sans-serif">{html.escape(name)}</text>'
        )
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _heatmap(path: Path, result: MultipathJointReceiverResult) -> None:
    rows = np.asarray(result.branch_metric_rows)
    bins = min(len(rows), 500)
    edges = rows.shape[1]
    # Each displayed value is the minimum observed metric in its actual row bin.
    blocks = np.array_split(rows, bins, axis=0)
    reduced = np.vstack([np.min(block, axis=0) for block in blocks])
    low, high = float(np.min(reduced)), float(np.max(reduced))
    width, height = 1200, 540
    left, top = 90, 75
    cell_w, cell_h = (width - left - 30) / edges, (height - top - 65) / bins
    parts = _svg_header("Метрики expanded transition trellis", width, height)
    for r in range(bins):
        for c in range(edges):
            fraction = 0.0 if high == low else (reduced[r, c] - low) / (high - low)
            red = int(245 - 180 * fraction)
            green = int(248 - 170 * fraction)
            blue = int(255 - 80 * fraction)
            parts.append(
                f'<rect x="{left + c * cell_w:.2f}" y="{top + r * cell_h:.2f}" width="{cell_w + 0.2:.2f}" height="{cell_h + 0.2:.2f}" fill="rgb({red},{green},{blue})"/>'
            )
    parts.extend(
        [
            f'<text x="{width / 2}" y="{height - 15}" text-anchor="middle" font-size="18" font-family="sans-serif">Індекс expanded transition (edge ID)</text>',
            f'<text x="22" y="{height / 2}" text-anchor="middle" font-size="18" transform="rotate(-90 22 {height / 2})" font-family="sans-serif">Символьний індекс (агреговані діапазони)</text>',
            f'<text x="{left}" y="{height - 42}" font-size="13" font-family="sans-serif">0</text>',
            f'<text x="{width - 30}" y="{height - 42}" text-anchor="end" font-size="13" font-family="sans-serif">{len(rows) - 1}</text>',
            f'<text x="{left}" y="{top - 14}" font-size="13" font-family="sans-serif">мін={low:.5g}, макс={high:.5g}; bins={bins}/{len(rows)}</text>',
            "</svg>",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _trellis_plot(path: Path, result: MultipathJointReceiverResult, start: int) -> None:
    nodes = result.expanded_nodes
    edges = result.expanded_edges
    frame = len(result.decisions)
    stop = min(frame, start + 20)
    width, height = max(1100, 80 * (stop - start + 1)), 760
    left, top, right, bottom = 70, 85, width - 30, height - 80
    x_step = (right - left) / max(1, stop - start)
    y_step = (bottom - top) / max(1, len(nodes) - 1)
    parts = _svg_header("ISI-aware augmented trellis — вибране 20-символьне вікно", width, height)
    selected = {d.symbol_index: d for d in result.decisions[start:stop]}
    for k in range(start, stop):
        x1, x2 = left + (k - start) * x_step, left + (k - start + 1) * x_step
        chosen = selected.get(k)
        for edge in edges:
            y1 = top + edge["source_node_id"] * y_step
            y2 = top + edge["target_node_id"] * y_step
            is_selected = chosen is not None and chosen.expanded_edge_id == edge["expanded_edge_id"]
            color = "#b42318" if is_selected else "#c9cdd3"
            stroke = 4.5 if is_selected else 0.8
            parts.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{stroke}" opacity="{0.95 if is_selected else 0.35}"/>'
            )
        parts.append(
            f'<text x="{(x1 + x2) / 2:.1f}" y="{height - 48}" text-anchor="middle" font-size="13" font-family="sans-serif">k={k}</text>'
        )
    for column in range(stop - start + 1):
        x = left + column * x_step
        for node in nodes:
            y = top + node["node_id"] * y_step
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#1668a5" stroke="white" stroke-width="1.5"/>'
            )
        if column == 0:
            for node in nodes:
                y = top + node["node_id"] * y_step
                history = ",".join(
                    "–" if phase < 0 else str(phase) for phase in node["previous_phase_history"]
                )
                label = f"{node['node_id']}:s={node['encoder_state']},bₚ=[{history}]"
                parts.append(
                    f'<text x="{x - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="11" font-family="sans-serif">{html.escape(label)}</text>'
                )
    parts.append(
        '<text x="90" y="58" font-size="14" font-family="sans-serif" fill="#b42318">Червоне — локальне рішення survivor; finite-depth рішення з різних вікон можуть не з’єднуватися.</text>'
    )
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def write_multipath_receiver_plots(
    observation: ReceiverObservation,
    result: MultipathJointReceiverResult,
    output_dir: str | Path,
    *,
    evaluation: MultipathReceiverEvaluation | None = None,
    separate_result: SeparateReceiverResult | None = None,
    evaluation_truth: EvaluationTruth | None = None,
) -> tuple[Path, ...]:
    """Write plots from receiver data; optional truth is used only after decoding."""
    if (
        type(observation) is not ReceiverObservation
        or result.observation_sha256 != observation.sha256
    ):
        raise ValueError("plot observation must match result observation hash")
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    selected = result.diagnostic_symbol_index
    decision = result.decisions[selected]
    candidate = result.diagnostic_candidate_predictions[decision.expanded_edge_id]
    actual = observation.received_samples[result.diagnostic_sample_indices]
    ix = result.diagnostic_sample_indices.astype(np.float64)
    path = root / "01_received_and_selected_prediction.svg"
    _line_plot(
        path,
        f"Прийнятий сигнал і вибране прогнозування, символ {selected}",
        "Абсолютний індекс відліку, n",
        "Амплітуда квадратури",
        ix,
        (
            ("Прийнятий I", actual.real, "#164e9b"),
            ("Прогнозований I", candidate.real, "#c43b32"),
            ("Прийнятий Q", actual.imag, "#24824a"),
            ("Прогнозований Q", candidate.imag, "#9a54a1"),
        ),
    )
    outputs.append(path)

    _heatmap(root / "02_expanded_branch_metric_heatmap.svg", result)
    outputs.append(root / "02_expanded_branch_metric_heatmap.svg")

    window_start = max(0, min(selected - 10, len(result.decisions) - 20))
    window_stop = min(len(result.decisions), window_start + 20)
    sample_start, sample_stop = (
        window_start * 8,
        min(window_stop * 8, len(observation.received_samples)),
    )
    window_indices = np.arange(sample_start, sample_stop, dtype=np.int64)
    path = root / "03_received_20_symbol_window.svg"
    _line_plot(
        path,
        f"Прийняті I/Q відліки: символи {window_start}–{window_stop - 1}",
        "Абсолютний індекс відліку, n",
        "Амплітуда квадратури",
        window_indices.astype(np.float64),
        (
            ("I", observation.received_samples[window_indices].real, "#164e9b"),
            ("Q", observation.received_samples[window_indices].imag, "#c43b32"),
        ),
    )
    outputs.append(path)

    zoom_indices = np.arange(
        selected * 8, min(selected * 8 + 20, len(observation.received_samples)), dtype=np.int64
    )
    path = root / "04_received_20_sample_zoom.svg"
    _line_plot(
        path,
        f"Деталізація 20 відліків від символу {selected}",
        "Абсолютний індекс відліку, n",
        "Амплітуда квадратури",
        zoom_indices.astype(np.float64),
        (
            ("I", observation.received_samples[zoom_indices].real, "#164e9b"),
            ("Q", observation.received_samples[zoom_indices].imag, "#c43b32"),
        ),
    )
    outputs.append(path)

    path = root / "05_augmented_trellis_survivors.svg"
    _trellis_plot(path, result, window_start)
    outputs.append(path)

    if evaluation_truth is not None:
        tx = evaluation_truth.transmitter_samples
        tx_indices = window_indices[window_indices < len(tx)]
        path = root / "06_transmitted_iq_evaluation_only.svg"
        _line_plot(
            path,
            "Передані I/Q відліки (лише evaluation/visualization truth)",
            "Абсолютний індекс відліку, n",
            "Амплітуда квадратури",
            tx_indices.astype(np.float64),
            (("Tx I", tx[tx_indices].real, "#164e9b"), ("Tx Q", tx[tx_indices].imag, "#c43b32")),
        )
        outputs.append(path)
        contributions = evaluation_truth.path_contributions[:, window_indices]
        series = tuple(
            (f"Промінь {index} I", contribution.real, f"hsl({index * 75 % 360},65%,42%)")
            for index, contribution in enumerate(contributions)
        )
        path = root / "07_path_contributions_evaluation_only.svg"
        _line_plot(
            path,
            "Внески променів каналу (evaluation-only truth)",
            "Абсолютний індекс відліку, n",
            "Дійсна квадратура внеску",
            window_indices.astype(np.float64),
            series,
        )
        outputs.append(path)

    if evaluation is not None:
        path = root / "08_bit_error_positions_evaluation_only.svg"
        positions = evaluation.bit_error_positions
        x = np.arange(len(result.decoded_information_bits), dtype=np.int64)
        y = np.zeros(len(x), dtype=np.float64)
        y[positions] = 1.0
        _line_plot(
            path,
            f"Позиції бітових помилок, BER={evaluation.ber:.6g} (evaluation-only)",
            "Індекс інформаційного біта",
            "Помилка (0/1)",
            x.astype(np.float64),
            (("Позиція помилки", y, "#c43b32"),),
        )
        outputs.append(path)

    if separate_result is not None:
        if separate_result.observation_sha256 != observation.sha256:
            raise ValueError("separate result must use the same received observation")
        path = root / "09_separate_vs_joint_decoded_bits.svg"
        joint = result.decoded_information_bits
        separate = separate_result.decoded_information_bits
        common = min(len(joint), len(separate))
        x = np.arange(common, dtype=np.float64)
        _line_plot(
            path,
            "Два приймачі на одному ReceiverObservation",
            "Індекс інформаційного біта",
            "Декодоване значення (0/1)",
            x,
            (
                ("Joint ISI-aware", joint[:common], "#164e9b"),
                ("Separate Hamming", separate[:common], "#c43b32"),
            ),
        )
        outputs.append(path)
    return tuple(outputs)
