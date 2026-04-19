"""
entrypoints/set_worktree_color.py — ad-hoc worktree titleBar color override.

CLI: `python -m millpy.entrypoints.set_worktree_color <color-name>`

Rewrites the current worktree's `.vscode/settings.json` with the selected
palette color. Use when you want the main worktree to get a non-green color
for a demo, or a child worktree to pick a specific color instead of the
auto-assigned rotation.

The color-name → hex mapping lives in `spawn_task.WORKTREE_COLOR_NAME_TO_HEX`
so this entrypoint and the spawn-time picker stay aligned.
"""
from __future__ import annotations

from . import _bootstrap  # noqa: F401

import argparse
import subprocess
import sys
from pathlib import Path

from millpy.entrypoints.spawn_task import (
    WORKTREE_COLOR_NAME_TO_HEX,
    write_vscode_settings_with_color,
)


_EXIT_USAGE = 2
_EXIT_NOT_A_GIT_REPO = 3


def _resolve_worktree_root() -> Path | None:
    """Return the current worktree root via `git rev-parse --show-toplevel`.

    Returns None if git rejects the directory (not a git repo) — the caller
    is responsible for exiting with a clear message.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    path = result.stdout.strip()
    if not path:
        return None
    return Path(path)


def _resolve_short_name(repo_root: Path) -> str:
    """Read `repo.short-name` from `.millhouse/config.yaml`. Fall back to
    the worktree directory basename if config is missing or malformed.
    """
    import re

    config_path = repo_root / ".millhouse" / "config.yaml"
    if config_path.exists():
        try:
            for line in config_path.read_text(encoding="utf-8").splitlines():
                m = re.match(r"^\s*short-name:\s*(.+)$", line)
                if m:
                    val = m.group(1).strip().strip("'\"")
                    if val not in ("~", "null", ""):
                        return val
        except OSError:
            pass
    return repo_root.name


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mill-color",
        description="Override the current worktree's VS Code titleBar color.",
    )
    parser.add_argument(
        "color",
        help=("palette color name; one of: "
              + ", ".join(sorted(WORKTREE_COLOR_NAME_TO_HEX.keys()))),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    color_name = args.color.strip().lower()
    if color_name not in WORKTREE_COLOR_NAME_TO_HEX:
        valid = ", ".join(sorted(WORKTREE_COLOR_NAME_TO_HEX.keys()))
        print(
            f"error: {color_name!r} is not a valid worktree color. Valid: {valid}",
            file=sys.stderr,
        )
        return _EXIT_USAGE
    color_hex = WORKTREE_COLOR_NAME_TO_HEX[color_name]

    worktree_root = _resolve_worktree_root()
    if worktree_root is None:
        print(
            "error: not inside a git worktree (git rev-parse --show-toplevel failed)",
            file=sys.stderr,
        )
        return _EXIT_NOT_A_GIT_REPO

    slug = worktree_root.name
    short_name = _resolve_short_name(worktree_root)

    settings_path = write_vscode_settings_with_color(
        worktree_root, color_hex, slug, short_name,
    )
    print(f"wrote {settings_path} (color={color_name} {color_hex})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
