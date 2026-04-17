"""
paths.py — Repository and plugin path resolution helpers for millpy.

All path helpers use pathlib.Path. Never return bare strings.

Two resolvers exist with different responsibilities:

- ``repo_root()`` returns the git toplevel. Use for source-content lookups
  (git log, file content, anything that lives in the tracked source tree).
- ``project_root()`` walks up from a starting directory looking for a
  ``_millhouse/`` directory and stops at the first match, falling back to
  the git toplevel if none is found. Use for mill-state lookups
  (config.yaml, task/, scratch/, children/). This is the primitive that
  supports nested-project layouts where a mill project lives at
  ``<git>/projects/sub/`` inside a larger git repo.

``millhouse_dir()`` routes through ``project_root()`` so every caller of
the _millhouse directory helper automatically benefits from nested-project
semantics without individual migration.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath

from millpy.core import subprocess_util


class RepoRootNotFound(ValueError):
    """Raised when core.paths.repo_root() cannot locate a git repository root."""


def repo_root(start: Path | None = None) -> Path:
    """Return the top-level git directory for the repository.

    Parameters
    ----------
    start:
        Directory to use as cwd for the git command. Defaults to the current
        working directory. Useful in tests that need to probe a specific path.

    Raises
    ------
    RepoRootNotFound
        If the given directory is not inside a git repository, or if git exits
        non-zero, or if stdout is empty.
    """
    cwd = str(start) if start is not None else None
    result = subprocess_util.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
    )
    if result.returncode != 0 or not result.stdout.strip():
        probe = start if start is not None else Path.cwd()
        raise RepoRootNotFound(
            f"Not inside a git repository (probed: {probe}). "
            f"git stderr: {result.stderr.strip()!r}"
        )
    return Path(result.stdout.strip())


def project_root(start: Path | None = None) -> Path:
    """Return the mill project root (directory containing ``_millhouse/``).

    Walks up from ``start`` (default ``Path.cwd()``) looking for a
    ``_millhouse/`` directory. Returns the first ancestor that contains one.
    If the walk reaches the git toplevel without finding a ``_millhouse/``,
    returns the git toplevel itself (fallback for flat layouts and for
    cold-start before ``mill-setup`` has created ``_millhouse/``).

    Raises ``RepoRootNotFound`` when ``start`` is not inside any git repo.
    """
    probe = Path(start).resolve() if start is not None else Path.cwd().resolve()
    git_root = repo_root(start=probe).resolve()

    current = probe if probe.is_dir() else probe.parent
    while True:
        if (current / "_millhouse").is_dir():
            return current
        if current == git_root:
            return git_root
        if current == current.parent:
            return git_root
        current = current.parent


def project_offset(git_root: Path, project_root: Path) -> PurePosixPath:
    """Return the relative offset from ``git_root`` to ``project_root``.

    - ``project_offset(X, X)`` returns ``PurePosixPath(".")`` (empty offset).
    - ``project_offset(<git>, <git>/projects/sub)`` returns
      ``PurePosixPath("projects/sub")``.
    - Raises ``ValueError`` if ``project_root`` is not a subpath of ``git_root``.

    Return type is ``PurePosixPath`` so the offset uses forward slashes on
    all platforms (appendable to any target path regardless of OS).
    """
    git = Path(git_root).resolve()
    project = Path(project_root).resolve()
    try:
        relative = project.relative_to(git)
    except ValueError as exc:
        raise ValueError(
            f"project_root {project!s} is not a subpath of git_root {git!s}"
        ) from exc
    parts = relative.parts
    if not parts:
        return PurePosixPath(".")
    return PurePosixPath(*parts)


def cwd_offset(start: Path | None = None) -> PurePosixPath:
    """Return the relative offset from the git toplevel to ``start``.

    Parameters
    ----------
    start:
        Probe directory. Defaults to ``Path.cwd()``. Resolved (absolute,
        symlinks followed) before comparison.

    Returns
    -------
    PurePosixPath
        - ``PurePosixPath(".")`` when ``start`` equals the git toplevel.
        - ``PurePosixPath("sub/deeper")`` when ``start`` is a subfolder.
        The returned path uses forward slashes on every platform, making
        it safe to append to any target path regardless of OS.

    Raises
    ------
    RepoRootNotFound
        If ``start`` is not inside any git repository.
    ValueError
        If ``start`` is not a subpath of the git toplevel (e.g. resolves
        outside the repo).
    """
    probe = Path(start).resolve() if start is not None else Path.cwd().resolve()
    git_root = repo_root(start=probe).resolve()
    relative = probe.relative_to(git_root)
    parts = relative.parts
    if not parts:
        return PurePosixPath(".")
    return PurePosixPath(*parts)


def millhouse_dir(start: Path | None = None) -> Path:
    """Return the _millhouse directory at the mill project root.

    Routes through ``project_root()`` so nested-project layouts resolve
    correctly. Propagates ``RepoRootNotFound`` when not inside a git repo.
    """
    return project_root(start=start) / "_millhouse"


def plugin_root() -> Path:
    """Return the plugins/mill/scripts/ directory (parent of the millpy package).

    Resolved from this file's location:
        .../plugins/mill/scripts/millpy/core/paths.py
        parents[0] = core/
        parents[1] = millpy/
        parents[2] = scripts/   ← returned
    """
    return Path(__file__).resolve().parents[2]
