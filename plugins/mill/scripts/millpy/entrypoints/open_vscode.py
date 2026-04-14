"""
entrypoints/open_vscode.py — VS Code launcher for millpy (live).

Scans _millhouse/children/ for active entries, presents a picker,
then opens VS Code in the selected worktree. Applies the B.4
project-within-worktree offset in nested-project layouts.

Live after W1 Step 10 skill-text flip: called directly via
_millhouse/mill-vscode.cmd or `python plugins/mill/scripts/open_vscode.py`.
"""
from __future__ import annotations

from . import _bootstrap  # noqa: F401

import os
import shutil
import sys
from pathlib import Path


def _build_launch_argv(child) -> list[str]:
    """Build the argv that would open VS Code in the child worktree.

    Exposed for parity-smoke testing without actually opening a window.

    Parameters
    ----------
    child:
        A Child dataclass instance.

    Returns
    -------
    list[str]
        The argv to pass to subprocess_util.run.
    """
    code = (
        shutil.which("code.cmd")
        or shutil.which("code")
        or os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Programs",
            "Microsoft VS Code",
            "bin",
            "code.cmd",
        )
    )
    worktree_path = str(child.worktree) if child.worktree else "."
    return [code, worktree_path]


def main(argv: list[str] | None = None) -> int:
    """Open VS Code in a selected active child worktree.

    Parameters
    ----------
    argv:
        Argument vector (unused).

    Returns
    -------
    int
        Exit code.
    """
    from millpy.core.log_util import log
    from millpy.core.paths import project_offset, project_root, repo_root
    from millpy.core.subprocess_util import run as subprocess_run
    from millpy.worktree.children import list_children

    try:
        root = project_root()
    except Exception as exc:
        print(f"[open_vscode] Not in a git repository: {exc}", file=sys.stderr)
        return 1

    millhouse_dir = root / "_millhouse"
    children_dir = millhouse_dir / "children"

    if not children_dir.exists():
        print("No _millhouse/children/ directory found. No spawned worktrees.")
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
            print(f"[open_vscode] Invalid selection: {raw!r}", file=sys.stderr)
            return 1
        selected = active[num - 1]

    # cwd bug fix: use child worktree as cwd (not repo root)
    # nested-project offset (B.4): same pattern as open_terminal.py.
    try:
        parent_git_root = repo_root(Path.cwd())
        parent_project_root = project_root(Path.cwd())
        offset = project_offset(parent_git_root, parent_project_root)
    except Exception as exc:
        log("open_vscode", f"offset computation failed, falling back to worktree root: {exc}")
        offset = None

    if offset is None or str(offset) in (".", ""):
        launch_cwd = Path(selected.worktree)
    else:
        launch_cwd = Path(selected.worktree) / str(offset)

    print(f"\nOpening VS Code in: {launch_cwd}\n")

    launch_argv = _build_launch_argv(selected)
    log("open_vscode", f"launch_argv={launch_argv} cwd={launch_cwd}")

    subprocess_run(launch_argv, cwd=launch_cwd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
