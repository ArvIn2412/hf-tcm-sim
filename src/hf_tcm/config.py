"""M0-only configuration validation; no simulation parameters are inferred."""

import json
from pathlib import Path
from typing import Any


class ConfigurationError(ValueError):
    """Invalid scaffold configuration (not a scientific model error)."""


def load_scaffold_config(path: str | Path) -> dict[str, Any]:
    """Read a minimal M0 JSON config; deliberately rejects simulation mode."""
    file_path = Path(path)
    try:
        with file_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Cannot read configuration {file_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigurationError("Configuration must be a JSON object")
    required = {"schema_version": 1, "project": "HF-TCM-SIM", "kind": "scaffold"}
    for key, expected in required.items():
        if data.get(key) != expected or type(data.get(key)) is not type(expected):
            raise ConfigurationError(f"{key} must be {expected!r}")
    if data.get("simulator_enabled") is not False:
        raise ConfigurationError("M0 configuration must disable simulation")
    if set(data) != set(required) | {"simulator_enabled"}:
        raise ConfigurationError("Unexpected or missing M0 configuration keys")
    return data
