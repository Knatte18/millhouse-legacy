#!/usr/bin/env python3
"""Shared file locking utility for task scripts."""

from pathlib import Path
import filelock

LOCK_PATH = Path('.llm/backlog.lock')


def get_lock(file_path):
    """Get a file lock if the target is backlog.md, otherwise None."""
    if Path(file_path).name == 'backlog.md':
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        return filelock.FileLock(LOCK_PATH, timeout=5)
    return None
