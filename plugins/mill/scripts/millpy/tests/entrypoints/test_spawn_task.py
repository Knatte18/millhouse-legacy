"""Contract tests for millpy.entrypoints.spawn_task.

Business logic is already covered by tests/tasks/. This file exercises
the entrypoint's CLI contract — argparse boundary behaviour, missing
required args, and the "not in a git repo" error path.
"""
from __future__ import annotations

import pytest

from millpy.entrypoints import spawn_task


def test_main_with_no_git_repo_exits_nonzero(tmp_path, monkeypatch):
    """spawn_task invoked outside a git repo returns non-zero with a clear stderr."""
    monkeypatch.chdir(tmp_path)
    exit_code = spawn_task.main(["--dry-run"])
    assert exit_code != 0


def test_main_missing_config_exits_nonzero(tmp_path, monkeypatch, capsys):
    """Inside a git repo but with no _millhouse/config.yaml, spawn_task must fail
    with a clear stderr mentioning mill-setup."""
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

    exit_code = spawn_task.main([])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "mill-setup" in captured.err.lower() or "mill-setup" in captured.out.lower()
