#!/usr/bin/env python3
"""Mark an incomplete item as done, or delete it."""

import argparse
import sys

from lib.state import change_state
from lib.locking import locked
from lib.parsing import read_lines, find_task, delete_block
from lib.io import write_file, is_backlog


def main():
    parser = argparse.ArgumentParser(description='Complete an incomplete task')
    parser.add_argument('file', help='Path to the task file')
    parser.add_argument('task_name', nargs='?', default=None,
                        help='Task name (case-insensitive substring match)')
    parser.add_argument('--delete', action='store_true',
                        help='Delete the entry instead of marking [x]')
    args = parser.parse_args()

    if is_backlog(args.file) and args.task_name is None:
        print('task_name is required for backlog operations.', file=sys.stderr)
        sys.exit(1)

    with locked(args.file):
        lines = read_lines(args.file)

        if args.task_name:
            idx = find_task(lines, name=args.task_name, top_level_only=False)
        else:
            idx = find_task(lines, states=[' ', '>', 'p', '!'], top_level_only=False)

        if idx is None:
            print('No incomplete items found.', file=sys.stderr)
            sys.exit(1)

        completed_line = lines[idx].rstrip('\n')
        print(completed_line)

        if args.delete:
            lines = delete_block(lines, idx)
        else:
            lines[idx] = change_state(lines[idx], 'x')

        write_file(args.file, lines, normalize=is_backlog(args.file))


if __name__ == '__main__':
    main()
