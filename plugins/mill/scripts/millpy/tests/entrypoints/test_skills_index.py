"""Unit tests for millpy.entrypoints.skills_index.

Tests the scanner against synthetic plugin/skills trees in tmp_path and
verifies the deterministic/byte-identical output contract.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from millpy.entrypoints.skills_index import (
    render_table,
    scan_skills,
    write_outputs,
)


def _write_skill(path: Path, name: str, description: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = textwrap.dedent(
        f"""\
        ---
        name: {name}
        description: {description}
        ---

        # {name}

        Body text for {name}.
        """
    )
    path.write_text(content, encoding="utf-8", newline="\n")


def _seed_synthetic_repo(repo_root: Path) -> None:
    """Build plugins/mill/skills/alpha, .../beta and plugins/python/skills/gamma."""
    _write_skill(
        repo_root / "plugins" / "mill" / "skills" / "alpha" / "SKILL.md",
        "alpha",
        "First alpha skill.",
    )
    _write_skill(
        repo_root / "plugins" / "mill" / "skills" / "beta" / "SKILL.md",
        "beta",
        "Second beta skill.",
    )
    _write_skill(
        repo_root / "plugins" / "python" / "skills" / "gamma" / "SKILL.md",
        "gamma",
        "Python gamma skill.",
    )


class TestScanSkills:
    def test_three_skills_across_two_plugins(self, tmp_path):
        _seed_synthetic_repo(tmp_path)
        result = scan_skills(tmp_path)
        assert sorted(result.keys()) == ["mill", "python"]
        assert [e["name"] for e in result["mill"]] == ["alpha", "beta"]
        assert [e["name"] for e in result["python"]] == ["gamma"]

    def test_entries_are_sorted_alphabetically(self, tmp_path):
        _write_skill(tmp_path / "plugins" / "mill" / "skills" / "z" / "SKILL.md", "z", "Z.")
        _write_skill(tmp_path / "plugins" / "mill" / "skills" / "a" / "SKILL.md", "a", "A.")
        _write_skill(tmp_path / "plugins" / "mill" / "skills" / "m" / "SKILL.md", "m", "M.")
        result = scan_skills(tmp_path)
        assert [e["name"] for e in result["mill"]] == ["a", "m", "z"]

    def test_missing_frontmatter_is_skipped(self, tmp_path, capsys):
        p = tmp_path / "plugins" / "mill" / "skills" / "broken" / "SKILL.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# No frontmatter here\n\nJust a body.\n", encoding="utf-8", newline="\n")
        result = scan_skills(tmp_path)
        assert result["mill"] == []
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower() or "warning" in captured.out.lower()

    def test_frontmatter_missing_name_is_skipped(self, tmp_path, capsys):
        p = tmp_path / "plugins" / "mill" / "skills" / "partial" / "SKILL.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "---\ndescription: No name\n---\n\nBody.\n",
            encoding="utf-8",
            newline="\n",
        )
        result = scan_skills(tmp_path)
        assert result["mill"] == []


class TestRenderTable:
    def test_exact_markdown_output(self):
        entries = [
            {"name": "alpha", "description": "A.", "path": "plugins/mill/skills/alpha/SKILL.md"},
            {"name": "beta", "description": "B.", "path": "plugins/mill/skills/beta/SKILL.md"},
        ]
        out = render_table(entries, "# Skills", Path("."))
        assert out == (
            "# Skills\n"
            "\n"
            "| Skill | Description |\n"
            "|---|---|\n"
            "| [alpha](plugins/mill/skills/alpha/SKILL.md) | A. |\n"
            "| [beta](plugins/mill/skills/beta/SKILL.md) | B. |\n"
        )

    def test_relative_links_for_per_plugin_index(self):
        entries = [
            {"name": "alpha", "description": "A.", "path": "plugins/mill/skills/alpha/SKILL.md"},
        ]
        out = render_table(entries, "# Mill Skills", Path("plugins") / "mill" / "skills")
        assert "[alpha](alpha/SKILL.md)" in out

    def test_description_collapses_embedded_newlines(self):
        entries = [
            {"name": "x", "description": "line 1\nline 2", "path": "plugins/mill/skills/x/SKILL.md"},
        ]
        out = render_table(entries, "# Skills", Path("."))
        assert "line 1 line 2" in out
        for row in out.splitlines():
            if row.startswith("| [x]"):
                assert "\n" not in row


class TestWriteOutputs:
    def test_idempotent_writes_produce_byte_identical_bytes(self, tmp_path):
        _seed_synthetic_repo(tmp_path)
        scan = scan_skills(tmp_path)
        write_outputs(tmp_path, scan)
        first_bytes = (tmp_path / "SKILLS.md").read_bytes()
        write_outputs(tmp_path, scan)
        second_bytes = (tmp_path / "SKILLS.md").read_bytes()
        assert first_bytes == second_bytes

    def test_no_crlf_in_generated_skills_md(self, tmp_path):
        _seed_synthetic_repo(tmp_path)
        scan = scan_skills(tmp_path)
        write_outputs(tmp_path, scan)
        data = (tmp_path / "SKILLS.md").read_bytes()
        assert b"\r\n" not in data

    def test_per_plugin_index_contains_only_its_skills(self, tmp_path):
        _seed_synthetic_repo(tmp_path)
        scan = scan_skills(tmp_path)
        write_outputs(tmp_path, scan)
        mill_index = (tmp_path / "plugins" / "mill" / "skills" / "INDEX.md").read_text(encoding="utf-8")
        assert "alpha" in mill_index and "beta" in mill_index
        assert "gamma" not in mill_index

    def test_combined_skills_md_contains_all(self, tmp_path):
        _seed_synthetic_repo(tmp_path)
        scan = scan_skills(tmp_path)
        write_outputs(tmp_path, scan)
        combined = (tmp_path / "SKILLS.md").read_text(encoding="utf-8")
        for marker in ("alpha", "beta", "gamma"):
            assert marker in combined
