"""M0 acceptance checks: importing the project must work."""

import importlib

import hf_tcm


def test_version() -> None:
    assert hf_tcm.__version__ == "0.1.0"


def test_public_packages_import() -> None:
    for module in (
        "coding",
        "modulation",
        "channels",
        "receiver",
        "decoding",
        "simulation",
        "analysis",
        "utils",
    ):
        assert importlib.import_module(f"hf_tcm.{module}") is not None
