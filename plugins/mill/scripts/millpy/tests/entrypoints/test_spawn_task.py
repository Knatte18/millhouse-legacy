"""Contract tests for millpy.entrypoints.spawn_task.

Business logic is already covered by tests/tasks/. This file exercises
the entrypoint's CLI contract — argparse boundary behaviour, missing
required args, the "not in a git repo" error path, and worktree color logic.
"""
from __future__ import annotations

import json
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Worktree color helpers
# ---------------------------------------------------------------------------

class TestPickWorktreeColor:
    """Green is reserved for the main worktree. Child worktrees always
    pick the first NON-green palette entry. See test_pick_worktree_color.py
    for the green-exclusion invariant tests.
    """

    def _first_non_green(self):
        return next(c for c in spawn_task._WORKTREE_COLOR_PALETTE
                    if c.lower() != spawn_task._MAIN_WORKTREE_COLOR.lower())

    def test_returns_first_non_green_color_when_no_siblings(self, tmp_path):
        """When worktrees_dir is empty, returns the first non-green palette color."""
        color = spawn_task._pick_worktree_color(tmp_path)
        assert color == self._first_non_green()

    def test_skips_color_used_by_sibling_worktree(self, tmp_path):
        """Skips a color already used by a sibling worktree's .vscode/settings.json."""
        first_non_green = self._first_non_green()
        sibling = tmp_path / "sibling"
        sibling.mkdir()
        vscode = sibling / ".vscode"
        vscode.mkdir()
        (vscode / "settings.json").write_text(
            json.dumps({
                "workbench.colorCustomizations": {
                    "titleBar.activeBackground": first_non_green,
                }
            }),
            encoding="utf-8",
        )

        # Skip the first non-green (in use) → return the next non-green.
        color = spawn_task._pick_worktree_color(tmp_path)
        non_green_palette = [c for c in spawn_task._WORKTREE_COLOR_PALETTE
                             if c.lower() != spawn_task._MAIN_WORKTREE_COLOR.lower()]
        assert color == non_green_palette[1]

    def test_wraps_around_when_all_non_green_colors_in_use(self, tmp_path):
        """When all non-green colors are in use, wraps to the first non-green."""
        non_green_palette = [c for c in spawn_task._WORKTREE_COLOR_PALETTE
                             if c.lower() != spawn_task._MAIN_WORKTREE_COLOR.lower()]
        for index, color in enumerate(non_green_palette):
            sibling = tmp_path / f"sibling-{index}"
            sibling.mkdir()
            vscode = sibling / ".vscode"
            vscode.mkdir()
            (vscode / "settings.json").write_text(
                json.dumps({
                    "workbench.colorCustomizations": {
                        "titleBar.activeBackground": color,
                    }
                }),
                encoding="utf-8",
            )

        color = spawn_task._pick_worktree_color(tmp_path)
        assert color == non_green_palette[0]
        assert color.lower() != spawn_task._MAIN_WORKTREE_COLOR.lower()

    def test_missing_worktrees_dir_returns_first_non_green(self, tmp_path):
        """When worktrees_dir does not exist, returns the first non-green palette color."""
        nonexistent = tmp_path / "does-not-exist"
        color = spawn_task._pick_worktree_color(nonexistent)
        assert color == self._first_non_green()


class TestWriteVscodeSettings:
    def _make_repo_root(self, tmp_path: Path, short_name: str = "myrepo") -> Path:
        """Create a minimal repo root with config.yaml."""
        (tmp_path / "_millhouse").mkdir(parents=True, exist_ok=True)
        config = tmp_path / "_millhouse" / "config.yaml"
        config.write_text(
            f"repo:\n  short-name: \"{short_name}\"\n",
            encoding="utf-8",
        )
        return tmp_path

    def test_creates_vscode_settings_with_color(self, tmp_path):
        """Creates .vscode/settings.json in new worktree with a color from the palette."""
        repo_root = self._make_repo_root(tmp_path / "repo")
        worktree = tmp_path / "worktrees" / "my-task"
        worktree.mkdir(parents=True)

        spawn_task._write_vscode_settings(
            worktree, "my-task", repo_root, repo_root / "_millhouse" / "config.yaml"
        )

        settings_path = worktree / ".vscode" / "settings.json"
        assert settings_path.exists()
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        color = data["workbench.colorCustomizations"]["titleBar.activeBackground"]
        assert color in spawn_task._WORKTREE_COLOR_PALETTE

    def test_skips_when_settings_already_exists(self, tmp_path):
        """Does not overwrite an existing .vscode/settings.json."""
        repo_root = self._make_repo_root(tmp_path / "repo")
        worktree = tmp_path / "worktrees" / "my-task"
        vscode = worktree / ".vscode"
        vscode.mkdir(parents=True)
        existing = vscode / "settings.json"
        existing.write_text('{"existing": true}', encoding="utf-8")

        spawn_task._write_vscode_settings(
            worktree, "my-task", repo_root, repo_root / "_millhouse" / "config.yaml"
        )

        data = json.loads(existing.read_text(encoding="utf-8"))
        assert data == {"existing": True}

    def test_window_title_contains_slug(self, tmp_path):
        """window.title in the written settings contains the task slug."""
        repo_root = self._make_repo_root(tmp_path / "repo", short_name="proj")
        worktree = tmp_path / "worktrees" / "add-feature"
        worktree.mkdir(parents=True)

        spawn_task._write_vscode_settings(
            worktree, "add-feature", repo_root, repo_root / "_millhouse" / "config.yaml"
        )

        data = json.loads((worktree / ".vscode" / "settings.json").read_text(encoding="utf-8"))
        assert "add-feature" in data["window.title"]
