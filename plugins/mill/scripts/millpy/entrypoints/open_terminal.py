"""
entrypoints/open_terminal.py — Terminal launcher for millpy (live).

Scans .millhouse/children/ for active entries, presents a picker,
then launches Claude Code in the selected worktree. Applies the B.4
project-within-worktree offset in nested-project layouts (see
main() for details).

Live after W1 Step 10 skill-text flip: called directly via
`.millhouse/mill-terminal.py` or `python plugins/mill/scripts/open_terminal.py`.
"""
from __future__ import annotations

from . import _bootstrap  # noqa: F401

import shutil
import sys
from pathlib import Path


def _build_launch_argv(child) -> list[str]:
    """Build the argv that would launch Claude Code in the child worktree.

    This is a private helper exposed for parity-smoke testing. The main()
    path calls this and then runs the result via subprocess_util.run.

    Parameters
    ----------
    child:
        A Child dataclass instance (from millpy.worktree.children).

    Returns
    -------
    list[str]
        The argv to pass to subprocess_util.run, with cwd=child.worktree.
    """
    # Launch claude directly in the worktree
    claude = shutil.which("claude") or "claude"
    return [claude, "--name", child.slug]


def main(argv: list[str] | None = None) -> int:
    """Launch Claude Code in a selected active child worktree.

    Parameters
    ----------
    argv:
        Argument vector (unused — no CLI args for this entry).

    Returns
    -------
    int
        Exit code.
    """
    from millpy.core.log_util import log
    from millpy.core.paths import cwd_offset, project_root
    from millpy.core.subprocess_util import run as subprocess_run
    from millpy.worktree.children import list_children

    try:
        root = project_root()
    except Exception as exc:
        print(f"[open_terminal] Not in a git repository: {exc}", file=sys.stderr)
        return 1

    millhouse_dir = root / ".millhouse"
    children_dir = millhouse_dir / "children"

    if not children_dir.exists():
        print("No .millhouse/children/ directory found. No spawned worktrees.")
        return 0

    children = list_children(millhouse_dir)
    active = [c for c in children if c.status == "active" and c.worktree is not None]

    if not active:
        print("No active child worktrees found.")
        return 0

    # Select child
    if len(active) == 1:
        selected = active[0]
        print(f"Auto-selecting: {selected.slug} ({selected.branch})")
    else:
        print("Active worktrees:\n")
        for i, c in enumerate(active, 1):
            print(f"  {i}) {c.slug}  ({c.branch})")
        print()
        raw = input(f"Select worktree (1-{len(active)}): ").strip()
        try:
            num = int(raw)
            if num < 1 or num > len(active):
                raise ValueError
        except ValueError:
            print(f"[open_terminal] Invalid selection: {raw!r}", file=sys.stderr)
            return 1
        selected = active[num - 1]

    # Preserve the parent's cwd subfolder when opening the child worktree.
    # For flat layouts where cwd == git root, offset is "." and the join
    # is a no-op.
    try:
        offset = cwd_offset()
    except Exception as exc:
        log("open_terminal", f"offset computation failed, falling back to worktree root: {exc}")
        offset = None

    if offset is None or str(offset) in (".", ""):
        launch_cwd = Path(selected.worktree)
    else:
        launch_cwd = Path(selected.worktree) / str(offset)

    print(f"\nLaunching Claude Code in: {launch_cwd}")
    print(f"Session name: {selected.slug}\n")

    launch_argv = _build_launch_argv(selected)
    log("open_terminal", f"launch_argv={launch_argv} cwd={launch_cwd}")

    subprocess_run(launch_argv, cwd=launch_cwd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
