from pathlib import Path

import numpy as np
import pytest

from hf_tcm.studio import system_signal as adapter


def test_system_signal_lod_preserves_extrema_and_last_sample(tmp_path: Path, monkeypatch):
    values = np.arange(1600, dtype=float)
    np.savez(
        tmp_path / "traces.npz",
        tx_samples=values.astype(complex),
        received_samples=values + 1j * values,
        noise_samples=1j * values,
        path_contributions=np.asarray([values.astype(complex)]),
    )
    monkeypatch.setattr(
        adapter, "load_run_summary", lambda root: {"sample_count": 1600, "frame_symbols": 200}
    )
    monkeypatch.setattr(adapter, "trace_window", lambda root, **kw: kw)
    view = adapter.system_signal(tmp_path, 0, 1600, 199, bins=32)
    assert view["raw"] is False
    assert view["series"]["RX I"][-1] == [1550, 1550.0, 1599.0]
    assert view["cloud"][-1][0] == 1599
    assert view["selected"]["start_symbol"] == 199
    exact = adapter.system_signal(tmp_path, 1592, 8, 199)
    assert exact["raw"] is True
    assert exact["series"]["RX Q"][-1] == [1599, 1599.0, 1599.0]
    with pytest.raises(ValueError):
        adapter.system_signal(tmp_path, 1600, 8, 199)
