"""
test_wiki_lifecycle.py — Integration: full wiki-based task lifecycle.

Tests the end-to-end task flow using real git repos (in tmp_path), covering:

  spawn  →  discuss  →  plan  →  (simulated code commits)  →  complete  →  merge cleanup

Layout
------
::

    tmp_path/
        main.git/       ← bare main repo
        main/           ← working clone (feature-test branch)
            _millhouse/ ← local config
            .mill/      →  tmp_path/main.wiki/  (junction)
        main.wiki.git/  ← bare wiki repo
        main.wiki/      ← wiki clone
            Home.md
            active/
                feature-test/
                    status.md
                    discussion.md

Skips on Windows when ``mklink /J`` is unavailable (rare CI environments).
"""
from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

from millpy.core import junction
from millpy.core.paths import active_dir, mill_junction_path, slug_from_branch


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


def _make_bare_repo(path: Path) -> None:
    """Init a bare git repo."""
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "--bare", "-q", str(path))


def _make_clone_with_branch(bare_path: Path, clone_path: Path, branch: str) -> None:
    """Create a working clone with an initial commit on ``branch``.

    1. Clone the bare repo.
    2. Create (or switch to) ``branch`` from the initial commit.
    3. Push it so ``git push`` later has a tracking upstream.
    """
    clone_path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", str(clone_path))
    _git("config", "user.email", "test@test.invalid", cwd=clone_path)
    _git("config", "user.name", "Test", cwd=clone_path)
    _git("config", "push.default", "current", cwd=clone_path)
    _git("remote", "add", "origin", str(bare_path), cwd=clone_path)
    # Initial empty commit on main
    _git("commit", "--allow-empty", "-q", "-m", "init", cwd=clone_path)
    _git("push", "-q", "origin", "HEAD:main", cwd=clone_path)
    # Create the feature branch
    if branch != "main":
        _git("checkout", "-b", branch, cwd=clone_path)
        _git("push", "-q", "origin", branch, cwd=clone_path)


def _make_wiki_clone_with_home(bare_wiki: Path, wiki_clone: Path) -> None:
    """Init wiki bare+clone with a minimal Home.md."""
    _make_bare_repo(bare_wiki)
    wiki_clone.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", str(wiki_clone))
    _git("config", "user.email", "test@test.invalid", cwd=wiki_clone)
    _git("config", "user.name", "Test", cwd=wiki_clone)
    _git("config", "push.default", "current", cwd=wiki_clone)
    _git("remote", "add", "origin", str(bare_wiki), cwd=wiki_clone)
    # Write minimal Home.md
    home = wiki_clone / "Home.md"
    home.write_text("# Tasks\n\n## [s] Feature Test\nA test task.\n", encoding="utf-8")
    _git("add", "Home.md", cwd=wiki_clone)
    _git("commit", "-q", "-m", "init Home.md", cwd=wiki_clone)
    _git("push", "-q", "origin", "HEAD:main", cwd=wiki_clone)


def _make_status_content(task_title: str, ts: str = "2026-04-18T10:00:00Z") -> str:
    return textwrap.dedent(f"""\
        # Status

        ```yaml
        task: {task_title}
        phase: discussing
        parent: main
        task_description: |
          A test task.
        ```

        ## Timeline

        ```text
        discussing              {ts}
        ```
        """)


# ---------------------------------------------------------------------------
# Config helper
# ---------------------------------------------------------------------------

