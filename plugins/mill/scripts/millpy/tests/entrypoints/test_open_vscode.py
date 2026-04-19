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
    (temp_git_repo / ".millhouse" / "children").mkdir(parents=True)
    child_worktree = temp_git_repo / "fake-child-worktree"
    child_worktree.mkdir()
    (child_worktree / ".millhouse").mkdir()

    captured_cwd = {}
    captured_argv = {}
    real_run = _make_real_run_passthrough()

    def _fake_subprocess_run(argv, *args, cwd=None, **kwargs):
        if argv and argv[0] == "git":
            return real_run(argv, cwd=cwd, **kwargs)
        captured_cwd["cwd"] = cwd
        captured_argv["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.chdir(temp_git_repo)
    monkeypatch.setattr("millpy.core.subprocess_util.run", _fake_subprocess_run)
    monkeypatch.setattr("millpy.worktree.children.list_children", lambda _: [_make_child(child_worktree)])

    exit_code = open_vscode.main()
    assert exit_code == 0
    assert Path(captured_cwd["cwd"]).resolve() == child_worktree.resolve()
    assert Path(captured_argv["argv"][1]).resolve() == child_worktree.resolve()


def test_nested_layout_launch_cwd_includes_offset(temp_git_repo, monkeypatch):
    project = temp_git_repo / "projects" / "sub"
    (project / ".millhouse" / "children").mkdir(parents=True)
    child_worktree = temp_git_repo / "fake-child-worktree"
    child_worktree.mkdir()
    (child_worktree / "projects" / "sub").mkdir(parents=True)

    captured_cwd = {}
    captured_argv = {}
    real_run = _make_real_run_passthrough()

    def _fake_subprocess_run(argv, *args, cwd=None, **kwargs):
        if argv and argv[0] == "git":
            return real_run(argv, cwd=cwd, **kwargs)
        captured_cwd["cwd"] = cwd
        captured_argv["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.chdir(project)
    monkeypatch.setattr("millpy.core.subprocess_util.run", _fake_subprocess_run)
    monkeypatch.setattr("millpy.worktree.children.list_children", lambda _: [_make_child(child_worktree)])

    exit_code = open_vscode.main()
    assert exit_code == 0
    assert Path(captured_cwd["cwd"]).resolve() == (child_worktree / "projects" / "sub").resolve()
    assert Path(captured_argv["argv"][1]).resolve() == (child_worktree / "projects" / "sub").resolve()


def test_offset_failure_falls_back_to_worktree(temp_git_repo, monkeypatch):
    (temp_git_repo / ".millhouse" / "children").mkdir(parents=True)
    child_worktree = temp_git_repo / "fake-child-worktree"
    child_worktree.mkdir()

    captured_cwd = {}
    captured_argv = {}
    real_run = _make_real_run_passthrough()

    def _fake_subprocess_run(argv, *args, cwd=None, **kwargs):
        if argv and argv[0] == "git":
            return real_run(argv, cwd=cwd, **kwargs)
        captured_cwd["cwd"] = cwd
        captured_argv["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def _raise_always(*args, **kwargs):
        raise ValueError("simulated offset failure")

    monkeypatch.chdir(temp_git_repo)
    monkeypatch.setattr("millpy.core.subprocess_util.run", _fake_subprocess_run)
    monkeypatch.setattr("millpy.worktree.children.list_children", lambda _: [_make_child(child_worktree)])
    monkeypatch.setattr("millpy.core.paths.cwd_offset", _raise_always)

    exit_code = open_vscode.main()
    assert exit_code == 0
    assert Path(captured_cwd["cwd"]).resolve() == child_worktree.resolve()
    assert Path(captured_argv["argv"][1]).resolve() == child_worktree.resolve()


def test_flat_subfolder_launch_cwd_includes_offset(temp_git_repo, monkeypatch):
    """Flat layout with cwd in a subfolder: launch_cwd and argv path == child/<subfolder>."""
    (temp_git_repo / ".millhouse" / "children").mkdir(parents=True)
    subfolder = temp_git_repo / "plugins" / "mill" / "scripts"
    subfolder.mkdir(parents=True)

    child_worktree = temp_git_repo / "fake-child-worktree"
    child_worktree.mkdir()
    (child_worktree / "plugins" / "mill" / "scripts").mkdir(parents=True)

    captured_cwd = {}
    captured_argv = {}
    real_run = _make_real_run_passthrough()

    def _fake_subprocess_run(argv, *args, cwd=None, **kwargs):
        if argv and argv[0] == "git":
            return real_run(argv, cwd=cwd, **kwargs)
        captured_cwd["cwd"] = cwd
        captured_argv["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.chdir(subfolder)
    monkeypatch.setattr("millpy.core.subprocess_util.run", _fake_subprocess_run)
    monkeypatch.setattr("millpy.worktree.children.list_children", lambda _: [_make_child(child_worktree)])

    exit_code = open_vscode.main()
    assert exit_code == 0
    expected = (child_worktree / "plugins" / "mill" / "scripts").resolve()
    assert Path(captured_cwd["cwd"]).resolve() == expected
    assert Path(captured_argv["argv"][1]).resolve() == expected


def test_argv_uses_launch_cwd_not_worktree_when_offset_nonempty(temp_git_repo, monkeypatch):
    """Critical invariant: argv path always equals launch_cwd, not child.worktree."""
    project = temp_git_repo / "projects" / "sub"
    (project / ".millhouse" / "children").mkdir(parents=True)

    child_worktree = temp_git_repo / "fake-child-worktree"
    child_worktree.mkdir()
    (child_worktree / "projects" / "sub").mkdir(parents=True)

    captured_argv = {}
    real_run = _make_real_run_passthrough()

    def _fake_subprocess_run(argv, *args, cwd=None, **kwargs):
        if argv and argv[0] == "git":
            return real_run(argv, cwd=cwd, **kwargs)
        captured_argv["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.chdir(project)
    monkeypatch.setattr("millpy.core.subprocess_util.run", _fake_subprocess_run)
    monkeypatch.setattr("millpy.worktree.children.list_children", lambda _: [_make_child(child_worktree)])

    exit_code = open_vscode.main()
    assert exit_code == 0
    argv_path = Path(captured_argv["argv"][1]).resolve()
    assert argv_path == (child_worktree / "projects" / "sub").resolve()
    assert argv_path != child_worktree.resolve()
