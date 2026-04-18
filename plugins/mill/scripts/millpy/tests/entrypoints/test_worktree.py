"""Contract tests for millpy.entrypoints.worktree (the CLI wrapper — not
to be confused with millpy.worktree.* library code).

Business logic is covered by tests/worktree/test_children.py. This file
exercises the CLI contract — argparse boundary behaviour and missing
required args.

Card 10 additions: .mill junction creation and config.local.yaml copy.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from millpy.entrypoints import worktree


def test_main_missing_required_args_exits_nonzero(capsys):
    """Missing --worktree-name and --branch-name raises SystemExit."""
    with pytest.raises(SystemExit) as exc_info:
        worktree.main([])
    assert exc_info.value.code != 0


def test_main_missing_branch_name_exits_nonzero(capsys):
    """Missing --branch-name alone is enough to fail parsing."""
    with pytest.raises(SystemExit):
        worktree.main(["--worktree-name", "foo"])


def test_main_dry_run_prints_plan_and_exits_zero(tmp_path, monkeypatch):
    """--dry-run should print the planned worktree path without creating anything."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )
    monkeypatch.chdir(tmp_path)

    exit_code = worktree.main([
        "--worktree-name", "test-wt",
        "--branch-name", "test-branch",
        "--dry-run",
    ])
    assert exit_code == 0


# ---------------------------------------------------------------------------
# Card 10: .mill junction and config.local.yaml copy
# ---------------------------------------------------------------------------

class TestWorktreeCreate:
    """Tests for the junction creation + config.local.yaml copy in main()."""

    def _setup_repo(self, tmp_path: Path) -> Path:
        """Initialize a git repo suitable for worktree operations."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "--allow-empty", "-q", "-m", "init"],
            check=True,
            env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                 "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
        )
        return repo

    def test_create_makes_mill_junction(self, tmp_path, monkeypatch):
        """After worktree add, .mill junction is created in the new worktree."""
        repo = self._setup_repo(tmp_path)
        wiki_dir = tmp_path / "test.wiki"
        wiki_dir.mkdir()

        worktrees_parent = tmp_path / "repo.worktrees"
        worktrees_parent.mkdir()
        new_wt = worktrees_parent / "test-wt"

        monkeypatch.chdir(repo)

        # Patch junction.create to record the call (avoid real mklink in CI)
        created_junctions: list[tuple] = []

        def fake_junction_create(target, link_path):
            created_junctions.append((target, link_path))
            # Simulate the junction by creating a real directory for test assertions.
            link_path.mkdir(parents=True, exist_ok=True)

        with patch("millpy.entrypoints.worktree.junction") as mock_junc, \
             patch("millpy.entrypoints.worktree.wiki_clone_path_fn", return_value=wiki_dir):
            mock_junc.create.side_effect = fake_junction_create
            mock_junc.remove.return_value = None

            exit_code = worktree.main([
                "--worktree-name", "test-wt",
                "--branch-name", "test-wt-branch",
                "--no-open",
            ])

        assert exit_code == 0, "main() should succeed"
        assert len(created_junctions) == 1, ".mill junction should be created once"
        _target, link_path = created_junctions[0]
        assert link_path.name == ".mill", "junction link_path should be named .mill"

    def test_create_copies_local_config_when_present(self, tmp_path, monkeypatch):
        """config.local.yaml from parent _millhouse/ is copied to new worktree."""
        repo = self._setup_repo(tmp_path)
        wiki_dir = tmp_path / "test.wiki"
        wiki_dir.mkdir()

        # Create a local config in the parent repo.
        src_local = repo / "_millhouse" / "config.local.yaml"
        src_local.parent.mkdir(parents=True, exist_ok=True)
        src_local.write_text("notifications:\n  slack:\n    webhook: secret\n", encoding="utf-8")

        monkeypatch.chdir(repo)

        with patch("millpy.entrypoints.worktree.junction") as mock_junc, \
             patch("millpy.entrypoints.worktree.wiki_clone_path_fn", return_value=wiki_dir):
            mock_junc.create.side_effect = lambda t, lp: lp.mkdir(parents=True, exist_ok=True)
            mock_junc.remove.return_value = None

            worktree.main([
                "--worktree-name", "test-wt",
                "--branch-name", "test-wt-branch2",
                "--no-open",
            ])

        # Find the new worktree path.
        worktrees_parent = repo.parent / f"{repo.name}.worktrees"
        new_wt = worktrees_parent / "test-wt"
        dst_local = new_wt / "_millhouse" / "config.local.yaml"
        assert dst_local.exists(), "config.local.yaml should be copied to new worktree"
        content = dst_local.read_text(encoding="utf-8")
        assert "secret" in content

    def test_create_no_error_when_local_config_absent(self, tmp_path, monkeypatch):
        """No error when parent has no config.local.yaml."""
        repo = self._setup_repo(tmp_path)
        wiki_dir = tmp_path / "test.wiki"
        wiki_dir.mkdir()

        monkeypatch.chdir(repo)

        with patch("millpy.entrypoints.worktree.junction") as mock_junc, \
             patch("millpy.entrypoints.worktree.wiki_clone_path_fn", return_value=wiki_dir):
            mock_junc.create.side_effect = lambda t, lp: lp.mkdir(parents=True, exist_ok=True)
            mock_junc.remove.return_value = None

            exit_code = worktree.main([
                "--worktree-name", "test-wt",
                "--branch-name", "test-wt-branch3",
                "--no-open",
            ])

        assert exit_code == 0


class TestWorktreeRemove:
    """Tests for the remove() function and junction cleanup."""

    def test_remove_clears_junction_before_git_cleanup(self, tmp_path):
        """remove() calls junction.remove for .mill before git worktree remove."""
        wt_path = tmp_path / "my-wt"
        wt_path.mkdir()
        mill_dir = wt_path / ".mill"
        mill_dir.mkdir()

        remove_calls: list[Path] = []

        def fake_junction_remove(lp):
            remove_calls.append(lp)

        with patch("millpy.entrypoints.worktree.junction") as mock_junc, \
             patch("millpy.entrypoints.worktree._git_worktree_remove") as mock_gwr:
            mock_junc.remove.side_effect = fake_junction_remove
            mock_gwr.return_value = None

            worktree.remove(wt_path)

        assert len(remove_calls) == 1
        assert remove_calls[0] == mill_dir

    def test_remove_idempotent_when_no_junction(self, tmp_path):
        """remove() is a no-op for .mill when junction doesn't exist."""
        wt_path = tmp_path / "my-wt"
        wt_path.mkdir()
        # No .mill directory.

        with patch("millpy.entrypoints.worktree.junction") as mock_junc, \
             patch("millpy.entrypoints.worktree._git_worktree_remove") as mock_gwr:
            mock_junc.remove.return_value = None
            mock_gwr.return_value = None

            worktree.remove(wt_path)  # Should not raise

        mock_junc.remove.assert_called_once_with(wt_path / ".mill")
