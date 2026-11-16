"""Small, honest command line interface for milestone M0 only."""

import argparse
import platform
import sys
from collections.abc import Sequence

from hf_tcm import __version__
from hf_tcm.config import ConfigurationError, load_scaffold_config


def build_parser() -> argparse.ArgumentParser:
    """Create the M0 CLI; simulations are intentionally unavailable."""
    parser = argparse.ArgumentParser(prog="hf-tcm", description="HF-TCM-SIM project scaffold")
    parser.add_argument("--version", action="version", version=f"hf-tcm {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check Python version and print project status")
    check = sub.add_parser("check-config", help="Validate a scaffold-only JSON config")
    check.add_argument("path", help="Path to an M0 JSON config")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a lightweight CLI command; returns an exit code."""
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        supported = sys.version_info >= (3, 11)
        print(f"HF-TCM-SIM {__version__} | Python {platform.python_version()}")
        print("M3 channel model core ready; experiment CLI runner not implemented.")
        print("Next milestone: M4 (blocked on open SCI-02 through SCI-04).")
        if not supported:
            print("ERROR: Python >= 3.11 is required", file=sys.stderr)
            return 1
        return 0
    if args.command == "check-config":
        try:
            load_scaffold_config(args.path)
        except ConfigurationError as exc:
            print(f"Invalid config: {exc}", file=sys.stderr)
            return 2
        print("Valid M0 scaffold config (no simulation was performed).")
        return 0
    return 2
