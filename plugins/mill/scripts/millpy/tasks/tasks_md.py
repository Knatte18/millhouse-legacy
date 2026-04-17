"""
tasks_md.py — Parser, renderer, and path resolver for tasks.md.

Handles both bulleted-list and prose-paragraph task bodies (Proposal 02 Fix C).
The PS1 predecessor was bullets-only; this parser captures body text verbatim.

Phase marker regex is `[>\\w]+` — the `>` character is preserved so any
historical `[>]` markers in old git history still parse cleanly. The current
"ready to claim" marker is `[s]` (mnemonic for mill-spawn); `s` is `\\w`-compatible
so `[>\\w]+` already covers it without a regex change.

`resolve_path(cfg)` returns the absolute path to `tasks.md` inside the tasks
worktree, reading `tasks.worktree-path` from the loaded config dict.
"""
from __future__ import annotations

import datetime
import os
import platform
import re
import time
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TasksLockError(RuntimeError):
    """Raised when the tasks worktree lock cannot be acquired."""


class GitPushError(RuntimeError):
    """Raised when a git operation (add, commit, push) fails."""


# ---------------------------------------------------------------------------
# Data type
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """A single task entry from tasks.md."""

    title: str
    phase: str | None
    body: str
    line_number: int


# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

# Matches ## headings with optional [phase] marker.
# Uses [>\w]+ so [>] also matches (documented gotcha: \w+ would miss >).
_HEADING_RE = re.compile(r"^##\s+(?:\[([>\w]+)\]\s+)?(.+)$")

