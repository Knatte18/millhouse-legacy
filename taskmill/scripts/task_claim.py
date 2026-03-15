#!/usr/bin/env python3
"""Claim a task for discussion by assigning it a thread number."""

import sys
from datetime import datetime, timezone

from lib.state import change_state
from lib.locking import locked
from lib.parsing import read_lines, find_task, find_used_digits, find_lowest_unused_digit
from lib.subbullet import upsert_subbullet
from lib.io import write_file, is_backlog


def main():
    if len(sys.argv) < 2:
        print('Usage: task_claim.py <file-path> [task-name]', file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    task_name = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else None

    with locked(file_path):
        lines = read_lines(file_path)

        if task_name:
            idx = find_task(lines, name=task_name, skip_claimed=True)
        else:
            idx = find_task(lines, states=['>', ' '])

        if idx is None:
            print('No eligible task found.', file=sys.stderr)
            sys.exit(1)

        used = find_used_digits(lines)
        digit = find_lowest_unused_digit(used)
        if digit is None:
            print('All thread slots (1-9) are in use.', file=sys.stderr)
            sys.exit(1)

        lines[idx] = change_state(lines[idx], str(digit))

        now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        upsert_subbullet(lines, idx, 'started', now)

        write_file(file_path, lines, normalize=is_backlog(file_path))
        print(lines[idx].rstrip('\n'))


if __name__ == '__main__':
    main()
