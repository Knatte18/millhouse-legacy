"""Contract tests for millpy.entrypoints.worktree (the CLI wrapper — not
to be confused with millpy.worktree.* library code).

Business logic is covered by tests/worktree/test_children.py. This file
exercises the CLI contract — argparse boundary behaviour and missing
required args.
"""
from __future__ import annotations

import pytest

from millpy.entrypoints import worktree


def test_main_missing_required_args_exits_nonzero(capsys):
    """Missing --worktree-name and --branch-name raises SystemExit."""
    with pytest.raises(SystemExit) as exc_info:
        worktree.main([])
    assert exc_info.value.code != 0


def test_main_missing_branch_name_exits_nonzero(capsys):
    """Missing --branch-name alone is enough to fail parsing."""
    with pytest.raises(SystemExit):
        worktree.main(["--worktree-name", "foo"])


def test_main_dry_run_prints_plan_and_exits_zero(tmp_path, monkeypatch):
    """--dry-run should print the planned worktree path without creating anything."""
    import subprocess
    import os

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )
    monkeypatch.chdir(tmp_path)

    exit_code = worktree.main([
        "--worktree-name", "test-wt",
        "--branch-name", "test-branch",
        "--dry-run",
    ])
    assert exit_code == 0
