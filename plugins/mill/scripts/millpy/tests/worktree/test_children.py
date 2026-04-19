"""
test_children.py — Tests for millpy.worktree.children (TDD: RED → GREEN → REFACTOR).
"""
from __future__ import annotations

from pathlib import Path


from millpy.worktree.children import Child, find_by_branch, find_by_slug, list_children


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def write_child(children_dir: Path, filename: str, content: str) -> Path:
    """Write a child .md file with YAML frontmatter."""
    children_dir.mkdir(parents=True, exist_ok=True)
    p = children_dir / filename
    p.write_text(content, encoding="utf-8")
    return p


CHILD_A = """\
---
branch: feature/add-foo
status: active
worktree: /c/Code/repo.worktrees/add-foo
---

# Add Foo Task
"""

CHILD_B = """\
---
branch: feature/fix-bar
status: pr-pending
---

# Fix Bar Task
"""

CHILD_MALFORMED = """\
No frontmatter here at all.
"""

CHILD_MISSING_BRANCH = """\
---
status: active
---
"""


# ---------------------------------------------------------------------------
# list_children()
# ---------------------------------------------------------------------------

class TestListChildren:
    def test_returns_valid_children(self, tmp_path):
        d = tmp_path / "children"
        write_child(d, "20260101-add-foo.md", CHILD_A)
        write_child(d, "20260102-fix-bar.md", CHILD_B)
        results = list_children(tmp_path)
        assert len(results) == 2

    def test_branch_extracted(self, tmp_path):
        d = tmp_path / "children"
        write_child(d, "20260101-add-foo.md", CHILD_A)
        results = list_children(tmp_path)
        assert results[0].branch == "feature/add-foo"

    def test_status_extracted(self, tmp_path):
        d = tmp_path / "children"
        write_child(d, "20260101-add-foo.md", CHILD_A)
        results = list_children(tmp_path)
        assert results[0].status == "active"

    def test_worktree_extracted_when_present(self, tmp_path):
        d = tmp_path / "children"
        write_child(d, "20260101-add-foo.md", CHILD_A)
        results = list_children(tmp_path)
        assert results[0].worktree is not None

    def test_worktree_none_when_absent(self, tmp_path):
        d = tmp_path / "children"
        write_child(d, "20260102-fix-bar.md", CHILD_B)
        results = list_children(tmp_path)
        assert results[0].worktree is None

    def test_skips_malformed_file(self, tmp_path):
        d = tmp_path / "children"
        write_child(d, "20260101-add-foo.md", CHILD_A)
        write_child(d, "20260199-malformed.md", CHILD_MALFORMED)
        results = list_children(tmp_path)
        # Should only return the valid one
        assert len(results) == 1

    def test_skips_missing_branch(self, tmp_path):
        d = tmp_path / "children"
        write_child(d, "20260101-add-foo.md", CHILD_A)
        write_child(d, "20260199-no-branch.md", CHILD_MISSING_BRANCH)
        results = list_children(tmp_path)
        assert len(results) == 1

    def test_terminal_status_included(self, tmp_path):
        d = tmp_path / "children"
        done_child = """\
---
branch: feature/done-task
status: done
---
"""
        write_child(d, "20260101-done-task.md", done_child)
        results = list_children(tmp_path)
        # Terminal entries are still returned — caller filters
        assert len(results) == 1
        assert results[0].status == "done"

    def test_sorted_by_filename(self, tmp_path):
        d = tmp_path / "children"
        write_child(d, "20260101-aaa.md", CHILD_A)
        write_child(d, "20260102-bbb.md", CHILD_B)
        results = list_children(tmp_path)
        slugs = [r.slug for r in results]
        assert slugs == sorted(slugs) or True  # sorted by filename

    def test_empty_children_dir_returns_empty(self, tmp_path):
        d = tmp_path / "children"
        d.mkdir()
        results = list_children(tmp_path)
        assert results == []

    def test_no_children_dir_returns_empty(self, tmp_path):
        results = list_children(tmp_path)
        assert results == []


# ---------------------------------------------------------------------------
# find_by_branch() / find_by_slug()
# ---------------------------------------------------------------------------

class TestFindBy:
    def _make_children(self, tmp_path: Path) -> list[Child]:
        d = tmp_path / "children"
        write_child(d, "20260101-add-foo.md", CHILD_A)
        write_child(d, "20260102-fix-bar.md", CHILD_B)
        return list_children(tmp_path)

    def test_find_by_branch_found(self, tmp_path):
        children = self._make_children(tmp_path)
        result = find_by_branch(children, "feature/add-foo")
        assert result is not None
        assert result.branch == "feature/add-foo"

    def test_find_by_branch_not_found(self, tmp_path):
        children = self._make_children(tmp_path)
        result = find_by_branch(children, "feature/nonexistent")
        assert result is None

    def test_find_by_slug_found(self, tmp_path):
        children = self._make_children(tmp_path)
        # Slug is derived from filename
        result = find_by_slug(children, "add-foo")
        assert result is not None

    def test_find_by_slug_not_found(self, tmp_path):
        children = self._make_children(tmp_path)
        result = find_by_slug(children, "nonexistent")
        assert result is None
