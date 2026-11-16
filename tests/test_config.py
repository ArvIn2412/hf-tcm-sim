"""The M0 configuration may not accidentally enable a non-existent simulator."""

import json
from pathlib import Path

import pytest

from hf_tcm.config import ConfigurationError, load_scaffold_config


@pytest.fixture
def sample_config(tmp_path: Path) -> Path:
    target = tmp_path / "config.json"
    target.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project": "HF-TCM-SIM",
                "kind": "scaffold",
                "simulator_enabled": False,
            }
        ),
        encoding="utf-8",
    )
    return target


def test_valid_scaffold_config(sample_config: Path) -> None:
    assert load_scaffold_config(sample_config)["simulator_enabled"] is False


def test_disallow_simulation(sample_config: Path) -> None:
    data = json.loads(sample_config.read_text(encoding="utf-8"))
    data["simulator_enabled"] = True
    sample_config.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="disable simulation"):
        load_scaffold_config(sample_config)


def test_bad_json(sample_config: Path) -> None:
    sample_config.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Cannot read"):
        load_scaffold_config(sample_config)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="Cannot read"):
        load_scaffold_config(tmp_path / "missing.json")


def test_unexpected_science_parameter(sample_config: Path) -> None:
    data = json.loads(sample_config.read_text(encoding="utf-8"))
    data["rician_k_linear"] = 999
    sample_config.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Unexpected"):
        load_scaffold_config(sample_config)
