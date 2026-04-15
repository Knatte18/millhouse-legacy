"""
plan_io.py — Plan path resolution and content reading for v1/v2 plans.

All callers go through this module — no inline v1-vs-v2 branching at call
sites. This is the single source of truth for reading plan files.

v1: _millhouse/task/plan.md (flat file)
v2: _millhouse/task/plan/ (directory with 00-overview.md + batch files)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from millpy.core.log_util import log


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

@dataclass
class PlanLocation:
    """Resolved location of a plan on disk.

    Attributes
    ----------
    kind:
        "v1" for a single plan.md file, "v2" for a plan/ directory.
    path:
        For v1: the plan.md file path.
        For v2: the plan/ directory path.
    overview:
        None for v1; absolute path to 00-overview.md for v2.
    batches:
        Empty list for v1; ordered list of batch file paths for v2
        (filename order, 00-overview.md excluded).
    """
    kind: Literal["v1", "v2"]
    path: Path
    overview: Path | None
    batches: list[Path] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict:
    """Extract the leading YAML frontmatter block and parse it.

    Handles the subset of YAML used by mill plan files:
    - Flat scalar key-value pairs (strings, booleans, integers)
    - Inline lists: key: [item1, item2, item3]

    Returns an empty dict if no frontmatter block is found.
    """
    # Find the --- delimiters
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not match:
        return {}

    fm_text = match.group(1)
    result: dict = {}

    for line in fm_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue

        colon_idx = stripped.index(":")
        key = stripped[:colon_idx].strip()
        raw_value = stripped[colon_idx + 1:].strip()

        # Inline list: [item1, item2] or []
        if raw_value.startswith("[") and raw_value.endswith("]"):
            inner = raw_value[1:-1].strip()
            if not inner:
                result[key] = []
            else:
                result[key] = [item.strip() for item in inner.split(",")]
            continue

        # Boolean
        if raw_value == "true":
            result[key] = True
            continue
        if raw_value == "false":
            result[key] = False
            continue

        # Null
        if raw_value in ("null", "~", ""):
            result[key] = None
            continue

        # Integer
        try:
            result[key] = int(raw_value)
            continue
        except ValueError:
            pass

        # Quoted string — strip quotes
        if (raw_value.startswith('"') and raw_value.endswith('"') and len(raw_value) >= 2):
            result[key] = raw_value[1:-1]
            continue
        if (raw_value.startswith("'") and raw_value.endswith("'") and len(raw_value) >= 2):
            result[key] = raw_value[1:-1]
            continue

        # Plain string
        result[key] = raw_value

    return result


def parse_frontmatter(text: str) -> dict:
    """Public wrapper over _parse_frontmatter.

    plan_validator.py imports this name to avoid cross-module _-prefixed
    imports.
    """
    return _parse_frontmatter(text)


def _write_frontmatter_field(path: Path, key: str, value: object) -> None:
    """Update one field in the frontmatter of a file in-place.

    Reads the file in binary mode, locates the frontmatter block, replaces
    the matching key line, and writes back. Preserves all other content and
    line endings byte-for-byte.

    Parameters
    ----------
    path:
        File to update.
    key:
        Frontmatter key to replace.
    value:
        New Python value (will be serialised as YAML scalar).

    Raises
    ------
    ValueError
        If the frontmatter block is not found or the key is not present.
    """
    # Serialize value to YAML scalar
    if value is True:
        yaml_value = "true"
    elif value is False:
        yaml_value = "false"
    elif value is None:
        yaml_value = "null"
    else:
        yaml_value = str(value)

    raw = path.read_bytes()

    # Detect line ending
    crlf = b"\r\n" in raw

    # Work in text for line-level replacement, then convert back
    text = raw.decode("utf-8")

    fm_match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not fm_match:
        raise ValueError(f"No frontmatter block found in {path}")

    fm_text = fm_match.group(1)
    new_fm_lines = []
    replaced = False
    for line in fm_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key}:") or stripped == f"{key}:":
            new_fm_lines.append(f"{key}: {yaml_value}")
            replaced = True
        else:
            new_fm_lines.append(line)

    if not replaced:
        raise ValueError(f"Key {key!r} not found in frontmatter of {path}")

    sep = "\r\n" if crlf else "\n"
    new_fm = sep.join(new_fm_lines)
    before = "---" + sep
    after = sep + "---" + sep

    new_text = before + new_fm + after + text[fm_match.end():]
    path.write_bytes(new_text.encode("utf-8"))


# ---------------------------------------------------------------------------
# Public API — path resolution
# ---------------------------------------------------------------------------

def resolve_plan_path(task_dir: Path) -> PlanLocation | None:
    """Resolve the plan location for a given task directory.

    Parameters
    ----------
    task_dir:
        Absolute path to `_millhouse/task/`.

    Returns
    -------
    PlanLocation or None
        v2 if task_dir/plan/ is a directory.
        v1 if task_dir/plan.md is a file.
        None if neither exists.
        If both exist: v2 wins and an INFO-level warning is logged.

    Raises
    ------
    FileNotFoundError or ValueError
        If a v2 plan directory exists but 00-overview.md is missing.
    """
    plan_dir = task_dir / "plan"
    plan_file = task_dir / "plan.md"

    has_dir = plan_dir.is_dir()
    has_file = plan_file.is_file()

    if has_dir and has_file:
        log("plan_io", "both v1 plan.md and v2 plan/ directory present; v2 takes precedence")

    if has_dir:
        return _build_v2_location(plan_dir)

    if has_file:
        return PlanLocation(kind="v1", path=plan_file, overview=None, batches=[])

    return None


def _build_v2_location(plan_dir: Path) -> PlanLocation:
    """Construct a PlanLocation for an existing v2 plan directory.

    Raises
    ------
    FileNotFoundError
        If 00-overview.md is missing from the directory.
    """
    overview = plan_dir / "00-overview.md"
    if not overview.exists():
        raise FileNotFoundError(
            f"v2 plan directory {plan_dir} is missing 00-overview.md"
        )

    # Collect batch files: all .md files except 00-overview.md, sorted by name
    batches = sorted(
        [p for p in plan_dir.iterdir() if p.suffix == ".md" and p.name != "00-overview.md"]
    )

    return PlanLocation(
        kind="v2",
        path=plan_dir,
        overview=overview,
        batches=batches,
    )


# ---------------------------------------------------------------------------
# Public API — content reading
# ---------------------------------------------------------------------------

def read_plan_content(loc: PlanLocation) -> str:
    """Return the plan content as a single string.

    v1: returns plan.md verbatim.
    v2: concatenates overview + batch files in filename order with separator
        headers of the form ``=== <relative-path> ===``.  Files are separated
        by ``\\n\\n---\\n\\n``. The final file has no trailing separator.
    """
    if loc.kind == "v1":
        return loc.path.read_text(encoding="utf-8")

    # v2 — build concatenation
    files = [loc.overview] + list(loc.batches)
    parts = []
    for f in files:
        rel = f.relative_to(loc.path.parent).as_posix()
        header = f"=== {rel} ===\n\n"
        parts.append(header + f.read_text(encoding="utf-8"))

    return "\n\n---\n\n".join(parts)


def read_files_touched(loc: PlanLocation) -> list[str]:
    """Return the flat list of repo-relative file paths the plan touches.

    v1: parses the ``## Files`` section bullet list.
    v2: parses the ``## All Files Touched`` section of 00-overview.md.
    """
    if loc.kind == "v1":
        text = loc.path.read_text(encoding="utf-8")
        return _parse_bullet_section(text, "## Files")
    else:
        text = loc.overview.read_text(encoding="utf-8")  # type: ignore[union-attr]
        return _parse_bullet_section(text, "## All Files Touched")


def _parse_bullet_section(text: str, heading: str) -> list[str]:
    """Extract bullet list items under a given heading.

    Returns a list of strings stripped of leading ``- `` and whitespace.
    Stops at the next ``## `` heading or end of file.
    """
    lines = text.splitlines()
    in_section = False
    result = []
    for line in lines:
        if line.strip() == heading:
            in_section = True
            continue
        if in_section:
            if line.startswith("## "):
                break
            stripped = line.strip()
            if stripped.startswith("-"):
                item = stripped.lstrip("-").strip()
                if item:
                    result.append(item)
    return result


def read_approved(loc: PlanLocation) -> bool:
    """Read the ``approved:`` frontmatter field."""
    text = _plan_frontmatter_source(loc).read_text(encoding="utf-8")
    fm = _parse_frontmatter(text)
    return bool(fm.get("approved", False))


def write_approved(loc: PlanLocation, value: bool) -> None:
    """Write the ``approved:`` frontmatter field."""
    _write_frontmatter_field(_plan_frontmatter_source(loc), "approved", value)


def read_started(loc: PlanLocation) -> str:
    """Read the ``started:`` frontmatter field."""
    source = _plan_frontmatter_source(loc)
    fm = _parse_frontmatter(source.read_text(encoding="utf-8"))
    if "started" not in fm or fm["started"] is None:
        raise ValueError(f"'started' field missing in frontmatter of {source}")
    return str(fm["started"])


def read_verify(loc: PlanLocation) -> str:
    """Read the ``verify:`` frontmatter field."""
    source = _plan_frontmatter_source(loc)
    fm = _parse_frontmatter(source.read_text(encoding="utf-8"))
    if "verify" not in fm or fm["verify"] is None:
        raise ValueError(f"'verify' field missing in frontmatter of {source}")
    return str(fm["verify"])


def read_dev_server(loc: PlanLocation) -> str | None:
    """Read the ``dev-server:`` frontmatter field.

    Returns None if the field is absent or set to the literal ``N/A``.
    """
    text = _plan_frontmatter_source(loc).read_text(encoding="utf-8")
    fm = _parse_frontmatter(text)
    val = fm.get("dev-server")
    if val is None or str(val) == "N/A":
        return None
    return str(val)


def _plan_frontmatter_source(loc: PlanLocation) -> Path:
    """Return the file that owns the plan-level frontmatter.

    v1: plan.md
    v2: 00-overview.md
    """
    if loc.kind == "v1":
        return loc.path
    return loc.overview  # type: ignore[return-value]
