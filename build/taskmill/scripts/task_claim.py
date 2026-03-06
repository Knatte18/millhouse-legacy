#!/usr/bin/env python3
"""Claim a task for discussion by assigning it a thread number."""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
import filelock

CHECKBOX_RE = re.compile(r'^(\s*)- \[(.)\] ')
LOCK_PATH = Path('.llm/backlog.lock')


def find_used_digits(lines):
    """Find all digit states currently in use."""
    used = set()
    for line in lines:
        m = CHECKBOX_RE.match(line)
        if m and m.group(2).isdigit():
            used.add(int(m.group(2)))
    return used


def find_lowest_unused_digit(used):
    """Find the lowest unused digit 1-9."""
    for n in range(1, 10):
        if n not in used:
            return n
    return None


def find_task_by_name(lines, name):
    """Find a task by name (case-insensitive substring match)."""
    name_lower = name.lower()
    for i, line in enumerate(lines):
        m = CHECKBOX_RE.match(line)
        if not m:
            continue
        indent, state = m.group(1), m.group(2)
        if len(indent) > 0:
            continue
        if state.isdigit():
            continue  # already claimed
        if name_lower in line.lower():
            return i
    return None


def find_task_by_priority(lines):
    """Find first [>] then first [ ] task."""
    for target in ('>', ' '):
        for i, line in enumerate(lines):
            m = CHECKBOX_RE.match(line)
            if not m:
                continue
            indent, state = m.group(1), m.group(2)
            if len(indent) > 0:
                continue
            if state.isdigit():
                continue
            if state == target:
                return i
    return None


def main():
    if len(sys.argv) < 2:
        print('Usage: task_claim.py <file-path> [task-name]', file=sys.stderr)
        sys.exit(1)

    file_path = Path(sys.argv[1])
    task_name = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else None

    if not file_path.exists():
        print(f'File not found: {sys.argv[1]}', file=sys.stderr)
        sys.exit(1)

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock = filelock.FileLock(LOCK_PATH, timeout=5)

    try:
        lock.acquire()
        lines = file_path.read_text(encoding='utf-8').splitlines(keepends=True)

        if task_name:
            idx = find_task_by_name(lines, task_name)
        else:
            idx = find_task_by_priority(lines)

        if idx is None:
            print('No eligible task found.', file=sys.stderr)
            sys.exit(1)

        used = find_used_digits(lines)
        digit = find_lowest_unused_digit(used)
        if digit is None:
            print('All thread slots (1-9) are in use.', file=sys.stderr)
            sys.exit(1)

        # Change state to [N]
        lines[idx] = re.sub(r'^(\s*- \[)[> ](\])', rf'\g<1>{digit}\2', lines[idx])

        # Add started timestamp as sub-bullet
        now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        started_line = f'  - started: {now}\n'

        # Find insertion point: after the task line and any existing sub-bullets
        insert_at = idx + 1
        while insert_at < len(lines):
            line = lines[insert_at]
            if line.strip() == '' or (not line.startswith('  ') and not line.startswith('\t')):
                break
            insert_at += 1
        lines.insert(insert_at, started_line)

        file_path.write_text(''.join(lines), encoding='utf-8')
        print(lines[idx].rstrip('\n'))
    finally:
        lock.release()


if __name__ == '__main__':
    main()
