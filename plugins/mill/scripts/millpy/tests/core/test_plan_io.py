"""
test_plan_io.py — Tests for millpy.core.plan_io (TDD: RED → GREEN → REFACTOR).
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from millpy.core.plan_io import (
    PlanLocation,
    parse_frontmatter,
    read_approved,
    read_dev_server,
    read_files_touched,
    read_plan_content,
    read_started,
    read_verify,
    resolve_plan_path,
    write_approved,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_v1_plan(tmp_path: Path, content: str | None = None) -> Path:
    """Write a minimal v1 plan.md and return its path."""
    p = tmp_path / "plan.md"
    text = content or textwrap.dedent("""\
        ---
        verify: python -m pytest tests
        dev-server: N/A
        approved: false
        started: 20260415-120000
        ---

        # Test Task

        ## Context

        A simple task.

        ## Files

        - plugins/mill/foo.py
        - plugins/mill/bar.py

        ## Steps

        ### Step 1: Do something

        - **Creates:** plugins/mill/foo.py
        - **Modifies:** none
        - **Requirements:**
          - Requirement 1.
        - **Commit:** `feat: add foo`
    """)
    p.write_text(text, encoding="utf-8")
    return p


def make_v2_overview(tmp_path: Path, content: str | None = None) -> Path:
    """Write a minimal v2 00-overview.md and return its path."""
    d = tmp_path / "plan"
    d.mkdir(exist_ok=True)
    p = d / "00-overview.md"
    text = content or textwrap.dedent("""\
        ---
        kind: plan-overview
        task: Test Task
        verify: python -m pytest tests
        dev-server: N/A
        approved: false
        started: 20260415-120000
        batches: [core, tasks]
        ---

        # Test Task

        ## Context

        A simple task.

        ## Shared Constraints

        - Use log_util.

        ## Shared Decisions

        (None.)

        ## Batch Graph

        ```yaml
        batches:
          core:
            depends-on: []
            summary: "Core module."
          tasks:
            depends-on: [core]
            summary: "Tasks module."
        ```

        ## All Files Touched

        - plugins/mill/foo.py
        - plugins/mill/bar.py
    """)
    p.write_text(text, encoding="utf-8")
    return p


def make_v2_batch(tmp_path: Path, filename: str = "01-core.md", content: str | None = None) -> Path:
    """Write a batch file and return its path."""
    d = tmp_path / "plan"
    d.mkdir(exist_ok=True)
    p = d / filename
    text = content or textwrap.dedent("""\
        ---
        kind: plan-batch
        batch-name: core
        batch-depends: []
        approved: false
        ---

        # Batch 01: core

        ## Batch-Specific Context

        (None.)

        ## Batch Files

        - plugins/mill/foo.py

        ## Steps

        ### Step 1: Create foo.py

        - **Creates:** plugins/mill/foo.py
        - **Modifies:** none
        - **Commit:** `feat: add foo`
    """)
    p.write_text(text, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# resolve_plan_path
# ---------------------------------------------------------------------------

class TestResolvePlanPath:
    def test_v1_plan_md(self, tmp_path):
        make_v1_plan(tmp_path)
        loc = resolve_plan_path(tmp_path)
        assert loc is not None
        assert loc.kind == "v1"
        assert loc.path == tmp_path / "plan.md"
        assert loc.overview is None
        assert loc.batches == []

    def test_v2_directory(self, tmp_path):
        make_v2_overview(tmp_path)
        make_v2_batch(tmp_path, "01-core.md")
        make_v2_batch(tmp_path, "02-tasks.md")
        loc = resolve_plan_path(tmp_path)
        assert loc is not None
        assert loc.kind == "v2"
        assert loc.path == tmp_path / "plan"
        assert loc.overview == tmp_path / "plan" / "00-overview.md"
        # Batches in filename order, overview excluded
        assert [b.name for b in loc.batches] == ["01-core.md", "02-tasks.md"]

    def test_neither_returns_none(self, tmp_path):
        loc = resolve_plan_path(tmp_path)
        assert loc is None

    def test_both_present_v2_wins(self, tmp_path, capsys):
        make_v1_plan(tmp_path)
        make_v2_overview(tmp_path)
        loc = resolve_plan_path(tmp_path)
        assert loc is not None
        assert loc.kind == "v2"
        captured = capsys.readouterr()
        assert "v2 takes precedence" in captured.err

    def test_v2_missing_overview_raises(self, tmp_path):
        d = tmp_path / "plan"
        d.mkdir()
        # No 00-overview.md — just a stray file
        (d / "01-core.md").write_text("hi", encoding="utf-8")
        with pytest.raises((FileNotFoundError, ValueError)):
            resolve_plan_path(tmp_path)


# ---------------------------------------------------------------------------
# read_plan_content
# ---------------------------------------------------------------------------

class TestReadPlanContent:
    def test_v1_verbatim(self, tmp_path):
        make_v1_plan(tmp_path)
        loc = resolve_plan_path(tmp_path)
        content = read_plan_content(loc)
        expected = (tmp_path / "plan.md").read_text(encoding="utf-8")
        assert content == expected

    def test_v2_separator_format(self, tmp_path):
        make_v2_overview(tmp_path)
        make_v2_batch(tmp_path, "01-core.md")
        make_v2_batch(tmp_path, "02-tasks.md")
        loc = resolve_plan_path(tmp_path)
        content = read_plan_content(loc)

        # Should start with the overview header
        assert content.startswith("=== plan/00-overview.md ===\n\n")
        # Should have a separator between overview and first batch
        assert "\n\n---\n\n=== plan/01-core.md ===" in content
        # Should have a separator between batches
        assert "\n\n---\n\n=== plan/02-tasks.md ===" in content
        # Final file should NOT have a trailing separator
        assert not content.endswith("---\n\n")
        assert not content.endswith("---\n")

    def test_v2_single_batch_no_trailing_separator(self, tmp_path):
        make_v2_overview(tmp_path)
        make_v2_batch(tmp_path, "01-core.md")
        loc = resolve_plan_path(tmp_path)
        content = read_plan_content(loc)
        # No trailing separator
        assert not content.rstrip().endswith("---")

    def test_v2_overview_only_no_separator(self, tmp_path):
        """An overview with no batch files should still produce valid output."""
        make_v2_overview(tmp_path)
        loc = resolve_plan_path(tmp_path)
        content = read_plan_content(loc)
        assert content.startswith("=== plan/00-overview.md ===\n\n")
        # No file separator should exist (frontmatter --- is ok)
        assert "\n\n---\n\n" not in content


# ---------------------------------------------------------------------------
# read_files_touched
# ---------------------------------------------------------------------------

class TestReadFilesTouched:
    def test_v1_files_section(self, tmp_path):
        make_v1_plan(tmp_path)
        loc = resolve_plan_path(tmp_path)
        files = read_files_touched(loc)
        assert files == ["plugins/mill/foo.py", "plugins/mill/bar.py"]

    def test_v2_all_files_touched_section(self, tmp_path):
        make_v2_overview(tmp_path)
        loc = resolve_plan_path(tmp_path)
        files = read_files_touched(loc)
        assert files == ["plugins/mill/foo.py", "plugins/mill/bar.py"]

    def test_strips_leading_dash_and_whitespace(self, tmp_path):
        p = tmp_path / "plan.md"
        p.write_text(textwrap.dedent("""\
            ---
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260101-000000
            ---
            ## Files
            - path/a.py
            -  path/b.py
            -   path/c.py
        """), encoding="utf-8")
        loc = resolve_plan_path(tmp_path)
        files = read_files_touched(loc)
        assert files == ["path/a.py", "path/b.py", "path/c.py"]


# ---------------------------------------------------------------------------
# read_approved / write_approved
# ---------------------------------------------------------------------------

class TestApproved:
    def test_read_v1_false(self, tmp_path):
        make_v1_plan(tmp_path)
        loc = resolve_plan_path(tmp_path)
        assert read_approved(loc) is False

    def test_read_v2_false(self, tmp_path):
        make_v2_overview(tmp_path)
        loc = resolve_plan_path(tmp_path)
        assert read_approved(loc) is False

    def test_write_v1_flip_to_true(self, tmp_path):
        make_v1_plan(tmp_path)
        loc = resolve_plan_path(tmp_path)
        write_approved(loc, True)
        # Read back
        loc2 = resolve_plan_path(tmp_path)
        assert read_approved(loc2) is True
        # Only the approved line changed — verify other frontmatter intact
        text = (tmp_path / "plan.md").read_text(encoding="utf-8")
        assert "verify: python -m pytest tests" in text
        assert "approved: true" in text
        assert "approved: false" not in text

    def test_write_v2_only_overview_changes(self, tmp_path):
        make_v2_overview(tmp_path)
        make_v2_batch(tmp_path, "01-core.md")
        batch_before = (tmp_path / "plan" / "01-core.md").read_bytes()
        loc = resolve_plan_path(tmp_path)
        write_approved(loc, True)
        # Batch file untouched
        assert (tmp_path / "plan" / "01-core.md").read_bytes() == batch_before
        # Overview updated
        loc2 = resolve_plan_path(tmp_path)
        assert read_approved(loc2) is True

    def test_write_v1_body_with_matching_key_not_corrupted(self, tmp_path):
        """Body lines containing 'approved:' must not be modified by write_approved."""
        p = tmp_path / "plan.md"
        p.write_text(textwrap.dedent("""\
            ---
            verify: pytest
            dev-server: N/A
            approved: false
            started: 20260415-120000
            ---

            # Task

            ## Context

            The plan approved: false description is accurate.
            approved: this line is in the body, not frontmatter.
        """), encoding="utf-8")
        loc = resolve_plan_path(tmp_path)
        write_approved(loc, True)
        text = p.read_text(encoding="utf-8")
        # Frontmatter field updated
        assert "approved: true\n" in text
        assert "approved: false\n" not in text
        # Body lines untouched
        assert "The plan approved: false description is accurate." in text
        assert "approved: this line is in the body, not frontmatter." in text

    def test_write_v1_crlf_line_endings_preserved(self, tmp_path):
        """CRLF line endings are preserved byte-for-byte after write_approved."""
        crlf_content = (
            "---\r\n"
            "verify: python -m pytest tests\r\n"
            "dev-server: N/A\r\n"
            "approved: false\r\n"
            "started: 20260415-120000\r\n"
            "---\r\n"
            "\r\n"
            "# Test Task\r\n"
        )
        p = tmp_path / "plan.md"
        p.write_bytes(crlf_content.encode("utf-8"))
        loc = resolve_plan_path(tmp_path)
        write_approved(loc, True)
        result = p.read_bytes()
        # approved line flipped
        assert b"approved: true\r\n" in result
        assert b"approved: false\r\n" not in result
        # all other lines preserve CRLF
        assert b"verify: python -m pytest tests\r\n" in result
        assert b"dev-server: N/A\r\n" in result
        assert b"started: 20260415-120000\r\n" in result


# ---------------------------------------------------------------------------
# read_started, read_verify, read_dev_server
# ---------------------------------------------------------------------------

class TestReadScalars:
    def test_read_started_v1(self, tmp_path):
        make_v1_plan(tmp_path)
        loc = resolve_plan_path(tmp_path)
        assert read_started(loc) == "20260415-120000"

    def test_read_verify_v1(self, tmp_path):
        make_v1_plan(tmp_path)
        loc = resolve_plan_path(tmp_path)
        assert read_verify(loc) == "python -m pytest tests"

    def test_read_dev_server_na_returns_none(self, tmp_path):
        make_v1_plan(tmp_path)
        loc = resolve_plan_path(tmp_path)
        assert read_dev_server(loc) is None

    def test_read_dev_server_value(self, tmp_path):
        p = tmp_path / "plan.md"
        p.write_text(textwrap.dedent("""\
            ---
            verify: noop
            dev-server: npm run dev
            approved: false
            started: 20260101-000000
            ---
        """), encoding="utf-8")
        loc = resolve_plan_path(tmp_path)
        assert read_dev_server(loc) == "npm run dev"

    def test_read_dev_server_missing_returns_none(self, tmp_path):
        p = tmp_path / "plan.md"
        p.write_text(textwrap.dedent("""\
            ---
            verify: noop
            approved: false
            started: 20260101-000000
            ---
        """), encoding="utf-8")
        loc = resolve_plan_path(tmp_path)
        assert read_dev_server(loc) is None

    def test_read_verify_missing_raises(self, tmp_path):
        p = tmp_path / "plan.md"
        p.write_text(textwrap.dedent("""\
            ---
            approved: false
            started: 20260101-000000
            ---
        """), encoding="utf-8")
        loc = resolve_plan_path(tmp_path)
        with pytest.raises(ValueError, match="verify"):
            read_verify(loc)

    def test_read_started_missing_raises(self, tmp_path):
        p = tmp_path / "plan.md"
        p.write_text(textwrap.dedent("""\
            ---
            verify: noop
            approved: false
            ---
        """), encoding="utf-8")
        loc = resolve_plan_path(tmp_path)
        with pytest.raises(ValueError, match="started"):
            read_started(loc)

    def test_read_v2_from_overview(self, tmp_path):
        make_v2_overview(tmp_path)
        loc = resolve_plan_path(tmp_path)
        assert read_verify(loc) == "python -m pytest tests"
        assert read_started(loc) == "20260415-120000"
        assert read_dev_server(loc) is None


# ---------------------------------------------------------------------------
# parse_frontmatter — public wrapper
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    def test_scalar_types(self):
        text = textwrap.dedent("""\
            ---
            verify: python -m pytest
            approved: false
            started: 20260415-000000
            ---
        """)
        fm = parse_frontmatter(text)
        assert fm["verify"] == "python -m pytest"
        assert fm["approved"] is False
        assert fm["started"] == "20260415-000000"

    def test_inline_list(self):
        text = textwrap.dedent("""\
            ---
            batches: [core, tasks-worktree, backends]
            ---
        """)
        fm = parse_frontmatter(text)
        assert fm["batches"] == ["core", "tasks-worktree", "backends"]

    def test_inline_list_empty(self):
        text = textwrap.dedent("""\
            ---
            batch-depends: []
            ---
        """)
        fm = parse_frontmatter(text)
        assert fm["batch-depends"] == []

    def test_no_frontmatter_returns_empty(self):
        fm = parse_frontmatter("# Title\n\nNo frontmatter here.")
        assert fm == {}
