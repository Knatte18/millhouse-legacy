"""Tests for millpy.entrypoints.regenerate_sidebar.

Card 12: regenerate_sidebar builds _Sidebar.md from Home.md + proposals/.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


def _make_wiki(tmp_path: Path, home_content: str) -> tuple[Path, Path]:
    """Create a minimal fake wiki directory with Home.md.

    Returns (project_dir, wiki_dir).
    """
    wiki_dir = tmp_path / "repo.wiki"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "Home.md").write_text(home_content, encoding="utf-8")
    (wiki_dir / "proposals").mkdir()

    project_dir = tmp_path / "repo"
    project_dir.mkdir()

    # Create .mill junction (fake: just a directory in tests)
    mill = project_dir / ".mill"
    mill.mkdir()
    # Link .mill to wiki_dir by symlinking or just copying content for tests
    # For unit tests, we fake the junction by writing files directly in .mill
    (mill / "Home.md").write_text(home_content, encoding="utf-8")
    (mill / "proposals").mkdir()

    return project_dir, wiki_dir


def _fake_cfg(wiki_dir: Path) -> dict:
    """Return a fake config dict pointing at wiki_dir."""
    return {
        "wiki": {"clone-path": str(wiki_dir)},
        "repo": {"branch-prefix": None},
    }


class TestRegenerateSidebarHappy:
    def test_sidebar_contains_tasks_link(self, tmp_path, monkeypatch):
        """Generated sidebar includes **[Tasks](Home)** link."""
        from millpy.entrypoints import regenerate_sidebar

        project_dir, wiki_dir = _make_wiki(
            tmp_path,
            "# Tasks\n\n## My Task\nA description.\n",
        )
        monkeypatch.chdir(project_dir)

        cfg = _fake_cfg(wiki_dir)
        with patch("millpy.entrypoints.regenerate_sidebar._load_cfg", return_value=cfg), \
             patch("millpy.tasks.wiki.acquire_lock"), \
             patch("millpy.tasks.wiki.release_lock"), \
             patch("millpy.tasks.wiki.write_commit_push"):
            regenerate_sidebar.main([])

        sidebar = (wiki_dir / "_Sidebar.md").read_text(encoding="utf-8")
        assert "**[Tasks](Home)**" in sidebar

    def test_proposals_sorted_alphabetically(self, tmp_path, monkeypatch):
        """Proposal entries are sorted alphabetically by display name."""
        from millpy.entrypoints import regenerate_sidebar

        project_dir, wiki_dir = _make_wiki(
            tmp_path,
            "# Tasks\n\n## My Task\nA description.\n",
        )
        proposals_dir = wiki_dir / "proposals"
        (proposals_dir / "zebra-task.md").write_text("# Zebra Task\nDesc.\n", encoding="utf-8")
        (proposals_dir / "apple-task.md").write_text("# Apple Task\nDesc.\n", encoding="utf-8")
        # Also update .mill/proposals
        mill_proposals = project_dir / ".mill" / "proposals"
        (mill_proposals / "zebra-task.md").write_text("# Zebra Task\nDesc.\n", encoding="utf-8")
        (mill_proposals / "apple-task.md").write_text("# Apple Task\nDesc.\n", encoding="utf-8")

        monkeypatch.chdir(project_dir)
        cfg = _fake_cfg(wiki_dir)

        with patch("millpy.entrypoints.regenerate_sidebar._load_cfg", return_value=cfg), \
             patch("millpy.tasks.wiki.acquire_lock"), \
             patch("millpy.tasks.wiki.release_lock"), \
             patch("millpy.tasks.wiki.write_commit_push"):
            regenerate_sidebar.main([])

        sidebar = (wiki_dir / "_Sidebar.md").read_text(encoding="utf-8")
        apple_pos = sidebar.index("Apple Task")
        zebra_pos = sidebar.index("Zebra Task")
        assert apple_pos < zebra_pos, "Apple should come before Zebra"

    def test_empty_proposals_dir_has_proposals_header(self, tmp_path, monkeypatch):
        """Empty proposals/ → sidebar has **Proposals** header with no entries."""
        from millpy.entrypoints import regenerate_sidebar

        project_dir, wiki_dir = _make_wiki(
            tmp_path,
            "# Tasks\n\n## My Task\nA description.\n",
        )
        monkeypatch.chdir(project_dir)
        cfg = _fake_cfg(wiki_dir)

        with patch("millpy.entrypoints.regenerate_sidebar._load_cfg", return_value=cfg), \
             patch("millpy.tasks.wiki.acquire_lock"), \
             patch("millpy.tasks.wiki.release_lock"), \
             patch("millpy.tasks.wiki.write_commit_push"):
            regenerate_sidebar.main([])

        sidebar = (wiki_dir / "_Sidebar.md").read_text(encoding="utf-8")
        assert "**Proposals**" in sidebar

    def test_proposal_without_heading_uses_file_stem(self, tmp_path, monkeypatch):
        """A proposal file with no # heading uses the file stem as display name."""
        from millpy.entrypoints import regenerate_sidebar

        project_dir, wiki_dir = _make_wiki(
            tmp_path,
            "# Tasks\n\n## My Task\nA description.\n",
        )
        proposals_dir = wiki_dir / "proposals"
        (proposals_dir / "no-heading.md").write_text("Some content without heading.\n", encoding="utf-8")
        mill_proposals = project_dir / ".mill" / "proposals"
        (mill_proposals / "no-heading.md").write_text("Some content without heading.\n", encoding="utf-8")

        monkeypatch.chdir(project_dir)
        cfg = _fake_cfg(wiki_dir)

        with patch("millpy.entrypoints.regenerate_sidebar._load_cfg", return_value=cfg), \
             patch("millpy.tasks.wiki.acquire_lock"), \
             patch("millpy.tasks.wiki.release_lock"), \
             patch("millpy.tasks.wiki.write_commit_push"):
            regenerate_sidebar.main([])

        sidebar = (wiki_dir / "_Sidebar.md").read_text(encoding="utf-8")
        assert "no-heading" in sidebar

    def test_acquire_lock_called_before_write(self, tmp_path, monkeypatch):
        """acquire_lock is called before the sidebar write."""
        from millpy.entrypoints import regenerate_sidebar

        project_dir, wiki_dir = _make_wiki(
            tmp_path,
            "# Tasks\n\n## My Task\nA description.\n",
        )
        monkeypatch.chdir(project_dir)
        cfg = _fake_cfg(wiki_dir)

        call_order = []

        def fake_acquire(cfg, slug, **kw):
            call_order.append("acquire")

        def fake_write(cfg, paths, msg):
            call_order.append("write")

        with patch("millpy.entrypoints.regenerate_sidebar._load_cfg", return_value=cfg), \
             patch("millpy.tasks.wiki.acquire_lock", side_effect=fake_acquire), \
             patch("millpy.tasks.wiki.release_lock"), \
             patch("millpy.tasks.wiki.write_commit_push", side_effect=fake_write):
            regenerate_sidebar.main([])

        assert call_order.index("acquire") < call_order.index("write")
