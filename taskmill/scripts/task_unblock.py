#!/usr/bin/env python3
"""Unblock a blocked item, transitioning [!] back to [ ]."""

import argparse
import sys

from lib.state import change_state
from lib.locking import locked
from lib.parsing import read_lines, find_task
from lib.subbullet import remove_subbullet
from lib.io import write_file, is_backlog


def main():
    parser = argparse.ArgumentParser(description='Unblock a blocked task')
    parser.add_argument('file', help='Path to the task file')
    parser.add_argument('--name', default=None,
                        help='Task name (case-insensitive substring match)')
    args = parser.parse_args()

    if is_backlog(args.file) and args.name is None:
        print('--name is required for backlog operations.', file=sys.stderr)
        sys.exit(1)

    with locked(args.file):
        lines = read_lines(args.file)

        if args.name:
            idx = find_task(lines, name=args.name, top_level_only=False)
        else:
            idx = find_task(lines, states=['!'], top_level_only=False)

        if idx is None:
            print('No blocked items found.', file=sys.stderr)
            sys.exit(1)

        lines[idx] = change_state(lines[idx], ' ')
        remove_subbullet(lines, idx, 'blocked')
        print(lines[idx].rstrip('\n'))

        write_file(args.file, lines, normalize=is_backlog(args.file))


if __name__ == '__main__':
    main()
