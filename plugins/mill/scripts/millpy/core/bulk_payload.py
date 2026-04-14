"""
bulk_payload.py — Build a line-numbered file-content payload for bulk review prompts.

Zero git imports. This module reads files from disk only. The git-diff helper
that drives file selection lives in core/git_ops.py (a sibling module), which
makes the "no git imports here" invariant trivially grep-enforceable.
"""
from __future__ import annotations

from pathlib import Path


def build_payload(paths: list[Path], *, base_dir: Path) -> str:
    """Build a line-numbered concatenated payload from a list of file paths.

    For each file, emits:
        === <relative-path-from-base_dir> ===
        <6-char right-justified line-number>\\t<line content>
        ...
        (blank line separating files)

    Line numbers are right-justified in a 6-character field (matching `cat -n`).
    Relative paths use forward slashes regardless of platform.

    Parameters
    ----------
    paths:
        List of absolute (or base_dir-relative) Path objects to include.
        Processed in the given order.
    base_dir:
        Directory used to compute the relative path shown in the header.

    Returns
    -------
    str
        The assembled payload string. Empty string if `paths` is empty.

    Raises
    ------
    FileNotFoundError
        If any path in `paths` does not exist.
    """
    if not paths:
        return ""

    parts: list[str] = []
    for path in paths:
        rel = path.relative_to(base_dir).as_posix()
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        header = f"=== {rel} ==="
        numbered_lines = [
            f"{lineno:>6}\t{line}"
            for lineno, line in enumerate(lines, start=1)
        ]
        block = "\n".join([header] + numbered_lines)
        parts.append(block)

    payload = "\n\n".join(parts) + "\n"
    return payload
