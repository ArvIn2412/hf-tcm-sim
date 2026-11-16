"""Small dependency-free SVG diagnostics built only from REPRO-06C outputs."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from hf_tcm.repro.adaptive_multipath_receiver import AdaptiveMultipathReceiverResult


def _svg(title: str, body: str, *, width: int = 1100, height: int = 480) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#fff"/><text x="{width / 2}" y="36" text-anchor="middle" font-family="sans-serif" font-size="25">{title}</text>
{body}</svg>'''


def write_adaptive_receiver_plots(
    result: AdaptiveMultipathReceiverResult,
    observation_samples: object,
    output_dir: str | Path,
    *,
    reference_bits: object | None = None,
    evaluation_coefficients: object | None = None,
    separate_decoded_bits: object | None = None,
) -> tuple[Path, ...]:
    """Write actual-data views; optional reference comparisons are evaluation-only."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    y = np.asarray(observation_samples, dtype=np.complex128)
    if y.ndim != 1 or y.size == 0:
        raise ValueError("observation_samples must be a nonempty complex vector")
    paths: list[Path] = []

    # Received I/Q: absolute receive sample index on x, baseband amplitude on y.
    take = np.linspace(0, len(y) - 1, min(len(y), 900), dtype=np.int64)

    def line(values: np.ndarray, color: str, lo: float, hi: float, width: int, height: int) -> str:
        xs = np.linspace(60, width - 30, len(values))
        span = hi - lo if hi > lo else 1.0
        ys = height - 65 - (values - lo) / span * (height - 130)
        points = " ".join(f"{x:.1f},{yy:.1f}" for x, yy in zip(xs, ys, strict=True))
        return f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{points}"/>'

    width, height = 1100, 480
    lo = float(min(y[take].real.min(), y[take].imag.min()))
    hi = float(max(y[take].real.max(), y[take].imag.max()))
    body = '<path d="M60 420H1070M60 70V420" stroke="#333" fill="none"/><text x="560" y="462" text-anchor="middle" font-size="18">Абсолютний індекс комплексного відліку n</text><text x="20" y="240" transform="rotate(-90 20 240)" text-anchor="middle" font-size="18">Амплітуда I/Q</text>'
    body += line(y[take].real, "#1565c0", lo, hi, width, height) + line(
        y[take].imag, "#c62828", lo, hi, width, height
    )
    body += '<text x="80" y="90" fill="#1565c0" font-size="17">I received</text><text x="210" y="90" fill="#c62828" font-size="17">Q received</text>'
    paths.append(_write(root / "01_received_iq.svg", _svg("Прийняті квадратури I/Q", body), result))

    means = result.estimator_mean_by_symbol_node
    valid = np.isfinite(means.real)
    summary = np.full((means.shape[0], means.shape[2]), np.nan + 1j * np.nan)
    for t in range(means.shape[0]):
        if np.any(valid[t]):
            summary[t] = np.nanmean(means[t], axis=0)
    for component, label, filename in (
        (summary.real, "Дійсна складова", "02_estimated_path_i.svg"),
        (summary.imag, "Уявна складова", "03_estimated_path_q.svg"),
    ):
        body = '<path d="M60 420H1070M60 70V420" stroke="#333" fill="none"/><text x="560" y="462" text-anchor="middle" font-size="18">TCM-символ k</text>'
        finite = component[np.isfinite(component)]
        if finite.size:
            low, high = float(finite.min()), float(finite.max())
            for index in range(component.shape[1]):
                vals = component[:, index]
                mask = np.isfinite(vals)
                if np.any(mask):
                    body += line(
                        vals[mask],
                        ("#1565c0", "#ef6c00", "#2e7d32", "#8e24aa")[index % 4],
                        low,
                        high,
                        width,
                        height,
                    )
        body += f'<text x="80" y="95" font-size="17">{label}; середнє survivor-оцінок</text>'
        paths.append(
            _write(
                root / filename,
                _svg(f"Оцінені коефіцієнти променів — {label.lower()}", body),
                result,
            )
        )

    # Metric heatmap is an actual image of branch metric rows; infinities are blank.
    metrics = result.branch_metric_rows
    finite = metrics[np.isfinite(metrics)]
    vmax = float(np.percentile(finite, 95)) if finite.size else 1.0
    cells: list[str] = []
    for row in range(min(metrics.shape[0], 600)):
        for col in range(metrics.shape[1]):
            value = metrics[row, col]
            if np.isfinite(value):
                shade = int(255 * min(max(value / max(vmax, 1e-15), 0), 1))
                cells.append(
                    f'<rect x="{60 + col * 14}" y="{62 + row * 0.45:.2f}" width="13" height="0.46" fill="rgb({shade},{255 - shade},70)"/>'
                )
    body = (
        "".join(cells)
        + '<path d="M60 60V420H1060" stroke="#222" fill="none"/><text x="560" y="455" text-anchor="middle" font-size="18">Ребро розширеної решітки</text><text x="22" y="240" transform="rotate(-90 22 240)" font-size="18">Символ k (огляд)</text>'
    )
    paths.append(
        _write(
            root / "04_euclidean_metric_heatmap.svg",
            _svg("Евклідові метрики кандидатів (фактичні branch costs)", body),
            result,
        )
    )

    # Decoded input pairs encoded as two-level tracks.
    bits = result.decoded_information_bits
    xs = np.linspace(70, 1050, len(bits))
    body = '<path d="M60 390H1070M60 80V390" stroke="#333" fill="none"/><text x="560" y="445" text-anchor="middle" font-size="18">Позиція відновленого інформаційного біта</text>'
    for index, (x, bit) in enumerate(zip(xs, bits, strict=True)):
        y0 = 175 if int(bit) else 320
        body += f'<circle cx="{x:.1f}" cy="{y0}" r="5" fill="#1565c0"/><text x="{x:.1f}" y="{y0 - 12}" text-anchor="middle" font-size="11">{int(bit)}</text>'
    paths.append(
        _write(
            root / "05_decoded_bits.svg",
            _svg("Відновлені інформаційні біти (receiver output)", body),
            result,
        )
    )

    selected = np.full((len(result.decisions), means.shape[2]), np.nan + 1j * np.nan)
    for decision in result.decisions:
        if decision.symbol_index < means.shape[0]:
            selected[decision.symbol_index] = means[decision.symbol_index, decision.target_node_id]
    for data, title, filename in (
        (
            np.abs(selected),
            "Оцінена амплітуда коефіцієнта каналу",
            "06_estimated_gain_magnitude.svg",
        ),
        (np.angle(selected), "Оцінена фаза коефіцієнта каналу", "07_estimated_gain_phase.svg"),
    ):
        body = '<path d="M60 420H1070M60 70V420" stroke="#333" fill="none"/><text x="560" y="462" text-anchor="middle" font-size="18">TCM symbol index k</text>'
        finite = data[np.isfinite(data)]
        if finite.size:
            low, high = float(finite.min()), float(finite.max())
            for path_index in range(data.shape[1]):
                values = data[:, path_index]
                mask = np.isfinite(values)
                if np.any(mask):
                    body += line(
                        values[mask],
                        ("#1565c0", "#ef6c00", "#2e7d32")[path_index % 3],
                        low,
                        high,
                        width,
                        height,
                    )
        paths.append(_write(root / filename, _svg(title, body), result))

    node_ids = np.asarray([item.target_node_id for item in result.decisions], dtype=np.float64)
    x_values = np.linspace(70, 1050, max(len(node_ids), 1))
    if node_ids.size:
        low, high = float(node_ids.min()), float(max(node_ids.max(), node_ids.min() + 1))
        y_values = 400 - (node_ids - low) / (high - low) * 300
        points = " ".join(f"{x:.1f},{y0:.1f}" for x, y0 in zip(x_values, y_values, strict=True))
        body = f'<path d="M60 420H1070M60 70V420" stroke="#333" fill="none"/><polyline fill="none" stroke="#1565c0" stroke-width="3" points="{points}"/><text x="560" y="462" text-anchor="middle" font-size="18">TCM symbol index k</text><text x="22" y="240" transform="rotate(-90 22 240)" font-size="18">Augmented node ID</text>'
        paths.append(
            _write(
                root / "08_augmented_survivor_path.svg",
                _svg("Вибраний шлях augmented trellis", body),
                result,
            )
        )

    innovations = np.asarray(result.diagnostics["innovation_energy_by_symbol_node"])
    body = '<path d="M55 60V420H390" stroke="#222" fill="none"/><text x="220" y="455" text-anchor="middle" font-size="18">Expanded node</text><text x="18" y="240" transform="rotate(-90 18 240)" font-size="18">Symbol index k</text>'
    maximum = float(np.nanmax(innovations)) if innovations.size else 1.0
    for row_index in range(innovations.shape[0]):
        for node_index, value in enumerate(innovations[row_index]):
            if np.isfinite(value):
                opacity = min(max(float(value) / max(maximum, 1e-15), 0.05), 1.0)
                body += f'<circle cx="{65 + node_index * 18}" cy="{70 + row_index * min(350 / max(innovations.shape[0], 1), 1):.2f}" r="3" fill="#00897b" opacity="{opacity:.2f}"/>'
    paths.append(
        _write(
            root / "09_survivor_innovation_map.svg",
            _svg("Інновації survivor-specific оцінювача", body),
            result,
        )
    )

    window = y[: min(y.size, 160)]
    low = float(min(window.real.min(), window.imag.min()))
    high = float(max(window.real.max(), window.imag.max()))
    body = '<path d="M60 420H1070M60 70V420" stroke="#333" fill="none"/><text x="560" y="462" text-anchor="middle" font-size="18">Absolute sample index n; first 20-symbol window</text>'
    body += line(window.real, "#1565c0", low, high, width, height)
    body += line(window.imag, "#c62828", low, high, width, height)
    paths.append(
        _write(
            root / "10_sliding_20_symbol_window.svg",
            _svg("Прийняті I/Q у першому 20-символьному вікні", body),
            result,
        )
    )

    if reference_bits is not None:
        reference = np.asarray(reference_bits, dtype=np.int8)
        if reference.shape != result.decoded_information_bits.shape:
            raise ValueError("reference_bits must match decoded bit count (evaluation only)")
        error_indices = np.flatnonzero(reference != result.decoded_information_bits)
        body = '<path d="M60 390H1070M60 80V390" stroke="#333" fill="none"/><text x="560" y="445" text-anchor="middle" font-size="18">Information bit index</text>'
        for bit_index in error_indices:
            x = 70 + 980 * bit_index / max(len(reference) - 1, 1)
            body += f'<line x1="{x:.1f}" x2="{x:.1f}" y1="100" y2="390" stroke="#c62828" stroke-width="2"/>'
        paths.append(
            _write(
                root / "11_bit_errors_evaluation_only.svg",
                _svg("Позиції бітових помилок (evaluation only)", body),
                result,
            )
        )
        if separate_decoded_bits is not None:
            separate = np.asarray(separate_decoded_bits, dtype=np.int8)
            if separate.shape != reference.shape:
                raise ValueError("separate_decoded_bits must match reference length")
            joint_errors = int(np.count_nonzero(result.decoded_information_bits != reference))
            separate_errors = int(np.count_nonzero(separate != reference))
            scale = max(joint_errors, separate_errors, 1)
            body = '<path d="M100 390H1000M100 80V390" stroke="#333" fill="none"/><text x="550" y="445" text-anchor="middle" font-size="18">Receiver arm</text>'
            for x, value, name, color in (
                (300, joint_errors, "Adaptive joint", "#1565c0"),
                (700, separate_errors, "Separate Hamming", "#ef6c00"),
            ):
                bar_height = 270 * value / scale
                body += f'<rect x="{x}" y="{390 - bar_height}" width="120" height="{bar_height}" fill="{color}"/><text x="{x + 60}" y="{375 - bar_height}" text-anchor="middle" font-size="20">{value}</text><text x="{x + 60}" y="420" text-anchor="middle" font-size="16">{name}</text>'
            paths.append(
                _write(
                    root / "14_dual_receiver_errors_evaluation_only.svg",
                    _svg("Помилки двох приймачів на одному кадрі (evaluation only)", body),
                    result,
                )
            )

    if evaluation_coefficients is not None:
        truth = np.asarray(evaluation_coefficients, dtype=np.complex128)
        if truth.ndim != 2 or truth.shape[0] != means.shape[2]:
            raise ValueError("evaluation_coefficients must have shape (paths, samples)")
        body = '<path d="M60 420H1070M60 70V420" stroke="#333" fill="none"/><text x="560" y="462" text-anchor="middle" font-size="18">TCM symbol index k</text>'
        for path_index in range(truth.shape[0]):
            sample_ids = np.minimum(np.arange(len(selected)) * 8 + 7, truth.shape[1] - 1)
            errors = np.abs(selected[:, path_index] - truth[path_index, sample_ids])
            mask = np.isfinite(errors)
            if np.any(mask):
                body += line(
                    errors[mask],
                    ("#c62828", "#1565c0", "#2e7d32")[path_index % 3],
                    0.0,
                    max(float(errors[mask].max()), 1e-12),
                    width,
                    height,
                )
        paths.append(
            _write(
                root / "12_channel_coefficient_error_evaluation_only.svg",
                _svg("Похибка оцінки коефіцієнтів (evaluation only)", body),
                result,
            )
        )
    predicted = np.asarray(result.diagnostics["predicted_samples_on_emitted_decisions"])
    valid_prediction = np.isfinite(predicted.real) & np.isfinite(predicted.imag)
    selected_indices = np.flatnonzero(valid_prediction)
    selected_indices = (
        selected_indices[
            np.linspace(
                0, len(selected_indices) - 1, min(len(selected_indices), 900), dtype=np.int64
            )
        ]
        if len(selected_indices)
        else selected_indices
    )
    if len(selected_indices):
        lo = float(
            min(
                y[selected_indices].real.min(),
                y[selected_indices].imag.min(),
                predicted[selected_indices].real.min(),
                predicted[selected_indices].imag.min(),
            )
        )
        hi = float(
            max(
                y[selected_indices].real.max(),
                y[selected_indices].imag.max(),
                predicted[selected_indices].real.max(),
                predicted[selected_indices].imag.max(),
            )
        )
        body = '<path d="M60 420H1070M60 70V420" stroke="#333" fill="none"/><text x="560" y="462" text-anchor="middle" font-size="18">Absolute receive sample index n</text>'
        for series, color in (
            (y[selected_indices].real, "#1565c0"),
            (predicted[selected_indices].real, "#ef6c00"),
            (y[selected_indices].imag, "#c62828"),
            (predicted[selected_indices].imag, "#2e7d32"),
        ):
            body += line(series, color, lo, hi, width, height)
        body += '<text x="75" y="95" font-size="15" fill="#1565c0">Observed I</text><text x="180" y="95" font-size="15" fill="#ef6c00">Predicted I</text><text x="310" y="95" font-size="15" fill="#c62828">Observed Q</text><text x="440" y="95" font-size="15" fill="#2e7d32">Predicted Q</text><text x="75" y="125" font-size="13">Predictions reconstructed after decode from local finite-depth decisions</text>'
        paths.append(
            _write(
                root / "13_predicted_vs_received_iq.svg",
                _svg("Порівняння спостережених і прогнозованих I/Q", body),
                result,
            )
        )
    return tuple(paths)


def _write(path: Path, svg: str, result: AdaptiveMultipathReceiverResult) -> Path:
    path.write_text(
        f"<!-- observation_sha256={result.observation_sha256}; result_sha256={result.result_sha256} -->\n{svg}\n",
        encoding="utf-8",
    )
    return path
