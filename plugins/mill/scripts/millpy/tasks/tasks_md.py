"""
tasks_md.py — Parser, renderer, and path resolver for Home.md (wiki task list).

After Card 6 migration, this module targets the GitHub Wiki's Home.md instead
of the orphan-branch tasks.md. Each entry in Home.md represents a task.

Entry format
------------
```
## [<phase>] <Display Name>
<description text>. [Background](<background-slug>.md)
```

- `[<phase>]` is optional. Valid values: s, active, completed, done.
- Background link (if present) is a markdown link `[Background](<slug>.md)`.
- `description` is the first line of body text (excluding the Background link).

`resolve_path(cfg)` returns the absolute path to `Home.md` inside the .millhouse/wiki/
junction at cwd. Raises `ConfigError` when the junction does not exist.

`write_commit_push(cfg, content, commit_msg)` writes `Home.md`, then delegates
to `wiki.write_commit_push` for commit+push. Uses `wiki.acquire_lock` /
`wiki.release_lock` to serialize concurrent writers.

Exceptions
----------
- `ValidationError` (ValueError subclass): raised by `validate()` when two
  entries share the same slug.
- `GitPushError` and `TasksLockError` are removed. Callers that used to catch
  them must now catch `wiki.WikiMergeConflict` and `wiki.LockBusy` instead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ValidationError(ValueError):
    """Raised when Home.md has duplicate slugs (two entries with the same slug)."""


# ---------------------------------------------------------------------------
# Data type
# ---------------------------------------------------------------------------

@dataclass
class TaskEntry:
    """A single task entry parsed from Home.md."""

    display_name: str
    """The human-readable task name (text after the optional phase marker)."""

    slug: str
    """URL-safe identifier derived by slugifying display_name."""

    phase: str | None
    """Phase marker string (e.g. "active", "s", "done") or None."""

    description: str
    """Body text of the entry (excluding the Background link line)."""

    background_slug: str | None
    """Slug of the background file (e.g. "new-task-system" from
    ``[Background](new-task-system.md)``), or None if absent."""


# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

# Matches ## headings with optional [phase] marker.
_HEADING_RE = re.compile(r"^##\s+(?:\[([^\]]+)\]\s+)?(.+)$")

# Matches a Background link anywhere in a line: [Background](slug.md)
_BACKGROUND_RE = re.compile(r"\[Background\]\(([^)]+)\.md\)")

# Valid phase values for Home.md task entries
_VALID_PHASES = {"s", "active", "completed", "done"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(display_name: str) -> str:
    """Convert a display name to a URL-safe slug.

    Rules:
    - Lowercase.
    - Replace each whitespace character with ``-``.
    - Strip all characters that are not alphanumeric or ``-``.

    Parameters
    ----------
    display_name:
        Human-readable task name.

    Returns
    -------
    str
        Slug string.

    Examples
    --------
    >>> slugify("New Task System!")
    'new-task-system'
    """
    s = display_name.lower()
    # Replace each whitespace char with dash
    s = re.sub(r"\s", "-", s)
    # Strip non-alphanumeric/non-dash characters
    s = re.sub(r"[^a-z0-9\-]", "", s)
    return s


def _extract_background_slug(body: str) -> str | None:
    """Extract the background slug from body text, or None."""
    m = _BACKGROUND_RE.search(body)
    if m:
        # m.group(1) is the filename without .md
        # Slugify it to normalize (e.g. strip any query params)
        raw = m.group(1)
        # Just return the raw stem — it's already a slug in well-formed files
        return raw
    return None


def _strip_background_link(body: str) -> str:
    """Remove the Background link from body text."""
    return _BACKGROUND_RE.sub("", body).strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_path(cfg: dict) -> Path:
    """Return the absolute path to Home.md inside the wiki junction.

    Looks for the wiki junction at ``cwd / ".millhouse" / "wiki"``.

    Parameters
    ----------
    cfg:
        Loaded config dict (currently unused — path derived from cwd).

    Returns
    -------
    Path
        ``<cwd>/.millhouse/wiki/Home.md``

    Raises
    ------
    ConfigError
        If the wiki junction does not exist.
    """
    from millpy.core.config import ConfigError  # local import to avoid cycles
    from millpy.core.paths import mill_junction_path

    mill = mill_junction_path()
    if not mill.exists():
        raise ConfigError(
            f".millhouse/wiki/ junction not found at {mill_junction_path()}. "
            "Run mill-setup to create the wiki junction."
        )
    return mill / "Home.md"


def parse(path: Path) -> list[TaskEntry]:
    """Parse Home.md into a list of TaskEntry instances.

    Each ``## `` heading is treated as a task entry. The body is everything
    between consecutive headings (or between the last heading and EOF).

    Parameters
    ----------
    path:
        Path to Home.md.

    Returns
    -------
    list[TaskEntry]
        Entries in file order.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    entries: list[TaskEntry] = []
    current_phase: str | None = None
    current_display_name: str = ""
    current_line: int | None = None
    body_lines: list[str] = []

    def _flush() -> None:
        if current_line is None:
            return
        body = "".join(body_lines).strip()
        bg_slug = _extract_background_slug(body)
        description = _strip_background_link(body)
        entries.append(TaskEntry(
            display_name=current_display_name,
            slug=slugify(current_display_name),
            phase=current_phase,
            description=description,
            background_slug=bg_slug,
        ))

    for lineno, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n").rstrip("\r")
        m = _HEADING_RE.match(line)
        if m and raw.startswith("## "):
            _flush()
            current_phase = m.group(1)  # None if no marker
            current_display_name = m.group(2).strip()
            current_line = lineno
            body_lines = []
        elif current_line is not None:
            body_lines.append(raw)

    _flush()
    return entries


