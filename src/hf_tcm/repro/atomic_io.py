"""Small same-directory atomic writes resilient to transient Windows locks."""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path


def atomic_replace_bytes(
    destination: str | os.PathLike[str],
    payload: bytes,
    *,
    replace_fn: Callable[[str | os.PathLike[str], str | os.PathLike[str]], None] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_attempts: int = 8,
    initial_delay_seconds: float = 0.05,
) -> None:
    """Write bytes to a sibling temporary file, fsync, then atomically replace.

    Only transient ``PermissionError`` from the final replace is retried.
    A unique temporary path avoids collisions between concurrent writers.
    """
    target = Path(destination)
    replace_fn = replace_fn or os.replace
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")
    if initial_delay_seconds < 0:
        raise ValueError("initial_delay_seconds must be nonnegative")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f"{target.name}.", suffix=".pending", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(max_attempts):
            try:
                replace_fn(temporary, target)
                return
            except PermissionError:
                if attempt + 1 == max_attempts:
                    raise
                sleep_fn(min(initial_delay_seconds * (2**attempt), 1.0))
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except PermissionError:
            # A leftover uniquely named pending file is ignored by manifests.
            pass

