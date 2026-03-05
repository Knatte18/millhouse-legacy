"""File locking for backlog.md concurrent access.

Provides a context manager that acquires .llm/backlog.lock before
reading/writing backlog.md. Only locks when the target file path
contains 'backlog.md'. For other files (e.g. plan files), the
context manager is a no-op.
"""

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

LOCK_TIMEOUT_SECONDS = 5
LOCK_POLL_INTERVAL = 0.1


@contextmanager
def lock_backlog(file_path):
    """Acquire .llm/backlog.lock if file_path is a backlog file, then yield."""
    if "backlog.md" not in Path(file_path).name:
        yield
        return

    project_root = _find_project_root(file_path)
    lock_dir = project_root / ".llm"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / "backlog.lock"

    fd = _acquire_lock(lock_file)
    try:
        yield
    finally:
        _release_lock(fd, lock_file)


def _find_project_root(file_path):
    """Walk up from file_path to find the directory containing doc/ or .llm/."""
    current = Path(file_path).resolve().parent
    while current != current.parent:
        if (current / "doc").is_dir() or (current / ".llm").is_dir():
            return current
        current = current.parent
    return Path(file_path).resolve().parent


def _acquire_lock(lock_file):
    """Create lock file exclusively with a timeout."""
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            return fd
        except FileExistsError:
            if time.monotonic() >= deadline:
                print(
                    f"Could not acquire lock {lock_file} within {LOCK_TIMEOUT_SECONDS}s",
                    file=sys.stderr,
                )
                sys.exit(1)
            time.sleep(LOCK_POLL_INTERVAL)


def _release_lock(fd, lock_file):
    """Close and remove the lock file."""
    os.close(fd)
    try:
        os.unlink(str(lock_file))
    except FileNotFoundError:
        pass
