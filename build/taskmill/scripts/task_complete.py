#!/usr/bin/env python3
"""Mark the first incomplete item as done, or delete it."""

import argparse
import re
import sys
from pathlib import Path
import filelock

CHECKBOX_RE = re.compile(r'^(\s*)- \[(.)\] ')
LOCK_PATH = Path('.llm/backlog.lock')


def find_incomplete(lines):
    """Find first [ ], [>], or [p] item. Returns index or None."""
    for i, line in enumerate(lines):
        m = CHECKBOX_RE.match(line)
        if m:
            state = m.group(2)
            if state in (' ', '>', 'p'):
                return i
    return None


def delete_block(lines, start):
    """Delete the task line, all indented sub-bullets, and trailing blank line."""
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() == '':
            end += 1
            break
        if line.startswith('  ') or line.startswith('\t'):
            end += 1
        else:
            break
    return lines[:start] + lines[end:]


def main():
    parser = argparse.ArgumentParser(description='Complete the first incomplete task')
    parser.add_argument('file', help='Path to the task file')
    parser.add_argument('--delete', action='store_true',
                        help='Delete the entry instead of marking [x]')
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f'File not found: {args.file}', file=sys.stderr)
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
        idx = find_incomplete(lines)
        if idx is None:
            print('No incomplete items found.', file=sys.stderr)
            sys.exit(1)

        completed_line = lines[idx].rstrip('\n')
        print(completed_line)

        if args.delete:
            lines = delete_block(lines, idx)
        else:
            lines[idx] = re.sub(r'^(\s*- \[)[> p1-9p](\])', r'\1x\2', lines[idx])

        file_path.write_text(''.join(lines), encoding='utf-8')
    finally:
        if lock:
            lock.release()


if __name__ == '__main__':
    main()
