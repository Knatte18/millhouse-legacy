"""
setup.py — Worktree setup helpers for millpy.

Handles VS Code settings.json generation (unique title bar color) and .env
copying. Not unit-tested (filesystem + subprocess glue).

Color palette matches mill-worktree.ps1 exactly. Fallback when all 8 colors
are in use: return the first palette entry (#2d7d46).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path


# ---------------------------------------------------------------------------
# Title bar color palette (exact order from mill-worktree.ps1)
# ---------------------------------------------------------------------------

_COLOR_PALETTE: list[str] = [
    "#2d7d46",
    "#7d2d6b",
    "#2d4f7d",
    "#7d5c2d",
    "#6b2d2d",
    "#2d6b6b",
    "#4a2d7d",
    "#7d462d",
]


def _read_existing_color(worktree: Path) -> str | None:
    """Read the titleBar.activeBackground color from a worktree's settings.json.

    Returns the color string or None if not present.
    """
    settings_path = worktree / ".vscode" / "settings.json"
    if not settings_path.exists():
        return None
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        customizations = data.get("workbench.colorCustomizations", {})
        return customizations.get("titleBar.activeBackground")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


def pick_color(existing_worktrees: list[Path]) -> str:
    """Return the first palette color not currently in use by any worktree.

    "In use" means: the worktree's .vscode/settings.json has
    workbench.colorCustomizations.titleBar.activeBackground set to that color.

    If all 8 palette colors are in use, returns the first palette entry
    (#2d7d46) as a fallback. This matches the PS1 behavior.

    Parameters
    ----------
    existing_worktrees:
        List of worktree root Paths to check for existing colors.

    Returns
    -------
    str
        A hex color string from the palette.
    """
    used: set[str] = set()
    for wt in existing_worktrees:
        color = _read_existing_color(wt)
        if color:
            used.add(color.lower())

    for color in _COLOR_PALETTE:
        if color.lower() not in used:
            return color

    # Fallback: all 8 palette colors are in use
    return _COLOR_PALETTE[0]


def write_vscode_settings(
    worktree: Path,
    color: str,
    short_name: str,
) -> None:
    """Write .vscode/settings.json with title bar color and window title.

    Parameters
    ----------
    worktree:
        Root path of the target worktree.
    color:
        Hex color string for the title bar (e.g. "#2d7d46").
    short_name:
        Short name used in the window title (e.g. "millhouse").
    """
    vscode_dir = worktree / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)

    settings = {
        "workbench.colorCustomizations": {
            "titleBar.activeBackground": color,
            "titleBar.activeForeground": "#ffffff",
            "titleBar.inactiveBackground": color,
            "titleBar.inactiveForeground": "#ffffffaa",
        },
        "window.title": f"{short_name} \u2014 ${{activeEditorShort}}",
    }

    settings_path = vscode_dir / "settings.json"
    settings_path.write_text(
        json.dumps(settings, indent=4) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def copy_env(parent_worktree: Path, child_worktree: Path) -> None:
    """Copy .env from parent worktree to child worktree if it exists.

    No-op if the parent .env is absent. Idempotent — running twice is safe.

    Parameters
    ----------
    parent_worktree:
        Source worktree root.
    child_worktree:
        Destination worktree root.
    """
    src = parent_worktree / ".env"
    if not src.exists():
        return
    dst = child_worktree / ".env"
    shutil.copy2(src, dst)
