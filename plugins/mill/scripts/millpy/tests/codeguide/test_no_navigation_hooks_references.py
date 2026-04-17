"""Regression guard — no `NavigationHooks` references under plugins/mill/.

NavigationHooks was removed from the codeguide workflow. Any future
reintroduction fails this test with a precise file:line report so the
offender can find and delete it.

The test file itself is skipped (it must contain the sentinel string to
assert on).
"""
from __future__ import annotations

import subprocess
from pathlib import Path


SENTINEL = "NavigationHooks"
# File extensions that can plausibly carry NavigationHooks references.
SCAN_EXTS = {".md", ".py", ".yaml", ".yml"}
# Paths under plugins/mill/ that the walker skips.
SKIP_DIRS = {"_millhouse", "_codeguide", "__pycache__"}


def _repo_root() -> Path:
    out = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
    return Path(out)


def _this_file() -> Path:
    return Path(__file__).resolve()


def _iter_files(root: Path):
    for entry in root.rglob("*"):
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in SCAN_EXTS:
            continue
        if entry.name.endswith(".bak"):
            continue
        parts = set(entry.relative_to(root).parts)
        if parts & SKIP_DIRS:
            continue
        yield entry


def test_no_navigation_hooks_references_remain():
    """Fail with a precise file:line list if any NavigationHooks references exist."""
    plugin_root = _repo_root() / "plugins" / "mill"
    this_file = _this_file()
    hits: list[str] = []

    for entry in _iter_files(plugin_root):
        if entry.resolve() == this_file:
            continue
        try:
            text = entry.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if SENTINEL in line:
                rel = entry.relative_to(plugin_root).as_posix()
                hits.append(f"{rel}:{lineno}: {line.strip()}")

    assert not hits, (
        f"Found {len(hits)} NavigationHooks reference(s) under plugins/mill/ "
        "(NavigationHooks was removed from the codeguide workflow):\n"
        + "\n".join(hits)
    )
