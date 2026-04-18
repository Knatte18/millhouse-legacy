"""
entrypoints/regenerate_sidebar.py — Regenerate _Sidebar.md for the wiki.

Reads Home.md and proposals/*.md from the wiki junction, builds sidebar
content, writes to _Sidebar.md in the wiki clone, and commits+pushes.

Called by: mill-setup, mill-spawn, mill-merge, mill-abandon, mill-resume.
Not a user-facing skill — no SKILL.md.

Exit codes
----------
0 — success
1 — error
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def _first_heading(path: Path) -> str | None:
    """Return the text of the first `# ` heading in a file, or None."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^#\s+(.+)$", line)
            if m:
                return m.group(1).strip()
    except OSError:
        pass
    return None


def _build_sidebar(proposals: list[tuple[str, str]]) -> str:
    """Build the sidebar markdown string.

    Parameters
    ----------
    proposals:
        List of (display_name, slug) tuples, already sorted.

    Returns
    -------
    str
        Full _Sidebar.md content.
    """
    lines = ["**[Tasks](Home)**", "", "**Proposals**"]
    for display_name, slug in proposals:
        lines.append(f"- [{display_name}]({slug})")
    lines.append("")  # trailing newline
    return "\n".join(lines)


def _load_cfg() -> dict:
    """Load merged config (shared + local). Exported for test patching."""
    from millpy.core.config import load_merged
    from millpy.core.paths import local_config_path, mill_junction_path

    mill = mill_junction_path()
    shared_cfg_path = mill / "config.yaml"
    local_cfg_path = local_config_path()
    return load_merged(shared_cfg_path, local_cfg_path)


def main(argv: list[str] | None = None) -> int:
    """Regenerate _Sidebar.md in the wiki clone.

    Idempotent: if Home.md and proposals/ haven't changed, git commit
    reports nothing to commit and the operation is a no-op.

    Returns
    -------
    int
        0 on success, 1 on error.
    """
    from millpy.core.paths import mill_junction_path, slug_from_branch, wiki_clone_path
    from millpy.tasks import wiki

    cfg = _load_cfg()

    mill = mill_junction_path()
    proposals_dir = mill / "proposals"

    # Collect proposals: (display_name, slug) sorted alphabetically by display_name.
    proposal_entries: list[tuple[str, str]] = []
    if proposals_dir.exists():
        for p in sorted(proposals_dir.glob("*.md")):
            slug = p.stem
            display_name = _first_heading(p) or slug
            proposal_entries.append((display_name, slug))

    # Sort case-insensitively by display name.
    proposal_entries.sort(key=lambda pair: pair[0].casefold())

    sidebar_content = _build_sidebar(proposal_entries)

    # Write to wiki clone (not via the junction — write directly to clone).
    wiki_path = wiki_clone_path(cfg)
    sidebar_path = wiki_path / "_Sidebar.md"

    # Acquire wiki lock before write.
    current_slug = slug_from_branch(cfg)
    wiki.acquire_lock(cfg, current_slug)
    try:
        sidebar_path.write_text(sidebar_content, encoding="utf-8", newline="\n")
        wiki.write_commit_push(cfg, ["_Sidebar.md"], "auto: regenerate sidebar")
    finally:
        wiki.release_lock(cfg)

    return 0


if __name__ == "__main__":
    sys.exit(main())
