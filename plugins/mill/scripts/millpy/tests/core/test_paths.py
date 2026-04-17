"""Tests for millpy.core.paths."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

import pytest

from millpy.core.paths import (
    RepoRootNotFound,
    cwd_offset,
    millhouse_dir,
    plugin_root,
    project_offset,
    project_root,
    repo_root,
)


def test_repo_root_returns_git_toplevel():
    """repo_root() inside a git repo returns an existing directory."""
    root = repo_root()
    assert root.is_dir()
    assert (root / ".git").exists() or (root / ".git").is_file()


def test_repo_root_non_git_raises_repo_root_not_found(tmp_path):
    """repo_root(start=<non-git-dir>) raises RepoRootNotFound, not CalledProcessError."""
    with pytest.raises(RepoRootNotFound):
        repo_root(start=tmp_path)


def test_repo_root_not_found_is_value_error(tmp_path):
    """RepoRootNotFound is a subclass of ValueError."""
    with pytest.raises(ValueError):
        repo_root(start=tmp_path)


def test_plugin_root_ends_in_scripts():
    """plugin_root() returns a Path ending in 'scripts'."""
    root = plugin_root()
    assert root.name == "scripts"
    assert root.is_dir()


# -------------------------------------------------------------------
# project_root / project_offset / millhouse_dir (B.1 nested-project)
# -------------------------------------------------------------------


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create an empty git repo at tmp_path with one commit.

    Returns the resolved Path to the git toplevel. Caller can create
    subdirectories and _millhouse/ placements for nested-project tests.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"},
    )
    return tmp_path.resolve()


def test_project_root_flat_layout_equals_repo_root(temp_git_repo):
    """Flat layout: _millhouse/ at git toplevel -> project_root() == repo_root()."""
    (temp_git_repo / "_millhouse").mkdir()
    assert project_root(start=temp_git_repo) == temp_git_repo


def test_project_root_nested_layout_walks_up(temp_git_repo):
    """Nested: _millhouse/ at <git>/projects/sub/ -> project_root() from src/ returns projects/sub/."""
    project = temp_git_repo / "projects" / "sub"
    (project / "_millhouse").mkdir(parents=True)
    (project / "src").mkdir()
    assert project_root(start=project / "src") == project


def test_project_root_from_inside_millhouse_subdir(temp_git_repo):
    """Walk-up from deep inside _millhouse/ still returns the project root."""
    project = temp_git_repo / "projects" / "sub"
    deep = project / "_millhouse" / "some" / "subdir"
    deep.mkdir(parents=True)
    assert project_root(start=deep) == project


def test_project_root_no_millhouse_falls_back_to_git_root(temp_git_repo):
    """No _millhouse/ anywhere -> fall back to git toplevel, do not raise."""
    sub = temp_git_repo / "a" / "b"
    sub.mkdir(parents=True)
    assert project_root(start=sub) == temp_git_repo


def test_project_root_outside_git_raises(tmp_path):
    """Outside any git repo -> RepoRootNotFound (same as repo_root)."""
    with pytest.raises(RepoRootNotFound):
        project_root(start=tmp_path)


def test_project_offset_flat_layout_is_dot():
    """project_offset(X, X) == PurePosixPath('.')."""
    x = Path("/some/path")
    assert project_offset(x, x) == PurePosixPath(".")


def test_project_offset_nested_returns_relative(tmp_path):
    """project_offset(git, git/projects/sub) == PurePosixPath('projects/sub')."""
    git = tmp_path
    project = tmp_path / "projects" / "sub"
    project.mkdir(parents=True)
    assert project_offset(git, project) == PurePosixPath("projects/sub")


def test_project_offset_unrelated_paths_raises(tmp_path):
    """project_offset raises ValueError when project is not a subpath of git."""
    git = tmp_path / "repo_a"
    unrelated = tmp_path / "repo_b"
    git.mkdir()
    unrelated.mkdir()
    with pytest.raises(ValueError):
        project_offset(git, unrelated)


def test_millhouse_dir_uses_project_root_in_nested_layout(temp_git_repo):
    """millhouse_dir() routes through project_root(), not repo_root()."""
    project = temp_git_repo / "projects" / "sub"
    (project / "_millhouse").mkdir(parents=True)
    (project / "src").mkdir()
    assert millhouse_dir(start=project / "src") == project / "_millhouse"


def test_millhouse_dir_flat_layout_unchanged(temp_git_repo):
    """In flat layout, millhouse_dir() == repo_root() / '_millhouse' (same as before)."""
    (temp_git_repo / "_millhouse").mkdir()
    assert millhouse_dir(start=temp_git_repo) == temp_git_repo / "_millhouse"


# -------------------------------------------------------------------
# cwd_offset
# -------------------------------------------------------------------


def test_cwd_offset_equal_to_git_root_returns_dot(temp_git_repo):
    """cwd_offset(start=<git-root>) returns PurePosixPath('.')."""
    assert cwd_offset(start=temp_git_repo) == PurePosixPath(".")


def test_cwd_offset_subfolder_returns_relative(temp_git_repo):
    """cwd_offset(start=<git>/sub/deeper) returns PurePosixPath('sub/deeper')."""
    deeper = temp_git_repo / "sub" / "deeper"
    deeper.mkdir(parents=True)
    assert cwd_offset(start=deeper) == PurePosixPath("sub/deeper")


def test_cwd_offset_uses_forward_slashes_on_all_platforms(temp_git_repo):
    """The returned value is a PurePosixPath; its str contains only forward slashes."""
    deeper = temp_git_repo / "a" / "b" / "c"
    deeper.mkdir(parents=True)
    result = cwd_offset(start=deeper)
    assert isinstance(result, PurePosixPath)
    assert "\\" not in str(result)


def test_cwd_offset_outside_git_raises_value_error(tmp_path):
    """A path not inside any git repo raises ValueError or RepoRootNotFound."""
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises((ValueError, RepoRootNotFound)):
        cwd_offset(start=outside)


def test_cwd_offset_defaults_to_cwd(temp_git_repo, monkeypatch):
    """Default start=None reads Path.cwd()."""
    sub = temp_git_repo / "sub"
    sub.mkdir()
    monkeypatch.chdir(sub)
    assert cwd_offset() == PurePosixPath("sub")
