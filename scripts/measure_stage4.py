"""Measure read-only API responses and Python RSS without new simulations."""

import json
import time
import urllib.request
from pathlib import Path


def main() -> None:
    samples = []
    for start, count in ((0, 160), (159840, 160), (0, 160000), (40000, 800)):
        address = (
            "http://127.0.0.1:18772/api/scientific/lab-window?"
            f"study_id=stage3-control-20000&start={start}&count={count}&selected={start}"
        )
        began = time.perf_counter()
        with urllib.request.urlopen(address) as response:
            data = response.read()
            charset = response.headers.get_content_charset()
        value = json.loads(data)
        samples.append(
            dict(
                start=start,
                count=count,
                bytes=len(data),
                ms=(time.perf_counter() - began) * 1000,
                charset=charset,
                buckets=len(value["series"]["RX I"]["points"]),
            )
        )
    # GetProcessMemoryInfo is measured in the server process via its OS PID.
    result = {"N": 20000, "n": 8, "api": samples, "server_rss": "NOT_MEASURED"}
    Path("outputs/ui_interactivity_stage4/api_performance.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
