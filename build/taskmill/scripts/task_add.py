#!/usr/bin/env python3
"""Append a new checkbox item to a file."""

import sys
from pathlib import Path
import filelock

LOCK_PATH = Path('.llm/backlog.lock')


def main():
    if len(sys.argv) < 3:
        print('Usage: task_add.py <file-path> <Title: description>', file=sys.stderr)
        sys.exit(1)

    file_path = Path(sys.argv[1])
    text = ' '.join(sys.argv[2:])

    if ':' in text:
        title, description = text.split(':', 1)
        entry = f'- [ ] **{title.strip()}**\n  {description.strip()}\n\n'
    else:
        entry = f'- [ ] **{text.strip()}**\n\n'

    is_backlog = file_path.name == 'backlog.md'

    if is_backlog:
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        lock = filelock.FileLock(LOCK_PATH, timeout=5)
    else:
        lock = None

    try:
        if lock:
            lock.acquire()
        if file_path.exists():
            content = file_path.read_text(encoding='utf-8')
            if not content.endswith('\n'):
                content += '\n'
        else:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            content = ''
        content += entry
        file_path.write_text(content, encoding='utf-8')
        print(entry.strip())
    finally:
        if lock:
            lock.release()


if __name__ == '__main__':
    main()
