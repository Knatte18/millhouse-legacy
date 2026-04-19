"""Tests for millpy.entrypoints.status_verify.

Card 11: mill-status-verify verifies status.md phase against directory state.
"""
from __future__ import annotations

from pathlib import Path



def _make_status_md(path: Path, phase: str) -> None:
    """Write a minimal status.md with the given phase."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "# Status\n"
        "\n"
        "```yaml\n"
        f"task: Test Task\n"
        f"phase: {phase}\n"
        "parent: main\n"
        "```\n"
        "\n"
        "## Timeline\n"
        "\n"
        "```text\n"
        f"{phase}              2026-04-18T00:00:00Z\n"
        "```\n"
    )
    path.write_text(content, encoding="utf-8")


def _make_active_dir(mill_dir: Path, slug: str) -> Path:
    """Create .millhouse/wiki/active/<slug>/ directory structure."""
    active = mill_dir / "active" / slug
    active.mkdir(parents=True, exist_ok=True)
    return active


class TestStatusVerifyConsistent:
    def test_phase_planned_with_discussion_and_plan_exits_0(
        self, tmp_path, monkeypatch, capsys
    ):
        """phase=planned, discussion.md + plan/ present → consistent, exit 0."""
        from millpy.entrypoints import status_verify

        mill = tmp_path / ".millhouse/wiki"
        slug = "my-task"
        active = _make_active_dir(mill, slug)
        _make_status_md(active / "status.md", "planned")
        (active / "discussion.md").write_text("# Discussion\n", encoding="utf-8")
        (active / "plan").mkdir()

        monkeypatch.chdir(tmp_path)
        # Fake slug_from_branch to return our slug
        monkeypatch.setattr(
            "millpy.core.paths.subprocess_util.run",
            lambda argv, **kw: _fake_git_branch(argv, slug),
        )

        exit_code = status_verify.main([])
        assert exit_code == 0

    def test_no_active_dir_prints_no_active_task(
        self, tmp_path, monkeypatch, capsys
    ):
        """No active dir → 'no active task', exit 0."""
        from millpy.entrypoints import status_verify

        mill = tmp_path / ".millhouse/wiki"
        mill.mkdir(parents=True)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "millpy.core.paths.subprocess_util.run",
            lambda argv, **kw: _fake_git_branch(argv, "my-task"),
        )

        exit_code = status_verify.main([])
        out = capsys.readouterr().out
        assert exit_code == 0
        assert "no active task" in out


class TestStatusVerifyMismatch:
    def test_phase_discussing_with_plan_dir_exits_1(
        self, tmp_path, monkeypatch, capsys
    ):
        """phase=discussing but plan/ exists → exit 1, report mismatch."""
        from millpy.entrypoints import status_verify

        mill = tmp_path / ".millhouse/wiki"
        slug = "my-task"
        active = _make_active_dir(mill, slug)
        _make_status_md(active / "status.md", "discussing")
        # plan/ present but status says discussing → mismatch
        (active / "plan").mkdir()

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "millpy.core.paths.subprocess_util.run",
            lambda argv, **kw: _fake_git_branch(argv, slug),
        )

        exit_code = status_verify.main([])
        out = capsys.readouterr().out
        assert exit_code == 1
        assert "plan/" in out

    def test_phase_complete_missing_plan_exits_1(
        self, tmp_path, monkeypatch, capsys
    ):
        """phase=complete but plan/ missing → exit 1."""
        from millpy.entrypoints import status_verify

        mill = tmp_path / ".millhouse/wiki"
        slug = "my-task"
        active = _make_active_dir(mill, slug)
        _make_status_md(active / "status.md", "complete")
        # No plan/, no discussion.md — should flag mismatch
        (active / "discussion.md").write_text("# Discussion\n", encoding="utf-8")
        # plan/ intentionally absent

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "millpy.core.paths.subprocess_util.run",
            lambda argv, **kw: _fake_git_branch(argv, slug),
        )

        exit_code = status_verify.main([])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

import subprocess


def _fake_git_branch(argv: list[str], slug: str) -> subprocess.CompletedProcess:
    """Fake subprocess_util.run for git branch --show-current."""
    if argv[:3] == ["git", "branch", "--show-current"]:
        return subprocess.CompletedProcess(argv, 0, stdout=slug, stderr="")
    # For any other command, run real subprocess
    import subprocess as _sp
    return _sp.run(argv, capture_output=True, text=True)
