"""
test_tasks_md.py — Tests for millpy.tasks.tasks_md (TDD: RED → GREEN → REFACTOR).
"""
from __future__ import annotations

import os
import subprocess
import textwrap
import types
from pathlib import Path

import pytest

from millpy.core.config import ConfigError
from millpy.tasks.tasks_md import (
    GitPushError,
    Task,
    TasksLockError,
    find,
    parse,
    render,
    resolve_path,
    validate,
    write_commit_push,
)


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

WITH_S_MARKER = """\
    # Tasks

    ## [s] Ready Task
    Description here.

    ## [done] Done Task
"""

WITH_LEGACY_GT_MARKER = """\
    # Tasks

    ## [>] Legacy Ready Task
    Description here.
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

    def test_s_marker_phase(self, tmp_path):
        p = write_tasks(tmp_path, WITH_S_MARKER)
        tasks = parse(p)
        assert tasks[0].phase == "s"
        assert tasks[0].title == "Ready Task"

    def test_done_marker_phase(self, tmp_path):
        p = write_tasks(tmp_path, WITH_S_MARKER)
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

    def test_s_marker_preserved(self, tmp_path):
        p = write_tasks(tmp_path, WITH_S_MARKER)
        tasks = parse(p)
        rendered = render(tasks)
        assert "## [s] Ready Task" in rendered


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

    def test_s_marker_is_valid(self, tmp_path):
        p = write_tasks(tmp_path, WITH_S_MARKER)
        errors = validate(p)
        assert errors == []

    def test_legacy_gt_marker_rejected(self, tmp_path):
        """The `[>]` marker is no longer a valid phase — `validate()` must flag it."""
        p = write_tasks(tmp_path, WITH_LEGACY_GT_MARKER)
        errors = validate(p)
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# parse() body normalization (trailing whitespace)
# ---------------------------------------------------------------------------

class TestParseBodyNormalization:
    def test_parse_normalizes_trailing_blank_lines_to_single_newline(self, tmp_path):
        """Two blank lines before next heading collapse to exactly one \\n terminator."""
        content = "# Tasks\n\n## A\n\nbody A\n\n\n## B\n"
        p = tmp_path / "tasks.md"
        p.write_text(content, encoding="utf-8")
        tasks = parse(p)
        assert tasks[0].body.endswith("\n")
        assert not tasks[0].body.endswith("\n\n")
        assert not tasks[0].body.endswith("\n\n\n")

    def test_parse_collapses_whitespace_only_body_to_empty(self, tmp_path):
        """Heading immediately followed by a blank line and the next heading → body == ''."""
        content = "# Tasks\n\n## A\n\n## B\n"
        p = tmp_path / "tasks.md"
        p.write_text(content, encoding="utf-8")
        tasks = parse(p)
        assert tasks[0].body == ""

    def test_render_parse_render_is_idempotent(self, tmp_path):
        """parse → render → write → parse → render produces byte-exact output."""
        content = (
            "# Tasks\n\n"
            "## One\nprose body one.\n\n"
            "## [active] Two\n- bullet a\n- bullet b\n\n"
            "## [done] Three\nprose body three.\n"
        )
        p = tmp_path / "tasks.md"
        p.write_text(content, encoding="utf-8")
        parsed1 = parse(p)
        rendered1 = render(parsed1)
        p2 = tmp_path / "tasks2.md"
        p2.write_text(rendered1, encoding="utf-8")
        parsed2 = parse(p2)
        rendered2 = render(parsed2)
        assert rendered1 == rendered2

    def test_blank_lines_between_tasks_do_not_accumulate_on_roundtrip(self, tmp_path):
        """Triple parse→render→write round-trip preserves byte count after the first."""
        content = (
            "# Tasks\n\n"
            "## One\nbody one.\n\n"
            "## Two\nbody two.\n"
        )
        p = tmp_path / "tasks.md"
        p.write_text(content, encoding="utf-8")

        def _round_trip(path: Path) -> Path:
            tasks_ = parse(path)
            rendered = render(tasks_)
            out = tmp_path / f"rt-{path.name}"
            out.write_text(rendered, encoding="utf-8")
            return out

        p1 = _round_trip(p)
        size1 = p1.stat().st_size
        p2 = _round_trip(p1)
        p3 = _round_trip(p2)
        assert p3.stat().st_size == size1

    def test_leading_blank_in_body_preserved(self, tmp_path):
        """Leading blank line in body (between heading and content) is preserved."""
        content = "# Tasks\n\n## A\n\nbody\n\n## B\n"
        p = tmp_path / "tasks.md"
        p.write_text(content, encoding="utf-8")
        tasks = parse(p)
        assert tasks[0].body.startswith("\n")

    def test_interior_blank_lines_preserved(self, tmp_path):
        """Interior blank lines (paragraph breaks inside a body) are preserved."""
        content = "# Tasks\n\n## A\n\npara one.\n\npara two.\n"
        p = tmp_path / "tasks.md"
        p.write_text(content, encoding="utf-8")
        tasks = parse(p)
        assert "para one.\n\npara two.\n" in tasks[0].body


# ---------------------------------------------------------------------------
# [completed] phase marker
# ---------------------------------------------------------------------------

WITH_COMPLETED_MARKER = """\
    # Tasks

    ## [completed] Completed Task
    Task work done, not yet merged.
