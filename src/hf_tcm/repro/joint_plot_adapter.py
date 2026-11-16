"""Read-only SVG diagnostics rendered from actual REPRO-05 arrays."""

from __future__ import annotations

import html
from pathlib import Path

import numpy as np

from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.joint_evaluation import JointEvaluation
from hf_tcm.repro.joint_receiver import JointReceiverResult
from hf_tcm.repro.separate_receiver import SeparateReceiverResult


def _svg_lines(title: str, x_label: str, y_label: str, series: list[tuple[str, np.ndarray]]) -> str:
    width, height = 1100, 560
    left, right, top, bottom = 90.0, 1060.0, 75.0, 475.0
    xs = [np.asarray(item[1][:, 0], dtype=float) for item in series]
    ys = [np.asarray(item[1][:, 1], dtype=float) for item in series]
    all_x = np.concatenate(xs)
    all_y = np.concatenate(ys)
    xmin, xmax = float(all_x.min()), float(all_x.max())
    ymin, ymax = float(all_y.min()), float(all_y.max())
    if xmin == xmax:
        xmin, xmax = xmin - 0.5, xmax + 0.5
    if ymin == ymax:
        ymin, ymax = ymin - 0.5, ymax + 0.5

    def px(value: float) -> float:
        return left + (value - xmin) * (right - left) / (xmax - xmin)

    def py(value: float) -> float:
        return bottom - (value - ymin) * (bottom - top) / (ymax - ymin)

    colors = ("#075985", "#b91c1c", "#047857", "#7e22ce")
    shapes = []
    for number, (label, values) in enumerate(series):
        coords = " ".join(f"{px(float(x)):.2f},{py(float(y)):.2f}" for x, y in values)
        shapes.append(
            f'<polyline points="{coords}" fill="none" stroke="{colors[number % len(colors)]}" stroke-width="2.5"><title>{html.escape(label)}</title></polyline>'
        )
        shapes.append(
            f'<text x="{left + number * 220}" y="520" font-size="14" fill="{colors[number % len(colors)]}">{html.escape(label)}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">'
        f'<title>{html.escape(title)}</title><rect width="100%" height="100%" fill="white"/>'
        f'<text x="550" y="38" text-anchor="middle" font-size="25">{html.escape(title)}</text>'
        f'<rect x="{left}" y="{top}" width="{right - left}" height="{bottom - top}" fill="#f8fafc" stroke="#334155"/>'
        + "".join(shapes)
        + f'<text x="550" y="550" text-anchor="middle" font-size="18">{html.escape(x_label)}</text>'
        + f'<text x="22" y="275" transform="rotate(-90 22 275)" text-anchor="middle" font-size="18">{html.escape(y_label)}</text>'
        + "</svg>"
    )


def _omitted_diagnostic_svg(title: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 560" role="img">'
        f"<title>{html.escape(title)}</title><rect width='100%' height='100%' fill='white'/>"
        f"<text x='550' y='38' text-anchor='middle' font-size='25'>{html.escape(title)}</text>"
        "<text x='550' y='285' text-anchor='middle' font-size='20'>"
        "Повну історію survivor-метрик не збережено (trace_output_mode=compact)."
        "</text></svg>"
    )


