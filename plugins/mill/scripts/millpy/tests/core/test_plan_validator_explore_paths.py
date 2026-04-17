"""Tests for `_extract_bullet_paths` — only path-like tokens count as paths.

Code identifiers in Explore commentary ( `_FOO`, `do_thing()`, `<TOKEN>` )
must not be misread as paths. Before the fix, every backtick-wrapped token
was treated as a path and triggered spurious "Explore path X not in Reads"
BLOCKING errors. See issue backlog entry "plan_validator Explore-path
parsing" (2026-04-16 sweep).
"""
from __future__ import annotations

from millpy.core.plan_validator import _extract_bullet_paths, _looks_like_path


class TestLooksLikePath:
    """Unit tests for the path-detection heuristic."""

    def test_slash_counts_as_path(self):
        assert _looks_like_path("plugins/mill/foo.py")
        assert _looks_like_path("templates/wrappers")  # extensionless but has /
        assert _looks_like_path("plugins/mill")

    def test_known_extension_counts_as_path(self):
        assert _looks_like_path("settings.json")  # root-level, no /
        assert _looks_like_path("SKILL.md")
        assert _looks_like_path("config.yaml")
        assert _looks_like_path("foo.py")

    def test_code_identifiers_are_not_paths(self):
        assert not _looks_like_path("_BAR")
        assert not _looks_like_path("do_thing()")
        assert not _looks_like_path("_WORKTREE_COLOR_PALETTE")
        assert not _looks_like_path("some_var")

    def test_placeholders_are_not_paths(self):
        assert not _looks_like_path("<TOKEN>")
        assert not _looks_like_path("{foo}")
        assert not _looks_like_path("${activeEditorShort}")


class TestExtractBulletPaths:
    def test_bullet_with_path_and_identifiers(self):
        """Leading path is extracted; code identifiers are ignored."""
        bullet = (
            "  - `scripts/foo.py` — the `_BAR` constant, `do_thing()` function"
        )
        paths = _extract_bullet_paths(bullet)
        assert paths == {"scripts/foo.py"}
        assert "_BAR" not in paths
        assert "do_thing()" not in paths

    def test_bullet_with_two_real_paths(self):
        """A bullet can reference multiple paths — both are extracted."""
        bullet = "  - `foo.py` and `bar.py`, compare how they differ"
        paths = _extract_bullet_paths(bullet)
        assert paths == {"foo.py", "bar.py"}

    def test_bullet_with_only_code_identifier(self):
        """Bullet mentioning only a bare identifier → no paths extracted."""
        bullet = "  - `some_var` — an unused global in the scope"
        paths = _extract_bullet_paths(bullet)
        assert paths == set()

    def test_bullet_with_placeholder_and_path(self):
        """Markdown-heavy commentary with placeholders still yields the path."""
        bullet = (
            "  - `path/to/file.py` — see the `{token}` placeholder, "
            "the `<TOKEN>` form, and `_underscored_thing`"
        )
        paths = _extract_bullet_paths(bullet)
        assert paths == {"path/to/file.py"}

    def test_bullet_with_no_backticks(self):
        """No backticks → no paths (Explore convention requires backticks)."""
        bullet = "  - see the spawn_task module"
        assert _extract_bullet_paths(bullet) == set()

    def test_bullet_with_slash_extensionless(self):
        """Token with '/' but no extension is still a path (e.g. directories)."""
        bullet = "  - `templates/wrappers` — the wrapper template dir"
        paths = _extract_bullet_paths(bullet)
        assert paths == {"templates/wrappers"}

    def test_bullet_with_extension_no_slash(self):
        """Token with known extension but no '/' is a path (root-level file)."""
        bullet = "  - `settings.json` — the VS Code settings file"
        paths = _extract_bullet_paths(bullet)
        assert paths == {"settings.json"}

    def test_multi_line_field(self):
        """Multi-line field values still extract paths per line."""
        field = (
            "  - `plugins/mill/foo.py` — one\n"
            "  - `plugins/mill/bar.py` — two, with `_PALETTE` constant"
        )
        paths = _extract_bullet_paths(field)
        assert paths == {"plugins/mill/foo.py", "plugins/mill/bar.py"}
