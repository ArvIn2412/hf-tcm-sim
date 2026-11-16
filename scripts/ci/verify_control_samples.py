"""Compare the existing N=20000 HTTP inspector/cloud with its original NPZ."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np


def main() -> None:
    folder = Path("outputs/scientific-exp03a/metric-studies/stage3-control-20000")
    array_path = folder / "trials/p000-t0000.npz"
    record = json.loads((folder / "trials/p000-t0000.json").read_text(encoding="utf-8"))
    checksum = hashlib.sha256(array_path.read_bytes()).hexdigest()
    assert checksum == record["array_file_sha256"]
    base = os.environ.get("HF_TCM_QA_BASE_URL", "http://127.0.0.1:18773")

    def window(**values):
        query = urllib.parse.urlencode({"study_id": folder.name, **values})
        with urllib.request.urlopen(
            base + "/api/scientific/lab-window?" + query, timeout=10
        ) as response:
            assert response.headers.get_content_charset() == "utf-8"
            return json.load(response)

    with np.load(array_path, allow_pickle=False) as arrays:
        tx, rx = arrays["transmitted_samples"], arrays["received_samples"]
        assert len(tx) == 160000
        checked = []
        for sample in (0, 7999, 8000, 159998, 159999):
            result = window(start=max(0, sample - 8), count=16, selected=sample)
            value = result["inspector"]
            assert value["sample"] == sample
            assert (value["tx_i"], value["tx_q"], value["rx_i"], value["rx_q"]) == (
                tx[sample].real,
                tx[sample].imag,
                rx[sample].real,
                rx[sample].imag,
            )
            checked.append(sample)
        full = window(start=0, count=160000, selected=159999)
        assert not full["series"]["RX I"]["raw"]
        for point in full["cloud"]:
            assert (point["i"], point["q"]) == (rx[point["sample"]].real, rx[point["sample"]].imag)
    summary = {
        "status": "PASS",
        "inspector_samples": checked,
        "cloud_points": len(full["cloud"]),
        "npz_sha256": checksum,
        "new_simulations": 0,
    }
    Path("outputs/release_readiness/control_sample_verification.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
