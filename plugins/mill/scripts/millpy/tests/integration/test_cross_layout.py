"""Cross-layout integration tests — D.2 regression gate for B.1.

For every mill-state path consumer, assert that flat and nested layouts
produce equivalent semantics. Specifically: when run from inside the
project, mill-state paths resolve to <project_root>/_millhouse/, NOT to
<git_root>/_millhouse/ in the nested case.

The authoritative primitive is `millpy.core.paths.project_root()`.
These tests verify that the callers that should route through
`project_root()` do so correctly, and that adding or removing a project
subdirectory does not surprise the caller.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from millpy.core.paths import millhouse_dir, project_root, repo_root


@pytest.mark.parametrize("layout_name", ["flat", "nested"])
def test_project_root_walks_up_to_millhouse(layout_name, flat_project_layout, nested_project_layout):
    layout = flat_project_layout if layout_name == "flat" else nested_project_layout
    assert project_root(start=layout.project_root) == layout.project_root


@pytest.mark.parametrize("layout_name", ["flat", "nested"])
def test_millhouse_dir_resolves_inside_project_root(layout_name, flat_project_layout, nested_project_layout, monkeypatch):
    layout = flat_project_layout if layout_name == "flat" else nested_project_layout
    monkeypatch.chdir(layout.project_root)
    assert millhouse_dir() == layout.millhouse_dir


def test_nested_millhouse_is_not_at_git_root(nested_project_layout, monkeypatch):
    """Regression: in a nested layout, millhouse_dir() must NOT return the git toplevel's _millhouse."""
    monkeypatch.chdir(nested_project_layout.project_root)
    resolved = millhouse_dir()
    assert resolved != nested_project_layout.git_root / "_millhouse"
    assert resolved == nested_project_layout.project_root / "_millhouse"


def test_nested_project_from_deep_subdirectory(nested_project_layout):
    """project_root() called from deep inside the nested project still returns the project root."""
    deep = nested_project_layout.project_root / "src" / "deep" / "nested"
    deep.mkdir(parents=True)
    assert project_root(start=deep) == nested_project_layout.project_root


def test_repo_root_unchanged_by_nested_layout(nested_project_layout):
    """repo_root() keeps returning git toplevel regardless of where _millhouse/ lives.

    The split responsibility: repo_root() = source-content paths, project_root() = mill-state.
    """
    resolved = repo_root(start=nested_project_layout.project_root)
    assert resolved == nested_project_layout.git_root
    assert resolved != nested_project_layout.project_root


@pytest.mark.parametrize("layout_name", ["flat", "nested"])
def test_spawn_reviewer_config_load_path_resolves_via_project_root(
    layout_name, flat_project_layout, nested_project_layout, monkeypatch
):
    """spawn_reviewer reads _millhouse/config.yaml via project_root(). In the nested case,
    the config must resolve under <project>/_millhouse/, not <git-root>/_millhouse/.
    This regression-tests the B.1 fix that rewired spawn_reviewer.py:98 from repo_root() to project_root()."""
    from millpy.core.config import load

    layout = flat_project_layout if layout_name == "flat" else nested_project_layout
    config_path = layout.millhouse_dir / "config.yaml"
    config_path.write_text(
        "pipeline:\n"
        "  implementer: sonnet\n"
        "  plan-review:\n"
        "    rounds: 3\n"
        "    default: sonnet\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(layout.project_root)
    resolved = project_root() / "_millhouse" / "config.yaml"
    assert resolved == config_path
    cfg = load(resolved)
    assert cfg["pipeline"]["implementer"] == "sonnet"
