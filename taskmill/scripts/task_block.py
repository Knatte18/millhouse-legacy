#!/usr/bin/env python3
"""Mark an incomplete item as blocked."""

import argparse
import sys

from lib.state import change_state
from lib.locking import locked
from lib.parsing import read_lines, find_task
from lib.subbullet import upsert_subbullet
from lib.io import write_file, is_backlog


def main():
    parser = argparse.ArgumentParser(description='Block an incomplete task')
    parser.add_argument('file', help='Path to the task file')
    parser.add_argument('reason', nargs='?', default=None,
                        help='Reason for blocking')
    parser.add_argument('--name', default=None,
                        help='Task name (case-insensitive substring match)')
    args = parser.parse_args()

    with locked(args.file):
        lines = read_lines(args.file)

        if args.name:
            idx = find_task(lines, name=args.name, top_level_only=False)
        else:
            idx = find_task(lines, states=[' ', '>', 'p'], top_level_only=False)

        if idx is None:
            print('No incomplete items found.', file=sys.stderr)
            sys.exit(1)

        lines[idx] = change_state(lines[idx], '!')
        print(lines[idx].rstrip('\n'))

        if args.reason:
            upsert_subbullet(lines, idx, 'blocked', args.reason)

        write_file(args.file, lines, normalize=is_backlog(args.file))


if __name__ == '__main__':
    main()