def _make_cfg(wiki_clone: Path) -> dict:
    """Build a minimal config dict pointing at the given wiki clone."""
    return {
        "wiki": {"clone-path": str(wiki_clone)},
        "repo": {"branch-prefix": ""},
    }


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def wiki_setup(tmp_path):
    """Set up bare+clone+wiki layout for full lifecycle tests.

    Yields a dict with keys:
      bare_repo, main_clone, bare_wiki, wiki_clone, project, cfg, slug
    """
    slug = "feature-test"
    branch = slug

    # Main repo
    bare_repo = tmp_path / "main.git"
    main_clone = tmp_path / "main"
    _make_bare_repo(bare_repo)
    _make_clone_with_branch(bare_repo, main_clone, branch)

    # Wiki repo
    bare_wiki = tmp_path / "main.wiki.git"
    wiki_clone = tmp_path / "main.wiki"
    _make_wiki_clone_with_home(bare_wiki, wiki_clone)

    # Local _millhouse/ directory (simulate mill-setup output)
    millhouse = main_clone / "_millhouse"
    millhouse.mkdir(parents=True, exist_ok=True)

    # Config dict (no config.yaml file needed — pass inline)
    cfg = _make_cfg(wiki_clone)

    yield {
        "bare_repo": bare_repo,
        "main_clone": main_clone,
        "bare_wiki": bare_wiki,
        "wiki_clone": wiki_clone,
        "project": main_clone,
        "cfg": cfg,
        "slug": slug,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestWikiLifecycle:
    """Full wiki-based task lifecycle: spawn → discuss → plan → complete → cleanup."""

    def test_lifecycle(self, wiki_setup, monkeypatch):
        """End-to-end lifecycle from spawn through merge cleanup."""
        from millpy.tasks import wiki as wiki_mod
        from millpy.tasks import tasks_md, status_md

        project = wiki_setup["project"]
        wiki_clone = wiki_setup["wiki_clone"]
        cfg = wiki_setup["cfg"]
        slug = wiki_setup["slug"]

        monkeypatch.chdir(project)

        # -------------------------------------------------------------------
        # Step 1: Spawn — create .mill/ junction, claim task in Home.md,
        #         write initial status.md at active/<slug>/
        # -------------------------------------------------------------------

        # Create .mill/ junction
        mill_link = project / ".mill"
        junction.create(wiki_clone, mill_link)
        assert mill_link.exists(), ".mill/ junction must exist"

        # Claim task in Home.md (simulate spawn_task core path)
        home_path = wiki_clone / "Home.md"
        home_content = home_path.read_text(encoding="utf-8")
        # Replace [s] with [active]
        claimed_content = home_content.replace("[s] Feature Test", "[active] Feature Test")
        home_path.write_text(claimed_content, encoding="utf-8")
        _git("add", "Home.md", cwd=wiki_clone)
        _git("commit", "-q", "-m", "task: claim Feature Test", cwd=wiki_clone)
        _git("push", "-q", cwd=wiki_clone)

        # Verify Home.md has [active] marker
        home_text = home_path.read_text(encoding="utf-8")
        assert "[active] Feature Test" in home_text, "Home.md must have [active] marker after claim"

        # Write initial status.md at active/<slug>/
        active_slug_dir = wiki_clone / "active" / slug
        active_slug_dir.mkdir(parents=True, exist_ok=True)
        status_path = active_slug_dir / "status.md"
        status_path.write_text(_make_status_content("Feature Test"), encoding="utf-8")
        _git("add", f"active/{slug}/status.md", cwd=wiki_clone)
        _git("commit", "-q", "-m", f"task: init {slug}", cwd=wiki_clone)
        _git("push", "-q", cwd=wiki_clone)

        # Assert status.md has phase: discussing
        data = status_md.load(status_path)
        assert data["phase"] == "discussing", f"Expected discussing, got {data['phase']!r}"

        # -------------------------------------------------------------------
        # Step 2: Discuss — write discussion.md, update phase to discussed
        # -------------------------------------------------------------------

        discussion_path = active_slug_dir / "discussion.md"
        discussion_path.write_text(
            "# Discussion\n\nThis task explores the wiki lifecycle.\n",
            encoding="utf-8",
        )
        wiki_mod.write_commit_push(
            cfg,
            [f"active/{slug}/discussion.md"],
            f"task: discussion {slug}",
        )

        # Assert discussion.md is in the wiki git history
        log_result = _git("log", "--oneline", cwd=wiki_clone)
        assert f"task: discussion {slug}" in log_result.stdout, (
            "discussion commit must appear in wiki history"
        )

        # Update phase to discussed
        status_md.append_phase(status_path, "discussed", cfg=None)
        wiki_mod.write_commit_push(
            cfg,
            [f"active/{slug}/status.md"],
            f"task: phase discussed",
        )

        data = status_md.load(status_path)
        assert data["phase"] == "discussed"

        # -------------------------------------------------------------------
        # Step 3: Plan — write plan/ directory, update phase to planned
        # -------------------------------------------------------------------

        plan_dir = active_slug_dir / "plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plan_dir / "overview.md"
        plan_file.write_text(
            "# Plan\n\n## Steps\n\n1. Do the thing.\n",
            encoding="utf-8",
        )
        wiki_mod.write_commit_push(
            cfg,
            [f"active/{slug}/plan/overview.md"],
            f"task: plan {slug}",
        )

        status_md.append_phase(status_path, "planned", cfg=None)
        wiki_mod.write_commit_push(cfg, [f"active/{slug}/status.md"], "task: phase planned")

        data = status_md.load(status_path)
        assert data["phase"] == "planned"

        # -------------------------------------------------------------------
        # Step 4: Simulate code commits on the feature branch
        # -------------------------------------------------------------------

        source_file = project / "feature.py"
        source_file.write_text("# feature implementation\n", encoding="utf-8")
        _git("add", "feature.py", cwd=project)
        _git("commit", "-q", "-m", "feat: add feature implementation", cwd=project)

        # -------------------------------------------------------------------
        # Step 5: Finalize — mark phase complete
        # -------------------------------------------------------------------

        status_md.append_phase(status_path, "complete", cfg=None)
        wiki_mod.write_commit_push(cfg, [f"active/{slug}/status.md"], "task: phase complete")

        data = status_md.load(status_path)
        assert data["phase"] == "complete"

        # -------------------------------------------------------------------
        # Step 6: Merge cleanup — delete active/<slug>/, mark Home.md [done]
        # -------------------------------------------------------------------

        # Simulate mill-merge: delete active/<slug>/ tree
        import shutil
        shutil.rmtree(str(active_slug_dir))
        _git("rm", "-r", f"active/{slug}", cwd=wiki_clone)
        _git("commit", "-q", "-m", f"task: merged {slug}", cwd=wiki_clone)
        _git("push", "-q", cwd=wiki_clone)

        # Mark Home.md [done]
        home_text = home_path.read_text(encoding="utf-8")
        done_content = home_text.replace("[active] Feature Test", "[done] Feature Test")
        home_path.write_text(done_content, encoding="utf-8")
        _git("add", "Home.md", cwd=wiki_clone)
        _git("commit", "-q", "-m", f"task: done {slug}", cwd=wiki_clone)
        _git("push", "-q", cwd=wiki_clone)

        # -------------------------------------------------------------------
        # Step 7: Assertions — post-merge state
        # -------------------------------------------------------------------

        # active/<slug>/ must no longer exist in the wiki
        assert not active_slug_dir.exists(), "active/<slug>/ must be deleted after merge"

        # Home.md entry must have [done] marker
        home_final = home_path.read_text(encoding="utf-8")
        assert "[done] Feature Test" in home_final, "Home.md must have [done] marker after merge"

        # All phase transitions committed: count commits with "task:" prefix
        log_all = _git("log", "--oneline", cwd=wiki_clone)
        task_commits = [
            line for line in log_all.stdout.splitlines() if "task:" in line
        ]
        assert len(task_commits) >= 5, (
            f"Expected at least 5 task: commits in wiki history, found {len(task_commits)}:\n"
            + "\n".join(task_commits)
        )

    def test_junction_idempotent_removal(self, wiki_setup, monkeypatch):
        """`junction.remove` is idempotent — calling it twice does not error."""
        project = wiki_setup["project"]
        wiki_clone = wiki_setup["wiki_clone"]

        monkeypatch.chdir(project)

        mill_link = project / ".mill"
        junction.create(wiki_clone, mill_link)
        assert mill_link.exists()

        # First removal
        junction.remove(mill_link)
        assert not mill_link.exists()

        # Second removal must be a no-op (idempotent)
        junction.remove(mill_link)  # must not raise

    def test_lockfile_not_committed(self, wiki_setup, monkeypatch):
        """.mill-lock must never appear in the wiki git history."""
        project = wiki_setup["project"]
        wiki_clone = wiki_setup["wiki_clone"]
        cfg = wiki_setup["cfg"]
        slug = wiki_setup["slug"]

        monkeypatch.chdir(project)

        # Simulate acquiring and releasing a lock
        from millpy.tasks.wiki import acquire_lock, release_lock
        acquire_lock(cfg, slug, timeout_seconds=5)
        release_lock(cfg)

        # .mill-lock must NOT be in git ls-files
        ls_files = _git("ls-files", cwd=wiki_clone)
        assert ".mill-lock" not in ls_files.stdout, (
            ".mill-lock must not be tracked in the wiki repo"
        )
