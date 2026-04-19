"""
test_subfolder_support.py — Integration: millhouse works when the project lives
in a subfolder of a git repo.

Regression guard: any helper that accidentally uses ``git rev-parse --show-toplevel``
instead of ``Path.cwd()`` would land ``.millhouse/wiki/`` and ``.millhouse/`` at the git
toplevel instead of the subfolder, causing the assertions below to fail.

Layout under test
-----------------
::

    tmp_path/
        outer.git/         ← bare repo
        outer/             ← working clone (git toplevel)
            sub/
                project/   ← actual millhouse project cwd
                    .millhouse/
                    .millhouse/wiki/ → tmp_path/outer.wiki/
        outer.wiki.git/    ← bare wiki repo
        outer.wiki/        ← wiki clone

Steps:

1. ``monkeypatch.chdir`` to ``outer/sub/project/``.
2. Simulate mill-setup: create ``.millhouse/`` at cwd; create ``.millhouse/wiki/`` junction pointing
   at the wiki clone.
3. Assert ``.millhouse/`` and ``.millhouse/wiki/`` are at the subfolder, NOT at ``outer/``.
4. Assert ``paths.project_dir()`` returns the subfolder path.
5. Assert ``paths.mill_junction_path()`` points inside the subfolder.
6. Write ``active/<slug>/status.md`` via ``append_phase`` (with cfg); assert the file
   exists inside the wiki clone and a new commit appears in the wiki's git log.
"""
from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

from millpy.core import junction
from millpy.core.paths import mill_junction_path, project_dir
from millpy.tasks.status_md import append_phase, load


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@test.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@test.invalid",
}


def _git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command, capturing output."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_GIT_ENV,
        check=check,
    )


