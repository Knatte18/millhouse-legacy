"""
wiki.py — Wiki-clone interaction helpers for millpy.

Provides sync, write-commit-push, auto-merge resolution, and advisory
lock primitives for the GitHub Wiki-based task system.

Public API
----------
sync_pull(cfg)
    Fetch + fast-forward merge the local wiki clone from origin.

write_commit_push(cfg, relative_paths, commit_msg)
    Stage named paths in the wiki clone, commit, push (with pull-rebase
    retry on non-fast-forward rejection).

auto_resolve_merge(wiki_path)
    Inspect conflict state and attempt automatic resolution for Home.md
    and _Sidebar.md. Returns True only when all conflicts are resolved.

acquire_lock(cfg, slug, timeout_seconds)
    Create .mill-lock atomically in the wiki clone, retrying up to
    timeout_seconds for a non-stale lock held by another writer.

release_lock(cfg)
    Delete .mill-lock idempotently.

Exceptions
----------
WikiSyncError         — any git failure inside sync_pull
WikiMergeConflict     — irresolvable rebase conflict (carries file paths)
LockBusy              — acquire_lock timed out (carries holder, age_seconds)
"""
from __future__ import annotations

import datetime
import os
import time
from pathlib import Path

from millpy.core import subprocess_util
from millpy.core.log_util import log
from millpy.core.paths import wiki_clone_path

_MODULE = "wiki"

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class WikiSyncError(RuntimeError):
    """Raised when a git operation inside sync_pull fails."""


class WikiMergeConflict(RuntimeError):
    """Raised when write_commit_push cannot resolve a rebase conflict.

    Attributes
    ----------
    paths:
        List of conflicted file paths (relative to wiki clone root).
    """

    def __init__(self, paths: list[str]) -> None:
        self.paths = paths
        super().__init__(f"Unresolvable wiki merge conflict in: {', '.join(paths)}")


