"""
test_wiki.py — Tests for millpy.tasks.wiki (TDD: RED → GREEN → REFACTOR).

Tests cover:
  - sync_pull happy path and error path
  - write_commit_push happy path, retry-on-push-failure, and conflict error
  - acquire_lock happy path, busy-lock timeout, and stale-lock overwrite
  - release_lock idempotency
  - auto_resolve_merge (unit level, no real git)
"""
from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from millpy.tasks.wiki import (
    LockBusy,
    WikiMergeConflict,
    WikiSyncError,
    acquire_lock,
    auto_resolve_merge,
    release_lock,
    sync_pull,
    write_commit_push,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cfg(tmp_path: Path) -> dict:
    """Minimal config dict pointing wiki clone at tmp_path."""
    return {"wiki": {"clone-path": str(tmp_path)}}


def _make_completed(returncode: int, stdout: str = "", stderr: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


# ---------------------------------------------------------------------------
# sync_pull
# ---------------------------------------------------------------------------

class TestSyncPull:
    def test_happy_path_calls_fetch_then_merge(self, tmp_path):
        """sync_pull runs fetch then merge --ff-only, returns None on success."""
        cfg = _cfg(tmp_path)
        _make_completed(0, stdout="refs/remotes/origin/HEAD")
        ok_fetch = _make_completed(0)
        ok_merge = _make_completed(0)

        with patch("millpy.tasks.wiki.subprocess_util.run") as mock_run:
            mock_run.side_effect = [
                # symbolic-ref
                _make_completed(0, stdout="refs/remotes/origin/main\n"),
                # fetch
                ok_fetch,
                # merge
                ok_merge,
            ]
            result = sync_pull(cfg)

        assert result is None
        assert mock_run.call_count == 3

    def test_symbolic_ref_failure_raises_wiki_sync_error(self, tmp_path):
        """sync_pull raises WikiSyncError when symbolic-ref fails."""
        cfg = _cfg(tmp_path)
        with patch("millpy.tasks.wiki.subprocess_util.run") as mock_run:
            mock_run.return_value = _make_completed(128, stderr="fatal: not a git repo")
            with pytest.raises(WikiSyncError):
                sync_pull(cfg)

    def test_fetch_failure_raises_wiki_sync_error(self, tmp_path):
        """sync_pull raises WikiSyncError when fetch fails."""
        cfg = _cfg(tmp_path)
        with patch("millpy.tasks.wiki.subprocess_util.run") as mock_run:
            mock_run.side_effect = [
                _make_completed(0, stdout="refs/remotes/origin/main\n"),
                _make_completed(1, stderr="fatal: unable to connect"),
            ]
            with pytest.raises(WikiSyncError):
                sync_pull(cfg)

    def test_merge_failure_raises_wiki_sync_error(self, tmp_path):
        """sync_pull raises WikiSyncError when merge --ff-only fails."""
        cfg = _cfg(tmp_path)
        with patch("millpy.tasks.wiki.subprocess_util.run") as mock_run:
            mock_run.side_effect = [
                _make_completed(0, stdout="refs/remotes/origin/main\n"),
                _make_completed(0),
                _make_completed(1, stderr="fatal: Not possible to fast-forward"),
            ]
            with pytest.raises(WikiSyncError):
                sync_pull(cfg)


# ---------------------------------------------------------------------------
# write_commit_push
# ---------------------------------------------------------------------------

class TestWriteCommitPush:
    def test_happy_path(self, tmp_path):
        """write_commit_push stages files, commits, and pushes on first try."""
        cfg = _cfg(tmp_path)
        paths = ["Home.md"]
        (tmp_path / "Home.md").write_text("# Home", encoding="utf-8")

        with patch("millpy.tasks.wiki.subprocess_util.run") as mock_run:
            mock_run.side_effect = [
                _make_completed(0),  # git add
                _make_completed(0),  # git commit
                _make_completed(0),  # git push
            ]
            write_commit_push(cfg, paths, "update Home.md")

        assert mock_run.call_count == 3

    def test_push_non_fast_forward_retries_after_rebase(self, tmp_path):
        """write_commit_push does pull --rebase then retries push on non-fast-forward."""
        cfg = _cfg(tmp_path)
        paths = ["Home.md"]

        with patch("millpy.tasks.wiki.subprocess_util.run") as mock_run:
            mock_run.side_effect = [
                _make_completed(0),  # git add
                _make_completed(0),  # git commit
                _make_completed(1, stderr="rejected non-fast-forward"),  # first push fails
                _make_completed(0),  # git pull --rebase
                _make_completed(0),  # retry push succeeds
            ]
            write_commit_push(cfg, paths, "update")

        assert mock_run.call_count == 5

    def test_irresolvable_conflict_raises_wiki_merge_conflict(self, tmp_path):
        """write_commit_push raises WikiMergeConflict when rebase has unresolvable conflict."""
        cfg = _cfg(tmp_path)
        paths = ["Home.md"]

        with patch("millpy.tasks.wiki.subprocess_util.run") as mock_run:
            with patch("millpy.tasks.wiki.auto_resolve_merge", return_value=False):
                mock_run.side_effect = [
                    _make_completed(0),  # git add
                    _make_completed(0),  # git commit
                    _make_completed(1, stderr="rejected non-fast-forward"),  # push fails
                    _make_completed(1, stderr="CONFLICT (content)"),  # pull --rebase fails
                    _make_completed(0),  # rebase --abort
                    # conflict file list
                    _make_completed(0, stdout="Home.md\n"),
                ]
                with pytest.raises(WikiMergeConflict) as exc_info:
                    write_commit_push(cfg, paths, "update")

        assert "Home.md" in exc_info.value.paths


# ---------------------------------------------------------------------------
# acquire_lock / release_lock
# ---------------------------------------------------------------------------

class TestLock:
    def test_acquire_creates_lockfile(self, tmp_path):
        """acquire_lock creates .mill-lock in the wiki clone."""
        cfg = _cfg(tmp_path)
        acquire_lock(cfg, slug="test-branch")
        lock_path = tmp_path / ".mill-lock"
        assert lock_path.exists()
        content = lock_path.read_text(encoding="utf-8")
        assert "test-branch" in content

    def test_acquire_raises_lock_busy_when_non_stale_lock_exists(self, tmp_path):
        """acquire_lock raises LockBusy when a non-stale lock is already present."""
        cfg = _cfg(tmp_path)
        lock_path = tmp_path / ".mill-lock"
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lock_path.write_text(f"other-branch\n{ts}\n", encoding="utf-8")
        with pytest.raises(LockBusy):
            acquire_lock(cfg, slug="new-branch", timeout_seconds=0.1)

    def test_acquire_overwrites_stale_lock(self, tmp_path):
        """acquire_lock overwrites a lock older than 5 minutes without raising."""
        cfg = _cfg(tmp_path)
        lock_path = tmp_path / ".mill-lock"
        # Write a stale timestamp (6 minutes ago)
        stale_ts = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=6)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        lock_path.write_text(f"stale-branch\n{stale_ts}\n", encoding="utf-8")
        # Should not raise
        acquire_lock(cfg, slug="new-branch")
        content = lock_path.read_text(encoding="utf-8")
        assert "new-branch" in content
        assert "stale-branch" not in content

    def test_release_lock_deletes_file(self, tmp_path):
        """release_lock removes the lockfile."""
        cfg = _cfg(tmp_path)
        lock_path = tmp_path / ".mill-lock"
        lock_path.write_text("test\n", encoding="utf-8")
        release_lock(cfg)
        assert not lock_path.exists()

    def test_release_lock_idempotent_when_no_file(self, tmp_path):
        """release_lock is a no-op when no lockfile exists."""
        cfg = _cfg(tmp_path)
        release_lock(cfg)  # should not raise


# ---------------------------------------------------------------------------
# auto_resolve_merge
# ---------------------------------------------------------------------------

class TestAutoResolveMerge:
    def test_returns_false_when_no_conflicts(self, tmp_path):
        """auto_resolve_merge returns False when no conflict files are found."""
        with patch("millpy.tasks.wiki.subprocess_util.run") as mock_run:
            mock_run.return_value = _make_completed(0, stdout="")
            result = auto_resolve_merge(tmp_path)
        assert result is False

    def test_home_md_additive_conflict_resolves(self, tmp_path):
        """auto_resolve_merge accepts both sides when only Home.md is conflicted
        with one unique ADD per side (different headings)."""
        conflict_content = (
            "# Wiki\n"
            "<<<<<<< HEAD\n"
            "## [active] branch-a\n"
            "=======\n"
            "## [active] branch-b\n"
            ">>>>>>> origin/main\n"
        )
        (tmp_path / "Home.md").write_text(conflict_content, encoding="utf-8")

        with patch("millpy.tasks.wiki.subprocess_util.run") as mock_run:
            mock_run.side_effect = [
                _make_completed(0, stdout="Home.md\n"),  # diff --name-only --diff-filter=U
                _make_completed(0),                      # git add Home.md
            ]
            result = auto_resolve_merge(tmp_path)
        assert result is True

    def test_sidebar_conflict_attempts_regenerate(self, tmp_path):
        """auto_resolve_merge calls regenerate_sidebar and git-adds _Sidebar.md."""
        (tmp_path / "_Sidebar.md").write_text(
            "<<<<<<< HEAD\n* A\n=======\n* B\n>>>>>>> origin/main\n",
            encoding="utf-8",
        )
        with patch("millpy.tasks.wiki.subprocess_util.run") as mock_run, \
             patch("millpy.entrypoints.regenerate_sidebar.main") as mock_regen:
            mock_run.side_effect = [
                _make_completed(0, stdout="_Sidebar.md\n"),  # diff --name-only
                _make_completed(0),                          # git add _Sidebar.md
            ]
            mock_regen.return_value = 0
            result = auto_resolve_merge(tmp_path)
        assert result is True
        mock_regen.assert_called_once()
