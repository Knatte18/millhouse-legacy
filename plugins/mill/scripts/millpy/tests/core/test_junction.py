"""Tests for millpy.core.junction."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from millpy.core.junction import create, remove


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_target(tmp_path: Path) -> Path:
    """Create a directory to use as junction target; put a file in it."""
    target = tmp_path / "target"
    target.mkdir()
    (target / "sentinel.txt").write_text("ok", encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# create — POSIX only (skip on Windows)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink test — skipped on Windows")
def test_create_posix_symlink(tmp_path: Path) -> None:
    """create(target, link) on POSIX creates a symlink pointing to target."""
    target = _make_target(tmp_path)
    link = tmp_path / "link"
    create(target, link)
    assert os.path.islink(link)
    assert os.readlink(str(link)) == str(target)


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink test — skipped on Windows")
def test_create_posix_link_is_directory(tmp_path: Path) -> None:
    """create(target, link) on POSIX: link behaves as a directory."""
    target = _make_target(tmp_path)
    link = tmp_path / "link"
    create(target, link)
    assert link.is_dir()
    assert (link / "sentinel.txt").read_text(encoding="utf-8") == "ok"


# ---------------------------------------------------------------------------
# create — Windows only (skip on POSIX)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name != "nt", reason="Windows junction test — skipped on POSIX")
def test_create_windows_junction_isdir(tmp_path: Path) -> None:
    """create(target, link) on Windows creates a junction; isdir returns True."""
    target = _make_target(tmp_path)
    link = tmp_path / "link"
    create(target, link)
    assert os.path.isdir(str(link))


@pytest.mark.skipif(os.name != "nt", reason="Windows junction test — skipped on POSIX")
def test_create_windows_junction_contents(tmp_path: Path) -> None:
    """create(target, link) on Windows: listing link returns target's contents."""
    target = _make_target(tmp_path)
    link = tmp_path / "link"
    create(target, link)
    assert (link / "sentinel.txt").read_text(encoding="utf-8") == "ok"


# ---------------------------------------------------------------------------
# create — error cases (both platforms)
# ---------------------------------------------------------------------------


def test_create_raises_when_link_exists(tmp_path: Path) -> None:
    """create(target, link) raises ValueError if link_path already exists."""
    target = _make_target(tmp_path)
    link = tmp_path / "link"
    link.mkdir()  # link already exists
    with pytest.raises(ValueError):
        create(target, link)


# ---------------------------------------------------------------------------
# remove — idempotent (both platforms)
# ---------------------------------------------------------------------------


def test_remove_nonexistent_is_noop(tmp_path: Path) -> None:
    """remove(nonexistent) does not raise."""
    remove(tmp_path / "does_not_exist")


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink removal — skipped on Windows")
def test_remove_posix_symlink(tmp_path: Path) -> None:
    """remove(link) on POSIX removes the symlink, target directory survives."""
    target = _make_target(tmp_path)
    link = tmp_path / "link"
    os.symlink(str(target), str(link))
    assert os.path.islink(str(link))
    remove(link)
    assert not link.exists()
    assert target.is_dir()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction removal — skipped on POSIX")
def test_remove_windows_junction(tmp_path: Path) -> None:
    """remove(link) on Windows removes the junction, target directory survives."""
    target = _make_target(tmp_path)
    link = tmp_path / "link"
    create(target, link)
    assert os.path.isdir(str(link))
    remove(link)
    assert not link.exists()
    assert target.is_dir()
