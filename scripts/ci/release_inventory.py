"""Read-only Git inventory; never stage, remove, commit or publish files."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def main() -> None:
    changed = set(git("diff", "HEAD", "--name-only", "-z").decode("utf-8").strip("\0").split("\0"))
    changed.update(
        git("ls-files", "--others", "--exclude-standard", "-z")
        .decode("utf-8")
        .strip("\0")
        .split("\0")
    )
    tracked = git("ls-files", "-z").decode("utf-8").strip("\0").split("\0")
    binary_research = {".zip", ".7z", ".pdf", ".doc", ".docx", ".rtf", ".npz", ".xlsx", ".pptx"}
    allowed = {
        ".py",
        ".js",
        ".mjs",
        ".css",
        ".html",
        ".md",
        ".ps1",
        ".cmd",
        ".toml",
        ".yml",
        ".yaml",
    }
    candidates, blocked = [], []
    for name in sorted(changed - {""}):
        path = Path(name)
        reason = None
        if name.startswith(("outputs/", "tmp/", ".historical-input/")):
            reason = "generated_or_historical_artifact"
        elif path.suffix.lower() not in allowed and name != ".gitignore":
            reason = "not_in_source_allowlist"
        elif path.exists() and path.stat().st_size > 2 * 1024 * 1024:
            reason = "exceeds_source_size_budget"
        if reason:
            blocked.append({"path": name, "reason": reason})
        else:
            candidates.append(
                {
                    "path": name,
                    "bytes": path.stat().st_size if path.exists() else 0,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
                    if path.is_file()
                    else None,
                }
            )
    result = {
        "head": git("rev-parse", "HEAD").decode().strip(),
        "scope": "all current uncommitted files, including inherited stage-4 work",
        "candidate_source_files": candidates,
        "blocked_changed_files": blocked,
        "already_tracked_documents_requiring_publication_review": [
            name for name in tracked if Path(name).suffix.lower() in binary_research
        ],
        "staged_files": git("diff", "--cached", "--name-only", "-z")
        .decode("utf-8")
        .strip("\0")
        .split("\0")
        if git("diff", "--cached", "--name-only")
        else [],
        "source_inventory_status": "PASS" if not blocked else "REVIEW_REQUIRED",
        "commit_or_push_performed": False,
    }
    output = Path("outputs/release_readiness")
    output.mkdir(parents=True, exist_ok=True)
    (output / "git_inventory.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "candidates": len(candidates),
                "blocked": len(blocked),
                "preexisting_document_count": len(
                    result["already_tracked_documents_requiring_publication_review"]
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
