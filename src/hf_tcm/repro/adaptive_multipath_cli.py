"""Explicit REPRO-06C adaptive receiver CLI; importing this module runs nothing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hf_tcm.repro.adaptive_multipath_config import AdaptiveMultipathReceiverConfig
from hf_tcm.repro.adaptive_multipath_io import save_adaptive_result
from hf_tcm.repro.adaptive_multipath_receiver import run_adaptive_multipath_receiver
from hf_tcm.repro.receiver_io import load_receiver_observation


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the REPRO-06C adaptive multipath receiver")
    parser.add_argument("--config", required=True, help="receiver configuration JSON")
    parser.add_argument("--input", required=True, help="REPRO-03 public observation directory")
    parser.add_argument("--output", required=True, help="new REPRO-06C output directory")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()
    config = AdaptiveMultipathReceiverConfig.from_json(
        Path(args.config).read_text(encoding="utf-8")
    )
    observation = load_receiver_observation(args.input)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "valid": True,
                    "observation_sha256": observation.sha256,
                    "receiver_config": config.to_dict(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    result = run_adaptive_multipath_receiver(observation, config)
    files = save_adaptive_result(result, args.output)
    summary = {
        "observation_sha256": result.observation_sha256,
        "result_sha256": result.result_sha256,
        "decoded_bits": int(result.decoded_information_bits.size),
        "trellis": [result.trellis_state_count, result.trellis_edge_count],
        "output_files": files,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
