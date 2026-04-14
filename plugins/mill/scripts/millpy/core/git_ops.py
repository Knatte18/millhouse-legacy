"""
git_ops.py — Thin git subprocess wrappers for millpy.

All functions delegate to core.subprocess_util.run. No caching, no global
state, no fancy error handling — exceptions propagate to the caller.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from millpy.core import subprocess_util


def git(
    args: list[str],
    *,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run `git <args>` and return the CompletedProcess.

    Parameters
    ----------
    args:
        Arguments to pass after `git`.
    cwd:
        Working directory. None uses the current directory.
    """
    return subprocess_util.run(["git"] + args, cwd=cwd)


def current_branch(cwd: Path | None = None) -> str:
    """Return the current branch name.

    Parameters
    ----------
    cwd:
        Working directory. None uses the current directory.
    """
    result = git(["branch", "--show-current"], cwd=cwd)
    return result.stdout.strip()


def worktree_list(cwd: Path | None = None) -> list[dict]:
    """Return a list of worktree descriptors from `git worktree list --porcelain`.

    Each entry is a dict with keys:
      - "path": str — absolute path of the worktree
      - "head": str — HEAD commit hash
      - "branch": str — branch name (without refs/heads/ prefix), or "" for detached

    Parameters
    ----------
    cwd:
        Working directory. None uses the current directory.
    """
    result = git(["worktree", "list", "--porcelain"], cwd=cwd)
    entries: list[dict] = []
    current: dict = {}
    for raw_line in result.stdout.splitlines():
        line = raw_line.rstrip()
        if line.startswith("worktree "):
            if current:
                entries.append(current)
            current = {"path": line[len("worktree "):], "head": "", "branch": ""}
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):]
        elif line.startswith("branch "):
            ref = line[len("branch "):]
            # Strip refs/heads/ prefix if present
            if ref.startswith("refs/heads/"):
                current["branch"] = ref[len("refs/heads/"):]
            else:
                current["branch"] = ref
        elif line == "bare":
            current["branch"] = ""
        # detached line → leave branch as ""
    if current:
        entries.append(current)
    return entries


def file_list_from_diff(
    base_ref: str,
    head_ref: str,
    *,
    cwd: Path | None = None,
) -> list[Path]:
    """Return repo-relative paths changed between base_ref and head_ref.

    Runs `git diff --name-only <base_ref>..<head_ref>`.

    Parameters
    ----------
    base_ref:
        Base git ref (commit, branch, tag).
    head_ref:
        Head git ref.
    cwd:
        Working directory. None uses the current directory.
    """
    result = git(["diff", "--name-only", f"{base_ref}..{head_ref}"], cwd=cwd)
    paths: list[Path] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped:
            paths.append(Path(stripped))
    return paths
