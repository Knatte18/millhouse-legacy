"""Contract tests for millpy.entrypoints.fetch_issues.

fetch_issues shells out to `gh` for the real work. These tests exercise
the CLI contract for the "no git repo" and "gh failure" paths — the happy
path (real gh call) is out of scope for unit tests and is covered by the
Step 15 E2E smoke.
"""
from __future__ import annotations

import pytest

from millpy.entrypoints import fetch_issues


def test_main_not_in_git_repo_exits_nonzero(tmp_path, monkeypatch, capsys):
    """fetch_issues invoked outside any git repo prints stderr and returns 1."""
    monkeypatch.chdir(tmp_path)
    exit_code = fetch_issues.main()
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "not in a git repository" in captured.err.lower() or "git" in captured.err.lower()
