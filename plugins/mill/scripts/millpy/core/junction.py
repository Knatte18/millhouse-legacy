"""
junction.py — Cross-platform directory junction/symlink helpers for millpy.

Provides a thin abstraction over OS-specific junction mechanisms:
  - Windows: directory junctions via ``mklink /J``
  - POSIX:   directory symlinks via ``os.symlink``

Public API
----------
create(target, link_path)
    Create a junction (Windows) or symlink (POSIX) at ``link_path`` pointing
    to ``target``. Both paths must be absolute. Raises ``ValueError`` if
    ``link_path`` already exists.

remove(link_path)
    Remove the junction/symlink at ``link_path``. Idempotent — silent no-op
    if ``link_path`` does not exist. Never recursively deletes the target.
"""
from __future__ import annotations

import os
from pathlib import Path

from millpy.core import subprocess_util
from millpy.core.log_util import log

_MODULE = "junction"


def create(target: Path, link_path: Path) -> None:
    """Create a directory junction (Windows) or symlink (POSIX).

    Parameters
    ----------
    target:
        Absolute path to the existing directory the junction will point at.
    link_path:
        Absolute path where the junction/symlink will be created.

    Raises
    ------
    ValueError
        If ``link_path`` already exists (as any file-system object).
    """
    if link_path.exists() or link_path.is_symlink():
        raise ValueError(f"{link_path} already exists — remove it before creating a junction")

    link_path.parent.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        # Windows: use mklink /J for directory junctions.
        # Normalise to Windows path form for cmd.exe.
        win_link = str(link_path).replace("/", "\\")
        win_target = str(target).replace("/", "\\")
        result = subprocess_util.run(
            ["cmd", "/c", "mklink", "/J", win_link, win_target],
        )
        if result.returncode != 0:
            raise OSError(
                f"mklink /J failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        log(_MODULE, f"created junction {link_path} -> {target}")
    else:
        os.symlink(str(target), str(link_path))
        log(_MODULE, f"created symlink {link_path} -> {target}")


def remove(link_path: Path) -> None:
    """Remove a directory junction or symlink.

    Idempotent — if ``link_path`` does not exist, returns silently.
    Never recursively deletes the target directory.

    Parameters
    ----------
    link_path:
        Path to the junction or symlink to remove.

    Raises
    ------
    ValueError
        If ``link_path`` exists but is neither a junction nor a symlink
        (i.e. it is an ordinary non-empty directory or a regular file that
        cannot be safely removed by this function).
    """
    if not link_path.exists() and not link_path.is_symlink():
        # Silent no-op — already absent.
        return

    if os.name == "nt":
        # Python 3.12+: os.path.isjunction detects Windows directory junctions.
        # Python 3.10/3.11 fallback: check FILE_ATTRIBUTE_REPARSE_POINT (0x400)
        # via os.lstat().st_file_attributes.
        is_junction = False
        if hasattr(os.path, "isjunction"):
            is_junction = os.path.isjunction(str(link_path))
        else:
            try:
                attrs = os.lstat(str(link_path)).st_file_attributes
                is_junction = bool(attrs & 0x400)
            except (OSError, AttributeError):
                is_junction = False

        if is_junction:
            os.rmdir(str(link_path))
            log(_MODULE, f"removed junction {link_path}")
        elif os.path.islink(str(link_path)):
            os.unlink(str(link_path))
            log(_MODULE, f"removed symlink {link_path}")
        else:
            raise ValueError(
                f"{link_path} is not a junction or symlink — refusing to remove"
            )
    else:
        if os.path.islink(str(link_path)):
            os.unlink(str(link_path))
            log(_MODULE, f"removed symlink {link_path}")
        else:
            raise ValueError(
                f"{link_path} is not a symlink — refusing to remove"
            )