def render(entries: list[TaskEntry]) -> str:
    """Render a list of TaskEntry objects back to Home.md text.

    Produces a ``# Tasks`` header followed by each entry. The Background link
    is appended to the description when ``background_slug`` is set.

    Parameters
    ----------
    entries:
        List of TaskEntry instances to render.

    Returns
    -------
    str
        The reconstructed Home.md content.
    """
    parts: list[str] = ["# Tasks\n"]
    for entry in entries:
        if entry.phase is not None:
            heading = f"## [{entry.phase}] {entry.display_name}\n"
        else:
            heading = f"## {entry.display_name}\n"
        parts.append("\n" + heading)

        # Build body: description + optional Background link
        desc = entry.description.strip()
        if entry.background_slug:
            if desc:
                body = f"{desc} [Background]({entry.background_slug}.md)\n"
            else:
                body = f"[Background]({entry.background_slug}.md)\n"
        else:
            body = f"{desc}\n" if desc else ""

        if body:
            parts.append(body)

    result = "".join(parts)
    if not result.endswith("\n"):
        result += "\n"
    return result


def validate(path: Path) -> list[str]:
    """Validate Home.md and raise ValidationError on slug collisions.

    Checks:
    1. Phase markers, if present, are in the valid set.
    2. No duplicate slugs (two entries that slugify to the same string).

    Parameters
    ----------
    path:
        Path to Home.md.

    Returns
    -------
    list[str]
        Error messages. Empty list means the file is valid.

    Raises
    ------
    ValidationError
        If two entries share the same slug.
    """
    entries = parse(path)
    errors: list[str] = []

    # Validate phase markers
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            m = re.match(r"^##\s+\[([^\]]+)\]", line)
            if m:
                marker = m.group(1)
                if marker not in _VALID_PHASES:
                    errors.append(
                        f"Line {lineno}: invalid phase marker [{marker!r}]; "
                        f"valid values are {sorted(_VALID_PHASES)}"
                    )

    # Check for slug collisions
    seen: dict[str, str] = {}  # slug → first display_name
    for entry in entries:
        if entry.slug in seen:
            raise ValidationError(
                f"Duplicate slug {entry.slug!r}: entries "
                f"{seen[entry.slug]!r} and {entry.display_name!r} both slugify to the same value"
            )
        seen[entry.slug] = entry.display_name

    return errors


def write_commit_push(cfg: dict, new_content: str, commit_msg: str) -> None:
    """Write new_content to Home.md, commit, and push via wiki helpers.

    Uses ``wiki.acquire_lock`` / ``wiki.release_lock`` for serialization.
    The actual commit+push is delegated to ``wiki.write_commit_push``.

    Parameters
    ----------
    cfg:
        Loaded config dict.
    new_content:
        Full replacement content for Home.md.
    commit_msg:
        Git commit message.

    Raises
    ------
    wiki.LockBusy
        If the wiki lock cannot be acquired (replaces the old TasksLockError).
    wiki.WikiMergeConflict
        If a rebase conflict cannot be auto-resolved (replaces GitPushError).
    RuntimeError
        If a git operation fails.
    """
    from millpy.tasks import wiki
    from millpy.core.paths import slug_from_branch

    home_path = resolve_path(cfg)
    slug = slug_from_branch(cfg)

    wiki.acquire_lock(cfg, slug)
    try:
        home_path.write_text(new_content, encoding="utf-8", newline="\n")
        wiki.write_commit_push(cfg, ["Home.md"], commit_msg)
    finally:
        wiki.release_lock(cfg)
