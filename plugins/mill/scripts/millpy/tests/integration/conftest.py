"""
conftest.py — shared fixtures for integration and cross-layout tests.

Three fixtures:
- temp_git_repo: an empty git repo with one commit, resolved to absolute path.
- flat_project_layout: temp_git_repo with _millhouse/ at the toplevel.
- nested_project_layout: temp_git_repo with _millhouse/ at projects/sub/.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


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


@dataclass(frozen=True)
class ProjectLayout:
    git_root: Path
    project_root: Path
    millhouse_dir: Path


@pytest.fixture
def flat_project_layout(temp_git_repo):
    """Flat layout: _millhouse/ at the git toplevel."""
    millhouse = temp_git_repo / "_millhouse"
    millhouse.mkdir()
    (millhouse / "scratch").mkdir()
    (millhouse / "task").mkdir()
    return ProjectLayout(
        git_root=temp_git_repo,
        project_root=temp_git_repo,
        millhouse_dir=millhouse,
    )


@pytest.fixture
def nested_project_layout(temp_git_repo):
    """Nested layout: _millhouse/ at <git>/projects/sub/."""
    project = temp_git_repo / "projects" / "sub"
    project.mkdir(parents=True)
    millhouse = project / "_millhouse"
    millhouse.mkdir()
    (millhouse / "scratch").mkdir()
    (millhouse / "task").mkdir()
    return ProjectLayout(
        git_root=temp_git_repo,
        project_root=project,
        millhouse_dir=millhouse,
    )