"""


class TestCompletedMarker:
    def test_completed_marker_is_valid(self, tmp_path):
        p = write_tasks(tmp_path, WITH_COMPLETED_MARKER)
        errors = validate(p)
        assert errors == []

    def test_completed_marker_parse_render_roundtrip(self, tmp_path):
        p = write_tasks(tmp_path, WITH_COMPLETED_MARKER)
        tasks = parse(p)
        rendered = render(tasks)
        p2 = tmp_path / "rt.md"
        p2.write_text(rendered, encoding="utf-8")
        tasks2 = parse(p2)
        assert tasks2[0].phase == "completed"
        assert "## [completed] Completed Task" in rendered


# ---------------------------------------------------------------------------
# resolve_path
# ---------------------------------------------------------------------------

class TestResolvePath:
    def test_resolve_path_returns_absolute_tasks_md_path(self, tmp_path):
        fake_wt = tmp_path / "fake-tasks-wt"
        fake_wt.mkdir()
        cfg = {"tasks": {"worktree-path": str(fake_wt)}}
        assert resolve_path(cfg) == fake_wt / "tasks.md"

    def test_resolve_path_raises_configerror_when_key_missing(self):
        for cfg in [{}, {"tasks": {}}, {"tasks": {"worktree-path": None}}]:
            with pytest.raises(ConfigError, match="Missing tasks.worktree-path"):
                resolve_path(cfg)

    def test_resolve_path_raises_filenotfound_when_worktree_missing(self, tmp_path):
        cfg = {"tasks": {"worktree-path": str(tmp_path / "does-not-exist")}}
        with pytest.raises(FileNotFoundError, match="Tasks worktree not found"):
            resolve_path(cfg)

    def test_resolve_path_raises_configerror_for_relative_path(self):
        cfg = {"tasks": {"worktree-path": "relative/path"}}
        with pytest.raises(ConfigError, match="must be absolute"):
            resolve_path(cfg)


# ---------------------------------------------------------------------------
# write_commit_push
# ---------------------------------------------------------------------------

def _make_git_wt(tmp_path: Path) -> tuple[Path, dict]:
    """Create a real git worktree with a bare remote and an initial tasks.md commit."""
    wt = tmp_path / "tasks-wt"
    wt.mkdir()
    bare = tmp_path / "tasks-wt-remote.git"
    subprocess.run(["git", "init", str(wt)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(wt), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(wt), "config", "user.name", "Test"], check=True, capture_output=True)
    (wt / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(wt), "add", "tasks.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(wt), "commit", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(wt), "remote", "add", "origin", str(bare)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", "HEAD"], check=True, capture_output=True)
    cfg = {"tasks": {"worktree-path": str(wt)}}
    return wt, cfg


class TestWriteCommitPush:
    def test_write_commit_push_writes_and_commits(self, tmp_path):
        wt, cfg = _make_git_wt(tmp_path)
        write_commit_push(cfg, "# Tasks\n\n## NEW\n", "test: add NEW")
        assert "## NEW" in (wt / "tasks.md").read_text(encoding="utf-8")
        result = subprocess.run(
            ["git", "-C", str(wt), "log", "--oneline", "-1"],
            capture_output=True, text=True, check=True,
        )
        assert "test: add NEW" in result.stdout

    def test_write_commit_push_releases_lock_on_success(self, tmp_path):
        wt, cfg = _make_git_wt(tmp_path)
        write_commit_push(cfg, "# Tasks\n\n## X\n", "test: X")
        assert not (wt / ".mill-tasks.lock").exists()

    def test_write_commit_push_releases_lock_on_failure(self, tmp_path, monkeypatch):
        wt, cfg = _make_git_wt(tmp_path)
        fail = types.SimpleNamespace(returncode=1, stdout="", stderr="git add error")
        monkeypatch.setattr("millpy.core.subprocess_util.run", lambda *a, **kw: fail)
        with pytest.raises(GitPushError):
            write_commit_push(cfg, "# Tasks\n", "test")
        assert not (wt / ".mill-tasks.lock").exists()

    def test_write_commit_push_raises_when_lock_held_by_live_pid(self, tmp_path):
        wt, cfg = _make_git_wt(tmp_path)
        lock = wt / ".mill-tasks.lock"
        lock.write_text(f"pid: {os.getpid()}\ntimestamp: 2026-01-01T00:00:00Z\n", encoding="utf-8")
        with pytest.raises(TasksLockError, match="Could not acquire"):
            write_commit_push(cfg, "# Tasks\n", "test", _acquire_timeout=1.0)

    def test_write_commit_push_clears_stale_lock(self, tmp_path, monkeypatch):
        wt, cfg = _make_git_wt(tmp_path)
        lock = wt / ".mill-tasks.lock"
        lock.write_text("pid: 999999\ntimestamp: 2026-01-01T00:00:00Z\n", encoding="utf-8")
        monkeypatch.setattr("millpy.tasks.tasks_md._pid_is_alive", lambda pid: False)
        write_commit_push(cfg, "# Tasks\n\n## STALE\n", "test: stale")
        assert "## STALE" in (wt / "tasks.md").read_text(encoding="utf-8")

    def test_write_commit_push_retries_on_non_ff(self, tmp_path, monkeypatch):
        wt, cfg = _make_git_wt(tmp_path)
        calls = []
        push_count = [0]
        def fake_run(argv, **kw):
            calls.append(list(argv))
            cmd = argv[3] if len(argv) > 3 else ""
            if cmd == "push":
                push_count[0] += 1
                if push_count[0] == 1:
                    return types.SimpleNamespace(returncode=1, stdout="", stderr="rejected non-fast-forward")
                return types.SimpleNamespace(returncode=0, stdout="", stderr="")
            if cmd == "pull":
                return types.SimpleNamespace(returncode=0, stdout="", stderr="")
            return types.SimpleNamespace(returncode=0, stdout="1 file changed", stderr="")
        monkeypatch.setattr("millpy.core.subprocess_util.run", fake_run)
        write_commit_push(cfg, "# Tasks\n", "test")
        assert push_count[0] >= 2

    def test_write_commit_push_aborts_on_rebase_conflict(self, tmp_path, monkeypatch):
        wt, cfg = _make_git_wt(tmp_path)
        calls = []
        def fake_run(argv, **kw):
            calls.append(list(argv))
            cmd = argv[3] if len(argv) > 3 else ""
            if cmd == "add":
                return types.SimpleNamespace(returncode=0, stdout="", stderr="")
            if cmd == "commit":
                return types.SimpleNamespace(returncode=0, stdout="1 file changed", stderr="")
            if cmd == "push":
                return types.SimpleNamespace(returncode=1, stdout="", stderr="rejected non-fast-forward")
            if cmd == "pull":
                return types.SimpleNamespace(returncode=1, stdout="", stderr="CONFLICT (content)")
            if cmd == "rebase":
                return types.SimpleNamespace(returncode=0, stdout="", stderr="")
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        monkeypatch.setattr("millpy.core.subprocess_util.run", fake_run)
        with pytest.raises(GitPushError, match="Rebase conflict"):
            write_commit_push(cfg, "# Tasks\n", "test")
        assert any(c[3:5] == ["rebase", "--abort"] for c in calls if len(c) >= 5)