def _heatmap(values: np.ndarray, title: str, unit: str) -> str:
    rows = np.asarray(values, dtype=float)
    stride = max(1, int(np.ceil(len(rows) / 300)))
    rows = rows[::stride]
    height = 100 + len(rows) * 16
    cell = 56
    maximum = float(np.max(rows)) if rows.size else 1.0
    maximum = maximum if maximum > 0 else 1.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {90 + 16 * cell} {height}" role="img">',
        f"<title>{html.escape(title)}</title><rect width='100%' height='100%' fill='white' />",
        f"<text x='500' y='28' text-anchor='middle' font-size='23'>{html.escape(title)}</text>",
    ]
    for edge in range(16):
        parts.append(
            f"<text x='{90 + edge * cell + cell / 2}' y='55' text-anchor='middle' font-size='12'>{edge}</text>"
        )
    for row_index, row in enumerate(rows):
        y = 65 + row_index * 16
        for edge, value in enumerate(row):
            shade = max(0, min(255, 245 - int(190 * value / maximum)))
            parts.append(
                f"<rect x='{90 + edge * cell}' y='{y}' width='{cell - 1}' height='15' fill='rgb({shade},{shade},255)'><title>Крок {row_index * stride}; ребро {edge}; {value:.8g} {html.escape(unit)}</title></rect>"
            )
        parts.append(
            f"<text x='82' y='{y + 12}' text-anchor='end' font-size='11'>{row_index * stride}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def _scatter(title: str, x_label: str, y_label: str, points: list[tuple[str, float, float]]) -> str:
    width, height = 760, 620
    left, right, top, bottom = 90.0, 710.0, 70.0, 540.0
    xs = np.asarray([item[1] for item in points], dtype=float)
    ys = np.asarray([item[2] for item in points], dtype=float)
    xmin, xmax = float(xs.min()), float(xs.max())
    ymin, ymax = float(ys.min()), float(ys.max())
    xpad = max((xmax - xmin) * 0.1, 0.1)
    ypad = max((ymax - ymin) * 0.1, 0.1)
    xmin, xmax, ymin, ymax = xmin - xpad, xmax + xpad, ymin - ypad, ymax + ypad

    def px(value: float) -> float:
        return left + (value - xmin) * (right - left) / (xmax - xmin)

    def py(value: float) -> float:
        return bottom - (value - ymin) * (bottom - top) / (ymax - ymin)

    marks = "".join(
        f'<circle cx="{px(real):.2f}" cy="{py(imag):.2f}" r="7" fill="#075985"><title>{html.escape(label)}; Re={real:.9g}; Im={imag:.9g}</title></circle>'
        for label, real, imag in points
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">'
        f'<title>{html.escape(title)}</title><rect width="100%" height="100%" fill="white"/>'
        f'<text x="380" y="36" text-anchor="middle" font-size="24">{html.escape(title)}</text>'
        f'<rect x="{left}" y="{top}" width="{right - left}" height="{bottom - top}" fill="#f8fafc" stroke="#334155"/>'
        f"{marks}"
        f'<text x="400" y="590" text-anchor="middle" font-size="18">{html.escape(x_label)}</text>'
        f'<text x="22" y="305" transform="rotate(-90 22 305)" text-anchor="middle" font-size="18">{html.escape(y_label)}</text>'
        f'<text x="{left}" y="560" font-size="13">{xmin:.4g}</text><text x="{right}" y="560" text-anchor="end" font-size="13">{xmax:.4g}</text>'
        f'<text x="{left - 8}" y="{top + 5}" text-anchor="end" font-size="13">{ymax:.4g}</text><text x="{left - 8}" y="{bottom}" text-anchor="end" font-size="13">{ymin:.4g}</text>'
        f"</svg>"
    )


def write_joint_receiver_plots(
    observation: ReceiverObservation,
    result: JointReceiverResult,
    output_dir: str | Path,
    *,
    evaluation: JointEvaluation | None = None,
    selected_symbol: int = 0,
) -> tuple[Path, ...]:
    if type(observation) is not ReceiverObservation or not isinstance(result, JointReceiverResult):
        raise TypeError("plots require ReceiverObservation and JointReceiverResult")
    if observation.sha256 != result.observation_sha256:
        raise ValueError("observation hash differs from receiver result")
    count = len(result.metric_rows)
    if type(selected_symbol) is not int or not 0 <= selected_symbol < count:
        raise ValueError("selected_symbol is outside the decoded frame")
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    x = observation.absolute_sample_index.astype(float)
    sample_count = count * observation.samples_per_symbol
    received_by_symbol = (
        observation.received_samples[:sample_count]
        .reshape(count, observation.samples_per_symbol)
        .mean(axis=1)
    )
    phase = result.candidate_phase_indices
    state_indices_by_label = {(0, 0): 0, (1, 0): 1, (0, 1): 2, (1, 1): 3}
    decoded_state_indices = np.asarray(
        [
            state_indices_by_label[tuple(int(bit) for bit in row)]
            for row in result.decoded_state_path
        ],
        dtype=np.int8,
    )
    plots: dict[str, str] = {
        "received_iq.svg": _svg_lines(
            "Прийняті комплексні відліки",
            "Абсолютний індекс відліку",
            "Амплітуда",
            [
                ("I, дійсна квадратура", np.column_stack((x, observation.received_samples.real))),
                ("Q, уявна квадратура", np.column_stack((x, observation.received_samples.imag))),
            ],
        ),
        "candidate_predictions.svg": _scatter(
            f"Кандидатні прогнози для символу {selected_symbol}",
            "Re(ŷ), амплітуда комплексної огинаючої",
            "Im(ŷ), амплітуда комплексної огинаючої",
            [
                (
                    f"Ребро {edge}, фаза b={int(phase[edge])}",
                    float(result.candidate_predictions[selected_symbol, edge, 0].real),
                    float(result.candidate_predictions[selected_symbol, edge, 0].imag),
                )
                for edge in range(16)
            ],
        ),
        "received_constellation.svg": _scatter(
            "Прийняте сузір’я (середнє 8 відліків на символ)",
            "Re(y), амплітуда комплексної огинаючої",
            "Im(y), амплітуда комплексної огинаючої",
            [
                (f"Символ {k}", float(value.real), float(value.imag))
                for k, value in enumerate(received_by_symbol)
            ],
        ),
        "euclidean_metric_heatmap.svg": _heatmap(
            result.metric_rows, "Евклідові метрики 16 переходів", "метрична одиниця"
        ),
        "posterior_weights.svg": _svg_lines(
            "Псевдоймовірнісні ваги кандидатів",
            "Індекс символу",
            "Нормована вага",
            [
                (
                    f"Ребро {edge}",
                    np.column_stack((np.arange(count), result.posterior_weights[:, edge])),
                )
                for edge in range(16)
            ],
        ),
        "estimated_channel.svg": _svg_lines(
            "Оцінка каналу до та після адаптивного оновлення",
            "Індекс символу",
            "Дійсна/уявна частина коефіцієнта",
            [
                ("Re(h pre)", np.column_stack((np.arange(count), result.estimator_pre.real))),
                ("Im(h pre)", np.column_stack((np.arange(count), result.estimator_pre.imag))),
                ("Re(h post)", np.column_stack((np.arange(count), result.estimator_post.real))),
                ("Im(h post)", np.column_stack((np.arange(count), result.estimator_post.imag))),
            ],
        ),
        "estimated_channel_magnitude.svg": _svg_lines(
            "Модуль оціненого коефіцієнта каналу",
            "Індекс символу",
            "|h|, безрозмірний коефіцієнт",
            [
                ("До оновлення", np.column_stack((np.arange(count), np.abs(result.estimator_pre)))),
                (
                    "Після оновлення",
                    np.column_stack((np.arange(count), np.abs(result.estimator_post))),
                ),
            ],
        ),
        "estimated_channel_phase.svg": _svg_lines(
            "Фаза оціненого коефіцієнта каналу",
            "Індекс символу",
            "arg(h), рад",
            [
                (
                    "До оновлення",
                    np.column_stack((np.arange(count), np.angle(result.estimator_pre))),
                ),
                (
                    "Після оновлення",
                    np.column_stack((np.arange(count), np.angle(result.estimator_post))),
                ),
            ],
        ),
        "innovation.svg": _svg_lines(
            "Історія інновації",
            "Індекс символу",
            "Інновація",
            [
                ("Re(ε)", np.column_stack((np.arange(count), result.innovation.real))),
                ("Im(ε)", np.column_stack((np.arange(count), result.innovation.imag))),
            ],
        ),
        "viterbi_path_metric.svg": _svg_lines(
            "Мінімальна накопичена метрика Вітербі",
            "Крок решітки",
            "Накопичена метрика",
            [
                (
                    "Мінімум станів",
                    np.column_stack(
                        (np.arange(count + 1), np.min(result.viterbi_state_metrics, axis=1))
                    ),
                )
            ],
        )
        if len(result.viterbi_state_metrics)
        else _omitted_diagnostic_svg("Накопичена метрика Вітербі"),
        "viterbi_state_path.svg": _svg_lines(
            "Відновлений шлях станів TCM",
            "Крок trellis",
            "Індекс стану (канонічний порядок)",
            [("Шлях", np.column_stack((np.arange(count + 1), decoded_state_indices)))],
        ),
    }
    start = max(0, min(selected_symbol - 10, count - 20))
    stop = min(count, start + 20)
    sample_start, sample_stop = start * 8, min(stop * 8, len(observation.received_samples))
    plots["window_20_symbols.svg"] = _svg_lines(
        f"20-символьне вікно: {start}–{stop - 1}",
        "Абсолютний індекс відліку",
        "I, амплітуда",
        [
            (
                "Прийнятий сигнал",
                np.column_stack(
                    (
                        x[sample_start:sample_stop],
                        observation.received_samples[sample_start:sample_stop].real,
                    )
                ),
            )
        ],
    )
    if evaluation is not None:
        plots["evaluation_bit_errors.svg"] = _svg_lines(
            "Помилки бітів (evaluation-only)",
            "Індекс інформаційного біта",
            "Помилка (0/1)",
            [
                (
                    "Помилки",
                    np.column_stack(
                        (
                            np.arange(evaluation.compared_information_bit_count),
                            np.isin(
                                np.arange(evaluation.compared_information_bit_count),
                                evaluation.bit_error_positions,
                            ).astype(float),
                        )
                    ),
                )
            ],
        )
    paths = []
    for filename, contents in plots.items():
        path = root / filename
        path.write_text(contents + "\n", encoding="utf-8")
        paths.append(path)
    return tuple(paths)


def write_dual_receiver_comparison_plot(
    joint: JointReceiverResult,
    separate: SeparateReceiverResult,
    output_path: str | Path,
) -> Path:
    """Plot decoded decisions from two runs of the same observation."""
    if joint.observation_sha256 != separate.observation_sha256:
        raise ValueError("receiver results do not share an observation hash")
    joint_bits = np.asarray(joint.decoded_information_bits, dtype=np.int8)
    separate_bits = np.asarray(separate.decoded_information_bits, dtype=np.int8)
    if joint_bits.shape != separate_bits.shape:
        raise ValueError("receiver outputs have different payload boundaries")
    x = np.arange(len(joint_bits), dtype=float)
    points = np.column_stack((x, joint_bits.astype(float)))
    comparison = np.column_stack((x, separate_bits.astype(float)))
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _svg_lines(
            "Спільний та роздільний приймач: декодовані біти",
            "Індекс інформаційного біта",
            "Декодоване значення біта",
            [("Joint Euclidean", points), ("Separate Hamming", comparison)],
        )
        + "\n",
        encoding="utf-8",
    )
    return path
