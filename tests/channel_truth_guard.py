"""Static AST guard for the estimated receiver and decoder source boundary."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "hf_tcm"
PROTECTED_DIRECTORIES = (SOURCE_ROOT / "receiver", SOURCE_ROOT / "decoding")
PROTECTED_CODING_MODULES = (
    SOURCE_ROOT / "coding" / "hypotheses.py",
    SOURCE_ROOT / "coding" / "posterior.py",
    SOURCE_ROOT / "coding" / "likelihood.py",
)

CHANNEL_GENERATOR_IMPORTS = {
    "apply_multipath",
    "generate_rician_coefficients",
    "generate_fluctuating_noise",
}


@dataclass(frozen=True, slots=True)
class Violation:
    """One statically detected forbidden reference in a protected module."""

    rule: str
    line: int
    detail: str


def is_protected_module(path: Path) -> bool:
    """Return whether path belongs to estimated/decision production code.

    All current and future Python modules under ``receiver/`` and
    ``decoding/`` are protected. The coding inference modules are listed
    explicitly; simulator, channel, analysis, and test code are out of scope.
    """
    resolved = path.resolve()
    if any(resolved.is_relative_to(directory.resolve()) for directory in PROTECTED_DIRECTORIES):
        return resolved.suffix == ".py"
    return resolved in {module.resolve() for module in PROTECTED_CODING_MODULES}


def protected_sources() -> tuple[Path, ...]:
    """Enumerate the current source boundary, including new receiver modules."""
    paths = {path for directory in PROTECTED_DIRECTORIES for path in directory.rglob("*.py")}
    paths.update(module for module in PROTECTED_CODING_MODULES if module.is_file())
    return tuple(sorted(paths))


def _module_name(node: ast.expr) -> str:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def audit_source(path: Path, source: str) -> tuple[Violation, ...]:
    """Find forbidden truth/generator-state references within the boundary.

    The check is intentionally static and scoped. It does not inspect simulator,
    oracle, or test modules, even if those modules legitimately use channel
    truth for generation or evaluation.
    """
    if not is_protected_module(path):
        return ()

    tree = ast.parse(source, filename=str(path))
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "ChannelTruth":
            violations.append(
                Violation("channel-truth-name", node.lineno, "ChannelTruth reference")
            )

        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if module.startswith("hf_tcm.channels") and alias.name == "ChannelTruth":
                    violations.append(
                        Violation(
                            "channel-truth-import",
                            node.lineno,
                            f"import of {module}.{alias.name}",
                        )
                    )
                if module.startswith("hf_tcm.channels") and alias.name in CHANNEL_GENERATOR_IMPORTS:
                    violations.append(
                        Violation(
                            "channel-generator-import",
                            node.lineno,
                            f"import of channel generator {module}.{alias.name}",
                        )
                    )

        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "hf_tcm.channels.multipath.ChannelTruth":
                    violations.append(
                        Violation(
                            "channel-truth-import",
                            node.lineno,
                            f"import of {alias.name}",
                        )
                    )

        if isinstance(node, ast.Attribute):
            if node.attr == "ChannelTruth":
                violations.append(
                    Violation("channel-truth-name", node.lineno, f"attribute {_module_name(node)}")
                )
            if node.attr == "truth":
                violations.append(
                    Violation("truth-attribute", node.lineno, f"attribute {_module_name(node)}")
                )
            if node.attr == "state" and isinstance(node.value, ast.Attribute):
                if node.value.attr == "bit_generator":
                    violations.append(
                        Violation(
                            "generator-state-access",
                            node.lineno,
                            f"attribute {_module_name(node)}",
                        )
                    )
            if node.attr in {"get_state", "getstate"}:
                violations.append(
                    Violation(
                        "generator-state-access",
                        node.lineno,
                        f"generator state method {_module_name(node)}",
                    )
                )
            if node.attr in CHANNEL_GENERATOR_IMPORTS:
                violations.append(
                    Violation(
                        "channel-generator-call",
                        node.lineno,
                        f"channel generator reference {_module_name(node)}",
                    )
                )

    return tuple(sorted(violations, key=lambda item: (item.line, item.rule, item.detail)))
