"""Read-only SVG diagnostics from actual REPRO-04 receiver arrays."""

from __future__ import annotations

import html
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.receiver_evaluation import ReceiverEvaluation
from hf_tcm.repro.separate_receiver import SeparateReceiverResult


def _line_svg(
    title: str,
    x_label: str,
    y_label: str,
    xs: NDArray,
    ys: NDArray,
    *,
    color: str = "#075985",
    scatter: bool = False,
) -> str:
    width, height = 1100, 560
    left, right, top, bottom = 90.0, 1060.0, 75.0, 475.0
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    if len(x) > 1800:
        selected = np.linspace(0, len(x) - 1, 1800, dtype=np.int64)
        x, y = x[selected], y[selected]
    xmin, xmax = float(np.min(x)), float(np.max(x))
    ymin, ymax = float(np.min(y)), float(np.max(y))
    if xmin == xmax:
        xmin, xmax = xmin - 0.5, xmax + 0.5
    if ymin == ymax:
        ymin, ymax = ymin - 0.5, ymax + 0.5

    def px(v: float) -> float:
        return left + (v - xmin) * (right - left) / (xmax - xmin)

    def py(v: float) -> float:
        return bottom - (v - ymin) * (bottom - top) / (ymax - ymin)

    if scatter:
        data_shape = "".join(
            f'<circle cx="{px(float(a)):.2f}" cy="{py(float(b)):.2f}" r="3" fill="{color}"><title>Re={float(a):.8g}; Im={float(b):.8g}</title></circle>'
            for a, b in zip(x, y, strict=True)
        )
    else:
        coords = " ".join(
            f"{px(float(a)):.2f},{py(float(b)):.2f}" for a, b in zip(x, y, strict=True)
        )
        data_shape = (
            f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2.5"/>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">'
        f'<title>{html.escape(title)}</title><rect width="100%" height="100%" fill="white"/>'
        f'<text x="550" y="38" text-anchor="middle" font-size="26">{html.escape(title)}</text>'
        f'<rect x="{left}" y="{top}" width="{right - left}" height="{bottom - top}" fill="#f8fafc" stroke="#334155"/>'
        f"{data_shape}"
        f'<text x="550" y="535" text-anchor="middle" font-size="18">{html.escape(x_label)}</text>'
        f'<text x="25" y="275" transform="rotate(-90 25 275)" text-anchor="middle" font-size="18">{html.escape(y_label)}</text>'
        f'<text x="{left}" y="500" font-size="13">{xmin:.4g}</text><text x="{right}" y="500" text-anchor="end" font-size="13">{xmax:.4g}</text>'
        f'<text x="{left - 8}" y="{top + 5}" text-anchor="end" font-size="13">{ymax:.4g}</text><text x="{left - 8}" y="{bottom}" text-anchor="end" font-size="13">{ymin:.4g}</text></svg>'
    )


def _omitted_diagnostic_svg(title: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 560" role="img">'
        f"<title>{html.escape(title)}</title><rect width='100%' height='100%' fill='white'/>"
        f"<text x='550' y='38' text-anchor='middle' font-size='26'>{html.escape(title)}</text>"
        "<text x='550' y='285' text-anchor='middle' font-size='20'>"
        "Повну історію survivor-метрик не збережено (trace_output_mode=compact)."
        "</text></svg>"
    )


