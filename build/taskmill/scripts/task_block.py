#!/usr/bin/env python3
"""Mark the first incomplete item as blocked."""

import sys

from lib.state import change_state
from lib.locking import locked
from lib.parsing import read_lines, find_incomplete
from lib.subbullet import upsert_subbullet
from lib.io import write_file, is_backlog


def main():
    if len(sys.argv) < 2:
        print('Usage: task_block.py <file-path> [reason]', file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    reason = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else None

    with locked(file_path):
        lines = read_lines(file_path)
        idx = find_incomplete(lines)
        if idx is None:
            print('No incomplete items found.', file=sys.stderr)
            sys.exit(1)

        lines[idx] = change_state(lines[idx], '!')
        print(lines[idx].rstrip('\n'))

        if reason:
            upsert_subbullet(lines, idx, 'blocked', reason)

        write_file(file_path, lines, normalize=is_backlog(file_path))


if __name__ == '__main__':
    main()
