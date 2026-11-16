"""Small dependency-free SVG plots for measured REPRO-07 trial records."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import numpy as np


def _svg(title: str, body: str, *, width: int = 1050, height: int = 620) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="white"/>'
        f'<text x="{width / 2}" y="36" text-anchor="middle" font-family="sans-serif" '
        f'font-size="25">{html.escape(title)}</text>{body}</svg>'
    )


def _axes(x_label: str, y_label: str, *, xmin: float, xmax: float, ymin: float, ymax: float) -> str:
    x0, x1, y0, y1 = 100.0, 1000.0, 530.0, 80.0
    return (
        f'<path d="M{x0} {y0}H{x1}M{x0} {y0}V{y1}" stroke="#202a35" stroke-width="2"/>'
        f'<text x="550" y="590" text-anchor="middle" font-size="19">{html.escape(x_label)}</text>'
        f'<text x="27" y="305" transform="rotate(-90 27 305)" text-anchor="middle" '
        f'font-size="19">{html.escape(y_label)}</text>'
        f'<text x="{x0 - 8}" y="{y0 + 25}" text-anchor="end" font-size="14">{ymin:.4g}</text>'
        f'<text x="{x0 - 8}" y="{y1 + 5}" text-anchor="end" font-size="14">{ymax:.4g}</text>'
        f'<text x="{x0}" y="{y0 + 22}" text-anchor="middle" font-size="14">{xmin:.4g}</text>'
        f'<text x="{x1}" y="{y0 + 22}" text-anchor="middle" font-size="14">{xmax:.4g}</text>'
    )


def _point_plot(
    title: str,
    x_label: str,
    y_label: str,
    xs: list[float],
    series: list[tuple[str, list[float], str]],
    output: Path,
    *,
    zero_note: bool = False,
) -> None:
    if not xs:
        output.write_text(
            _svg(title, '<text x="90" y="120" font-size="20">Немає завершених вимірювань</text>'),
            encoding="utf-8",
        )
        return
    values = [v for _, ys, _ in series for v in ys if v == v]
    ymax = max(values, default=1.0)
    if ymax <= 0:
        ymax = 1.0
    ymin = min(0.0, *values) if values else 0.0
    pad = max((ymax - ymin) * 0.08, 1e-12)
    ymin -= pad
    ymax += pad
    xmin, xmax = min(xs), max(xs)
    if xmin == xmax:
        xmax = xmin + 1.0
    x0, x1, y0, y1 = 100.0, 1000.0, 530.0, 80.0
    body = _axes(x_label, y_label, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
    legend_y = 75
    for index, (label, ys, color) in enumerate(series):
        points: list[str] = []
        for x, y in zip(xs, ys, strict=True):
            px = x0 + (x - xmin) / (xmax - xmin) * (x1 - x0)
            py = y0 - (y - ymin) / (ymax - ymin) * (y0 - y1)
            points.append(f"{px:.2f},{py:.2f}")
            body += f'<circle cx="{px:.2f}" cy="{py:.2f}" r="7" fill="{color}"/>'
            if zero_note and y == 0:
                body += (
                    f'<text x="{px + 9:.2f}" y="{py - 8:.2f}" font-size="13">0 (виміряно)</text>'
                )
        if len(points) > 1:
            body += f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="3"/>'
        body += (
            f'<path d="M720 {legend_y + index * 25}h28" stroke="{color}" stroke-width="4"/>'
            f'<text x="755" y="{legend_y + 5 + index * 25}" font-size="15">{html.escape(label)}</text>'
        )
    output.write_text(_svg(title, body), encoding="utf-8")


def write_experiment_plots(
    summary: dict[str, Any], trial_records: list[dict[str, Any]], output_dir: str | Path
) -> tuple[Path, ...]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    points = [p for p in summary["points"] if p.get("completed_trials", 0)]
    xs = [float(p["noise_variance_complex_per_sample"]) for p in points]
    files: list[Path] = []
    for name, ylabel, akey, bkey in (
        ("01_ber_vs_noise_variance.svg", "BER інформаційних бітів", "joint_ber", "separate_ber"),
        (
            "02_pair_ser_vs_noise_variance.svg",
            "SER інформаційних пар",
            "joint_pair_ser",
            "separate_pair_ser",
        ),
    ):
        path = root / name
        _point_plot(
            "Виміряні BER/SER залежно від дисперсії шуму",
            "E[|w[n]|²], комплексна дисперсія шуму на відлік (sample-domain)",
            ylabel,
            xs,
            [
                ("Joint Euclidean (06C)", [float(p[akey]) for p in points], "#1769aa"),
                ("Separate Hamming (04)", [float(p[bkey]) for p in points], "#d84315"),
            ],
            path,
            zero_note=True,
        )
        files.append(path)
    if not points:
        path = root / "03_delta_ber_paired_cluster_ci.svg"
        path.write_text(
            _svg(
                "Парна різниця BER та trial-bootstrap довірчі інтервали",
                '<text x="90" y="120" font-size="20">Немає завершених вимірювань</text>',
            ),
            encoding="utf-8",
        )
        files.append(path)
        deltas: list[float] = []
        lows: list[float | None] = []
        highs: list[float | None] = []
        xs = []
    else:
        deltas = [float(p["delta_ber_joint_minus_separate"]) for p in points]
        lows = []
        highs = []
        for point in points:
            interval = point["confidence_intervals"].get("delta_ber_ci")
            lows.append(None if interval is None else interval[0])
            highs.append(None if interval is None else interval[1])
    if points:
        xmin, xmax = min(xs), max(xs)
        if xmin == xmax:
            xmax = xmin + 1.0
        extent = (
            max([abs(v) for v in deltas + [v for v in lows + highs if v is not None]] + [1e-9])
            * 1.15
        )
        body = _axes(
            "E[|w[n]|²], комплексна дисперсія шуму на відлік",
            "ΔBER = BER Joint − BER Separate",
            xmin=xmin,
            xmax=xmax,
            ymin=-extent,
            ymax=extent,
        )
        x0, x1, y0, y1 = 100.0, 1000.0, 530.0, 80.0
        zero_y = y0 - (0 - (-extent)) / (2 * extent) * (y0 - y1)
        body += f'<path d="M{x0} {zero_y:.2f}H{x1}" stroke="#555" stroke-dasharray="8 6"/>'
        for x, value, low, high in zip(xs, deltas, lows, highs, strict=True):
            if low is None or high is None:
                continue
            px = x0 + (x - xmin) / (xmax - xmin) * (x1 - x0)
            py = y0 - (value + extent) / (2 * extent) * (y0 - y1)
            pylo = y0 - (float(low) + extent) / (2 * extent) * (y0 - y1)
            pyhi = y0 - (float(high) + extent) / (2 * extent) * (y0 - y1)
            body += f'<path d="M{px:.2f} {pylo:.2f}V{pyhi:.2f}" stroke="#4527a0" stroke-width="3"/>'
            body += f'<circle cx="{px:.2f}" cy="{py:.2f}" r="7" fill="#4527a0"/>'
        path = root / "03_delta_ber_paired_cluster_ci.svg"
        path.write_text(
            _svg("Парна різниця BER та trial-bootstrap довірчі інтервали", body), encoding="utf-8"
        )
        files.append(path)

    completed = sorted(
        (r for r in trial_records if r.get("status") == "completed"),
        key=lambda r: (r["point_index"], r["trial_index"]),
    )
    diffs = [r["joint_bit_errors"] - r["separate_bit_errors"] for r in completed]
    if diffs:
        lo, hi = min(diffs), max(diffs)
        if lo == hi:
            hi = lo + 1
        bins = min(20, max(4, int(len(diffs) ** 0.5)))
        counts = [0] * bins
        for value in diffs:
            idx = min(bins - 1, int((value - lo) / (hi - lo) * bins))
            counts[idx] += 1
        max_count = max(counts) or 1
        body = _axes(
            "Різниця кількості помилок у парі (Joint − Separate)",
            "Кількість парних trial-ів",
            xmin=lo,
            xmax=hi,
            ymin=0,
            ymax=max_count,
        )
        for i, count in enumerate(counts):
            x = 120 + i * 850 / bins
            h = count / max_count * 410
            body += f'<rect x="{x:.2f}" y="{530 - h:.2f}" width="{850 / bins - 2:.2f}" height="{h:.2f}" fill="#00897b"/>'
    else:
        body = '<text x="80" y="100" font-size="20">Немає завершених trial-ів</text>'
    path = root / "04_paired_error_difference_distribution.svg"
    path.write_text(
        _svg("Розподіл парних різниць кількості бітових помилок", body), encoding="utf-8"
    )
    files.append(path)

    running: dict[int, tuple[int, int]] = {}
    cumulative: list[tuple[int, int, int]] = []
    for row in completed:
        point = int(row["point_index"])
        ja, sb = running.get(point, (0, 0))
        ja += int(row["joint_bit_errors"])
        sb += int(row["separate_bit_errors"])
        running[point] = (ja, sb)
        cumulative.append(
            (
                len(
                    [
                        r
                        for r in completed
                        if r["point_index"] == point and r["trial_index"] <= row["trial_index"]
                    ]
                ),
                ja,
                sb,
            )
        )
    if cumulative:
        maxerr = max([v for _, a, b in cumulative for v in (a, b)] + [1])
        body = _axes(
            "Завершений парний trial (послідовно у файлі)",
            "Накопичена кількість помилок",
            xmin=1,
            xmax=max(1, len(cumulative)),
            ymin=0,
            ymax=maxerr,
        )
        body += '<text x="720" y="75" font-size="15" fill="#1769aa">Joint</text><text x="800" y="75" font-size="15" fill="#d84315">Separate</text>'
        for idx, (_, ja, sb) in enumerate(cumulative):
            px = 100 + (idx / max(1, len(cumulative) - 1)) * 900
            body += f'<circle cx="{px:.1f}" cy="{530 - ja / maxerr * 450:.1f}" r="3" fill="#1769aa"/><circle cx="{px:.1f}" cy="{530 - sb / maxerr * 450:.1f}" r="3" fill="#d84315"/>'
    else:
        body = '<text x="80" y="100" font-size="20">Немає завершених trial-ів</text>'
    path = root / "05_cumulative_errors_by_trial.svg"
    path.write_text(
        _svg("Накопичення помилок у завершених парних trial-ах", body), encoding="utf-8"
    )
    files.append(path)

    times_a = [float(r["joint_seconds"]) for r in completed]
    times_b = [float(r["separate_seconds"]) for r in completed]
    if completed:
        txs = list(range(1, len(completed) + 1))
        path = root / "06_receiver_runtime_by_trial.svg"
        _point_plot(
            "Виміряний час обробки приймачами",
            "Парний trial ID у відсортованому порядку",
            "Час, s",
            [float(x) for x in txs],
            [("Joint Euclidean", times_a, "#1769aa"), ("Separate Hamming", times_b, "#d84315")],
            path,
        )
    else:
        path = root / "06_receiver_runtime_by_trial.svg"
        path.write_text(
            _svg(
                "Виміряний час обробки приймачами",
                '<text x="80" y="100">Немає завершених trial-ів</text>',
            ),
            encoding="utf-8",
        )
    files.append(path)
    return tuple(files)


def write_selected_trial_plots(
    trial_directory: str | Path, output_directory: str | Path
) -> tuple[Path, ...]:
    """Write evaluation-only plots for a selected trial with saved diagnostics."""
    trial_root = Path(trial_directory)
    archive = trial_root / "diagnostics.npz"
    if not archive.is_file():
        return ()
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    with np.load(archive, allow_pickle=False) as arrays:
        received = np.asarray(arrays["received_samples"])
        decoded_joint = np.asarray(arrays["joint_decoded_bits"])
        decoded_separate = np.asarray(arrays["separate_decoded_bits"])
        reference = np.asarray(arrays["reference_bits"])
        means = (
            np.asarray(arrays["joint_estimator_mean"])
            if "joint_estimator_mean" in arrays.files
            else None
        )

    sample_ids = np.linspace(0, received.size - 1, min(1200, received.size), dtype=np.int64)
    xvals = np.linspace(100, 1000, sample_ids.size)
    low = float(min(received[sample_ids].real.min(), received[sample_ids].imag.min()))
    high = float(max(received[sample_ids].real.max(), received[sample_ids].imag.max()))
    span = high - low or 1.0
    pi = " ".join(
        f"{x:.1f},{530 - (float(v.real) - low) / span * 450:.1f}"
        for x, v in zip(xvals, received[sample_ids], strict=True)
    )
    pq = " ".join(
        f"{x:.1f},{530 - (float(v.imag) - low) / span * 450:.1f}"
        for x, v in zip(xvals, received[sample_ids], strict=True)
    )
    body = _axes(
        "Абсолютний індекс прийнятого відліку n",
        "Комплексна огинаюча I/Q",
        xmin=0,
        xmax=max(1, received.size - 1),
        ymin=low,
        ymax=high,
    )
    body += f'<polyline points="{pi}" fill="none" stroke="#1769aa" stroke-width="2"/>'
    body += f'<polyline points="{pq}" fill="none" stroke="#d84315" stroke-width="2"/>'
    body += '<text x="760" y="75" font-size="15" fill="#1769aa">I received</text>'
    body += '<text x="870" y="75" font-size="15" fill="#d84315">Q received</text>'
    iq_path = output / "07_selected_trial_received_iq.svg"
    iq_path.write_text(_svg("Вибраний trial: прийнятий сигнал I/Q", body), encoding="utf-8")

    err_a = np.flatnonzero(decoded_joint != reference)
    err_b = np.flatnonzero(decoded_separate != reference)
    body = _axes(
        "Індекс інформаційного біта",
        "Помилка (позначка = одна помилка)",
        xmin=0,
        xmax=max(1, reference.size - 1),
        ymin=0,
        ymax=1,
    )
    for color, errors, label, y in (
        ("#1769aa", err_a, "Joint", 210),
        ("#d84315", err_b, "Separate", 390),
    ):
        body += f'<text x="105" y="{y - 8}" font-size="15" fill="{color}">{label}</text>'
        for index in errors:
            px = 110 + float(index) / max(1, reference.size - 1) * 880
            body += f'<path d="M{px:.1f} {y}v45" stroke="{color}" stroke-width="3"/>'
    error_path = output / "08_selected_trial_bit_error_positions.svg"
    error_path.write_text(
        _svg("Вибраний trial: evaluation-only позиції бітових помилок", body),
        encoding="utf-8",
    )

    if means is None:
        return iq_path, error_path

    means_by_time = np.full((means.shape[0], means.shape[2]), np.nan + 1j * np.nan)
    for t in range(means.shape[0]):
        for path_index in range(means.shape[2]):
            values = means[t, :, path_index]
            values = values[np.isfinite(values.real)]
            if values.size:
                means_by_time[t, path_index] = np.mean(values)
    finite = means_by_time[np.isfinite(means_by_time.real)]
    low = float(min(finite.real.min(), finite.imag.min())) if finite.size else -1.0
    high = float(max(finite.real.max(), finite.imag.max())) if finite.size else 1.0
    span = high - low or 1.0
    body = _axes(
        "TCM-символ k",
        "Оцінений коефіцієнт, I/Q",
        xmin=0,
        xmax=max(1, means.shape[0] - 1),
        ymin=low,
        ymax=high,
    )
    xs = np.linspace(100, 1000, means.shape[0])
    colors = ("#1769aa", "#00897b", "#d84315", "#8e24aa")
    for path_index in range(means.shape[2]):
        for component, color in (
            ("real", colors[(2 * path_index) % len(colors)]),
            ("imag", colors[(2 * path_index + 1) % len(colors)]),
        ):
            sequence = getattr(means_by_time[:, path_index], component)
            points = []
            for x, value in zip(xs, sequence, strict=True):
                if np.isfinite(value):
                    y = 530 - (float(value) - low) / span * 450
                    points.append(f"{x:.1f},{y:.1f}")
            if points:
                body += f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2"/>'
    body += '<text x="590" y="75" font-size="14">I/Q — середнє оцінок активних survivor nodes для кожного променя</text>'
    estimate_path = output / "09_selected_trial_survivor_estimates.svg"
    estimate_path.write_text(
        _svg("Вибраний trial: діагностика estimator bank", body), encoding="utf-8"
    )
    return iq_path, error_path, estimate_path
