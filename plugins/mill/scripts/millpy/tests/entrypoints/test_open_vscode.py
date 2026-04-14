"""Tests for open_vscode.py — nested-project offset (B.4) fix.

Mirrors test_open_terminal.py exactly. Same three scenarios.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from millpy.entrypoints import open_vscode


@dataclass
class _FakeChild:
    slug: str
    branch: str
    status: str = "active"
    worktree: str = ""


def _make_child(worktree_path: Path) -> _FakeChild:
    return _FakeChild(slug="test-slug", branch="test-branch", worktree=str(worktree_path))


@pytest.fixture
def temp_git_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )
    return tmp_path.resolve()


def _make_real_run_passthrough():
    from millpy.core.subprocess_util import run as real_run
    return real_run


def test_flat_layout_launch_cwd_equals_worktree(temp_git_repo, monkeypatch):
    (temp_git_repo / "_millhouse" / "children").mkdir(parents=True)
    child_worktree = temp_git_repo / "fake-child-worktree"
    child_worktree.mkdir()
    (child_worktree / "_millhouse").mkdir()

    captured_cwd = {}
    real_run = _make_real_run_passthrough()

    def _fake_subprocess_run(argv, *args, cwd=None, **kwargs):
        if argv and argv[0] == "git":
            return real_run(argv, cwd=cwd, **kwargs)
        captured_cwd["cwd"] = cwd
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.chdir(temp_git_repo)
    monkeypatch.setattr("millpy.core.subprocess_util.run", _fake_subprocess_run)
    monkeypatch.setattr("millpy.worktree.children.list_children", lambda _: [_make_child(child_worktree)])

    exit_code = open_vscode.main()
    assert exit_code == 0
    assert Path(captured_cwd["cwd"]).resolve() == child_worktree.resolve()


def test_nested_layout_launch_cwd_includes_offset(temp_git_repo, monkeypatch):
    project = temp_git_repo / "projects" / "sub"
    (project / "_millhouse" / "children").mkdir(parents=True)
    child_worktree = temp_git_repo / "fake-child-worktree"
    child_worktree.mkdir()
    (child_worktree / "projects" / "sub").mkdir(parents=True)

    captured_cwd = {}
    real_run = _make_real_run_passthrough()

    def _fake_subprocess_run(argv, *args, cwd=None, **kwargs):
        if argv and argv[0] == "git":
            return real_run(argv, cwd=cwd, **kwargs)
        captured_cwd["cwd"] = cwd
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.chdir(project)
    monkeypatch.setattr("millpy.core.subprocess_util.run", _fake_subprocess_run)
    monkeypatch.setattr("millpy.worktree.children.list_children", lambda _: [_make_child(child_worktree)])

    exit_code = open_vscode.main()
    assert exit_code == 0
    assert Path(captured_cwd["cwd"]).resolve() == (child_worktree / "projects" / "sub").resolve()


def test_offset_failure_falls_back_to_worktree(temp_git_repo, monkeypatch):
    (temp_git_repo / "_millhouse" / "children").mkdir(parents=True)
    child_worktree = temp_git_repo / "fake-child-worktree"
    child_worktree.mkdir()

    captured_cwd = {}
    real_run = _make_real_run_passthrough()

    def _fake_subprocess_run(argv, *args, cwd=None, **kwargs):
        if argv and argv[0] == "git":
            return real_run(argv, cwd=cwd, **kwargs)
        captured_cwd["cwd"] = cwd
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def _raise_always(*args, **kwargs):
        raise ValueError("simulated offset failure")

    monkeypatch.chdir(temp_git_repo)
    monkeypatch.setattr("millpy.core.subprocess_util.run", _fake_subprocess_run)
    monkeypatch.setattr("millpy.worktree.children.list_children", lambda _: [_make_child(child_worktree)])
    monkeypatch.setattr("millpy.core.paths.project_offset", _raise_always)

    exit_code = open_vscode.main()
    assert exit_code == 0
    assert Path(captured_cwd["cwd"]).resolve() == child_worktree.resolve()
