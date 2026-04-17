"""Regression tests for `_pick_worktree_color` — green is always excluded.

The main worktree invariant is that its `.vscode/settings.json` has
`titleBar.activeBackground = "#2d7d46"` (green). Child worktrees MUST NOT
pick green, even if the main worktree's settings.json is missing or has
a different color. See plugins/mill/skills/mill-setup/SKILL.md for the
main-is-always-green invariant and `_MAIN_WORKTREE_COLOR` in spawn_task.
"""
from __future__ import annotations

import json

from millpy.entrypoints import spawn_task


_GREEN = "#2d7d46"


def test_green_is_excluded_when_worktrees_dir_empty(tmp_path):
    """Empty worktrees_dir returns purple, never green."""
    color = spawn_task._pick_worktree_color(tmp_path)
    assert color.lower() != _GREEN.lower()
    assert color == "#7d2d6b"  # purple — first non-green color


def test_green_is_excluded_when_sibling_uses_purple(tmp_path):
    """Sibling using purple → returns next non-green non-purple = blue."""
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    vscode = sibling / ".vscode"
    vscode.mkdir()
    (vscode / "settings.json").write_text(
        json.dumps({
            "workbench.colorCustomizations": {
                "titleBar.activeBackground": "#7d2d6b",  # purple
            }
        }),
        encoding="utf-8",
    )

    color = spawn_task._pick_worktree_color(tmp_path)
    assert color.lower() != _GREEN.lower()
    assert color == "#2d4f7d"  # blue


def test_wraps_to_purple_never_green_when_all_non_green_in_use(tmp_path):
    """With all 7 non-green colors in use, wrap to purple — never green."""
    non_green_palette = [c for c in spawn_task._WORKTREE_COLOR_PALETTE
                        if c.lower() != _GREEN.lower()]
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
    assert color.lower() != _GREEN.lower()
    assert color == "#7d2d6b"  # purple


def test_green_excluded_even_when_sibling_uses_green(tmp_path):
    """Sibling with green settings.json → green is ignored (already excluded)."""
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    vscode = sibling / ".vscode"
    vscode.mkdir()
    (vscode / "settings.json").write_text(
        json.dumps({
            "workbench.colorCustomizations": {
                "titleBar.activeBackground": _GREEN,
            }
        }),
        encoding="utf-8",
    )

    color = spawn_task._pick_worktree_color(tmp_path)
    assert color.lower() != _GREEN.lower()
    assert color == "#7d2d6b"  # purple


def test_nonexistent_worktrees_dir_returns_purple(tmp_path):
    """Missing worktrees_dir → purple, never green."""
    nonexistent = tmp_path / "does-not-exist"
    color = spawn_task._pick_worktree_color(nonexistent)
    assert color.lower() != _GREEN.lower()
    assert color == "#7d2d6b"


def test_malformed_sibling_settings_treated_as_no_color(tmp_path):
    """Sibling with malformed settings.json (missing titleBar field) → purple."""
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    vscode = sibling / ".vscode"
    vscode.mkdir()
    (vscode / "settings.json").write_text(
        json.dumps({"workbench.colorCustomizations": {}}),
        encoding="utf-8",
    )

    color = spawn_task._pick_worktree_color(tmp_path)
    assert color == "#7d2d6b"  # purple


def test_main_worktree_color_constant_is_green():
    """Sanity pin — the main-worktree-color constant is #2d7d46."""
    assert spawn_task._MAIN_WORKTREE_COLOR.lower() == _GREEN.lower()
