"""Tests for open_terminal.py — nested-project offset (B.4) fix.

Covers only the launch-cwd derivation. The picker UI and Claude-CLI
invocation are mocked out. Three scenarios:
  - Flat layout: offset is empty, launch_cwd == selected.worktree
  - Nested layout: offset is "projects/sub", launch_cwd is joined
  - Offset computation fails: falls back to selected.worktree, warning logged
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from millpy.entrypoints import open_terminal


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


def test_flat_layout_launch_cwd_equals_worktree(temp_git_repo, monkeypatch, capsys):
    """Flat layout: offset is '.', launch_cwd == child worktree root."""
    (temp_git_repo / ".millhouse" / "children").mkdir(parents=True)

    child_worktree = temp_git_repo / "fake-child-worktree"
    child_worktree.mkdir()
    (child_worktree / ".millhouse").mkdir()

    captured_cwd = {}
    real_run = __import__("millpy.core.subprocess_util", fromlist=["run"]).run

    def _fake_subprocess_run(argv, *args, cwd=None, **kwargs):
        if argv and argv[0] == "git":
            return real_run(argv, cwd=cwd, **kwargs)
        captured_cwd["cwd"] = cwd
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def _fake_list_children(millhouse_dir):
        return [_make_child(child_worktree)]

    monkeypatch.chdir(temp_git_repo)
    monkeypatch.setattr("millpy.core.subprocess_util.run", _fake_subprocess_run)
    monkeypatch.setattr("millpy.worktree.children.list_children", _fake_list_children)

    exit_code = open_terminal.main()
    assert exit_code == 0
    assert Path(captured_cwd["cwd"]).resolve() == child_worktree.resolve()


def test_nested_layout_launch_cwd_includes_offset(temp_git_repo, monkeypatch):
    """Nested: .millhouse/ at <git>/projects/sub/, launch_cwd == child/projects/sub."""
    project = temp_git_repo / "projects" / "sub"
    (project / ".millhouse" / "children").mkdir(parents=True)

    child_worktree = temp_git_repo / "fake-child-worktree"
    child_worktree.mkdir()
    (child_worktree / "projects" / "sub").mkdir(parents=True)

    captured_cwd = {}
    real_run = __import__("millpy.core.subprocess_util", fromlist=["run"]).run

    def _fake_subprocess_run(argv, *args, cwd=None, **kwargs):
        if argv and argv[0] == "git":
            return real_run(argv, cwd=cwd, **kwargs)
        captured_cwd["cwd"] = cwd
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def _fake_list_children(millhouse_dir):
        return [_make_child(child_worktree)]

    monkeypatch.chdir(project)
    monkeypatch.setattr("millpy.core.subprocess_util.run", _fake_subprocess_run)
    monkeypatch.setattr("millpy.worktree.children.list_children", _fake_list_children)

    exit_code = open_terminal.main()
    assert exit_code == 0
    assert Path(captured_cwd["cwd"]).resolve() == (child_worktree / "projects" / "sub").resolve()


def test_offset_failure_falls_back_to_worktree(temp_git_repo, monkeypatch):
    """If cwd_offset raises, launch_cwd falls back to selected.worktree."""
    (temp_git_repo / ".millhouse" / "children").mkdir(parents=True)

    child_worktree = temp_git_repo / "fake-child-worktree"
    child_worktree.mkdir()

    captured_cwd = {}
    real_run = __import__("millpy.core.subprocess_util", fromlist=["run"]).run

    def _fake_subprocess_run(argv, *args, cwd=None, **kwargs):
        if argv and argv[0] == "git":
            return real_run(argv, cwd=cwd, **kwargs)
        captured_cwd["cwd"] = cwd
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def _fake_list_children(millhouse_dir):
        return [_make_child(child_worktree)]

    def _raise_always(*args, **kwargs):
        raise ValueError("simulated offset failure")

    monkeypatch.chdir(temp_git_repo)
    monkeypatch.setattr("millpy.core.subprocess_util.run", _fake_subprocess_run)
    monkeypatch.setattr("millpy.worktree.children.list_children", _fake_list_children)
    monkeypatch.setattr("millpy.core.paths.cwd_offset", _raise_always)

    exit_code = open_terminal.main()
    assert exit_code == 0
    assert Path(captured_cwd["cwd"]).resolve() == child_worktree.resolve()


def test_flat_subfolder_launch_cwd_includes_offset(temp_git_repo, monkeypatch):
    """Flat layout with cwd in a subfolder: launch_cwd == child/<subfolder>."""
    (temp_git_repo / ".millhouse" / "children").mkdir(parents=True)
    subfolder = temp_git_repo / "plugins" / "mill" / "scripts"
    subfolder.mkdir(parents=True)

    child_worktree = temp_git_repo / "fake-child-worktree"
    child_worktree.mkdir()
    (child_worktree / "plugins" / "mill" / "scripts").mkdir(parents=True)

    captured_cwd = {}
    real_run = __import__("millpy.core.subprocess_util", fromlist=["run"]).run

    def _fake_subprocess_run(argv, *args, cwd=None, **kwargs):
        if argv and argv[0] == "git":
            return real_run(argv, cwd=cwd, **kwargs)
        captured_cwd["cwd"] = cwd
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def _fake_list_children(millhouse_dir):
        return [_make_child(child_worktree)]

    monkeypatch.chdir(subfolder)
    monkeypatch.setattr("millpy.core.subprocess_util.run", _fake_subprocess_run)
    monkeypatch.setattr("millpy.worktree.children.list_children", _fake_list_children)

    exit_code = open_terminal.main()
    assert exit_code == 0
    assert Path(captured_cwd["cwd"]).resolve() == (child_worktree / "plugins" / "mill" / "scripts").resolve()
