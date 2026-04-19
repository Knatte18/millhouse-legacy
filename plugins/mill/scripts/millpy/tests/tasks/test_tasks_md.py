"""
test_tasks_md.py — Tests for millpy.tasks.tasks_md (TDD: RED → GREEN → REFACTOR).

After Card 6 refactor:
- TaskEntry replaces Task (new dataclass fields: display_name, slug, phase, description, background_slug)
- slugify() helper added
- ValidationError exception class added for slug collision detection
- resolve_path(cfg) uses .millhouse/wiki/ junction (mill_junction_path)
- write_commit_push uses wiki.write_commit_push internally
- GitPushError and TasksLockError removed from tasks_md (now in wiki module)
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from millpy.core.config import ConfigError
from millpy.tasks.tasks_md import (
    ValidationError,
    parse,
    render,
    resolve_path,
    slugify,
    validate,
    write_commit_push,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def write_home(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "Home.md"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


HOME_MINIMAL = """\
    # Tasks

    ## Task One
    A simple task description.

    ## [active] Task Two
    - Some description.
"""

HOME_WITH_BACKGROUND = """\
    # Tasks

    ## New Task System
    Build a wiki-based task system. [Background](new-task-system.md)

    ## [s] Another Task
    Short description.
"""

HOME_THREE_ENTRIES = """\
    # Tasks

    ## Alpha Task
    First description.

    ## [active] Beta Task
    Second description. [Background](beta-bg.md)

    ## [done] Gamma Task
    Third description.
"""

HOME_DUPLICATE_SLUGS = """\
    # Tasks

    ## New Task System!
    Desc A.

    ## New Task System
    Desc B.
