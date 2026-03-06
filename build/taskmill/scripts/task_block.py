#!/usr/bin/env python3
"""Mark the first incomplete item as blocked."""

import re
import sys
from pathlib import Path
import filelock

CHECKBOX_RE = re.compile(r'^(\s*)- \[(.)\] ')
LOCK_PATH = Path('.llm/backlog.lock')


def main():
    if len(sys.argv) < 2:
        print('Usage: task_block.py <file-path> [reason]', file=sys.stderr)
        sys.exit(1)

    file_path = Path(sys.argv[1])
    reason = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else None

    if not file_path.exists():
        print(f'File not found: {sys.argv[1]}', file=sys.stderr)
        sys.exit(1)

    is_backlog = file_path.name == 'backlog.md'

    if is_backlog:
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        lock = filelock.FileLock(LOCK_PATH, timeout=5)
    else:
        lock = None

    try:
        if lock:
            lock.acquire()
        lines = file_path.read_text(encoding='utf-8').splitlines(keepends=True)

        idx = None
        for i, line in enumerate(lines):
            m = CHECKBOX_RE.match(line)
            if m and m.group(2) in (' ', '>', 'p'):
                idx = i
                break

        if idx is None:
            print('No incomplete items found.', file=sys.stderr)
            sys.exit(1)

        lines[idx] = re.sub(r'^(\s*- \[)[> p1-9p](\])', r'\1!\2', lines[idx])
        print(lines[idx].rstrip('\n'))

        if reason:
            # Insert blocked reason as sub-bullet after the task line
            indent = '  '
            reason_line = f'{indent}- blocked: {reason}\n'
            lines.insert(idx + 1, reason_line)

        file_path.write_text(''.join(lines), encoding='utf-8')
    finally:
        if lock:
            lock.release()


if __name__ == '__main__':
    main()
