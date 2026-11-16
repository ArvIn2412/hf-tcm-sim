"""Profile the original read-only historical HTTP loader; no simulation calls."""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import logging
import pstats
import threading
import time
import urllib.request
from pathlib import Path

from hf_tcm.studio import server as module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", choices=("before", "after"), default="after")
    label = parser.parse_args().label
    out = Path("outputs/release_readiness")
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, filename=out / f"exp01b_{label}.log", encoding="utf-8")
    events = []
    done = threading.Event()
    original = module.load_historical_exp01b_energy_study

    def loader():
        began = time.perf_counter()
        print("EXP01B loader started", flush=True)
        profile = cProfile.Profile()
        try:
            return profile.runcall(original)
        finally:
            stream = io.StringIO()
            pstats.Stats(profile, stream=stream).sort_stats("cumulative").print_stats(35)
            (out / f"exp01b_{label}_profile.txt").write_text(stream.getvalue(), encoding="utf-8")
            events.append({"phase": "loader", "seconds": time.perf_counter() - began})
            print(json.dumps(events[-1]), flush=True)
            done.set()

    module.load_historical_exp01b_energy_study = loader
    server = module.make_server(port=0, default_view="scientific")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{server.server_port}"
    began = time.perf_counter()
    try:
        with urllib.request.urlopen(
            address + "/api/scientific/energy-studies/historical/exp01b-static-amplitude-005",
            timeout=30,
        ) as response:
            payload = json.load(response)
        events.append(
            {
                "phase": "client",
                "seconds": time.perf_counter() - began,
                "status": "PASS",
                "trials": payload["completed_trials"],
            }
        )
    except (OSError, TimeoutError) as error:
        events.append(
            {
                "phase": "client",
                "seconds": time.perf_counter() - began,
                "status": "TIMEOUT_OR_IO_ERROR",
                "error": str(error),
            }
        )
    print(json.dumps(events[-1]), flush=True)
    try:
        health_began = time.perf_counter()
        with urllib.request.urlopen(address + "/api/health", timeout=5) as response:
            health = json.load(response)
        events.append(
            {
                "phase": "concurrent_health",
                "seconds": time.perf_counter() - health_began,
                "result": health,
            }
        )
        if not done.wait(300):
            events.append({"phase": "loader", "status": "NOT_FINISHED_WITHIN_DIAGNOSTIC_BUDGET"})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
        (out / f"exp01b_{label}.json").write_text(json.dumps(events, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