def _heatmap_svg(metrics: NDArray[np.int8]) -> str:
    values = np.asarray(metrics)
    row_height, left = 18, 90
    cell = 58
    stride = max(1, int(np.ceil(len(values) / 120)))
    height = max(240, 100 + int(np.ceil(len(values) / stride)) * row_height)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {left + 16 * cell + 20} {height}" role="img"><title>Метрики Хемінга</title><rect width="100%" height="100%" fill="white"/><text x="500" y="28" text-anchor="middle" font-size="23">Метрики Хемінга: 16 ребер на символ</text>'
    ]
    for edge in range(16):
        out.append(
            f'<text x="{left + edge * cell + cell / 2}" y="55" text-anchor="middle" font-size="12">{edge}</text>'
        )
    for row in range(0, len(values), stride):
        y = 65 + (row // stride) * row_height
        for edge, cost in enumerate(values[row]):
            shade = 255 - int(cost) * 45
            out.append(
                f'<rect x="{left + edge * cell}" y="{y}" width="{cell - 1}" height="{row_height - 1}" fill="rgb(210,{shade},{shade})"><title>Символ {row}, ребро {edge}, відстань Хемінга {int(cost)}</title></rect>'
            )
        out.append(
            f'<text x="{left - 8}" y="{y + 13}" text-anchor="end" font-size="11">{row}</text>'
        )
    out.append("</svg>")
    return "".join(out)


def write_receiver_plots(
    observation: ReceiverObservation,
    result: SeparateReceiverResult,
    output_dir: str | Path,
    *,
    evaluation: ReceiverEvaluation | None = None,
    selected_symbol: int = 0,
) -> tuple[Path, ...]:
    if not isinstance(observation, ReceiverObservation) or not isinstance(
        result, SeparateReceiverResult
    ):
        raise TypeError("plots require ReceiverObservation and SeparateReceiverResult")
    if result.observation_sha256 != observation.sha256:
        raise ValueError("plot observation does not match receiver result hash")
    count = len(result.hard_phase_indices)
    if type(selected_symbol) is not int or not 0 <= selected_symbol < count:
        raise ValueError("selected_symbol must identify a decoded symbol")
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    sample_x = observation.absolute_sample_index
    i_path = _line_svg(
        "Прийнятий сигнал: квадратура I",
        "Абсолютний індекс відліку",
        "I, амплітуда",
        sample_x,
        observation.received_samples.real,
    )
    q_path = _line_svg(
        "Прийнятий сигнал: квадратура Q",
        "Абсолютний індекс відліку",
        "Q, амплітуда",
        sample_x,
        observation.received_samples.imag,
        color="#b91c1c",
    )
    constellation = _line_svg(
        "Сузір’я прийнятих символів",
        "Re(y), амплітуда",
        "Im(y), амплітуда",
        np.real(np.mean(observation.received_samples[: count * 8].reshape(count, 8), axis=1)),
        np.imag(np.mean(observation.received_samples[: count * 8].reshape(count, 8), axis=1)),
        scatter=True,
    )
    symbol_x = np.arange(count)
    views: dict[str, str] = {
        "received_i.svg": i_path,
        "received_q.svg": q_path,
        "received_constellation.svg": constellation,
        "hard_phase_decisions.svg": _line_svg(
            "Жорсткі рішення 8PSK",
            "Індекс символу",
            "Фазовий індекс",
            symbol_x,
            result.hard_phase_indices,
        ),
        "hamming_metric_heatmap.svg": _heatmap_svg(result.hamming_branch_metrics),
        "viterbi_path_metric.svg": _line_svg(
            "Накопичена метрика Вітербі",
            "Крок решітки",
            "Ціла метрика Хемінга",
            np.arange(len(result.accumulated_state_metrics)),
            np.min(result.accumulated_state_metrics, axis=1),
        )
        if len(result.accumulated_state_metrics)
        else _omitted_diagnostic_svg("Накопичена метрика Вітербі"),
        "decoded_state_path.svg": _line_svg(
            "Шлях станів декодера",
            "Крок решітки",
            "Індекс стану",
            np.arange(len(result.decoded_state_path)),
            result.decoded_state_path[:, 0] * 2 + result.decoded_state_path[:, 1],
        ),
    }
    selected_start = max(0, min(selected_symbol - 9, count - 20))
    selected_end = min(count, selected_start + 20)
    start_sample, end_sample = selected_start * 8, selected_end * 8
    views["window_20_symbols.svg"] = _line_svg(
        f"Прийнятий I: вікно символів {selected_start}–{selected_end - 1}",
        "Абсолютний індекс відліку",
        "I, амплітуда",
        sample_x[start_sample:end_sample],
        observation.received_samples.real[start_sample:end_sample],
    )
    detail_start = selected_symbol * 8
    detail_end = min(detail_start + 20, len(observation.received_samples))
    views["detail_20_samples.svg"] = _line_svg(
        f"Деталізація 20 відліків біля символу {selected_symbol}",
        "Абсолютний індекс відліку",
        "I, амплітуда",
        sample_x[detail_start:detail_end],
        observation.received_samples.real[detail_start:detail_end],
    )
    views["hard_coded_bit_triples.svg"] = _line_svg(
        "Жорсткі кодові трійки",
        "Індекс символу",
        "Бітове значення за позицією",
        np.repeat(symbol_x, 3),
        result.hard_coded_triples.reshape(-1),
        color="#047857",
    )
    if evaluation is not None:
        views["evaluation_bit_errors.svg"] = _line_svg(
            "Позиції бітових помилок (evaluation-only)",
            "Індекс інформаційного біта",
            "Помилка",
            np.arange(evaluation.compared_information_bit_count),
            np.isin(
                np.arange(evaluation.compared_information_bit_count), evaluation.bit_error_positions
            ).astype(np.int8),
            color="#b91c1c",
        )
        views["evaluation_reference_phase.svg"] = _line_svg(
            "Фактична та reference фаза (evaluation-only)",
            "Індекс інформаційного символу",
            "Фазовий індекс 8PSK",
            np.arange(evaluation.compared_symbol_count),
            result.hard_phase_indices[: evaluation.compared_symbol_count]
            - evaluation.reference_phase_indices,
            color="#9333ea",
        )
    paths = []
    for filename, content in views.items():
        target = root / filename
        target.write_text(content + "\n", encoding="utf-8")
        paths.append(target)
    return tuple(paths)
