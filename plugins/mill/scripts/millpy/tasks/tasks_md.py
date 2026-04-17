"""
tasks_md.py — Parser and renderer for tasks.md.

Handles both bulleted-list and prose-paragraph task bodies (Proposal 02 Fix C).
The PS1 predecessor was bullets-only; this parser captures body text verbatim.

Phase marker regex uses \\[([>\\w]+)\\] (not \\[(\\w+)\\]) so [>] matches — this
is a documented gotcha: \\w+ excludes the > character.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Data type
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """A single task entry from tasks.md."""

    title: str
    phase: str | None
    body: str
    line_number: int


# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

# Matches ## headings with optional [phase] marker.
# Uses [>\w]+ so [>] also matches (documented gotcha: \w+ would miss >).
_HEADING_RE = re.compile(r"^##\s+(?:\[([>\w]+)\]\s+)?(.+)$")

# Valid phase values for tasks.md (not status.md vocabulary)
_VALID_PHASES = {">", "active", "done", "abandoned"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(path: Path) -> list[Task]:
    """Parse tasks.md into a list of Task dataclass instances.

    Captures every `## ` heading as a task. The body is everything between
    one `## ` heading and the next (or EOF), verbatim. Both bullet-list and
    prose-paragraph bodies are supported.

    Parameters
    ----------
    path:
        Path to the tasks.md file.

    Returns
    -------
    list[Task]
        Tasks in file order.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    tasks: list[Task] = []
    current_line: int | None = None
    current_phase: str | None = None
    current_title: str = ""
    body_lines: list[str] = []

    def _flush(next_start: int) -> None:
        if current_line is None:
            return
        body = "".join(body_lines)
        # Normalize trailing whitespace so parse→render→parse is idempotent:
        # collapse all-whitespace bodies to empty string, and strip trailing
        # blank lines down to a single "\n" terminator. Leading and interior
        # blank lines are preserved verbatim.
        if not body.strip():
            body = ""
        else:
            body = body.rstrip("\n") + "\n"
        tasks.append(Task(
            title=current_title,
            phase=current_phase,
            body=body,
            line_number=current_line,
        ))

    for lineno, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n").rstrip("\r")
        m = _HEADING_RE.match(line)
        if m and raw.startswith("## "):
            _flush(lineno)
            current_phase = m.group(1)  # None if no marker
            current_title = m.group(2).strip()
            current_line = lineno
            body_lines = []
        elif current_line is not None:
            body_lines.append(raw)

    _flush(len(lines) + 1)
    return tasks


def render(tasks: list[Task]) -> str:
    """Render a list of Task objects back to tasks.md text.

    Produces a `# Tasks` header followed by each task. The body is emitted
    verbatim. A trailing newline is always present.

    Parameters
    ----------
    tasks:
        List of Task instances to render.

    Returns
    -------
    str
        The reconstructed tasks.md content.
    """
    parts: list[str] = ["# Tasks\n"]
    for task in tasks:
        if task.phase is not None:
            heading = f"## [{task.phase}] {task.title}\n"
        else:
            heading = f"## {task.title}\n"
        parts.append("\n" + heading)
        if task.body:
            parts.append(task.body)
    result = "".join(parts)
    if not result.endswith("\n"):
        result += "\n"
    return result


def find(tasks: list[Task], title: str) -> Task | None:
    """Return the first task matching the given title, or None.

    Parameters
    ----------
    tasks:
        List of Task instances to search.
    title:
        Exact title string (without phase marker).

    Returns
    -------
    Task | None
    """
    for task in tasks:
        if task.title == title:
            return task
    return None


def validate(path: Path) -> list[str]:
    """Validate tasks.md structural rules.

    Checks:
    1. Exactly one `# ` heading, at line 1.
    2. All task entries use `## ` headings.
    3. Phase markers, if present, are in the valid set.
    4. No orphaned content before the first `## ` heading.

    Parameters
    ----------
    path:
        Path to the tasks.md file.

    Returns
    -------
    list[str]
        Error messages. Empty list means the file is valid.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors: list[str] = []

    h1_count = 0
    h1_line = None
    first_h2_line = None

    for lineno, line in enumerate(lines, start=1):
        if line.startswith("# ") and not line.startswith("## "):
            h1_count += 1
            h1_line = lineno
        if line.startswith("## "):
            if first_h2_line is None:
                first_h2_line = lineno
            # Validate phase marker
            m = re.match(r"^##\s+\[([^\]]+)\]", line)
            if m:
                marker = m.group(1)
                if marker not in _VALID_PHASES:
                    errors.append(
                        f"Line {lineno}: invalid phase marker [{marker!r}]; "
                        f"valid values are {sorted(_VALID_PHASES)}"
                    )

    if h1_count != 1:
        errors.append(
            f"Expected exactly one `# ` heading (found {h1_count})"
        )

    if h1_line is not None and h1_line != 1:
        errors.append(
            f"`# ` heading must be at line 1 (found at line {h1_line})"
        )

    # Check for orphaned content before first ## heading
    if first_h2_line is not None:
        for lineno, line in enumerate(lines[1:], start=2):
            if lineno >= first_h2_line:
                break
            if line.strip() and not line.startswith("# "):
                errors.append(
                    f"Line {lineno}: orphaned content before first ## heading"
                )

    return errors
