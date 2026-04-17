"""Tests for the `set_worktree_color` entrypoint (mill-color).

Covers: happy path (all 8 palette names), idempotency, invalid-color exit,
missing-argument exit, and the "not a git repo" path.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from millpy.entrypoints import set_worktree_color
from millpy.entrypoints.spawn_task import WORKTREE_COLOR_NAME_TO_HEX


def _mock_worktree_root(tmp_path: Path):
    """Patch `_resolve_worktree_root` to return tmp_path."""
    return patch.object(
        set_worktree_color, "_resolve_worktree_root", return_value=tmp_path
    )


class TestSetWorktreeColorHappy:
    def test_purple_writes_correct_hex(self, tmp_path, capsys):
        with _mock_worktree_root(tmp_path):
            exit_code = set_worktree_color.main(["purple"])
        assert exit_code == 0

        settings_path = tmp_path / ".vscode" / "settings.json"
        assert settings_path.exists()
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert data["workbench.colorCustomizations"]["titleBar.activeBackground"] == "#7d2d6b"

    @pytest.mark.parametrize("name,hex_", sorted(WORKTREE_COLOR_NAME_TO_HEX.items()))
    def test_all_palette_names_accepted(self, tmp_path, name, hex_):
        with _mock_worktree_root(tmp_path):
            exit_code = set_worktree_color.main([name])
        assert exit_code == 0

        settings_path = tmp_path / ".vscode" / "settings.json"
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert data["workbench.colorCustomizations"]["titleBar.activeBackground"] == hex_

    def test_case_insensitive(self, tmp_path):
        with _mock_worktree_root(tmp_path):
            exit_code = set_worktree_color.main(["PURPLE"])
        assert exit_code == 0

    def test_idempotent(self, tmp_path):
        """Running twice with the same color → identical settings.json content."""
        with _mock_worktree_root(tmp_path):
            set_worktree_color.main(["blue"])
            first = (tmp_path / ".vscode" / "settings.json").read_text(encoding="utf-8")
            set_worktree_color.main(["blue"])
            second = (tmp_path / ".vscode" / "settings.json").read_text(encoding="utf-8")
        assert first == second

    def test_overwrites_existing_settings(self, tmp_path):
        """Running again with a different color overwrites — explicit user action."""
        with _mock_worktree_root(tmp_path):
            set_worktree_color.main(["blue"])
            set_worktree_color.main(["red"])

        data = json.loads((tmp_path / ".vscode" / "settings.json").read_text(encoding="utf-8"))
        assert data["workbench.colorCustomizations"]["titleBar.activeBackground"] == WORKTREE_COLOR_NAME_TO_HEX["red"]


class TestSetWorktreeColorErrors:
    def test_invalid_color_exits_2_with_valid_list(self, tmp_path, capsys):
        with _mock_worktree_root(tmp_path):
            exit_code = set_worktree_color.main(["magenta"])
        assert exit_code == 2

        err = capsys.readouterr().err
        assert "magenta" in err
        # The error lists all valid names.
        for name in WORKTREE_COLOR_NAME_TO_HEX:
            assert name in err

    def test_missing_argument_exits_2(self, tmp_path):
        with _mock_worktree_root(tmp_path), pytest.raises(SystemExit) as exc:
            set_worktree_color.main([])
        assert exc.value.code == 2

    def test_not_a_git_repo_exits_nonzero(self, tmp_path, capsys):
        with patch.object(
            set_worktree_color, "_resolve_worktree_root", return_value=None
        ):
            exit_code = set_worktree_color.main(["purple"])
        assert exit_code != 0
        err = capsys.readouterr().err
        assert "git" in err.lower() or "worktree" in err.lower()


class TestResolveWorktreeRoot:
    def test_returns_none_on_nonzero_exit(self):
        """When git rejects the dir (not a repo), resolver returns None."""
        def _fake_run(*args, **kwargs):
            raise subprocess.CalledProcessError(128, args[0])
        with patch.object(subprocess, "run", _fake_run):
            assert set_worktree_color._resolve_worktree_root() is None

    def test_returns_path_on_success(self, tmp_path):
        class _FakeResult:
            stdout = str(tmp_path) + "\n"
        with patch.object(subprocess, "run", return_value=_FakeResult()):
            result = set_worktree_color._resolve_worktree_root()
        assert result == tmp_path
