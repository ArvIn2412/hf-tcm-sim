"""Read-only system waveform view; no receiver calculations."""

from pathlib import Path

import numpy as np

from hf_tcm.studio.scientific import load_run_summary, trace_window


def system_signal(root: Path, start: int, count: int, symbol: int, bins: int = 1000) -> dict:
    summary = load_run_summary(root)
    total = summary["sample_count"]
    if not 0 <= start < total or count < 1 or not 0 <= symbol < summary["frame_symbols"]:
        raise ValueError("signal position outside frame")
    stop = min(total, start + count)
    bins = max(32, min(2000, bins))
    width = max(1, int(np.ceil((stop - start) / bins)))
    with np.load(root / "traces.npz", allow_pickle=False) as data:
        tx, rx, noise = data["tx_samples"], data["received_samples"], data["noise_samples"]
        components = {
            "TX I": tx.real,
            "TX Q": tx.imag,
            "RX I": rx.real,
            "RX Q": rx.imag,
            "Шум I": noise.real,
            "Шум Q": noise.imag,
        }
        for i, path in enumerate(data["path_contributions"]):
            components[f"Промінь {i + 1} I"] = path.real
            components[f"Промінь {i + 1} Q"] = path.imag
        series = {}
        for name, values in components.items():
            series[name] = [
                [
                    i,
                    float(np.min(values[i : min(i + width, stop, len(values))])),
                    float(np.max(values[i : min(i + width, stop, len(values))])),
                ]
                for i in range(start, min(stop, len(values)), width)
            ]
        indices = np.unique(
            np.append(np.linspace(start, stop - 1, min(bins, stop - start), dtype=int), symbol * 8)
        )
        cloud = [[int(i), float(rx[i].real), float(rx[i].imag)] for i in indices if i < len(rx)]
    return {
        "start": start,
        "stop": stop,
        "total": total,
        "raw": width == 1,
        "series": series,
        "cloud": cloud,
        "selected": trace_window(root, start_symbol=symbol, symbol_count=1),
    }