# Valid phase values for tasks.md (not status.md vocabulary)
_VALID_PHASES = {"s", "active", "completed", "done", "abandoned"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_path(cfg: dict) -> Path:
    """Return the absolute path to tasks.md inside the tasks worktree.

    Parameters
    ----------
    cfg:
        Loaded config dict from ``millpy.core.config.load``.

    Returns
    -------
    Path
        ``<tasks-worktree-path>/tasks.md``

    Raises
    ------
    ConfigError
        If ``tasks.worktree-path`` is missing, empty, or not absolute.
    FileNotFoundError
        If the tasks worktree directory does not exist.
    """
    from millpy.core.config import ConfigError  # local import to avoid cycles

    tasks_cfg = cfg.get("tasks") or {}
    raw = tasks_cfg.get("worktree-path") if tasks_cfg else None
    if not raw:
        raise ConfigError(
            "Missing tasks.worktree-path in _millhouse/config.yaml. "
            "Run mill-setup to bootstrap the tasks worktree."
        )
    if not Path(raw).is_absolute():
        raise ConfigError(f"tasks.worktree-path must be absolute: {raw}")
    if not Path(raw).is_dir():
        raise FileNotFoundError(
            f"Tasks worktree not found at {raw}. Run mill-setup to create it."
        )
    return Path(raw) / "tasks.md"


def _pid_is_alive(pid: int) -> bool:
    from millpy.core.subprocess_util import run as _run
    try:
        if platform.system() == "Windows":
            result = _run(["tasklist", "/FI", f"PID eq {pid}"])
            return f" {pid} " in result.stdout
        else:
            result = _run(["kill", "-0", str(pid)])
            return result.returncode == 0
    except Exception:
        return False


def _acquire_lock(lock_path: Path, timeout_seconds: float = 30.0, poll_interval: float = 0.5) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not lock_path.exists():
            try:
                with open(lock_path, "x", encoding="utf-8") as f:
                    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    f.write(f"pid: {os.getpid()}\ntimestamp: {ts}\n")
                return
            except FileExistsError:
                pass
        else:
            try:
                content = lock_path.read_text(encoding="utf-8")
                pid_line = next((l for l in content.splitlines() if l.startswith("pid: ")), None)
                if pid_line is None:
                    lock_path.unlink(missing_ok=True)
                    continue
                pid = int(pid_line.removeprefix("pid: ").strip())
                if _pid_is_alive(pid):
                    time.sleep(poll_interval)
                    continue
                lock_path.unlink(missing_ok=True)
            except (ValueError, OSError):
                lock_path.unlink(missing_ok=True)
        time.sleep(poll_interval)
    raise TasksLockError(f"Could not acquire {lock_path} within {timeout_seconds}s; live PID holds it")


def _release_lock(lock_path: Path) -> None:
    lock_path.unlink(missing_ok=True)


def write_commit_push(cfg: dict, new_content: str, commit_msg: str, *, _acquire_timeout: float = 30.0) -> None:
    """Write new_content to tasks.md, commit, and push with pull-rebase retry.

    Parameters
    ----------
    cfg:
        Loaded config dict with ``tasks.worktree-path``.
    new_content:
        Full replacement content for tasks.md.
    commit_msg:
        Git commit message.
    _acquire_timeout:
        Lock acquisition timeout in seconds (test-seam parameter).

    Raises
    ------
    TasksLockError
        If the PID lock cannot be acquired within the timeout.
    GitPushError
        If any git operation fails.
    """
    from millpy.core.subprocess_util import run as _run

    tasks_md_path = resolve_path(cfg)
    tasks_wt = tasks_md_path.parent
    lock_path = tasks_wt / ".mill-tasks.lock"

    _acquire_lock(lock_path, timeout_seconds=_acquire_timeout)
    try:
        tasks_md_path.write_text(new_content, encoding="utf-8", newline="\n")

        add = _run(["git", "-C", str(tasks_wt), "add", "tasks.md"])
        if add.returncode != 0:
            raise GitPushError(f"git add failed: {add.stderr}")

        commit = _run(["git", "-C", str(tasks_wt), "commit", "-m", commit_msg])
        if commit.returncode != 0:
            combined = (commit.stdout or "") + (commit.stderr or "")
            if "nothing to commit" in combined:
                return
            raise GitPushError(f"git commit failed: {commit.stderr}")

        push = None
        for _attempt in range(3):
            push = _run(["git", "-C", str(tasks_wt), "push"])
            if push.returncode == 0:
                return
            if "non-fast-forward" in push.stderr or "rejected" in push.stderr:
                rebase = _run(["git", "-C", str(tasks_wt), "pull", "--rebase"])
                if rebase.returncode != 0:
                    _run(["git", "-C", str(tasks_wt), "rebase", "--abort"])
                    raise GitPushError(
                        f"Rebase conflict on tasks.md: {rebase.stderr}. "
                        "Two writers edited overlapping headings. Aborted rebase."
                    )
                continue
            raise GitPushError(f"Push failed: {push.stderr}")
        raise GitPushError(f"Push failed after 3 attempts: {push.stderr if push else 'unknown'}")
    finally:
        _release_lock(lock_path)


def parse(path: Path) -> list[Task]:
    """Parse tasks.md into a list of Task dataclass instances.

    Captures every `## ` heading as a task. The body is everything between
    one `## ` heading and the next (or EOF), verbatim. Both bullet-list and
    prose-paragraph bodies are supported.

    Parameters
    ----------
    path:
        Path to the tasks.md file.

    Returns
    -------
    list[Task]
        Tasks in file order.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    tasks: list[Task] = []
    current_line: int | None = None
    current_phase: str | None = None
    current_title: str = ""
    body_lines: list[str] = []

    def _flush(next_start: int) -> None:
        if current_line is None:
            return
        body = "".join(body_lines)
        # Normalize trailing whitespace so parse→render→parse is idempotent:
        # collapse all-whitespace bodies to empty string, and strip trailing
        # blank lines down to a single "\n" terminator. Leading and interior
        # blank lines are preserved verbatim.
        if not body.strip():
            body = ""
        else:
            body = body.rstrip("\n") + "\n"
        tasks.append(Task(
            title=current_title,
            phase=current_phase,
            body=body,
            line_number=current_line,
        ))

    for lineno, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n").rstrip("\r")
        m = _HEADING_RE.match(line)
        if m and raw.startswith("## "):
            _flush(lineno)
            current_phase = m.group(1)  # None if no marker
            current_title = m.group(2).strip()
            current_line = lineno
            body_lines = []
        elif current_line is not None:
            body_lines.append(raw)

    _flush(len(lines) + 1)
    return tasks


def render(tasks: list[Task]) -> str:
    """Render a list of Task objects back to tasks.md text.

    Produces a `# Tasks` header followed by each task. The body is emitted
    verbatim. A trailing newline is always present.

    Parameters
    ----------
    tasks:
        List of Task instances to render.

    Returns
    -------
    str
        The reconstructed tasks.md content.
    """
    parts: list[str] = ["# Tasks\n"]
    for task in tasks:
        if task.phase is not None:
            heading = f"## [{task.phase}] {task.title}\n"
        else:
            heading = f"## {task.title}\n"
        parts.append("\n" + heading)
        if task.body:
            parts.append(task.body)
    result = "".join(parts)
    if not result.endswith("\n"):
        result += "\n"
    return result


def find(tasks: list[Task], title: str) -> Task | None:
    """Return the first task matching the given title, or None.

    Parameters
    ----------
    tasks:
        List of Task instances to search.
    title:
        Exact title string (without phase marker).

    Returns
    -------
    Task | None
    """
    for task in tasks:
        if task.title == title:
            return task
    return None


def validate(path: Path) -> list[str]:
    """Validate tasks.md structural rules.

    Checks:
    1. Exactly one `# ` heading, at line 1.
    2. All task entries use `## ` headings.
    3. Phase markers, if present, are in the valid set.
    4. No orphaned content before the first `## ` heading.

    Parameters
    ----------
    path:
        Path to the tasks.md file.

    Returns
    -------
    list[str]
        Error messages. Empty list means the file is valid.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors: list[str] = []

    h1_count = 0
    h1_line = None
    first_h2_line = None

    for lineno, line in enumerate(lines, start=1):
        if line.startswith("# ") and not line.startswith("## "):
            h1_count += 1
            h1_line = lineno
        if line.startswith("## "):
            if first_h2_line is None:
                first_h2_line = lineno
            # Validate phase marker
            m = re.match(r"^##\s+\[([^\]]+)\]", line)
            if m:
                marker = m.group(1)
                if marker not in _VALID_PHASES:
                    errors.append(
                        f"Line {lineno}: invalid phase marker [{marker!r}]; "
                        f"valid values are {sorted(_VALID_PHASES)}"
                    )

    if h1_count != 1:
        errors.append(
            f"Expected exactly one `# ` heading (found {h1_count})"
        )

    if h1_line is not None and h1_line != 1:
        errors.append(
            f"`# ` heading must be at line 1 (found at line {h1_line})"
        )

    # Check for orphaned content before first ## heading
    if first_h2_line is not None:
        for lineno, line in enumerate(lines[1:], start=2):
            if lineno >= first_h2_line:
                break
            if line.strip() and not line.startswith("# "):
                errors.append(
                    f"Line {lineno}: orphaned content before first ## heading"
                )

    return errors
