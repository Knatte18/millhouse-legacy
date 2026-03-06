#!/usr/bin/env python3
"""Extract the next incomplete task/step with its context lines."""

import argparse
import re
import sys
from pathlib import Path
import filelock

CHECKBOX_RE = re.compile(r'^(\s*)- \[(.)\] ')
LOCK_PATH = Path('.llm/backlog.lock')


def find_task(lines, include_planned):
    """Find the next task by priority. Returns (index, match) or (None, None)."""
    priorities = ['>']
    if include_planned:
        priorities.append('p')
    priorities.append(' ')

    for target_state in priorities:
        for i, line in enumerate(lines):
            m = CHECKBOX_RE.match(line)
            if not m:
                continue
            indent, state = m.group(1), m.group(2)
            if len(indent) > 0:
                continue  # skip indented sub-steps
            if state.isdigit():
                continue  # skip claimed tasks
            if state == target_state:
                return i, m
    return None, None


def extract_block(lines, start):
    """Extract the task line and all indented sub-bullets below it."""
    result = [lines[start]]
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.strip() == '':
            continue
        if line.startswith('  ') or line.startswith('\t'):
            result.append(line)
        else:
            break
    return result


def main():
    parser = argparse.ArgumentParser(description='Get next incomplete task')
    parser.add_argument('file', help='Path to the task file')
    parser.add_argument('--include-planned', action='store_true',
                        help='Include [p] tasks in selection priority')
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
        idx, match = find_task(lines, args.include_planned)
        if idx is None:
            print('No incomplete items found.', file=sys.stderr)
            sys.exit(1)
        block = extract_block(lines, idx)
        print(''.join(block), end='')
    finally:
        if lock:
            lock.release()


if __name__ == '__main__':
    main()
