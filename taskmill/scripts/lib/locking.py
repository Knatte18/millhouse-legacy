from contextlib import contextmanager
from pathlib import Path
import filelock

LOCK_PATH = Path('.llm/backlog.lock')

def get_lock(file_path):
    """Get a file lock if the target is backlog.md, otherwise None."""
    if Path(file_path).name == 'backlog.md':
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        return filelock.FileLock(str(LOCK_PATH), timeout=5)
    return None

@contextmanager
def locked(file_path):
    """Context manager that acquires the lock (if any) on entry and releases on exit."""
    lock = get_lock(file_path)
    try:
        if lock:
            lock.acquire()
        yield
    finally:
        if lock:
            lock.release()
