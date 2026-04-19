"""Tests for millpy.core.paths."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path, PurePosixPath

import pytest

from millpy.core.paths import (
    RepoRootNotFound,
    active_dir,
    active_junction_path,
    active_status_path,
    cwd_offset,
    local_config_path,
    mill_junction_path,
    millhouse_dir,
    plugin_root,
    project_dir,
    project_offset,
    project_root,
    repo_root,
    slug_file_path,
    slug_from_branch,
    wiki_clone_path,
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
    subdirectories and .millhouse/ placements for nested-project tests.
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
    """Flat layout: .millhouse/ at git toplevel -> project_root() == repo_root()."""
    (temp_git_repo / ".millhouse").mkdir()
    assert project_root(start=temp_git_repo) == temp_git_repo


def test_project_root_nested_layout_walks_up(temp_git_repo):
    """Nested: .millhouse/ at <git>/projects/sub/ -> project_root() from src/ returns projects/sub/."""
    project = temp_git_repo / "projects" / "sub"
    (project / ".millhouse").mkdir(parents=True)
    (project / "src").mkdir()
    assert project_root(start=project / "src") == project


def test_project_root_from_inside_millhouse_subdir(temp_git_repo):
    """Walk-up from deep inside .millhouse/ still returns the project root."""
    project = temp_git_repo / "projects" / "sub"
    deep = project / ".millhouse" / "some" / "subdir"
    deep.mkdir(parents=True)
    assert project_root(start=deep) == project


def test_project_root_no_millhouse_falls_back_to_git_root(temp_git_repo):
    """No .millhouse/ anywhere -> fall back to git toplevel, do not raise."""
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


def test_millhouse_dir_returns_cwd_millhouse(tmp_path, monkeypatch):
    """millhouse_dir() returns cwd / '.millhouse' (project_dir()-anchored)."""
    monkeypatch.chdir(tmp_path)
    assert millhouse_dir() == tmp_path / ".millhouse"


def test_millhouse_dir_subfolder_follows_cwd(tmp_path, monkeypatch):
    """millhouse_dir() from a subfolder returns that subfolder / '.millhouse'."""
    sub = tmp_path / "projects" / "sub"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    assert millhouse_dir() == sub / ".millhouse"


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


# -------------------------------------------------------------------
# slug_from_branch (Card 2 — new helpers)
# -------------------------------------------------------------------


def test_slug_from_branch_strips_prefix(monkeypatch):
    """slug_from_branch with branch-prefix 'mh' on 'mh/foo' returns 'foo'."""
    from millpy.core import subprocess_util

    cfg: dict = {"repo": {"branch-prefix": "mh"}}

    def fake_run(argv, **kwargs):
        import subprocess

        if argv == ["git", "branch", "--show-current"]:
            r = subprocess.CompletedProcess(argv, 0)
            r.stdout = "mh/foo"
            r.stderr = ""
            return r
        raise AssertionError(f"unexpected call: {argv}")

    monkeypatch.setattr(subprocess_util, "run", fake_run)
    assert slug_from_branch(cfg) == "foo"


def test_slug_from_branch_no_prefix(monkeypatch):
    """slug_from_branch with empty branch-prefix on 'foo' returns 'foo'."""
    from millpy.core import subprocess_util

    cfg: dict = {}

    def fake_run(argv, **kwargs):
        import subprocess

        if argv == ["git", "branch", "--show-current"]:
            r = subprocess.CompletedProcess(argv, 0)
            r.stdout = "foo"
            r.stderr = ""
            return r
        raise AssertionError(f"unexpected call: {argv}")

    monkeypatch.setattr(subprocess_util, "run", fake_run)
    assert slug_from_branch(cfg) == "foo"


def test_slug_from_branch_no_match_returns_full(monkeypatch):
    """slug_from_branch with prefix 'mh' on 'hotfix/bar' returns 'hotfix/bar' (no strip)."""
    from millpy.core import subprocess_util

    cfg: dict = {"repo": {"branch-prefix": "mh"}}

    def fake_run(argv, **kwargs):
        import subprocess

        if argv == ["git", "branch", "--show-current"]:
            r = subprocess.CompletedProcess(argv, 0)
            r.stdout = "hotfix/bar"
            r.stderr = ""
            return r
        raise AssertionError(f"unexpected call: {argv}")

    monkeypatch.setattr(subprocess_util, "run", fake_run)
    assert slug_from_branch(cfg) == "hotfix/bar"


# -------------------------------------------------------------------
# mill_junction_path
# -------------------------------------------------------------------


def test_mill_junction_path_defaults_to_cwd(tmp_path, monkeypatch):
    """mill_junction_path() returns cwd / '.millhouse' / 'wiki' when cwd is used."""
    monkeypatch.chdir(tmp_path)
    assert mill_junction_path() == tmp_path / ".millhouse" / "wiki"


def test_mill_junction_path_explicit_cwd(tmp_path):
    """mill_junction_path(cwd=<path>) returns <path>/.millhouse/wiki."""
    assert mill_junction_path(cwd=tmp_path) == tmp_path / ".millhouse" / "wiki"


# -------------------------------------------------------------------
# active_dir
# -------------------------------------------------------------------


def test_active_dir_with_explicit_slug(tmp_path, monkeypatch):
    """active_dir(cfg, 'my-task') returns <cwd>/.millhouse/wiki/active/my-task."""
    monkeypatch.chdir(tmp_path)
    cfg: dict = {}
    result = active_dir(cfg, "my-task")
    assert result == tmp_path / ".millhouse" / "wiki" / "active" / "my-task"


def test_active_dir_no_slug_reads_git(monkeypatch, tmp_path):
    """active_dir(cfg) with no slug reads from git branch via slug_from_branch."""
    from millpy.core import subprocess_util

    monkeypatch.chdir(tmp_path)
    cfg: dict = {}

    def fake_run(argv, **kwargs):
        import subprocess

        if argv == ["git", "branch", "--show-current"]:
            r = subprocess.CompletedProcess(argv, 0)
            r.stdout = "my-feature"
            r.stderr = ""
            return r
        raise AssertionError(f"unexpected call: {argv}")

    monkeypatch.setattr(subprocess_util, "run", fake_run)
    result = active_dir(cfg)
    assert result == tmp_path / ".millhouse" / "wiki" / "active" / "my-feature"


# -------------------------------------------------------------------
# active_status_path
# -------------------------------------------------------------------


def test_active_status_path(monkeypatch, tmp_path):
    """active_status_path(cfg) returns active_dir(cfg) / 'status.md'."""
    from millpy.core import subprocess_util

    monkeypatch.chdir(tmp_path)
    cfg: dict = {}

    def fake_run(argv, **kwargs):
        import subprocess

        if argv == ["git", "branch", "--show-current"]:
            r = subprocess.CompletedProcess(argv, 0)
            r.stdout = "some-task"
            r.stderr = ""
            return r
        raise AssertionError(f"unexpected call: {argv}")

    monkeypatch.setattr(subprocess_util, "run", fake_run)
    result = active_status_path(cfg)
    assert result == tmp_path / ".millhouse" / "wiki" / "active" / "some-task" / "status.md"


# -------------------------------------------------------------------
# local_config_path
# -------------------------------------------------------------------


def test_local_config_path_defaults_to_cwd(tmp_path, monkeypatch):
    """local_config_path() returns cwd / '.millhouse' / 'config.local.yaml'."""
    monkeypatch.chdir(tmp_path)
    assert local_config_path() == tmp_path / ".millhouse" / "config.local.yaml"


def test_local_config_path_explicit_cwd(tmp_path):
    """local_config_path(cwd=<path>) returns <path>/.millhouse/config.local.yaml."""
    assert local_config_path(cwd=tmp_path) == tmp_path / ".millhouse" / "config.local.yaml"


# -------------------------------------------------------------------
# project_dir
# -------------------------------------------------------------------


def test_project_dir_returns_cwd(tmp_path, monkeypatch):
    """project_dir() returns Path.cwd()."""
    monkeypatch.chdir(tmp_path)
    assert project_dir() == tmp_path


def test_project_dir_subfolder(tmp_path, monkeypatch):
    """project_dir() when cwd is a subfolder returns that subfolder (not git root)."""
    sub = tmp_path / "repo" / "sub" / "project"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    assert project_dir() == sub


# -------------------------------------------------------------------
# wiki_clone_path
# -------------------------------------------------------------------


def test_wiki_clone_path_explicit_config(tmp_path):
    """wiki_clone_path returns wiki.clone-path from config when set."""
    cfg: dict = {"wiki": {"clone-path": str(tmp_path / "mywiki")}}
    result = wiki_clone_path(cfg)
    assert result == tmp_path / "mywiki"


def test_wiki_clone_path_derived_from_remote_url(monkeypatch, tmp_path):
    """wiki_clone_path derives <parent>/<repo-name>.wiki/ from git remote URL."""
    from millpy.core import subprocess_util

    monkeypatch.chdir(tmp_path)

    def fake_run(argv, **kwargs):
        import subprocess

        if argv == ["git", "remote", "get-url", "origin"]:
            r = subprocess.CompletedProcess(argv, 0)
            r.stdout = "https://github.com/org/myrepo.git"
            r.stderr = ""
            return r
        if argv == ["git", "rev-parse", "--show-toplevel"]:
            r = subprocess.CompletedProcess(argv, 0)
            r.stdout = str(tmp_path)
            r.stderr = ""
            return r
        raise AssertionError(f"unexpected call: {argv}")

    monkeypatch.setattr(subprocess_util, "run", fake_run)
    cfg: dict = {"repo": {"short-name": "Myrepo"}}
    result = wiki_clone_path(cfg)
    # repo-name comes from remote URL basename, not short-name
    assert result == tmp_path.parent / "myrepo.wiki"


# -------------------------------------------------------------------
# active_junction_path
# -------------------------------------------------------------------


def test_active_junction_path_defaults_to_cwd(tmp_path, monkeypatch):
    """active_junction_path() returns cwd / '.millhouse' / 'active'."""
    monkeypatch.chdir(tmp_path)
    assert active_junction_path() == tmp_path / ".millhouse" / "active"


def test_active_junction_path_explicit_cwd(tmp_path):
    """active_junction_path(cwd=<path>) returns <path>/.millhouse/active."""
    assert active_junction_path(cwd=tmp_path) == tmp_path / ".millhouse" / "active"


# -------------------------------------------------------------------
# slug_file_path
# -------------------------------------------------------------------


def test_slug_file_path(tmp_path, monkeypatch):
    """slug_file_path('my-task') returns cwd / '.millhouse' / 'my-task.slug.md'."""
    monkeypatch.chdir(tmp_path)
    assert slug_file_path("my-task") == tmp_path / ".millhouse" / "my-task.slug.md"
