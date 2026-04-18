"""
entrypoints/worktree.py — Worktree creator for millpy (live).

Creates a git worktree with millhouse setup (colors, .env copy, config).
Card 10: also creates a .mill junction pointing at the wiki clone and copies
_millhouse/config.local.yaml from the parent worktree.

Live after W1 Step 10 skill-text flip: called directly via
`_millhouse/mill-worktree.py` or `python plugins/mill/scripts/worktree.py`.
"""
from __future__ import annotations

from . import _bootstrap  # noqa: F401

import argparse
import sys
from pathlib import Path


# Module-level alias for wiki_clone_path — allows tests to patch it without
# patching the entire paths module.
from millpy.core.paths import wiki_clone_path as wiki_clone_path_fn
from millpy.core import junction


def remove(worktree_path: Path) -> None:
    """Remove the .mill junction from a worktree, then clean up via git.

    Parameters
    ----------
    worktree_path:
        Absolute path to the worktree being removed.
    """
    junction.remove(worktree_path / ".mill")
    _git_worktree_remove(worktree_path)


def _git_worktree_remove(worktree_path: Path) -> None:
    """Run ``git worktree remove`` for the given path.

    Separated as a helper to allow patching in tests without touching
    the junction removal logic.

    Parameters
    ----------
    worktree_path:
        Path to pass to ``git worktree remove``.
    """
    from millpy.core.git_ops import git, worktree_list
    from millpy.core.paths import repo_root
    try:
        repo = repo_root()
    except Exception:
        return
    git(["worktree", "remove", "--force", str(worktree_path)], cwd=repo)


def main(argv: list[str] | None = None) -> int:
    """Create a git worktree with millhouse setup.

    Parameters
    ----------
    argv:
        Argument vector. Defaults to sys.argv[1:].

    Returns
    -------
    int
        Exit code (0 = success, non-zero = error).
    """
    from millpy.core.git_ops import git, worktree_list
    from millpy.core.log_util import log
    from millpy.core.paths import repo_root, local_config_path
    from millpy.core.subprocess_util import run as subprocess_run
    from millpy.worktree.setup import copy_env, pick_color, write_vscode_settings

    parser = argparse.ArgumentParser(
        prog="worktree",
        description="Create a git worktree with millhouse setup.",
    )
    parser.add_argument(
        "--worktree-name",
        required=True,
        help="Name for the worktree (also used as directory name by default).",
    )
    parser.add_argument(
        "--branch-name",
        required=True,
        help="Branch name for the new worktree.",
    )
    parser.add_argument(
        "--dir-name",
        default="",
        help="Override directory name (defaults to --worktree-name).",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        default=False,
        help="Do not open VS Code after creation.",
    )
    parser.add_argument(
        "--terminal",
        action="store_true",
        default=False,
        help="Open in a terminal instead of VS Code.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview what would happen without making changes.",
    )

    args = parser.parse_args(argv)

    if "/" in args.worktree_name:
        print(
            f"[worktree] WorktreeName must not contain '/'. Got: {args.worktree_name!r}",
            file=sys.stderr,
        )
        return 1

    dir_name = args.dir_name or args.worktree_name

    try:
        repo = repo_root()
    except Exception as exc:
        print(f"[worktree] Not in a git repository: {exc}", file=sys.stderr)
        return 1

    # Hub detection: bare repo sits as .bare sibling to worktrees
    hub_root = repo.parent
    is_hub = (hub_root / ".bare").exists()

    if is_hub:
        worktrees_parent = hub_root
    else:
        worktrees_parent = repo.parent / f"{repo.name}.worktrees"

    project_path = worktrees_parent / dir_name
    short_name = args.worktree_name

    if args.dry_run:
        print(f"[DryRun] Would create worktree at {project_path} on branch {args.branch_name}")
        print(f"[DryRun] Would write .vscode/settings.json with a unique title bar color")
        print(str(project_path))
        return 0

    # Create worktree
    result = git(
        ["worktree", "add", "-b", args.branch_name, str(project_path)],
        cwd=repo,
    )
    if result.returncode != 0:
        print(f"[worktree] git worktree add failed: {result.stderr}", file=sys.stderr)
        return 1

    log("worktree", f"Created worktree at {project_path}")

    # Pick color and write VS Code settings
    try:
        existing = [Path(wt["path"]) for wt in worktree_list(cwd=repo)]
        color = pick_color(existing)
        write_vscode_settings(project_path, color, short_name)
        log("worktree", f"VS Code settings: color={color}")
    except Exception as exc:
        log("worktree", f"VS Code settings failed (non-fatal): {exc}")

    # Copy .env from parent
    try:
        copy_env(repo, project_path)
    except Exception as exc:
        log("worktree", f"copy_env failed (non-fatal): {exc}")

    # Load config (best-effort; empty dict on failure — wiki_clone_path falls back to remote URL)
    cfg: dict = {}
    try:
        from millpy.core.config import load as _load_config
        src_config = repo / "_millhouse" / "config.yaml"
        if src_config.exists():
            cfg = _load_config(src_config)
    except Exception as exc:
        log("worktree", f"config load failed (non-fatal): {exc}")

    # Copy _millhouse/config.yaml to new worktree
    src_config = repo / "_millhouse" / "config.yaml"
    dst_millhouse = project_path / "_millhouse"
    dst_millhouse.mkdir(parents=True, exist_ok=True)
    dst_config = dst_millhouse / "config.yaml"
    if src_config.exists() and not dst_config.exists():
        import shutil
        shutil.copy2(str(src_config), str(dst_config))

    # Copy _millhouse/config.local.yaml to new worktree (Card 10)
    src_local = local_config_path(repo)
    dst_local = local_config_path(project_path)
    if src_local.exists() and not dst_local.exists():
        import shutil as _shutil
        dst_local.parent.mkdir(parents=True, exist_ok=True)
        _shutil.copy2(str(src_local), str(dst_local))
        log("worktree", f"Copied config.local.yaml to {dst_local}")

    # Create .mill junction pointing at wiki clone (Card 10)
    try:
        wiki_path = wiki_clone_path_fn(cfg)
        mill_link = project_path / ".mill"
        junction.create(wiki_path, mill_link)
        log("worktree", f"Created .mill junction -> {wiki_path}")
    except Exception as exc:
        log("worktree", f".mill junction creation failed (non-fatal): {exc}")

    # Emit project path (parity with PS1)
    print(str(project_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