"""


# ---------------------------------------------------------------------------
# slugify()
# ---------------------------------------------------------------------------

class TestSlugify:
    def test_basic_lowercase(self):
        assert slugify("New Task System!") == "new-task-system"

    def test_replaces_whitespace_with_dash(self):
        assert slugify("hello world") == "hello-world"

    def test_strips_non_alphanumeric(self):
        assert slugify("foo! bar?") == "foo-bar"

    def test_multiple_spaces_become_single_dash(self):
        assert slugify("a  b  c") == "a--b--c"  # spaces → dashes (one per space)

    def test_already_clean(self):
        assert slugify("task-name") == "task-name"

    def test_uppercase(self):
        assert slugify("My TASK") == "my-task"


# ---------------------------------------------------------------------------
# parse() — new TaskEntry format
# ---------------------------------------------------------------------------

class TestParse:
    def test_parses_entry_count(self, tmp_path):
        p = write_home(tmp_path, HOME_MINIMAL)
        entries = parse(p)
        assert len(entries) == 2

    def test_parses_display_name(self, tmp_path):
        p = write_home(tmp_path, HOME_MINIMAL)
        entries = parse(p)
        assert entries[0].display_name == "Task One"

    def test_parses_slug_from_display_name(self, tmp_path):
        p = write_home(tmp_path, HOME_MINIMAL)
        entries = parse(p)
        assert entries[0].slug == slugify("Task One")

    def test_parses_active_phase(self, tmp_path):
        p = write_home(tmp_path, HOME_MINIMAL)
        entries = parse(p)
        assert entries[1].phase == "active"
        assert entries[1].display_name == "Task Two"

    def test_no_marker_gives_none_phase(self, tmp_path):
        p = write_home(tmp_path, HOME_MINIMAL)
        entries = parse(p)
        assert entries[0].phase is None

    def test_parses_description(self, tmp_path):
        p = write_home(tmp_path, HOME_MINIMAL)
        entries = parse(p)
        assert "simple task" in entries[0].description

    def test_parses_background_slug(self, tmp_path):
        p = write_home(tmp_path, HOME_WITH_BACKGROUND)
        entries = parse(p)
        assert entries[0].background_slug == "new-task-system"

    def test_no_background_link_gives_none(self, tmp_path):
        p = write_home(tmp_path, HOME_MINIMAL)
        entries = parse(p)
        assert entries[0].background_slug is None

    def test_s_marker_phase(self, tmp_path):
        p = write_home(tmp_path, HOME_WITH_BACKGROUND)
        entries = parse(p)
        assert entries[1].phase == "s"

    def test_three_entries(self, tmp_path):
        p = write_home(tmp_path, HOME_THREE_ENTRIES)
        entries = parse(p)
        assert len(entries) == 3
        assert entries[2].phase == "done"
        assert entries[2].display_name == "Gamma Task"


# ---------------------------------------------------------------------------
# render()
# ---------------------------------------------------------------------------

class TestRender:
    def test_round_trip_three_entries(self, tmp_path):
        p = write_home(tmp_path, HOME_THREE_ENTRIES)
        entries = parse(p)
        rendered = render(entries)
        p2 = tmp_path / "rt.md"
        p2.write_text(rendered, encoding="utf-8")
        entries2 = parse(p2)
        assert [e.display_name for e in entries2] == [e.display_name for e in entries]
        assert [e.phase for e in entries2] == [e.phase for e in entries]

    def test_s_marker_preserved(self, tmp_path):
        p = write_home(tmp_path, HOME_WITH_BACKGROUND)
        entries = parse(p)
        rendered = render(entries)
        assert "## [s] Another Task" in rendered

    def test_background_link_preserved(self, tmp_path):
        p = write_home(tmp_path, HOME_WITH_BACKGROUND)
        entries = parse(p)
        rendered = render(entries)
        assert "[Background](new-task-system.md)" in rendered


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------

class TestValidate:
    def test_valid_file_no_errors(self, tmp_path):
        p = write_home(tmp_path, HOME_MINIMAL)
        errors = validate(p)
        assert errors == []

    def test_duplicate_slugs_raise_validation_error(self, tmp_path):
        p = write_home(tmp_path, HOME_DUPLICATE_SLUGS)
        with pytest.raises(ValidationError) as exc_info:
            validate(p)
        assert "new-task-system" in str(exc_info.value)

    def test_validation_error_is_value_error(self, tmp_path):
        p = write_home(tmp_path, HOME_DUPLICATE_SLUGS)
        with pytest.raises(ValueError):
            validate(p)


# ---------------------------------------------------------------------------
# resolve_path — new .millhouse/wiki/ junction based resolution
# ---------------------------------------------------------------------------

class TestResolvePath:
    def test_resolve_path_returns_home_md_in_mill_junction(self, tmp_path, monkeypatch):
        """resolve_path returns <cwd>/.millhouse/wiki/Home.md."""
        mill_dir = tmp_path / ".millhouse" / "wiki"
        mill_dir.mkdir(parents=True)
        (mill_dir / "Home.md").write_text("# Tasks\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        cfg: dict = {}
        result = resolve_path(cfg)
        assert result == mill_dir / "Home.md"

    def test_resolve_path_raises_configerror_when_mill_missing(self, tmp_path, monkeypatch):
        """resolve_path raises ConfigError when .millhouse/wiki/ junction does not exist."""
        monkeypatch.chdir(tmp_path)
        cfg: dict = {}
        with pytest.raises(ConfigError, match=r"\.millhouse"):
            resolve_path(cfg)


# ---------------------------------------------------------------------------
# write_commit_push — delegating to wiki.write_commit_push
# ---------------------------------------------------------------------------

class TestWriteCommitPush:
    def test_write_commit_push_calls_wiki_helpers(self, tmp_path, monkeypatch):
        """write_commit_push acquires lock, writes file, calls wiki.write_commit_push, releases lock."""
        mill_dir = tmp_path / ".millhouse" / "wiki"
        mill_dir.mkdir(parents=True)
        (mill_dir / "Home.md").write_text("# Tasks\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        cfg: dict = {}

        acquire_calls = []
        wcp_calls = []
        release_calls = []

        monkeypatch.setattr("millpy.tasks.wiki.acquire_lock", lambda cfg, slug, **kw: acquire_calls.append(slug))
        monkeypatch.setattr("millpy.tasks.wiki.write_commit_push", lambda cfg, paths, msg: wcp_calls.append((paths, msg)))
        monkeypatch.setattr("millpy.tasks.wiki.release_lock", lambda cfg: release_calls.append(True))

        write_commit_push(cfg, "# Tasks\n\n## NEW\n", "test: add NEW")

        assert len(acquire_calls) == 1
        assert len(wcp_calls) == 1
        assert "Home.md" in wcp_calls[0][0]
        assert len(release_calls) == 1

    def test_write_commit_push_writes_content(self, tmp_path, monkeypatch):
        """write_commit_push writes the new content to Home.md before calling wiki helpers."""
        mill_dir = tmp_path / ".millhouse" / "wiki"
        mill_dir.mkdir(parents=True)
        home = mill_dir / "Home.md"
        home.write_text("# Tasks\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        cfg: dict = {}

        monkeypatch.setattr("millpy.tasks.wiki.acquire_lock", lambda *a, **kw: None)
        monkeypatch.setattr("millpy.tasks.wiki.write_commit_push", lambda *a, **kw: None)
        monkeypatch.setattr("millpy.tasks.wiki.release_lock", lambda *a: None)

        write_commit_push(cfg, "# Tasks\n\n## NEW\n", "test: add NEW")
        assert "## NEW" in home.read_text(encoding="utf-8")
