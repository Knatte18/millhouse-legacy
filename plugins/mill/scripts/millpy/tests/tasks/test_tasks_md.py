"""
test_tasks_md.py — Tests for millpy.tasks.tasks_md (TDD: RED → GREEN → REFACTOR).
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from millpy.tasks.tasks_md import Task, find, parse, render, validate


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def write_tasks(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "tasks.md"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


MINIMAL = """\
    # Tasks

    ## Task One
    A simple task.

    ## [active] Task Two
    - Bullet one
    - Bullet two
"""

TWO_H1 = """\
    # Tasks

    # Extra H1

    ## Task One
"""

WITH_GT_MARKER = """\
    # Tasks

    ## [>] Ready Task
    Description here.

    ## [done] Done Task
"""

PROSE_BODY = """\
    # Tasks

    ## Prose Task
    This is the first paragraph. It spans one line.

    This is the second paragraph.

    And a third.
"""


# ---------------------------------------------------------------------------
# parse()
# ---------------------------------------------------------------------------

class TestParse:
    def test_parses_task_count(self, tmp_path):
        p = write_tasks(tmp_path, MINIMAL)
        tasks = parse(p)
        assert len(tasks) == 2

    def test_parses_title(self, tmp_path):
        p = write_tasks(tmp_path, MINIMAL)
        tasks = parse(p)
        assert tasks[0].title == "Task One"

    def test_parses_active_phase(self, tmp_path):
        p = write_tasks(tmp_path, MINIMAL)
        tasks = parse(p)
        assert tasks[1].phase == "active"
        assert tasks[1].title == "Task Two"

    def test_no_marker_gives_none_phase(self, tmp_path):
        p = write_tasks(tmp_path, MINIMAL)
        tasks = parse(p)
        assert tasks[0].phase is None

    def test_gt_marker_phase(self, tmp_path):
        p = write_tasks(tmp_path, WITH_GT_MARKER)
        tasks = parse(p)
        assert tasks[0].phase == ">"
        assert tasks[0].title == "Ready Task"

    def test_done_marker_phase(self, tmp_path):
        p = write_tasks(tmp_path, WITH_GT_MARKER)
        tasks = parse(p)
        assert tasks[1].phase == "done"

    def test_prose_body_verbatim(self, tmp_path):
        p = write_tasks(tmp_path, PROSE_BODY)
        tasks = parse(p)
        assert len(tasks) == 1
        assert "first paragraph" in tasks[0].body
        assert "second paragraph" in tasks[0].body
        assert "third" in tasks[0].body

    def test_line_number_set(self, tmp_path):
        p = write_tasks(tmp_path, MINIMAL)
        tasks = parse(p)
        # Task One starts at ## heading; line numbers are 1-based
        assert tasks[0].line_number >= 1

    def test_bullet_body(self, tmp_path):
        p = write_tasks(tmp_path, MINIMAL)
        tasks = parse(p)
        assert "Bullet one" in tasks[1].body
        assert "Bullet two" in tasks[1].body

    def test_tasks_md_smoke(self):
        """Smoke: parse the repo's own tasks.md without crashing."""
        repo_tasks = Path(__file__).parents[5] / "tasks.md"
        if repo_tasks.exists():
            tasks = parse(repo_tasks)
            assert len(tasks) >= 1


# ---------------------------------------------------------------------------
# find()
# ---------------------------------------------------------------------------

class TestFind:
    def test_find_existing(self, tmp_path):
        p = write_tasks(tmp_path, MINIMAL)
        tasks = parse(p)
        t = find(tasks, "Task One")
        assert t is not None
        assert t.title == "Task One"

    def test_find_missing_returns_none(self, tmp_path):
        p = write_tasks(tmp_path, MINIMAL)
        tasks = parse(p)
        assert find(tasks, "Nonexistent") is None


# ---------------------------------------------------------------------------
# render()
# ---------------------------------------------------------------------------

class TestRender:
    def test_round_trip_basic(self, tmp_path):
        p = write_tasks(tmp_path, MINIMAL)
        tasks = parse(p)
        rendered = render(tasks)
        # Parse the rendered output and compare titles
        p2 = tmp_path / "rt.md"
        p2.write_text(rendered, encoding="utf-8")
        tasks2 = parse(p2)
        assert [t.title for t in tasks2] == [t.title for t in tasks]
        assert [t.phase for t in tasks2] == [t.phase for t in tasks]

    def test_gt_marker_preserved(self, tmp_path):
        p = write_tasks(tmp_path, WITH_GT_MARKER)
        tasks = parse(p)
        rendered = render(tasks)
        assert "## [>] Ready Task" in rendered


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------

class TestValidate:
    def test_valid_file_no_errors(self, tmp_path):
        p = write_tasks(tmp_path, MINIMAL)
        errors = validate(p)
        assert errors == []

    def test_two_h1_headings_error(self, tmp_path):
        p = write_tasks(tmp_path, TWO_H1)
        errors = validate(p)
        assert len(errors) > 0

    def test_invalid_phase_marker_error(self, tmp_path):
        text = "# Tasks\n\n## [invalid] Task\n"
        p = tmp_path / "tasks.md"
        p.write_text(text, encoding="utf-8")
        errors = validate(p)
        assert len(errors) > 0

    def test_gt_marker_is_valid(self, tmp_path):
        p = write_tasks(tmp_path, WITH_GT_MARKER)
        errors = validate(p)
        assert errors == []
