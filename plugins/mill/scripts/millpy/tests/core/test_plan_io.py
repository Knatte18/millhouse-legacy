"""
test_plan_io.py — Tests for millpy.core.plan_io (TDD: RED → GREEN → REFACTOR).
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from millpy.core.plan_io import (
    parse_frontmatter,
    read_approved,
    read_card_index,
    read_dev_server,
    read_files_touched,
    read_plan_content,
    read_root,
    read_started,
    read_verify,
    resolve_path,
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


def make_v3_overview(tmp_path: Path, content: str | None = None) -> Path:
    """Write a minimal v3 00-overview.md and return its path."""
    d = tmp_path / "plan"
    d.mkdir(exist_ok=True)
    p = d / "00-overview.md"
    text = content or textwrap.dedent("""\
        ---
        kind: plan-overview
        task: Test Task v3
        verify: python -m pytest tests
        dev-server: N/A
        approved: false
        started: 20260415-120000
        root: plugins/mill/scripts/millpy
        ---

        # Test Task v3

        ## Context

        A simple task.

        ## Shared Constraints

        - Use log_util.

        ## Shared Decisions

        (None.)

        ## Card Index

        ```yaml
        1:
          slug: add-foo
          creates: [core/foo.py]
          modifies: []
          reads: [core/bar.py]
          depends-on: []
        2:
          slug: update-bar
          creates: []
          modifies: [core/bar.py]
          reads: [core/foo.py]
          depends-on: [1]
        ```

        ## All Files Touched

        - core/foo.py
        - core/bar.py
    """)
    p.write_text(text, encoding="utf-8")
    return p


def make_v3_card(
    tmp_path: Path,
    filename: str = "card-01-add-foo.md",
    content: str | None = None,
) -> Path:
    """Write a v3 card file and return its path."""
    d = tmp_path / "plan"
    d.mkdir(exist_ok=True)
    p = d / filename
    text = content or textwrap.dedent("""\
        ---
        kind: plan-card
        card-number: 1
        card-slug: add-foo
        ---

        ### Step 1: Add foo.py

        - **Creates:** `core/foo.py`
        - **Modifies:** none
        - **Reads:** `core/bar.py`
        - **Requirements:**
          - Requirement 1.
        - **Explore:**
          - `core/bar.py` — pattern to follow.
        - **depends-on:** []
        - **Commit:** `feat: add foo`
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

# ---------------------------------------------------------------------------
# v3 resolve_plan_path
# ---------------------------------------------------------------------------

class TestResolvePlanPathV3:
    def test_v3_detected_by_card_files(self, tmp_path):
        make_v3_overview(tmp_path)
        make_v3_card(tmp_path, "card-01-add-foo.md")
        make_v3_card(tmp_path, "card-02-update-bar.md")
        loc = resolve_plan_path(tmp_path)
        assert loc is not None
        assert loc.kind == "v3"
        assert loc.path == tmp_path / "plan"
        assert loc.overview == tmp_path / "plan" / "00-overview.md"
        assert [c.name for c in loc.cards] == ["card-01-add-foo.md", "card-02-update-bar.md"]

    def test_v3_cards_sorted_by_filename(self, tmp_path):
        make_v3_overview(tmp_path)
        make_v3_card(tmp_path, "card-02-update-bar.md")
        make_v3_card(tmp_path, "card-01-add-foo.md")
        loc = resolve_plan_path(tmp_path)
        assert [c.name for c in loc.cards] == ["card-01-add-foo.md", "card-02-update-bar.md"]

    def test_v3_batches_empty(self, tmp_path):
        make_v3_overview(tmp_path)
        make_v3_card(tmp_path, "card-01-add-foo.md")
        loc = resolve_plan_path(tmp_path)
        assert loc.batches == []

    def test_v3_wins_over_v2_batch_files(self, tmp_path):
        """v3 (card-*.md) takes priority over v2 (NN-slug.md) when both present."""
        make_v3_overview(tmp_path)
        make_v3_card(tmp_path, "card-01-add-foo.md")
        # Also add a v2-style batch file
        d = tmp_path / "plan"
        (d / "01-core.md").write_text("# batch", encoding="utf-8")
        loc = resolve_plan_path(tmp_path)
        assert loc.kind == "v3"

    def test_v3_root_field_populated(self, tmp_path):
        make_v3_overview(tmp_path)
        make_v3_card(tmp_path, "card-01-add-foo.md")
        loc = resolve_plan_path(tmp_path)
        assert loc.root == "plugins/mill/scripts/millpy"

    def test_v3_root_empty_when_absent(self, tmp_path):
        make_v3_overview(tmp_path, textwrap.dedent("""\
            ---
            kind: plan-overview
            task: No Root Task
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260415-120000
            root:
            ---
            ## Card Index
            ```yaml
            ```
            ## All Files Touched
        """))
        make_v3_card(tmp_path, "card-01-add-foo.md")
        loc = resolve_plan_path(tmp_path)
        assert loc.root == ""

    def test_v3_no_card_files_falls_back_to_v2(self, tmp_path):
        """plan/ with only NN-slug.md files → v2."""
        make_v2_overview(tmp_path)
        make_v2_batch(tmp_path, "01-core.md")
        loc = resolve_plan_path(tmp_path)
        assert loc.kind == "v2"


# ---------------------------------------------------------------------------
# read_card_index
# ---------------------------------------------------------------------------

