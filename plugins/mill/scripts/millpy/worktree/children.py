"""
children.py — Child worktree registry parser for millpy.

Scans .millhouse/children/*.md files, parses YAML frontmatter, and returns
Child dataclass instances. Uses the shared _parse_yaml_mapping helper from
millpy.core.config — does NOT re-implement YAML parsing.

Malformed files are skipped with a warning via core.log_util.log.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from millpy.core.config import _parse_yaml_mapping
from millpy.core.log_util import log


# ---------------------------------------------------------------------------
# Data type
# ---------------------------------------------------------------------------

@dataclass
class Child:
    """A child worktree entry parsed from a .millhouse/children/*.md file."""

    slug: str
    branch: str
    worktree: Path | None
    status: str
    path: Path


# ---------------------------------------------------------------------------
# Frontmatter extraction
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---",
    re.DOTALL,
)


def _extract_frontmatter(text: str) -> dict | None:
    """Extract and parse YAML frontmatter from a markdown file.

    Returns the parsed dict or None if no frontmatter block is found.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        return _parse_yaml_mapping(m.group(1))
    except Exception:
        return None


def _slug_from_filename(filename: str) -> str:
    """Derive a slug from a child filename.

    Strips a leading timestamp prefix (YYYYMMDD-) and the .md extension.
    Example: '20260101-add-foo.md' → 'add-foo'.
    """
    name = filename[: -len(".md")] if filename.endswith(".md") else filename
    # Strip leading timestamp prefix like 20260101- or 20260101-123456-
    name = re.sub(r"^\d{8}-", "", name)
    return name


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_children(millhouse_dir: Path) -> list[Child]:
    """Scan millhouse_dir/children/*.md and return parsed Child entries.

    Files that are missing frontmatter, have unparseable YAML, or lack a
    `branch:` key are skipped with a warning. Entries are sorted by filename.

    Parameters
    ----------
    millhouse_dir:
        The .millhouse directory for the worktree (not the children/ subdir).

    Returns
    -------
    list[Child]
        Valid child entries in filename order.
    """
    children_dir = millhouse_dir / "children"
    if not children_dir.is_dir():
        return []

    md_files = sorted(children_dir.glob("*.md"))
    results: list[Child] = []

    for md_path in md_files:
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError as exc:
            log("children", f"Warning: cannot read {md_path}: {exc}")
            continue

        fm = _extract_frontmatter(text)
        if fm is None:
            log("children", f"Warning: no frontmatter in {md_path.name}, skipping")
            continue

        branch = fm.get("branch")
        if not branch:
            log("children", f"Warning: missing branch: in {md_path.name}, skipping")
            continue

        status = str(fm.get("status", ""))
        worktree_raw = fm.get("worktree")
        worktree: Path | None = Path(str(worktree_raw)) if worktree_raw else None
        slug = _slug_from_filename(md_path.name)

        results.append(Child(
            slug=slug,
            branch=str(branch),
            worktree=worktree,
            status=status,
            path=md_path,
        ))

    return results


def find_by_branch(children: list[Child], branch: str) -> Child | None:
    """Return the first Child with the given branch name, or None.

    Parameters
    ----------
    children:
        List of Child instances to search.
    branch:
        Branch name to match.
    """
    for child in children:
        if child.branch == branch:
            return child
    return None


def find_by_slug(children: list[Child], slug: str) -> Child | None:
    """Return the first Child with the given slug, or None.

    Parameters
    ----------
    children:
        List of Child instances to search.
    slug:
        Slug string to match (derived from filename, e.g. 'add-foo').
    """
    for child in children:
        if child.slug == slug:
            return child
    return None
