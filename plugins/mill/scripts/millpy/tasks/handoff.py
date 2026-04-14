"""
handoff.py — Handoff brief materializer for millpy.

Writes _millhouse/handoff.md (or any given output_path) with task context for
the receiving mill-start session.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def materialize(
    task_title: str,
    task_description: str,
    phase: str,
    output_path: Path,
) -> None:
    """Write a handoff.md file at output_path.

    Template:
        # Handoff

        - Task: <task_title>
        - Phase: <phase>
        - Timestamp: <UTC ISO-8601>

        ## Description

        <task_description>

    Parameters
    ----------
    task_title:
        The task title string.
    task_description:
        The task description (may be multi-line). Preserved verbatim.
    phase:
        Current phase string (e.g. "planned", "implementing").
    output_path:
        Destination file path. Raises OSError if the parent directory does not exist.

    Raises
    ------
    OSError
        If the file cannot be written (e.g. parent directory missing).
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    content = (
        "# Handoff\n"
        "\n"
        f"- Task: {task_title}\n"
        f"- Phase: {phase}\n"
        f"- Timestamp: {timestamp}\n"
        "\n"
        "## Description\n"
        "\n"
        f"{task_description}"
    )
    if not content.endswith("\n"):
        content += "\n"

    # Use write_bytes to control encoding and line endings explicitly
    output_path.write_text(content, encoding="utf-8", newline="\n")