class TestReadCardIndex:
    def test_happy_parses_two_cards(self, tmp_path):
        make_v3_overview(tmp_path)
        make_v3_card(tmp_path, "card-01-add-foo.md")
        loc = resolve_plan_path(tmp_path)
        index = read_card_index(loc)
        assert 1 in index
        assert 2 in index
        assert index[1]["slug"] == "add-foo"
        assert index[1]["creates"] == ["core/foo.py"]
        assert index[1]["modifies"] == []
        assert index[1]["reads"] == ["core/bar.py"]
        assert index[1]["depends-on"] == []
        assert index[2]["depends-on"] == ["1"]

    def test_empty_card_index_returns_empty_dict(self, tmp_path):
        make_v3_overview(tmp_path, textwrap.dedent("""\
            ---
            kind: plan-overview
            task: Empty Index
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260415-120000
            root: ""
            ---
            ## Card Index
            ```yaml
            ```
            ## All Files Touched
        """))
        make_v3_card(tmp_path, "card-01-add-foo.md")
        loc = resolve_plan_path(tmp_path)
        index = read_card_index(loc)
        assert index == {}

    def test_no_card_index_section_returns_empty_dict(self, tmp_path):
        """v2 overview (no Card Index) → empty dict."""
        make_v2_overview(tmp_path)
        loc = resolve_plan_path(tmp_path)
        index = read_card_index(loc)
        assert index == {}

    def test_multi_item_list_parsed(self, tmp_path):
        make_v3_overview(tmp_path, textwrap.dedent("""\
            ---
            kind: plan-overview
            task: Multi
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260415-120000
            root: plugins/mill
            ---
            ## Card Index
            ```yaml
            1:
              slug: multi-reads
              creates: []
              modifies: [core/a.py]
              reads: [core/b.py, core/c.py, core/d.py]
              depends-on: []
            ```
            ## All Files Touched
        """))
        make_v3_card(tmp_path, "card-01-multi-reads.md")
        loc = resolve_plan_path(tmp_path)
        index = read_card_index(loc)
        assert index[1]["reads"] == ["core/b.py", "core/c.py", "core/d.py"]
        assert index[1]["modifies"] == ["core/a.py"]

    def test_v1_returns_empty_dict(self, tmp_path):
        make_v1_plan(tmp_path)
        loc = resolve_plan_path(tmp_path)
        index = read_card_index(loc)
        assert index == {}


# ---------------------------------------------------------------------------
# read_root / resolve_path
# ---------------------------------------------------------------------------

class TestReadRootAndResolvePath:
    def test_read_root_v3(self, tmp_path):
        make_v3_overview(tmp_path)
        make_v3_card(tmp_path, "card-01-add-foo.md")
        loc = resolve_plan_path(tmp_path)
        assert read_root(loc) == "plugins/mill/scripts/millpy"

    def test_read_root_v1_empty(self, tmp_path):
        make_v1_plan(tmp_path)
        loc = resolve_plan_path(tmp_path)
        assert read_root(loc) == ""

    def test_resolve_path_with_root(self, tmp_path):
        make_v3_overview(tmp_path)
        make_v3_card(tmp_path, "card-01-add-foo.md")
        loc = resolve_plan_path(tmp_path)
        result = resolve_path(loc, "core/dag.py")
        assert result == "plugins/mill/scripts/millpy/core/dag.py"

    def test_resolve_path_no_root(self, tmp_path):
        make_v1_plan(tmp_path)
        loc = resolve_plan_path(tmp_path)
        result = resolve_path(loc, "plugins/mill/core/dag.py")
        assert result == "plugins/mill/core/dag.py"


# ---------------------------------------------------------------------------
# v3 read_files_touched (with root prefix)
# ---------------------------------------------------------------------------

class TestReadFilesTouchedV3:
    def test_v3_prepends_root(self, tmp_path):
        make_v3_overview(tmp_path)
        make_v3_card(tmp_path, "card-01-add-foo.md")
        loc = resolve_plan_path(tmp_path)
        files = read_files_touched(loc)
        assert files == [
            "plugins/mill/scripts/millpy/core/foo.py",
            "plugins/mill/scripts/millpy/core/bar.py",
        ]

    def test_v3_no_root_no_prefix(self, tmp_path):
        make_v3_overview(tmp_path, textwrap.dedent("""\
            ---
            kind: plan-overview
            task: No Root Task
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260415-120000
            root:
            ---
            ## Card Index
            ```yaml
            1:
              slug: foo
              creates: [plugins/mill/core/foo.py]
              modifies: []
              reads: []
              depends-on: []
            ```
            ## All Files Touched

            - plugins/mill/core/foo.py
        """))
        make_v3_card(tmp_path, "card-01-foo.md")
        loc = resolve_plan_path(tmp_path)
        files = read_files_touched(loc)
        assert files == ["plugins/mill/core/foo.py"]


# ---------------------------------------------------------------------------
# v3 read_plan_content
# ---------------------------------------------------------------------------

class TestReadPlanContentV3:
    def test_v3_includes_overview_and_cards(self, tmp_path):
        make_v3_overview(tmp_path)
        make_v3_card(tmp_path, "card-01-add-foo.md")
        make_v3_card(tmp_path, "card-02-update-bar.md")
        loc = resolve_plan_path(tmp_path)
        content = read_plan_content(loc)
        assert content.startswith("=== plan/00-overview.md ===\n\n")
        assert "\n\n---\n\n=== plan/card-01-add-foo.md ===" in content
        assert "\n\n---\n\n=== plan/card-02-update-bar.md ===" in content
        assert not content.endswith("---\n\n")

    def test_v3_overview_only_no_trailing_separator(self, tmp_path):
        make_v3_overview(tmp_path)
        make_v3_card(tmp_path, "card-01-add-foo.md")
        loc = resolve_plan_path(tmp_path)
        content = read_plan_content(loc)
        assert not content.rstrip().endswith("---")


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