def _make_repo_with_clone(bare_path: Path, clone_path: Path) -> None:
    """Create a bare repo + working clone with an initial commit.

    Strategy:
    1. Init the bare repo.
    2. Init a non-bare working clone pointing at the bare repo.
    3. Make an initial commit and push, setting up the tracking branch.
    Sets ``push.default = current`` so future bare ``git push`` calls work
    without needing explicit refspecs.
    """
    # Step 1: init bare repo
    bare_path.parent.mkdir(parents=True, exist_ok=True)
    _git("init", "--bare", "-q", str(bare_path))

    # Step 2: init working clone pointing at the bare repo as origin
    clone_path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", str(clone_path))
    _git("config", "user.email", "test@test.invalid", cwd=clone_path)
    _git("config", "user.name", "Test", cwd=clone_path)
    # Set push.default=current so plain `git push` pushes the current branch
    # to same-named remote branch, without requiring a pre-configured upstream.
    _git("config", "push.default", "current", cwd=clone_path)
    _git("remote", "add", "origin", str(bare_path), cwd=clone_path)

    # Step 3: create initial commit and push
    _git("commit", "--allow-empty", "-q", "-m", "init", cwd=clone_path)
    _git("push", "-q", "origin", "HEAD", cwd=clone_path)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def subfolder_layout(tmp_path):
    """Set up the full bare+clone+wiki layout described in the module docstring."""
    # --- Main repo ---
    bare_repo = tmp_path / "outer.git"
    working_clone = tmp_path / "outer"
    _make_repo_with_clone(bare_repo, working_clone)

    # The actual project directory lives at a subfolder inside the working clone.
    project = working_clone / "sub" / "project"
    project.mkdir(parents=True)

    # --- Wiki repo ---
    bare_wiki = tmp_path / "outer.wiki.git"
    wiki_clone = tmp_path / "outer.wiki"
    _make_repo_with_clone(bare_wiki, wiki_clone)

    return {
        "bare_repo": bare_repo,
        "working_clone": working_clone,
        "project": project,
        "bare_wiki": bare_wiki,
        "wiki_clone": wiki_clone,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSubfolderPathResolution:
    """Path helpers must resolve to cwd (subfolder), not git toplevel."""

    def test_project_dir_returns_cwd_subfolder(self, subfolder_layout, monkeypatch):
        """project_dir() returns the subfolder, not the git toplevel."""
        project = subfolder_layout["project"]
        monkeypatch.chdir(project)

        result = project_dir()
        assert result.resolve() == project.resolve()
        assert result.resolve() != subfolder_layout["working_clone"].resolve()

    def test_mill_junction_path_is_inside_subfolder(self, subfolder_layout, monkeypatch):
        """mill_junction_path() returns <subfolder>/.millhouse/wiki, not <git-root>/.millhouse/wiki."""
        project = subfolder_layout["project"]
        monkeypatch.chdir(project)

        mill = mill_junction_path()
        assert mill.resolve() == (project / ".millhouse" / "wiki").resolve()
        assert mill.resolve() != (subfolder_layout["working_clone"] / ".millhouse" / "wiki").resolve()

    def test_millhouse_dir_is_inside_subfolder(self, subfolder_layout, monkeypatch):
        """.millhouse/ created at cwd must be inside the subfolder."""
        project = subfolder_layout["project"]
        millhouse = project / ".millhouse"
        millhouse.mkdir()
        monkeypatch.chdir(project)

        # Verify the directory exists at the subfolder, not at git root
        assert millhouse.exists()
        assert not (subfolder_layout["working_clone"] / ".millhouse").exists()


@pytest.mark.integration
class TestSubfolderJunctionSetup:
    """mill-setup simulation: .millhouse/wiki junction lands at the subfolder, not git root."""

    def test_mill_junction_created_at_subfolder(self, subfolder_layout, monkeypatch):
        """.millhouse/wiki junction is created at <subfolder>/.millhouse/wiki, not <git-root>/.millhouse/wiki."""
        project = subfolder_layout["project"]
        wiki_clone = subfolder_layout["wiki_clone"]
        monkeypatch.chdir(project)

        mill_link = project / ".millhouse" / "wiki"
        junction.create(wiki_clone, mill_link)

        # Junction exists at the subfolder
        assert mill_link.exists()

        # Junction does NOT exist at git root
        git_root_mill = subfolder_layout["working_clone"] / ".millhouse" / "wiki"
        assert not git_root_mill.exists()

    def test_mill_junction_points_at_wiki_clone(self, subfolder_layout, monkeypatch):
        """The .millhouse/wiki junction resolves inside the wiki clone."""
        project = subfolder_layout["project"]
        wiki_clone = subfolder_layout["wiki_clone"]
        monkeypatch.chdir(project)

        mill_link = project / ".millhouse" / "wiki"
        junction.create(wiki_clone, mill_link)

        # A file created inside wiki_clone is visible through the junction
        (wiki_clone / "probe.txt").write_text("hello", encoding="utf-8")
        assert (mill_link / "probe.txt").read_text(encoding="utf-8") == "hello"


@pytest.mark.integration
class TestSubfolderAppendPhase:
    """append_phase writes status.md into the wiki clone and commits."""

    def _make_status_content(self) -> str:
        return textwrap.dedent("""\
            # Status

            ```yaml
            task: Subfolder Test Task
            phase: discussing
            parent: main
            discussion: .millhouse/task/discussion.md
            plan: .millhouse/task/plan.md
            task_description: |
              Test task for subfolder support
            ```

            ## Timeline

            ```text
            discussing              2026-04-18T10:00:00Z
            ```
            """)

    def test_append_phase_updates_status_in_wiki(self, subfolder_layout, monkeypatch):
        """append_phase with cfg writes status.md into the wiki and commits."""
        project = subfolder_layout["project"]
        wiki_clone = subfolder_layout["wiki_clone"]
        subfolder_layout["bare_wiki"]
        monkeypatch.chdir(project)

        # Simulate mill-setup: create .millhouse/wiki junction
        mill_link = project / ".millhouse" / "wiki"
        junction.create(wiki_clone, mill_link)

        # Create the active/<slug>/ directory in the wiki clone
        slug = "subfolder-test"
        active_dir = wiki_clone / "active" / slug
        active_dir.mkdir(parents=True)

        # Write initial status.md into the wiki clone (via junction)
        status_path = active_dir / "status.md"
        status_path.write_text(self._make_status_content(), encoding="utf-8")

        # Stage and commit the initial file in the wiki clone
        _git("add", "active/", cwd=wiki_clone)
        _git("commit", "-m", "task: init subfolder-test", cwd=wiki_clone)

        # Build cfg pointing at the wiki clone
        cfg = {"wiki": {"clone-path": str(wiki_clone)}}

        # Call append_phase with cfg — should update YAML + timeline + commit
        status_via_junction = mill_link / "active" / slug / "status.md"
        append_phase(status_via_junction, "discussed", cfg=cfg)

        # Assert YAML phase was updated
        data = load(status_via_junction)
        assert data["phase"] == "discussed"

        # Assert timeline entry was appended
        text = status_via_junction.read_text(encoding="utf-8")
        assert "discussed" in text

        # Assert a commit was created in the wiki clone
        log_result = _git("log", "--oneline", "-5", cwd=wiki_clone)
        assert "task: phase discussed" in log_result.stdout

    def test_no_cfg_skips_wiki_commit(self, subfolder_layout, monkeypatch):
        """append_phase without cfg updates the file but does NOT commit to wiki."""
        project = subfolder_layout["project"]
        wiki_clone = subfolder_layout["wiki_clone"]
        monkeypatch.chdir(project)

        # Create .millhouse/wiki junction
        mill_link = project / ".millhouse" / "wiki"
        junction.create(wiki_clone, mill_link)

        slug = "no-cfg-test"
        active_dir = wiki_clone / "active" / slug
        active_dir.mkdir(parents=True)
        status_path = active_dir / "status.md"
        status_path.write_text(self._make_status_content(), encoding="utf-8")

        # Commit initial file
        _git("add", "active/", cwd=wiki_clone)
        _git("commit", "-m", "task: init no-cfg-test", cwd=wiki_clone)

        # Get the commit count before
        before = _git("rev-list", "--count", "HEAD", cwd=wiki_clone)
        count_before = int(before.stdout.strip())

        # append_phase with no cfg — should NOT create a new commit
        status_via_junction = mill_link / "active" / slug / "status.md"
        append_phase(status_via_junction, "discussed")

        after = _git("rev-list", "--count", "HEAD", cwd=wiki_clone)
        count_after = int(after.stdout.strip())
        assert count_after == count_before, (
            f"Expected no new commit (cfg=None path), but commit count "
            f"went from {count_before} to {count_after}"
        )

    def test_status_file_not_at_git_root_level(self, subfolder_layout, monkeypatch):
        """The status.md file lives inside the wiki clone, not at git-root/.millhouse/."""
        project = subfolder_layout["project"]
        wiki_clone = subfolder_layout["wiki_clone"]
        monkeypatch.chdir(project)

        # Create .millhouse/wiki junction
        mill_link = project / ".millhouse" / "wiki"
        junction.create(wiki_clone, mill_link)

        slug = "root-check"
        active_dir = wiki_clone / "active" / slug
        active_dir.mkdir(parents=True)
        status_path = active_dir / "status.md"
        status_path.write_text(self._make_status_content(), encoding="utf-8")

        # The traditional pre-migration path must NOT exist at the git root
        git_root = subfolder_layout["working_clone"]
        legacy_path = git_root / ".millhouse" / "task" / "status.md"
        assert not legacy_path.exists(), (
            f"status.md should NOT exist at the git root legacy path {legacy_path}"
        )

        # The actual file lives in the wiki clone (via the junction)
        via_junction = mill_link / "active" / slug / "status.md"
        assert via_junction.exists()
