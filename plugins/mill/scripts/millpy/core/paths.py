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

New wiki-based helpers (Card 2)
---------------------------------
- ``project_dir()``       — canonical project root = ``Path.cwd()``. Replaces
                            ``project_root()`` for ``.mill/`` / ``_millhouse/``
                            path building. ``project_root()`` is NOT removed —
                            external callers still use it until their own cards
                            migrate them.
- ``slug_from_branch()``  — derive task slug from current git branch.
- ``wiki_clone_path()``   — resolve wiki clone directory from config or remote URL.
- ``mill_junction_path()``— ``<cwd>/.mill`` junction path.
- ``active_dir()``        — ``<cwd>/.mill/active/<slug>`` directory.
- ``active_status_path()``— ``active_dir() / 'status.md'``.
- ``local_config_path()`` — ``<cwd>/_millhouse/config.local.yaml``.
"""
from __future__ import annotations

import re
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


def millhouse_dir() -> Path:
    """Return the _millhouse directory at the current project root.

    Routes through ``project_dir()`` (cwd-anchored) so the result is
    consistent with ``.mill/`` path resolution.
    """
    return project_dir() / "_millhouse"


def plugin_root() -> Path:
    """Return the plugins/mill/scripts/ directory (parent of the millpy package).

    Resolved from this file's location:
        .../plugins/mill/scripts/millpy/core/paths.py
        parents[0] = core/
        parents[1] = millpy/
        parents[2] = scripts/   ← returned
    """
    return Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Wiki-based helpers (new task system — Card 2)
# ---------------------------------------------------------------------------


def project_dir() -> Path:
    """Return the canonical project root as ``Path.cwd()``.

    This is the cwd-anchored complement to ``project_root()``.  Use this
    (not ``project_root()``) when building ``.mill/`` or ``_millhouse/``
    paths for the new wiki-based task system.  It deliberately does NOT walk
    up or call git — the project boundary is wherever the user (or mill-setup)
    placed it, which is always cwd for a properly-entered worktree.

    ``project_root()`` is kept intact for external callers that have not yet
    been migrated.
    """
    return Path.cwd()


def slug_from_branch(cfg: dict) -> str:
    """Derive the task slug from the current git branch name.

    Strips the optional ``repo.branch-prefix`` (e.g. ``"mh"``) from the
    branch name.  The prefix must be followed by ``/`` to match — a prefix
    of ``"mh"`` strips ``"mh/"`` from the front of ``"mh/foo"`` but leaves
    ``"hotfix/bar"`` unchanged.

    Parameters
    ----------
    cfg:
        Parsed config dict (from ``millpy.core.config.load``).

    Returns
    -------
    str
        The slug: branch name with leading ``<prefix>/`` removed if present.
    """
    result = subprocess_util.run(["git", "branch", "--show-current"])
    branch = result.stdout.strip()

    repo = cfg.get("repo") or {}
    prefix = str(repo.get("branch-prefix") or "").strip()
    if prefix and branch.startswith(prefix + "/"):
        return branch[len(prefix) + 1:]
    return branch


def wiki_clone_path(cfg: dict) -> Path:
    """Resolve the wiki clone directory.

    Resolution order:
    1. ``wiki.clone-path`` in config (explicit override).
    2. Derived: ``<parent-of-cwd>/<repo-name>.wiki/``, where ``repo-name``
       is the basename of ``git remote get-url origin`` (with ``.git`` stripped).

    Parameters
    ----------
    cfg:
        Parsed config dict.

    Returns
    -------
    Path
        Absolute path to the wiki clone directory (not required to exist yet).
    """
    wiki_cfg = cfg.get("wiki") or {}
    explicit = wiki_cfg.get("clone-path")
    if explicit:
        return Path(explicit)

    result = subprocess_util.run(["git", "remote", "get-url", "origin"])
    url = result.stdout.strip()
    basename = url.rstrip("/").rsplit("/", 1)[-1]
    basename = re.sub(r"\.wiki\.git$", "", basename)
    basename = re.sub(r"\.git$", "", basename)
    repo_name = basename.lower()

    parent = Path.cwd().parent
    return parent / f"{repo_name}.wiki"


def mill_junction_path(cwd: Path | None = None) -> Path:
    """Return the ``.mill`` junction path at the project root.

    Parameters
    ----------
    cwd:
        Explicit base directory. Defaults to ``Path.cwd()``.

    Returns
    -------
    Path
        ``<cwd>/.mill``
    """
    base = cwd if cwd is not None else Path.cwd()
    return base / ".mill"


def active_dir(cfg: dict, slug: str | None = None) -> Path:
    """Return the active task directory inside the wiki junction.

    Parameters
    ----------
    cfg:
        Parsed config dict (passed to ``slug_from_branch`` when slug is None).
    slug:
        Explicit slug override.  If ``None``, derives from the current git
        branch via ``slug_from_branch(cfg)``.

    Returns
    -------
    Path
        ``<cwd>/.mill/active/<slug>``
    """
    if slug is None:
        slug = slug_from_branch(cfg)
    return mill_junction_path() / "active" / slug


def active_status_path(cfg: dict) -> Path:
    """Return the status.md path for the current task.

    Equivalent to ``active_dir(cfg) / 'status.md'``.

    Parameters
    ----------
    cfg:
        Parsed config dict.

    Returns
    -------
    Path
        ``<cwd>/.mill/active/<slug>/status.md``
    """
    return active_dir(cfg) / "status.md"


def local_config_path(cwd: Path | None = None) -> Path:
    """Return the local (machine-only) config override path.

    Parameters
    ----------
    cwd:
        Explicit base directory. Defaults to ``Path.cwd()``.

    Returns
    -------
    Path
        ``<cwd>/_millhouse/config.local.yaml``
    """
    base = cwd if cwd is not None else Path.cwd()
    return base / "_millhouse" / "config.local.yaml"