class LockBusy(RuntimeError):
    """Raised when acquire_lock times out waiting for a held lock.

    Attributes
    ----------
    holder:
        The slug written into the existing lockfile.
    age_seconds:
        Approximate age of the lock in seconds at time of timeout.
    """

    def __init__(self, holder: str, age_seconds: int) -> None:
        self.holder = holder
        self.age_seconds = age_seconds
        super().__init__(
            f"Wiki lock held by {holder!r} (age {age_seconds}s); timed out waiting"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_STALE_SECONDS = 5 * 60  # 5 minutes


def _wiki_path(cfg: dict) -> Path:
    """Return the wiki clone Path from config."""
    return wiki_clone_path(cfg)


def _detect_default_branch(wiki_path: Path) -> str:
    """Return the default remote branch name from symbolic-ref."""
    result = subprocess_util.run(
        ["git", "-C", str(wiki_path), "symbolic-ref", "refs/remotes/origin/HEAD"],
    )
    if result.returncode != 0:
        raise WikiSyncError(
            f"Cannot detect default branch: {result.stderr.strip()!r}"
        )
    # refs/remotes/origin/main → main
    ref = result.stdout.strip()
    parts = ref.split("/")
    return parts[-1] if parts else "main"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sync_pull(cfg: dict) -> None:
    """Fetch + fast-forward merge the wiki clone from origin.

    Parameters
    ----------
    cfg:
        Parsed config dict (from ``millpy.core.config.load``).

    Raises
    ------
    WikiSyncError
        On any git failure (symbolic-ref, fetch, or merge --ff-only).
    """
    wiki = _wiki_path(cfg)
    log(_MODULE, f"sync_pull: wiki={wiki}")

    # 1. Detect default branch.
    branch = _detect_default_branch(wiki)

    # 2. Fetch.
    fetch = subprocess_util.run(["git", "-C", str(wiki), "fetch", "origin"])
    if fetch.returncode != 0:
        raise WikiSyncError(f"git fetch failed: {fetch.stderr.strip()!r}")

    # 3. Fast-forward merge.
    merge = subprocess_util.run(
        ["git", "-C", str(wiki), "merge", "--ff-only", f"origin/{branch}"]
    )
    if merge.returncode != 0:
        raise WikiSyncError(
            f"git merge --ff-only origin/{branch} failed: {merge.stderr.strip()!r}"
        )

    log(_MODULE, "sync_pull: complete")


def write_commit_push(
    cfg: dict,
    relative_paths: list[str],
    commit_msg: str,
) -> None:
    """Stage, commit, and push changes in the wiki clone.

    Retries once via ``git pull --rebase`` on push non-fast-forward rejection.
    Calls ``auto_resolve_merge`` when rebase fails; raises
    ``WikiMergeConflict`` when conflicts remain unresolved.

    Parameters
    ----------
    cfg:
        Parsed config dict.
    relative_paths:
        Paths (relative to wiki clone root) to stage.
    commit_msg:
        Commit message.

    Raises
    ------
    WikiMergeConflict
        If a rebase conflict cannot be auto-resolved.
    RuntimeError
        If add or commit fails for a reason other than "nothing to commit".
    """
    wiki = _wiki_path(cfg)
    log(_MODULE, f"write_commit_push: wiki={wiki} paths={relative_paths!r}")

    # Stage.
    add = subprocess_util.run(
        ["git", "-C", str(wiki), "add", "--"] + list(relative_paths)
    )
    if add.returncode != 0:
        raise RuntimeError(f"git add failed: {add.stderr.strip()!r}")

    # Commit.
    commit = subprocess_util.run(
        ["git", "-C", str(wiki), "commit", "-m", commit_msg]
    )
    if commit.returncode != 0:
        combined = (commit.stdout or "") + (commit.stderr or "")
        if "nothing to commit" in combined:
            log(_MODULE, "write_commit_push: nothing to commit, skip push")
            return
        raise RuntimeError(f"git commit failed: {commit.stderr.strip()!r}")

    # Push (with one rebase retry on non-fast-forward).
    for attempt in range(2):
        push = subprocess_util.run(["git", "-C", str(wiki), "push"])
        if push.returncode == 0:
            log(_MODULE, "write_commit_push: pushed successfully")
            return

        if "non-fast-forward" in push.stderr or "rejected" in push.stderr:
            log(_MODULE, f"write_commit_push: push rejected on attempt {attempt + 1}, rebasing")
            rebase = subprocess_util.run(
                ["git", "-C", str(wiki), "pull", "--rebase"]
            )
            if rebase.returncode == 0:
                continue  # retry push

            # Rebase failed — attempt auto-resolution.
            if auto_resolve_merge(wiki):
                # Continue push retry loop after successful auto-resolve.
                continue

            # Cannot resolve — abort and report.
            subprocess_util.run(["git", "-C", str(wiki), "rebase", "--abort"])
            # Collect conflicted files.
            diff = subprocess_util.run(
                ["git", "-C", str(wiki), "diff", "--name-only", "--diff-filter=U"]
            )
            conflicted = [p for p in diff.stdout.splitlines() if p.strip()]
            raise WikiMergeConflict(conflicted or ["<unknown>"])

        raise RuntimeError(f"git push failed: {push.stderr.strip()!r}")

    raise RuntimeError("write_commit_push: push still failing after rebase retry")


def auto_resolve_merge(wiki_path: Path) -> bool:
    """Attempt automatic resolution of merge conflicts in the wiki clone.

    Resolution rules:
    - Home.md only, each side adds exactly one unique heading → accept both,
      ``git add Home.md``.
    - _Sidebar.md only → regenerate from Home.md via lazy import of
      ``millpy.entrypoints.regenerate_sidebar``.
    - Anything else (multi-file conflict, non-additive Home.md) → return False.

    Parameters
    ----------
    wiki_path:
        Absolute path to the wiki clone directory.

    Returns
    -------
    bool
        True iff all conflicts were resolved and the index is clean.
    """
    # Discover conflicted files.
    diff = subprocess_util.run(
        ["git", "-C", str(wiki_path), "diff", "--name-only", "--diff-filter=U"]
    )
    conflicted = [p for p in diff.stdout.splitlines() if p.strip()]
    if not conflicted:
        log(_MODULE, "auto_resolve_merge: no conflicts found")
        return False

    log(_MODULE, f"auto_resolve_merge: conflicted files={conflicted!r}")

    if conflicted == ["Home.md"]:
        return _resolve_home_md(wiki_path)

    if conflicted == ["_Sidebar.md"]:
        return _resolve_sidebar_md(wiki_path)

    log(_MODULE, f"auto_resolve_merge: cannot auto-resolve multi-file conflict {conflicted!r}")
    return False


def _resolve_home_md(wiki_path: Path) -> bool:
    """Resolve a Home.md conflict where each side adds exactly one unique heading."""
    home = wiki_path / "Home.md"
    try:
        content = home.read_text(encoding="utf-8")
    except OSError as exc:
        log(_MODULE, f"auto_resolve_merge: cannot read Home.md: {exc}")
        return False

    lines = content.splitlines()

    # Find all conflict hunks.
    hunks: list[tuple[list[str], list[str]]] = []
    ours: list[str] = []
    theirs: list[str] = []
    in_conflict = False
    in_theirs = False

    for line in lines:
        if line.startswith("<<<<<<<"):
            in_conflict = True
            in_theirs = False
            ours = []
            theirs = []
        elif line.startswith("=======") and in_conflict:
            in_theirs = True
        elif line.startswith(">>>>>>>") and in_conflict:
            hunks.append((list(ours), list(theirs)))
            in_conflict = False
        elif in_conflict:
            if in_theirs:
                theirs.append(line)
            else:
                ours.append(line)

    if not hunks:
        log(_MODULE, "auto_resolve_merge: no conflict hunks found in Home.md")
        return False

    # Verify: each hunk has exactly one ADD on each side with different content.
    for our_lines, their_lines in hunks:
        our_non_empty = [l for l in our_lines if l.strip()]
        their_non_empty = [l for l in their_lines if l.strip()]
        if len(our_non_empty) != 1 or len(their_non_empty) != 1:
            log(_MODULE, "auto_resolve_merge: Home.md hunk has multiple or zero lines per side")
            return False
        if our_non_empty[0] == their_non_empty[0]:
            log(_MODULE, "auto_resolve_merge: Home.md hunk sides are identical")
            return False

    # Accept both: rebuild file without conflict markers.
    resolved_lines: list[str] = []
    in_conflict = False
    in_theirs = False

    for line in lines:
        if line.startswith("<<<<<<<"):
            in_conflict = True
            in_theirs = False
        elif line.startswith("=======") and in_conflict:
            in_theirs = True
        elif line.startswith(">>>>>>>") and in_conflict:
            in_conflict = False
            in_theirs = False
        else:
            resolved_lines.append(line)

    home.write_text("\n".join(resolved_lines) + "\n", encoding="utf-8")
    git_add = subprocess_util.run(
        ["git", "-C", str(wiki_path), "add", "Home.md"]
    )
    if git_add.returncode != 0:
        log(_MODULE, f"auto_resolve_merge: git add Home.md failed: {git_add.stderr!r}")
        return False

    log(_MODULE, "auto_resolve_merge: Home.md resolved (accepted both sides)")
    return True


def _resolve_sidebar_md(wiki_path: Path) -> bool:
    """Resolve a _Sidebar.md conflict by regenerating from Home.md."""
    try:
        from millpy.entrypoints.regenerate_sidebar import main as _regen_sidebar
        _regen_sidebar([])
        git_add = subprocess_util.run(
            ["git", "-C", str(wiki_path), "add", "_Sidebar.md"]
        )
        if git_add.returncode != 0:
            log(_MODULE, f"auto_resolve_merge: git add _Sidebar.md failed: {git_add.stderr!r}")
            return False
        log(_MODULE, "auto_resolve_merge: _Sidebar.md resolved via regeneration")
        return True
    except ImportError:
        log(
            _MODULE,
            "auto_resolve_merge: regenerate_sidebar not available; cannot auto-resolve _Sidebar.md conflict",
        )
        return False


# ---------------------------------------------------------------------------
# Lock helpers
# ---------------------------------------------------------------------------


def acquire_lock(cfg: dict, slug: str, timeout_seconds: int = 30) -> None:
    """Create .mill-lock in the wiki clone atomically.

    Retries every 500 ms up to ``timeout_seconds`` when a non-stale lock
    exists. A lock is considered stale when its timestamp is more than 5
    minutes old — stale locks are overwritten without waiting.

    Parameters
    ----------
    cfg:
        Parsed config dict.
    slug:
        Slug written into the lockfile (identifies the holder).
    timeout_seconds:
        Maximum seconds to wait for the lock.

    Raises
    ------
    LockBusy
        If a non-stale lock is held for longer than ``timeout_seconds``.
    """
    wiki = _wiki_path(cfg)
    lock_path = wiki / ".mill-lock"
    deadline = time.monotonic() + timeout_seconds

    while True:
        ts_now = datetime.datetime.now(datetime.timezone.utc)
        ts_str = ts_now.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Try atomic create.
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"{slug}\n{ts_str}\n")
            log(_MODULE, f"acquire_lock: acquired by {slug!r}")
            return
        except FileExistsError:
            pass

        # Lock exists — check staleness.
        try:
            content = lock_path.read_text(encoding="utf-8")
            lines = content.strip().splitlines()
            holder = lines[0] if lines else "<unknown>"
            lock_ts_str = lines[1] if len(lines) > 1 else ""
            try:
                lock_ts = datetime.datetime.strptime(
                    lock_ts_str, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=datetime.timezone.utc)
                age_seconds = int((ts_now - lock_ts).total_seconds())
            except ValueError:
                age_seconds = _STALE_SECONDS + 1  # treat unparseable as stale
                holder = "<unknown>"

            if age_seconds > _STALE_SECONDS:
                log(_MODULE, f"acquire_lock: overwriting stale lock (age={age_seconds}s)")
                lock_path.write_text(f"{slug}\n{ts_str}\n", encoding="utf-8")
                return

            if time.monotonic() >= deadline:
                raise LockBusy(holder, age_seconds)

        except (OSError, IndexError):
            # Lock disappeared between exists-check and read — retry.
            pass

        time.sleep(0.5)


def release_lock(cfg: dict) -> None:
    """Delete .mill-lock from the wiki clone.

    Idempotent — no-op if the lockfile does not exist.

    Parameters
    ----------
    cfg:
        Parsed config dict.
    """
    wiki = _wiki_path(cfg)
    lock_path = wiki / ".mill-lock"
    if lock_path.exists():
        lock_path.unlink()
        log(_MODULE, "release_lock: released")
